"""AI 카드 결과 이미지의 vision OCR 검수 (Phase 4.3, plan §14.4).

흐름:
  image_path (PNG/WebP) → bytes → base64 → anthropic.Anthropic().messages.create()
  multimodal content (image + text) → Sonnet 4.6 vision → JSON {text_detected, ...}
  → text_rule 분기로 (verdict, cost_usd) 반환.

설계 결정 (plan §14.4, 2026-05-18 사용자 컨펌):
  - **anthropic SDK 별 path** — claude-agent-sdk 0.1.77 ContentBlock 에 ImageBlock
    정의 부재 (`claude_agent_sdk/types.py:992-999`). vision 은 plan §12 SDK 통일
    결정과 직교. anthropic.Anthropic().messages.create() multimodal 표준 path.
  - **모델**: Sonnet 4.6 (`claude-sonnet-4-6`) — 기존 review.py 와 같은 모델.
  - **cost 환산**: anthropic.Usage → cost_usd (Sonnet 4.6 rate).
  - **호출자가 image_path 전달** — production 은 orchestrator 가 webp 경로 직접 전달
    (spike 의 노션 sourcing path 는 제거).

Spike: scripts/_spike_vision_review.py (commit 38d66e9, 2026-05-18 실측
$0.0065 / 2.883s / text_detected=false).
"""
from __future__ import annotations

import asyncio
import base64
import logging
import os
from pathlib import Path
from typing import Any, Final

from anthropic import Anthropic

from tools.llm._common import _extract_json

logger = logging.getLogger(__name__)


# Sonnet 4.6 vision pricing (anthropic 공식 docs, 2026-05-18 기준 USD/M tokens).
_SONNET_46_RATE: Final[dict[str, float]] = {
    "input": 3.0,
    "output": 15.0,
    "cache_creation": 3.75,
    "cache_read": 0.30,
}

_VISION_MODEL: Final[str] = "claude-sonnet-4-6"
_MAX_TOKENS: Final[int] = 512
_TIMEOUT_S: Final[int] = 30

_ALLOWED_TEXT_RULES: Final[frozenset[str]] = frozenset({"zero"})  # MVP — factual / kakao 분기는 trigger 시 추가

_VISION_SYSTEM_PROMPT: Final[str] = """\
이 이미지를 OCR 하여 JSON 한 객체로만 반환하라. 설명/주석 X.

스키마:
{
  "text_detected": <bool>,
  "text_pixels_pct": <float, 0-100, 이미지 전체 대비 텍스트 영역 비율 추정>,
  "ocr_tokens": <int, 감지된 토큰(단어) 개수>,
  "korean_text": <str, 감지된 한글 원문 그대로. 없으면 빈 문자열>,
  "english_text": <str, 감지된 영문 원문 그대로. 없으면 빈 문자열>
}

text_detected = true 조건: 어떤 텍스트라도 감지됨 (간판, 자막, 워터마크, 캡션 포함).
text_detected = false 조건: 시각적 형태만 있고 글자 형태가 전혀 없음.
"""


def _cost_from_usage(usage: Any) -> float:
    """anthropic.Usage → cost_usd 환산 (Sonnet 4.6 rate)."""
    inp = getattr(usage, "input_tokens", 0) or 0
    out = getattr(usage, "output_tokens", 0) or 0
    cache_w = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cache_r = getattr(usage, "cache_read_input_tokens", 0) or 0
    return (
        inp * _SONNET_46_RATE["input"]
        + out * _SONNET_46_RATE["output"]
        + cache_w * _SONNET_46_RATE["cache_creation"]
        + cache_r * _SONNET_46_RATE["cache_read"]
    ) / 1_000_000


def _media_type_from_bytes(data: bytes) -> str:
    """magic bytes 로 media_type 판단. production 은 PNG/WebP 둘 다 cover."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "image/gif"
    raise ValueError(f"vision_review: 알 수 없는 image media type (head 12B: {data[:12]!r})")


def _call_vision_sync(image_bytes: bytes, media_type: str) -> tuple[dict[str, Any], Any]:
    """anthropic SDK sync 호출. (parsed_json, usage) 반환.

    anthropic SDK 0.102 는 sync API. asyncio.to_thread 로 wrapping 은 호출자 책임.
    """
    client = Anthropic()
    b64 = base64.b64encode(image_bytes).decode("ascii")

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": b64,
                    },
                },
                {"type": "text", "text": "이 이미지를 OCR 해줘. JSON 스키마 정확히 준수."},
            ],
        }
    ]

    resp = client.messages.create(
        model=_VISION_MODEL,
        max_tokens=_MAX_TOKENS,
        system=_VISION_SYSTEM_PROMPT,
        messages=messages,
    )

    # resp.content 는 list[TextBlock | ...]. 첫 TextBlock 의 text 추출.
    result_text = ""
    for block in resp.content:
        text = getattr(block, "text", None)
        if text:
            result_text += text

    if not result_text.strip():
        raise RuntimeError(f"vision_review: 빈 응답 (stop_reason={resp.stop_reason!r})")

    parsed = _extract_json(result_text.strip())
    if not isinstance(parsed, dict):
        raise RuntimeError(f"vision_review: JSON 파싱 결과가 dict 아님: {parsed!r}")

    return parsed, resp.usage


def _apply_text_rule_zero(ocr: dict[str, Any]) -> tuple[bool, str]:
    """text_rule=zero 분기. (passed, reason) 반환.

    폐기 조건 (plan §19.16 본문):
      - text_pixels_pct >= 1.0 OR ocr_tokens >= 3 → 텍스트 환각 의심 → 폐기
    그 외 → 통과.
    """
    text_detected = bool(ocr.get("text_detected"))
    pct = float(ocr.get("text_pixels_pct") or 0.0)
    tokens = int(ocr.get("ocr_tokens") or 0)
    korean = (ocr.get("korean_text") or "").strip()
    english = (ocr.get("english_text") or "").strip()

    if not text_detected:
        return True, ""

    if pct >= 1.0 or tokens >= 3:
        fragments = []
        if korean:
            fragments.append(f"한글={korean[:40]!r}")
        if english:
            fragments.append(f"영문={english[:40]!r}")
        detail = " ".join(fragments) if fragments else "(no text content)"
        return False, (
            f"text_rule=zero 위반: text_pixels_pct={pct:.2f} ocr_tokens={tokens} {detail}"
        )

    # text_detected=true 지만 픽셀/토큰 모두 임계값 미달 — 노이즈로 간주 (통과).
    return True, ""


async def vision_review(
    image_path: Path,
    *,
    text_rule: str = "zero",
) -> tuple[dict[str, Any], float]:
    """이미지 → Sonnet 4.6 vision OCR → (verdict, cost_usd) 반환.

    verdict 스키마:
        passed          : bool   — text_rule 통과 여부
        text_detected   : bool
        text_pixels_pct : float
        ocr_tokens      : int
        korean_text     : str
        english_text    : str
        reason          : str    — passed=False 시 폐기 사유 한 줄 (passed=True 면 "")

    text_rule="zero" (MVP, plan §14.4 단순화 2026-05-18):
        text_detected=true AND (pixels_pct >= 1.0 OR tokens >= 3) → 폐기.

    text_rule="factual" / "kakao_levenshtein" → NotImplementedError (4.3 MVP scope 밖).
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "vision_review: ANTHROPIC_API_KEY 미설정. .env 확인."
        )
    if text_rule not in _ALLOWED_TEXT_RULES:
        raise NotImplementedError(
            f"vision_review: text_rule={text_rule!r} 미구현 (MVP 는 'zero' 만). "
            f"plan §14.4 trigger 시 추가."
        )
    if not image_path.is_file():
        raise FileNotFoundError(f"vision_review: image_path 부재 — {image_path}")

    image_bytes = image_path.read_bytes()
    media_type = _media_type_from_bytes(image_bytes)
    logger.info(
        "vision_review: image=%s media_type=%s size=%d bytes",
        image_path.name, media_type, len(image_bytes),
    )

    # anthropic SDK 0.102 sync API 이므로 asyncio.to_thread 로 비동기 wrapping.
    # timeout 은 asyncio.timeout 으로 호출자 control.
    async with asyncio.timeout(_TIMEOUT_S):
        parsed, usage = await asyncio.to_thread(_call_vision_sync, image_bytes, media_type)

    cost_usd = _cost_from_usage(usage)

    if text_rule == "zero":
        passed, reason = _apply_text_rule_zero(parsed)
    else:
        # 위 _ALLOWED_TEXT_RULES 가드로 unreachable.
        raise NotImplementedError(f"vision_review: text_rule={text_rule!r}")

    verdict = {
        "passed": passed,
        "text_detected": bool(parsed.get("text_detected")),
        "text_pixels_pct": float(parsed.get("text_pixels_pct") or 0.0),
        "ocr_tokens": int(parsed.get("ocr_tokens") or 0),
        "korean_text": str(parsed.get("korean_text") or ""),
        "english_text": str(parsed.get("english_text") or ""),
        "reason": reason,
    }
    logger.info(
        "vision_review: image=%s passed=%s cost=$%.6f reason=%s",
        image_path.name, passed, cost_usd, reason or "(ok)",
    )
    return verdict, cost_usd
