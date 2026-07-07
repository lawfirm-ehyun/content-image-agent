"""페이지 본문 블록을 재귀적으로 모두 fetch.

flat list 반환 (DFS). column/toggle/synced_block 같은 컨테이너는 has_children=True라
자식까지 포함. parent 정보가 필요한 분석은 호출 측에서 block.parent로 별도 처리.

child_page / child_database 는 재귀 제외 (2026-07-07 e2e 발견) — 하위 "페이지"의
본문은 이 페이지의 본문이 아님. 포함 시:
  (a) 남의 글 텍스트가 analyze/review 의 "본문" 으로 오염 (절대 룰 #1 위반 벡터)
  (b) 하위 페이지 블록이 이미지 앵커 후보로 노출 → §19.2 ancestor 검증에서
      AncestorMismatchError — 렌더/업로드 비용 지출 후 슬롯 폐기.
"""
from __future__ import annotations

from typing import Any, Final

from tools.notion import get_client
from tools.notion._retry import notion_call

# has_children=True 여도 내부로 내려가지 않는 타입 — 별도 "페이지" 소속 콘텐츠.
_SKIP_RECURSE_TYPES: Final[frozenset[str]] = frozenset({"child_page", "child_database"})


async def get_page_blocks(page_id: str) -> list[dict[str, Any]]:
    """page_id의 모든 block을 재귀 flatten해서 반환. paginate 자동 처리."""
    return await _fetch_recursive(page_id)


async def _fetch_recursive(parent_id: str) -> list[dict[str, Any]]:
    client = get_client()
    out: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        kwargs: dict[str, Any] = {"block_id": parent_id, "page_size": 100}
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = await notion_call(client.blocks.children.list, **kwargs)
        for block in resp.get("results", []):
            out.append(block)
            if (
                block.get("has_children")
                and block.get("type") not in _SKIP_RECURSE_TYPES
            ):
                out.extend(await _fetch_recursive(block["id"]))
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return out
