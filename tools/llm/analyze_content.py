"""본문 블록 → image_slots 결정 (slot_selection.md 스킬).

Phase 4.2 (2026-05-15): 감성형 카드 `ai_visual` 신설 — skills/visual_styles/*.md
디렉터리 scan → 슬림 표 (name/tone/use_when) 를 analyze prompt 에 inject. LLM 이
본문 보고 best fit `visual_style` 매칭. 매칭 실패 시 슬롯 폐기 (silent fallback 금지).
"""
from __future__ import annotations

import json
import logging
from typing import Any

from tools.limits import ANALYZE_BUDGET_USD, MAX_BLOCKS_PROMPT_CHARS
from tools.llm._common import compact_blocks, load_skill, query_json
from tools.visual_styles import list_visual_styles

logger = logging.getLogger(__name__)


def _format_visual_styles_table() -> str:
    """Phase 4.2 — analyze prompt에 inject할 visual_styles 슬림 표 (name/tone/use_when만).

    prompt_template 본문은 runtime ai_render에서만 사용 (LLM에 노출 X). LLM은 매칭
    결과로 visual_style=<name> 만 결정 — scene/mood/accent_target 도 본문 사실 안에서 합성.

    skills/visual_styles/ 디렉터리가 비어있거나 모두 파싱 실패면 빈 문자열 반환 — 호출자가
    inject skip. (analyze prompt 안정성 보장 — visual_styles 없어도 정보형 카드 작동.)
    """
    styles = list_visual_styles()
    if not styles:
        return ""
    lines = [
        "## Visual Styles (ai_visual 카드 visual_style 선택지)",
        "",
        "본문이 감성형 카드(`ai_visual`)에 부합하면 아래 표에서 best fit `visual_style` 결정. "
        "use_when 패턴과 본문 톤이 명확히 매칭되지 않으면 슬롯 폐기 (임의 default 금지).",
        "",
        "| name | tone | use_when |",
        "|---|---|---|",
    ]
    for s in styles:
        name = s.name.replace("|", "\\|")
        tone = s.tone.replace("|", "\\|").replace("\n", " ")
        use_when = s.use_when.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {name} | {tone} | {use_when} |")
    lines.append("")
    lines.append(
        "ai_visual 슬롯 trigger 시 `extracted_data` 에 다음 필수: "
        "`visual_style`=<위 표 name 중 1>, `scene`=<자연어 장면 묘사, 본문 사실 안에서 합성>, "
        "`mood`=<분위기 키워드>. 옵션: `accent_target`=<wine-magenta 강조 요소 자연어>."
    )
    return "\n".join(lines)


def _blocks_for_prompt(compacted: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """LLM 노출용 blocks — UUID 제거 + 순번 idx 부여 (v1.8.2, plan §5).

    LLM 이 32자 UUID 를 그대로 베끼다 환각하는 구조 자체를 제거 — 위치는
    `position_after_block_index`(idx) 로만 선택하고, idx→block_id 변환은
    `_gate_slots` 가 수행. UUID 제거로 블록당 ~45 chars 절약 (§19.8 압축 진입 빈도 ↓).

    주의: idx 는 **호출 시점의 compacted 리스트** 기준 — 압축 모드(_compress_for_analyze)
    적용 후 호출해야 LLM 이 보는 목록과 idx 가 1:1 대응.
    """
    return [
        {"idx": i, "type": c["type"], "text": c["text"]}
        for i, c in enumerate(compacted)
    ]


def _coerce_index(val: Any) -> int | None:
    """LLM 산출 position_after_block_index 를 int 로 정규화. 불가하면 None.

    JSON 스키마를 강제할 수 없는 단발 query() 특성상 "3"(str) / 3.0(float) 관용 수용.
    bool 은 int subclass 이지만 위치 의미가 없으므로 배제.
    """
    if isinstance(val, bool):
        return None
    if isinstance(val, int):
        return val
    if isinstance(val, float) and val.is_integer():
        return int(val)
    if isinstance(val, str):
        s = val.strip()
        if s.lstrip("-").isdigit():
            return int(s)
    return None


def _gate_slots(
    slots: list[Any], compacted: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """analyze 산출 슬롯 게이트 — 위치 해석 + ai_visual 필수 필드 검증 (v1.8.2).

    위치 해석 (§19.18 원천 차단):
      - `position_after_block_index` → 0 <= idx < len(compacted) 검증 후
        compacted[idx]["id"] 를 `position_after_block_id` 에 주입
        (orchestrator 인터페이스 불변 — slot["position_after_block_id"] 소비 유지).
      - 범위 밖/비정수 idx → 슬롯 drop.
      - legacy: index 키 자체가 없고 `position_after_block_id` 가 known-id set 에
        있으면 수용 (전환기 안전망). index 키가 있는데 invalid 면 legacy fallback X.

    ai_visual: visual_style/scene/mood 누락·미정의 → drop (5/18 fix 사상 유지).
    """
    known_block_ids = {c["id"] for c in compacted if c.get("id")}
    valid_styles = {s.name for s in list_visual_styles()}
    filtered: list[dict[str, Any]] = []
    for slot in slots:
        if not isinstance(slot, dict):
            logger.warning("analyze gate: 슬롯이 dict 아님 — drop: %r", slot)
            continue

        aid: str | None = None
        raw_idx = slot.get("position_after_block_index")
        idx = _coerce_index(raw_idx)
        if idx is not None and 0 <= idx < len(compacted):
            aid = compacted[idx]["id"]
        elif "position_after_block_index" not in slot:
            legacy = slot.get("position_after_block_id")
            if legacy and legacy in known_block_ids:
                aid = legacy
                logger.warning(
                    "analyze gate: legacy position_after_block_id 수용 — type=%s "
                    "(skill 스키마는 v1.8.7 부터 index)", slot.get("type"),
                )
        if not aid:
            logger.warning(
                "analyze gate: 위치 결함 슬롯 폐기 — type=%s index=%r legacy_id=%r "
                "(유효 범위 0..%d)",
                slot.get("type"), raw_idx,
                slot.get("position_after_block_id"), len(compacted) - 1,
            )
            continue
        slot["position_after_block_id"] = aid

        if slot.get("type") == "ai_visual":
            data = slot.get("extracted_data") or {}
            vs = (data.get("visual_style") or "").strip() if isinstance(data, dict) else ""
            scene = (data.get("scene") or "").strip() if isinstance(data, dict) else ""
            mood = (data.get("mood") or "").strip() if isinstance(data, dict) else ""
            reasons: list[str] = []
            if not vs:
                reasons.append("visual_style 누락/빈값")
            elif valid_styles and vs not in valid_styles:
                reasons.append(
                    f"visual_style={vs!r} 미정의 (유효: {sorted(valid_styles)})"
                )
            if not scene:
                reasons.append("scene 누락/빈값")
            if not mood:
                reasons.append("mood 누락/빈값")
            if reasons:
                logger.warning(
                    "analyze gate: ai_visual 슬롯 폐기 — %s | data=%r",
                    "; ".join(reasons), data,
                )
                continue
        filtered.append(slot)
    return filtered


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


async def analyze_content(
    blocks: list[dict[str, Any]],
    page_title: str = "",
) -> tuple[list[dict[str, Any]], float]:
    """Notion blocks 리스트 → (image_slots, cost_usd).

    image_slots 각 항목 스키마 (slot_selection.md v1.8.7 출력):
        type, sub_type?, position_after_block_index, extracted_data (alt_text 포함)
    본 함수가 idx→block_id 변환 후 `position_after_block_id` 로 반환 (v1.8.2 —
    LLM 에 UUID 미노출, 환각 원천 차단. orchestrator 인터페이스 불변).

    page_title: Notion page title property 값. v1.9 plan §13 — alt_text 의 target keyword source.
                비우면 prompt 에서 명시 X (alt_text 생성은 가능하나 키워드 일관성 ↓).

    blocks는 compact 형태(id/type/text)로 변환해 inject — raw JSON은 80KB+ 가능,
    SDK stdin 한계(22KB) 초과로 exit 1 발생. §19.8 — compact가 한계 초과면 압축 모드 fallback.
    """
    skill = load_skill("meta/slot_selection.md")
    visual = load_skill("style/ehyun_visual_guide.md")

    compacted = compact_blocks(blocks)
    # v1.8.2 — LLM 에는 UUID 대신 순번 idx 노출 (환각 원천 차단, plan §5).
    blocks_compact = json.dumps(
        _blocks_for_prompt(compacted), ensure_ascii=False, separators=(",", ":"),
    )

    if len(blocks_compact) > MAX_BLOCKS_PROMPT_CHARS:
        logger.warning(
            "본문 compact %d chars > %d 한계 — §19.8 압축 모드 fallback (slot 결정용 한정)",
            len(blocks_compact), MAX_BLOCKS_PROMPT_CHARS,
        )
        compacted = _compress_for_analyze(compacted)
        # idx 는 압축 후 리스트 기준으로 재부여 — LLM 이 보는 목록과 1:1 대응.
        blocks_compact = json.dumps(
            _blocks_for_prompt(compacted), ensure_ascii=False, separators=(",", ":"),
        )
        logger.warning("압축 후 %d chars (%d 블록)", len(blocks_compact), len(compacted))

    page_title_block = (
        f"PAGE TITLE: {page_title}\n"
        "→ 모든 슬롯의 alt_text 에 이 제목의 핵심 명사 1회 자연스럽게 포함 "
        "(stuffing 2회+ 금지, 본문에 없는 사실 추가 X).\n\n"
        if page_title.strip()
        else ""
    )

    user_prompt = (
        f"{page_title_block}"
        "다음은 Notion 페이지의 모든 block(JSON 배열)이다. "
        "각 block 은 idx(순번)/type/text. "
        "본 스킬 룰에 따라 image_slots를 결정하고 JSON 객체로 반환하라. "
        "슬롯 위치는 position_after_block_index 에 직전 block 의 idx(정수)로 지정.\n\n"
        f"BLOCKS:\n{blocks_compact}\n\n"
        '응답 스키마: {"image_slots": [...]}'
    )

    visual_styles_table = _format_visual_styles_table()

    system = (
        "너는 이현 블로그 이미지 슬롯 결정 어시스턴트다. "
        "본문에 명시된 데이터만 추출하고 추측·의역은 절대 금지.\n\n"
        "## Slot Selection 스킬\n" + skill +
        "\n\n## 비주얼 가이드\n" + visual +
        (("\n\n" + visual_styles_table) if visual_styles_table else "")
    )

    # 페이지당 1회 호출. v1.3에서 slot_selection 스킬이 두꺼워져 cache_creation 47K + output 13K
    # 토큰까지 늘어 실측 ~$0.37. cap 0.30 도달 사례 발생 → 0.50으로 상향.
    # (페이지 cap $1.50 안에서 안전: analyze 0.50 + review × 슬롯3 × 0.30 = $1.40)
    parsed, cost = await query_json(user_prompt, system, max_budget_usd=ANALYZE_BUDGET_USD)
    if isinstance(parsed, dict) and "image_slots" in parsed:
        slots = parsed["image_slots"]
    elif isinstance(parsed, list):
        slots = parsed
    else:
        raise ValueError(f"analyze_content 응답 형식 예상 외: {parsed!r}")

    # 게이트 계보:
    # - 5/18 fix (root cause #2): ai_visual visual_style 누락이 ai_render 까지 미뤄져
    #   3회 헛재시도 → analyze 단계 게이트로 강제.
    # - 5/20 §19.18: 환각 UUID known-id set 사전 검증 (운영 1건 $0.10 누수).
    # - v1.8.2 (2026-07-06): 인덱스 선택 방식으로 원천 차단 — LLM 은 UUID 를 아예
    #   보지 못하고 idx 만 출력, _gate_slots 가 idx→block_id 변환. §19.18 known-id
    #   게이트는 legacy 출력 안전망으로 유지.
    filtered = _gate_slots(slots, compacted)

    if len(filtered) != len(slots):
        logger.info(
            "analyze gate: %d개 폐기 (전체 %d → %d 슬롯)",
            len(slots) - len(filtered), len(slots), len(filtered),
        )
    return filtered, cost
