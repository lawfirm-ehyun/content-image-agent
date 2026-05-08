"""슬롯 데이터 prompt_review (본문 일치 + 변호사법 §23 검사)."""
from __future__ import annotations

import json
from typing import Any

from tools.llm._common import load_skill, query_json


async def review_input(
    slot_type: str,
    slot_data: dict[str, Any],
    page_text: str,
) -> tuple[dict[str, Any], float]:
    """슬롯 input 데이터 검토. ({passed, issues, revised_data?}, cost_usd) 튜플 반환.

    slot_type   : "simple_table" | "chart"
    slot_data   : extracted_data dict (template variables)
    page_text   : 본문 일치 검증을 위한 원문 (본문 모든 텍스트를 한 문자열로 연결한 것)
    """
    skill = load_skill("meta/prompt_review.md")
    image_type_skill = load_skill(f"image_types/{slot_type}.md")

    user_prompt = (
        f"## 슬롯 타입\n{slot_type}\n\n"
        f"## 추출된 데이터 (검토 대상)\n{json.dumps(slot_data, ensure_ascii=False, indent=2)}\n\n"
        f"## 본문 원문 (일치 검증 기준)\n{page_text}\n\n"
        '응답 스키마: {"passed": bool, "issues": [string], '
        '"revised_data": {...}|null}'
    )

    system = (
        "너는 이현 블로그 이미지 슬롯의 입력을 검토하는 셀프 리뷰어다. "
        "본문 일치(절대 룰 #1)와 변호사법 §23을 엄격히 적용한다.\n\n"
        "## Prompt Review 스킬\n" + skill +
        f"\n\n## {slot_type} 스킬\n" + image_type_skill
    )

    # 슬롯당 1회 호출. page_text 13KB+ inject로 비용 크니 페이지 cap $0.50의 절반 가까이 허용.
    parsed, cost = await query_json(user_prompt, system, max_budget_usd=0.20)
    if not isinstance(parsed, dict) or "passed" not in parsed:
        raise ValueError(f"review_input 응답 형식 예상 외: {parsed!r}")
    parsed.setdefault("issues", [])
    parsed.setdefault("revised_data", None)
    return parsed, cost
