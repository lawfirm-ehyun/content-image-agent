"""페이지 본문 블록을 재귀적으로 모두 fetch.

flat list 반환 (DFS). column/toggle/synced_block 같은 컨테이너는 has_children=True라
자식까지 포함. parent 정보가 필요한 분석은 호출 측에서 block.parent로 별도 처리.
"""
from __future__ import annotations

import asyncio
from typing import Any

from tools.notion import get_client


async def get_page_blocks(page_id: str) -> list[dict[str, Any]]:
    """page_id의 모든 block을 재귀 flatten해서 반환. paginate 자동 처리."""
    return await asyncio.to_thread(_fetch_recursive, page_id)


def _fetch_recursive(parent_id: str) -> list[dict[str, Any]]:
    client = get_client()
    out: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        kwargs: dict[str, Any] = {"block_id": parent_id, "page_size": 100}
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = client.blocks.children.list(**kwargs)
        for block in resp.get("results", []):
            out.append(block)
            if block.get("has_children"):
                out.extend(_fetch_recursive(block["id"]))
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return out
