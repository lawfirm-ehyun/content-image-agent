"""AI 카드 공통 렌더 path — gpt_image_2 호출 wrapper.

v1.6.1 신설 (plan §12 P3.2). card_type + extracted_data → gpt_image_2 → PNG file 저장.

지원 카드:
  - illustration (gpt-image instant, quality=medium) — **deprecated v1.8 Phase 4.2**:
    ai_visual + skills/visual_styles/point_color_line.md 로 흡수. 호출 path 보존
    (backwards compat).
  - kakao_dialogue (gpt-image thinking, quality=high)
  - ai_visual (Phase 4.2 신설) — skills/visual_styles/<name>.md frontmatter 기반.
    LLM이 본문 보고 visual_style 매칭 → ai_render가 prompt_template 치환 → gpt-image 호출.

설계:
  - **prompt 합성은 카드별 함수로 분리** — _build_illustration_prompt / _build_kakao_prompt
    / _build_ai_visual_prompt. plan §7.8/§7.9/§14.2 자연어 prompt template 그대로.
  - **exact_korean_strings 필드는 prompt에 literal 인용** — gpt-image가 한글 텍스트 박을 때
    원문 일치 위해 프롬프트에 명시적 인용 (kakao_dialogue).
  - **ai_visual은 frontmatter quality에 따라 instant/thinking 라우팅** — medium→instant,
    high→thinking. aspect_ratio도 frontmatter에서 직접 결정 (1024x1024 / 1024x1536 / 1536x1024).
  - **반환은 ImageResult** — orchestrator는 기존 chart/template과 동일 인터페이스 사용.
  - **slot 단위 비용 cap 검증은 caller(orchestrator) 책임** — ai_render는 호출만.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from tools.image.gpt_image_2 import ImageResult, generate_instant, generate_thinking
from tools.visual_styles import load_visual_style

logger = logging.getLogger(__name__)


# ============================================================================
# Prompt builders — plan §7.8/§7.9 자연어 template
# ============================================================================


def _build_illustration_prompt(data: dict[str, Any]) -> str:
    """plan §7.8 v1.6.2 자연어 prompt template.

    scene/mood는 필수. accent_target은 옵션 (없으면 자연어 default).

    **deprecated v1.8 Phase 4.2 (2026-05-15)**: ai_visual + skills/visual_styles/
    point_color_line.md 가 동일 톤 + 더 풍부한 스타일 옵션을 제공. 신규 illustration
    trigger 는 ai_visual 로 라우팅 권장. 본 함수는 backwards compat 유지 (즉시 삭제 X).
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
    # #f5f5f5) 과 시각 톤 통일. Phase 4.2 에서 ai_visual + 스타일 라이브러리
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


def _build_ai_visual_prompt(data: dict[str, Any]) -> tuple[str, str, str]:
    """Phase 4.2 신설 — skills/visual_styles/<name>.md 기반 prompt 합성.

    extracted_data["visual_style"] 가 frontmatter `name` 과 매칭되는 skill md 를 로드,
    body 의 `prompt_template` fenced block 에서 {scene}/{mood}/{accent_target} 치환.

    Returns:
        (prompt, size, quality) — size는 ImageSize Literal (1024x1024/1024x1536/1536x1024),
        quality는 ImageQuality (medium/high). frontmatter aspect_ratio/quality 그대로 전달.

    Raises:
        ValueError — visual_style 누락 / skill md 부재 / scene·mood 누락 / placeholder 불일치.
    """
    visual_style_name = (data.get("visual_style") or "").strip()
    if not visual_style_name:
        raise ValueError(
            "ai_visual extracted_data에 visual_style 필수 (skills/visual_styles/<name>.md)"
        )
    style = load_visual_style(visual_style_name)

    scene = (data.get("scene") or "").strip()
    mood = (data.get("mood") or "").strip()
    accent_target = (
        (data.get("accent_target") or "").strip()
        or style.accent_target_default
        or "a key element"
    )

    if not scene or not mood:
        raise ValueError(
            f"ai_visual extracted_data에 scene/mood 필수. "
            f"받은: scene={scene!r}, mood={mood!r}, visual_style={visual_style_name!r}"
        )

    try:
        prompt = style.prompt_template.format(
            scene=scene,
            mood=mood,
            accent_target=accent_target,
        )
    except KeyError as e:
        raise ValueError(
            f"ai_visual {visual_style_name!r} prompt_template에 "
            f"미정의 placeholder {e} — frontmatter 검토"
        ) from e

    return prompt, style.aspect_ratio, style.quality


# ============================================================================
# 공개 API
# ============================================================================


async def render_ai_card(
    card_type: str,
    data: dict[str, Any],
    out_png: Path,
) -> ImageResult:
    """카드 타입별 분기 → gpt_image_2 호출 → PNG 저장. ImageResult 반환.

    card_type  : "illustration" (deprecated) | "kakao_dialogue" | "ai_visual"
    data       : slot["extracted_data"]
    out_png    : 저장 경로
    """
    if card_type == "illustration":
        prompt = _build_illustration_prompt(data)
        result = await generate_instant(prompt, size="1024x1024", quality="medium")
    elif card_type == "kakao_dialogue":
        prompt = _build_kakao_prompt(data)
        result = await generate_thinking(prompt, size="1024x1536", quality="high")
    elif card_type == "ai_visual":
        prompt, size, quality = _build_ai_visual_prompt(data)
        if quality == "high":
            result = await generate_thinking(prompt, size=size, quality=quality)
        else:
            result = await generate_instant(prompt, size=size, quality=quality)
    else:
        raise ValueError(f"ai_render 미지원 card_type={card_type!r}")

    out_png.parent.mkdir(parents=True, exist_ok=True)
    out_png.write_bytes(result.png_bytes)
    logger.info(
        "ai_render: %s → %s (size=%s quality=%s cost=$%.4f)",
        card_type, out_png.name, result.size, result.quality, result.cost_usd,
    )
    return result
