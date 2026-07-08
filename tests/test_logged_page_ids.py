"""get_logged_page_ids 성공-행-only 필터 테스트 (v1.8.4, §19.1 멱등성 좁힘).

notion_call / resolve_data_source_id / get_client 를 monkeypatch — 네트워크 X.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from tools.notion import log_metadata

# client.databases.query / data_sources.query 속성 체인만 흉내 — 실호출은 fake_call 이 가로챔.
_FAKE_CLIENT = SimpleNamespace(
    databases=SimpleNamespace(query=lambda **kw: None),
    data_sources=SimpleNamespace(query=lambda **kw: None),
)


def _row(page_id: str, review_passed: bool) -> dict[str, Any]:
    return {
        "properties": {
            "셀프 리뷰": {"checkbox": review_passed},
            "관련 페이지": {
                "rich_text": [
                    {"type": "mention", "mention": {"type": "page", "page": {"id": page_id}}},
                ],
            },
        },
    }


PAGE_OK = "aaaaaaaa-0000-0000-0000-000000000000"     # 성공 행 있음
PAGE_FAIL = "bbbbbbbb-0000-0000-0000-000000000000"   # 실패 행만
PAGE_MIXED = "cccccccc-0000-0000-0000-000000000000"  # 성공 1 + 실패 1


def _patch(monkeypatch, rows: list[dict[str, Any]]) -> None:
    async def fake_call(fn: Any, **kwargs: Any) -> dict[str, Any]:
        return {"results": rows}

    monkeypatch.setattr(log_metadata, "notion_call", fake_call)
    monkeypatch.setattr(log_metadata, "get_client", lambda: _FAKE_CLIENT)
    # ds_id == log_db_id → databases.query 경로 (분기 무관, fake_call 이 가로챔)
    monkeypatch.setattr(log_metadata, "resolve_data_source_id", lambda db: db)


def test_success_row_included(monkeypatch):
    _patch(monkeypatch, [_row(PAGE_OK, True)])
    out = asyncio.run(log_metadata.get_logged_page_ids("db"))
    assert log_metadata.norm_uuid(PAGE_OK) in out


def test_failure_only_page_excluded(monkeypatch):
    # 전부 실패 페이지 = 성공 행 없음 → skip set 제외 → 재처리 대상
    _patch(monkeypatch, [_row(PAGE_FAIL, False), _row(PAGE_FAIL, False)])
    out = asyncio.run(log_metadata.get_logged_page_ids("db"))
    assert out == set()


def test_mixed_page_included(monkeypatch):
    # 일부 성공 페이지 = 성공 행 1개라도 있으면 skip (중복 방지)
    _patch(monkeypatch, [_row(PAGE_MIXED, True), _row(PAGE_MIXED, False)])
    out = asyncio.run(log_metadata.get_logged_page_ids("db"))
    assert log_metadata.norm_uuid(PAGE_MIXED) in out


def test_mixed_bag(monkeypatch):
    _patch(monkeypatch, [
        _row(PAGE_OK, True),
        _row(PAGE_FAIL, False),
        _row(PAGE_MIXED, False),
        _row(PAGE_MIXED, True),
    ])
    out = asyncio.run(log_metadata.get_logged_page_ids("db"))
    assert out == {log_metadata.norm_uuid(PAGE_OK), log_metadata.norm_uuid(PAGE_MIXED)}
