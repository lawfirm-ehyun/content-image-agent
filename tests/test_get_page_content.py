"""get_page_blocks 재귀 규칙 테스트 — child_page/child_database 제외 (2026-07-07 e2e 발견).

notion_call 을 monkeypatch 해 canned 트리로 검증. 네트워크 X.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from tools.notion import get_page_content

# client.blocks.children.list 속성 체인만 흉내 — 실호출은 _fake_notion_call 이 가로챔.
_FAKE_CLIENT = SimpleNamespace(
    blocks=SimpleNamespace(children=SimpleNamespace(list=lambda **kw: None)),
)


def _block(bid: str, btype: str, has_children: bool = False) -> dict[str, Any]:
    return {"id": bid, "type": btype, "has_children": has_children, btype: {}}


# parent_id → children 응답 (단일 페이지 fixture)
TREE: dict[str, list[dict[str, Any]]] = {
    "page-1": [
        _block("p1", "paragraph"),
        _block("toggle-1", "toggle", has_children=True),
        _block("childpage-1", "child_page", has_children=True),
        _block("childdb-1", "child_database", has_children=True),
        _block("p2", "paragraph"),
    ],
    "toggle-1": [_block("t1-child", "paragraph")],
    # child_page/childdb 내부는 fetch 되면 안 됨 — 접근 시 테스트 실패용 센티널
    "childpage-1": [_block("FORBIDDEN", "paragraph")],
    "childdb-1": [_block("FORBIDDEN", "paragraph")],
}


async def _fake_notion_call(fn: Any, **kwargs: Any) -> dict[str, Any]:
    return {"results": TREE[kwargs["block_id"]], "has_more": False}


def test_child_page_and_database_not_recursed(monkeypatch):
    monkeypatch.setattr(get_page_content, "notion_call", _fake_notion_call)
    monkeypatch.setattr(get_page_content, "get_client", lambda: _FAKE_CLIENT)

    blocks = asyncio.run(get_page_content.get_page_blocks("page-1"))
    ids = [b["id"] for b in blocks]

    assert "FORBIDDEN" not in ids            # 하위 페이지/DB 내부 미진입
    assert "childpage-1" in ids              # child_page 블록 자체는 목록에 존재 (텍스트 없어 compact에서 자연 제외)
    assert "t1-child" in ids                 # toggle 등 일반 컨테이너는 기존대로 재귀
    assert ids == ["p1", "toggle-1", "t1-child", "childpage-1", "childdb-1", "p2"]  # DFS 순서 유지
