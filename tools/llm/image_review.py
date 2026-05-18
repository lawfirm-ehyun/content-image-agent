"""AI 카드 결과 이미지의 vision 검수 분기 (Phase 4.3, plan §14.4).

review.py 와의 분리 이유 (plan §14.4 "또는 별 image_review.py" 옵션 채택):
  - review.py:review_input  — **slot_data prompt 검토** (LLM text-only, query_json).
    본문 일치 + 변호사법 §23 1차 regex pass.
  - image_review.py:review_image — **결과 이미지 검토** (vision multimodal, anthropic SDK 별 path).
    text_rule 분기 — gpt-image 텍스트 환각 차단.

text_rule 결정:
  - slot_type=ai_visual: skills/visual_styles/<visual_style>.md frontmatter text_rule
  - slot_type=illustration / kakao_dialogue: "zero" 고정 (v1.8 5종 visual_style 모두 zero)
  - 그 외 (정보형 5종): 호출자 (orchestrator) 가드 — image_review 진입 X

Phase 4.3 MVP (2026-05-18 단순화): text_rule="zero" 단일 분기만 실행.
factual / kakao_levenshtein 분기는 trigger 발생 시 추가 (§19.11 / §19.16 paper-only).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Final

from tools.render.vision_review import vision_review
from tools.visual_styles import load_visual_style

logger = logging.getLogger(__name__)


# 호출자가 미리 가드해야 할 set — image_review 진입 가능한 slot_type 만 명시.
# orchestrator.AI_CARD_TYPES 와 정합 (Phase 4.3 시점).
_VISION_REVIEW_SLOT_TYPES: Final[frozenset[str]] = frozenset({
    "illustration",     # v1.8 deprecated, backwards compat — text_rule=zero 고정
    "kakao_dialogue",   # text_rule=zero 고정 (kakao OCR Levenshtein 은 trigger 시 §19.11 추가)
    "ai_visual",        # frontmatter text_rule 사용
})


def _resolve_text_rule(slot_type: str, visual_style: str | None) -> str:
    """slot_type + visual_style 로 text_rule 결정.

    plan §14.4 MVP 단순화: v1.8 5종 visual_styles 모두 text_rule=zero — 어느 경로든 "zero".
    factual frontmatter 트리거 시 vision_review.py 가 NotImplementedError raise (paper-only).
    """
    if slot_type == "ai_visual":
        if not visual_style:
            raise ValueError(
                "review_image: slot_type=ai_visual 인데 visual_style 누락. "
                "orchestrator 가 slot.extracted_data['visual_style'] 전달 필요."
            )
        style = load_visual_style(visual_style)
        return style.text_rule
    if slot_type in ("illustration", "kakao_dialogue"):
        return "zero"
    # 가드 — 정보형 5종은 호출자 측에서 차단됐어야 함.
    raise ValueError(
        f"review_image: slot_type={slot_type!r} 는 vision 검수 대상 아님. "
        f"호출자 (orchestrator) AI_CARD_TYPES 가드 확인."
    )


async def review_image(
    slot_type: str,
    image_path: Path,
    *,
    visual_style: str | None = None,
) -> tuple[dict[str, Any], float]:
    """AI 카드 webp/png 이미지 vision 검수. (verdict, cost_usd) 반환.

    Args:
        slot_type   : "illustration" | "kakao_dialogue" | "ai_visual"
        image_path  : 렌더된 webp/png 파일 경로
        visual_style: ai_visual 일 때만 (skills/visual_styles/<name>.md 의 name)

    Returns:
        verdict 스키마는 vision_review.py 동일:
          passed / text_detected / text_pixels_pct / ocr_tokens /
          korean_text / english_text / reason

    Raises:
        ValueError: slot_type 가 vision 검수 대상 아님 / ai_visual + visual_style 누락
        FileNotFoundError: image_path 부재
        RuntimeError: ANTHROPIC_API_KEY 미설정 또는 vision API 응답 이상
        NotImplementedError: text_rule="factual" / "kakao_levenshtein" (MVP scope 밖)
    """
    if slot_type not in _VISION_REVIEW_SLOT_TYPES:
        raise ValueError(
            f"review_image: slot_type={slot_type!r} 는 vision 검수 대상 아님. "
            f"허용: {sorted(_VISION_REVIEW_SLOT_TYPES)}"
        )

    text_rule = _resolve_text_rule(slot_type, visual_style)
    logger.info(
        "review_image: slot_type=%s visual_style=%s text_rule=%s image=%s",
        slot_type, visual_style or "(n/a)", text_rule, image_path.name,
    )

    return await vision_review(image_path, text_rule=text_rule)
