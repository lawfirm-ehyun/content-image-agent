"""슬롯 데이터 prompt_review (본문 일치 + 변호사법 §23 검사)."""
from __future__ import annotations

import json
from typing import Any

from tools.compliance.keywords import check_keywords, format_violations
from tools.limits import REVIEW_BUDGET_USD
from tools.llm._common import load_skill, query_json


def _collect_strings(value: Any) -> list[str]:
    """slot_data를 재귀 순회해 모든 string leaf를 수집 (§23 1차 pass 입력)."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        out: list[str] = []
        for v in value.values():
            out.extend(_collect_strings(v))
        return out
    if isinstance(value, list):
        out = []
        for item in value:
            out.extend(_collect_strings(item))
        return out
    return []


async def review_input(
    slot_type: str,
    slot_data: dict[str, Any],
    page_text: str,
) -> tuple[dict[str, Any], float]:
    """슬롯 input 데이터 검토. ({passed, issues, revised_data?}, cost_usd) 튜플 반환.

    slot_type   : "simple_table" | "chart"
    slot_data   : extracted_data dict (template variables)
    page_text   : 본문 일치 검증을 위한 원문 (본문 모든 텍스트를 한 문자열로 연결한 것)

    plan §19.7 — 1차 regex pass로 §23 명시 키워드 위반 즉시 폐기 (LLM 호출 절약).
    위반 발견 시 (parsed=passed:False + issues, cost=0.0) 반환 — LLM 호출 X.
    """
    # 1차 regex pass — slot_data 안 모든 string leaf 합쳐 §23 키워드 검사.
    slot_text = "\n".join(_collect_strings(slot_data))
    violations = check_keywords(slot_text)
    if violations:
        return (
            {
                "passed": False,
                "issues": [format_violations(violations)],
                "revised_data": None,
            },
            0.0,
        )

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

    # 슬롯당 1회 호출. 실측: cache_creation 40K 토큰 들어가 두 번째 슬롯 review에서 $0.20에 정확히
    # 닿아 error_max_budget_usd 발생 → $0.30으로 상향 (page cap $1.00 안 안전 마진).
    parsed, cost = await query_json(user_prompt, system, max_budget_usd=REVIEW_BUDGET_USD)
    if not isinstance(parsed, dict) or "passed" not in parsed:
        raise ValueError(f"review_input 응답 형식 예상 외: {parsed!r}")
    parsed.setdefault("issues", [])
    parsed.setdefault("revised_data", None)
    return parsed, cost
