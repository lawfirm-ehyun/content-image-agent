"""AI 카드 공통 렌더 path — gpt_image_2 호출 wrapper.

v1.6.1 신설 (plan §12 P3.2). card_type + extracted_data → gpt_image_2 → PNG file 저장.

지원 카드 (P3.3/P3.4에서 prompt 합성 디테일 추가):
  - illustration (gpt-image instant, quality=medium)
  - kakao_dialogue (gpt-image thinking, quality=high)

설계:
  - **prompt 합성은 카드별 함수로 분리** — _build_illustration_prompt / _build_kakao_prompt.
    plan §7.8/§7.9 자연어 prompt template 그대로.
  - **exact_korean_strings 필드는 prompt에 literal 인용** — gpt-image가 한글 텍스트 박을 때
    원문 일치 위해 프롬프트에 명시적 인용.
  - **반환은 PNG 경로** — orchestrator는 기존 chart/template과 동일 인터페이스 사용.
  - **slot 단위 비용 cap 검증은 caller(orchestrator) 책임** — ai_render는 호출만.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from tools.image.gpt_image_2 import ImageResult, generate_instant, generate_thinking

logger = logging.getLogger(__name__)


# ============================================================================
# Prompt builders — plan §7.8/§7.9 자연어 template
# ============================================================================


def _build_illustration_prompt(data: dict[str, Any]) -> str:
    """plan §7.8 v1.6.2 자연어 prompt template.

    scene/mood는 필수. accent_target은 옵션 (없으면 자연어 default).
    """
    scene = data.get("scene", "").strip()
    mood = data.get("mood", "").strip()
    accent_target = data.get("accent_target", "").strip()

    if not scene or not mood:
        raise ValueError(
            f"illustration extracted_data에 scene/mood 필수. "
            f"받은 값: scene={scene!r}, mood={mood!r}"
        )

    accent_clause = (
        f" with {accent_target} highlighted in wine-magenta"
        if accent_target
        else " with restrained wine-magenta accent on a key element"
    )

    # v1.8 Phase 4.1 (2026-05-15): "clean white background" → "soft light gray
    # warm neutral background" 로 정합. 정보형 카드 light-gray 배경(--card-bg
    # #eaeaea) 과 시각 톤 통일. Phase 4.2 에서 ai_visual + 스타일 라이브러리
    # 로 흡수되며 본 함수 자체 deprecate 예정 — 그 전까지 잠정 표현.
    return (
        "Korean editorial line illustration, minimalist outline drawing.\n"
        f"Scene: {scene}.\n"
        f"Mood: {mood}.\n"
        f"Single weight black outlines on a soft light gray warm neutral background, "
        f"no color fill except{accent_clause}.\n"
        "Side view, back view, or silhouette — avoid direct front portraits with detailed faces.\n"
        "No text, signs, or letters inside the image.\n"
        "Modern Korean urban context (Korean offices, streets, or courtrooms as fits the scene).\n"
        "Style reference: editorial minimalism, single-line drawing, restrained color use."
    )


def _build_kakao_prompt(data: dict[str, Any]) -> str:
    """plan §7.9 v1.6.2 자연어 prompt template + exact_korean_strings literal 인용.

    messages는 필수 (≥ 1개).
    """
    title = (data.get("title") or "").strip()
    messages = data.get("messages") or []

    if not messages:
        raise ValueError("kakao_dialogue extracted_data에 messages 필수 (≥ 1개)")

    header = (
        f"Korean KakaoTalk chat screenshot, Samsung Android style. Chat area only "
        f"(no status bar, no keyboard).\n\n"
    )

    title_line = (
        f'Header at top: back arrow on the left, chat title "{title}" in the center, '
        f"search and menu icons on the right.\n\n"
        if title
        else (
            "Header at top: back arrow on the left, a short chat title in the center, "
            "search and menu icons on the right.\n\n"
        )
    )

    # 메시지 literal 인용 — gpt-image 한글 정확성 확보
    msg_lines = ["Messages (in order):"]
    for m in messages:
        sender = (m.get("sender_label") or "").strip()
        text = (m.get("text") or "").strip()
        time = (m.get("time") or "").strip()
        time_part = f' at "{time}"' if time else ""
        msg_lines.append(f'  - sender "{sender}"{time_part}: "{text}"')
    msg_block = "\n".join(msg_lines) + "\n\n"

    styling = (
        "If the sender label suggests the user/client (e.g. 의뢰인), render that message as a "
        "yellow bubble aligned right, no avatar, small sender label above. "
        "Otherwise render as a white bubble aligned left, with a pastel circular avatar "
        "(muted pink or green) holding a person icon, small sender label above.\n\n"
        "Use authentic KakaoTalk styling: light blue chat background, soft yellow self-bubbles, "
        "white other-bubbles with rounded corners, pastel circular avatars in muted tones. "
        "Korean Pretendard or Apple SD Gothic Neo font feel.\n\n"
        "Render every message text exactly as written above — do not paraphrase, omit, "
        "or add words. Korean text must match character-by-character."
    )

    return header + title_line + msg_block + styling


# ============================================================================
# 공개 API
# ============================================================================


async def render_ai_card(
    card_type: str,
    data: dict[str, Any],
    out_png: Path,
) -> ImageResult:
    """카드 타입별 분기 → gpt_image_2 호출 → PNG 저장. ImageResult 반환.

    card_type  : "illustration" | "kakao_dialogue"
    data       : slot["extracted_data"]
    out_png    : 저장 경로
    """
    if card_type == "illustration":
        prompt = _build_illustration_prompt(data)
        result = await generate_instant(prompt, size="1024x1024", quality="medium")
    elif card_type == "kakao_dialogue":
        prompt = _build_kakao_prompt(data)
        result = await generate_thinking(prompt, size="1024x1536", quality="high")
    else:
        raise ValueError(f"ai_render 미지원 card_type={card_type!r}")

    out_png.parent.mkdir(parents=True, exist_ok=True)
    out_png.write_bytes(result.png_bytes)
    logger.info(
        "ai_render: %s → %s (size=%s quality=%s cost=$%.4f)",
        card_type, out_png.name, result.size, result.quality, result.cost_usd,
    )
    return result
