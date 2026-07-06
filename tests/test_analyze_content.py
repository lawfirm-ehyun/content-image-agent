"""_gate_slots / _coerce_index / _blocks_for_prompt 단위 테스트 (v1.8.2 인덱스 전환).

LLM 호출 없이 게이트 로직만 검증 — analyze_content() 본체는 query_json 의존이라
e2e (scripts/test_phase1.py) 영역. plan §5 "block 위치 환각 차단 (원천 + 사후)" 참조.
"""
from __future__ import annotations

from typing import Any

from tools.llm.analyze_content import (
    _blocks_for_prompt,
    _coerce_index,
    _gate_slots,
)

# compact_blocks 산출 형태 (id/type/text) 모사
COMPACTED: list[dict[str, Any]] = [
    {"id": "aaaa1111-0000-0000-0000-000000000000", "type": "heading_2", "text": "제목"},
    {"id": "bbbb2222-0000-0000-0000-000000000000", "type": "paragraph", "text": "본문 A"},
    {"id": "cccc3333-0000-0000-0000-000000000000", "type": "paragraph", "text": "본문 B"},
]


def _table_slot(**overrides: Any) -> dict[str, Any]:
    slot: dict[str, Any] = {
        "type": "simple_table",
        "extracted_data": {"title": "표", "headers": ["a", "b"], "rows": [["1", "2"]]},
    }
    slot.update(overrides)
    return slot


# === _coerce_index ============================================================

def test_coerce_index_int():
    assert _coerce_index(2) == 2
    assert _coerce_index(0) == 0
    assert _coerce_index(-1) == -1  # 범위 검증은 _gate_slots 책임


def test_coerce_index_str_and_float():
    assert _coerce_index("2") == 2
    assert _coerce_index(" 1 ") == 1
    assert _coerce_index(2.0) == 2


def test_coerce_index_invalid():
    assert _coerce_index(True) is None   # bool 은 int subclass 지만 배제
    assert _coerce_index(False) is None
    assert _coerce_index(1.5) is None
    assert _coerce_index("1.5") is None
    assert _coerce_index("abc") is None
    assert _coerce_index(None) is None
    assert _coerce_index([1]) is None


# === _gate_slots — 위치 해석 ==================================================

def test_valid_index_resolves_to_block_id():
    out = _gate_slots([_table_slot(position_after_block_index=1)], COMPACTED)
    assert len(out) == 1
    assert out[0]["position_after_block_id"] == COMPACTED[1]["id"]


def test_string_index_accepted():
    out = _gate_slots([_table_slot(position_after_block_index="2")], COMPACTED)
    assert len(out) == 1
    assert out[0]["position_after_block_id"] == COMPACTED[2]["id"]


def test_out_of_range_index_dropped():
    assert _gate_slots([_table_slot(position_after_block_index=99)], COMPACTED) == []
    assert _gate_slots([_table_slot(position_after_block_index=-1)], COMPACTED) == []
    assert _gate_slots([_table_slot(position_after_block_index=len(COMPACTED))], COMPACTED) == []


def test_bool_index_dropped():
    # True 가 idx=1 로 해석되면 안 됨 (bool 은 int subclass)
    assert _gate_slots([_table_slot(position_after_block_index=True)], COMPACTED) == []


def test_missing_position_dropped():
    assert _gate_slots([_table_slot()], COMPACTED) == []


def test_non_dict_slot_dropped():
    assert _gate_slots(["문자열", 42, None], COMPACTED) == []


# === _gate_slots — legacy UUID 안전망 =========================================

def test_legacy_known_uuid_accepted():
    slot = _table_slot(position_after_block_id=COMPACTED[0]["id"])
    out = _gate_slots([slot], COMPACTED)
    assert len(out) == 1
    assert out[0]["position_after_block_id"] == COMPACTED[0]["id"]


def test_legacy_hallucinated_uuid_dropped():
    slot = _table_slot(position_after_block_id="dead-beef-0000")
    assert _gate_slots([slot], COMPACTED) == []


def test_invalid_index_does_not_fall_back_to_legacy():
    # index 키가 존재하면 invalid 여도 legacy fallback 금지 — 스키마 혼용 억제
    slot = _table_slot(
        position_after_block_index=99,
        position_after_block_id=COMPACTED[0]["id"],
    )
    assert _gate_slots([slot], COMPACTED) == []


# === _gate_slots — ai_visual 필수 필드 (기존 5/18 게이트 유지) =================

def _ai_visual_slot(data: dict[str, Any]) -> dict[str, Any]:
    return {"type": "ai_visual", "position_after_block_index": 0, "extracted_data": data}


def test_ai_visual_valid_kept():
    # miniature_stock — skills/visual_styles/ 실제 정의 (조건부 default)
    out = _gate_slots(
        [_ai_visual_slot({"visual_style": "miniature_stock", "scene": "장면", "mood": "차분함"})],
        COMPACTED,
    )
    assert len(out) == 1


def test_ai_visual_missing_fields_dropped():
    assert _gate_slots([_ai_visual_slot({"scene": "장면", "mood": "차분함"})], COMPACTED) == []
    assert _gate_slots(
        [_ai_visual_slot({"visual_style": "miniature_stock", "mood": "차분함"})], COMPACTED,
    ) == []
    assert _gate_slots(
        [_ai_visual_slot({"visual_style": "없는스타일", "scene": "장면", "mood": "차분함"})],
        COMPACTED,
    ) == []


# === _blocks_for_prompt =======================================================

def test_blocks_for_prompt_no_uuid_and_sequential_idx():
    out = _blocks_for_prompt(COMPACTED)
    assert [b["idx"] for b in out] == [0, 1, 2]
    for b in out:
        assert "id" not in b  # UUID 미노출 — 환각 원천 차단
        assert set(b) == {"idx", "type", "text"}
