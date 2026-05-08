"""본문 블록 → image_slots 결정 (slot_selection.md 스킬).

Phase 1 활성: simple_table + chart(line)만. 다른 패턴은 슬롯 결정 X.
"""
from __future__ import annotations

import json
from typing import Any

from tools.llm._common import compact_blocks, load_skill, query_json


async def analyze_content(blocks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], float]:
    """Notion blocks 리스트 → (image_slots, cost_usd).

    image_slots 각 항목 스키마 (slot_selection.md 출력):
        type, sub_type?, position_after_block_id, extracted_data

    blocks는 compact 형태(id/type/text)로 변환해 inject — raw JSON은 80KB+ 가능,
    SDK stdin 한계(22KB) 초과로 exit 1 발생.
    """
    skill = load_skill("meta/slot_selection.md")
    visual = load_skill("style/ehyun_visual_guide.md")

    compacted = compact_blocks(blocks)
    blocks_compact = json.dumps(compacted, ensure_ascii=False, separators=(",", ":"))
    user_prompt = (
        "다음은 Notion 페이지의 모든 block(JSON 배열)이다. "
        "본 스킬 룰에 따라 image_slots를 결정하고 JSON 객체로 반환하라.\n\n"
        f"BLOCKS:\n{blocks_compact}\n\n"
        '응답 스키마: {"image_slots": [...]}'
    )

    system = (
        "너는 이현 블로그 이미지 슬롯 결정 어시스턴트다. "
        "본문에 명시된 데이터만 추출하고 추측·의역은 절대 금지.\n\n"
        "## Slot Selection 스킬\n" + skill +
        "\n\n## 비주얼 가이드\n" + visual
    )

    # 페이지당 1회 호출. CLI auto-mode classifier가 Haiku 동시 호출 + Sonnet 큰 응답이라
    # 실측 ~$0.16. cap 여유 두고 페이지 cap $0.50의 60%까지 허용.
    parsed, cost = await query_json(user_prompt, system, max_budget_usd=0.30)
    if isinstance(parsed, dict) and "image_slots" in parsed:
        return parsed["image_slots"], cost
    if isinstance(parsed, list):
        return parsed, cost
    raise ValueError(f"analyze_content 응답 형식 예상 외: {parsed!r}")
