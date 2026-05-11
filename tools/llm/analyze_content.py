"""본문 블록 → image_slots 결정 (slot_selection.md 스킬).

Phase 1 활성: simple_table + chart(line)만. 다른 패턴은 슬롯 결정 X.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from tools.llm._common import compact_blocks, load_skill, query_json

logger = logging.getLogger(__name__)

# user_prompt 한계 MAX_USER_PROMPT_CHARS(20K)에서 system_prompt·구조 텍스트 빼고 본문에 남길 여유.
# 초과 시 압축 모드 fallback (§19.8).
MAX_BLOCKS_PROMPT_CHARS = 18_000


def _compress_for_analyze(compacted: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """본문이 너무 클 때 slot 결정에 의미 있는 블록만 유지하는 압축 모드 (§19.8).

    유지: heading_1/2/3, 그 직후 첫 paragraph, table_row (표 데이터는 slot 결정 필수).
    폐기: 그 외 paragraph/list/callout/quote 등 부가 설명.

    review_input은 원본 page_text(`_blocks_to_text`)를 별도 path로 받으므로
    본문 일치 검증 정확도는 영향 없음. 압축은 analyze(슬롯 위치 결정) 한정.
    """
    out: list[dict[str, Any]] = []
    keep_next_paragraph = False
    for c in compacted:
        bt = c.get("type", "")
        if bt.startswith("heading_"):
            out.append(c)
            keep_next_paragraph = True
        elif keep_next_paragraph and bt == "paragraph":
            out.append(c)
            keep_next_paragraph = False
        elif bt == "table_row":
            out.append(c)
            keep_next_paragraph = False
    return out


async def analyze_content(blocks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], float]:
    """Notion blocks 리스트 → (image_slots, cost_usd).

    image_slots 각 항목 스키마 (slot_selection.md 출력):
        type, sub_type?, position_after_block_id, extracted_data

    blocks는 compact 형태(id/type/text)로 변환해 inject — raw JSON은 80KB+ 가능,
    SDK stdin 한계(22KB) 초과로 exit 1 발생. §19.8 — compact가 한계 초과면 압축 모드 fallback.
    """
    skill = load_skill("meta/slot_selection.md")
    visual = load_skill("style/ehyun_visual_guide.md")

    compacted = compact_blocks(blocks)
    blocks_compact = json.dumps(compacted, ensure_ascii=False, separators=(",", ":"))

    if len(blocks_compact) > MAX_BLOCKS_PROMPT_CHARS:
        logger.warning(
            "본문 compact %d chars > %d 한계 — §19.8 압축 모드 fallback (slot 결정용 한정)",
            len(blocks_compact), MAX_BLOCKS_PROMPT_CHARS,
        )
        compacted = _compress_for_analyze(compacted)
        blocks_compact = json.dumps(compacted, ensure_ascii=False, separators=(",", ":"))
        logger.warning("압축 후 %d chars (%d 블록)", len(blocks_compact), len(compacted))

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

    # 페이지당 1회 호출. v1.3에서 slot_selection 스킬이 두꺼워져 cache_creation 47K + output 13K
    # 토큰까지 늘어 실측 ~$0.37. cap 0.30 도달 사례 발생 → 0.50으로 상향.
    # (페이지 cap $1.50 안에서 안전: analyze 0.50 + review × 슬롯3 × 0.30 = $1.40)
    parsed, cost = await query_json(user_prompt, system, max_budget_usd=0.50)
    if isinstance(parsed, dict) and "image_slots" in parsed:
        return parsed["image_slots"], cost
    if isinstance(parsed, list):
        return parsed, cost
    raise ValueError(f"analyze_content 응답 형식 예상 외: {parsed!r}")
