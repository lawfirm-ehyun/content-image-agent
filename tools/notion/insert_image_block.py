"""특정 위치 다음에 image block 삽입.

플로우:
  1. upload_image.py로 file_upload_id 획득.
  2. 본 모듈로 parent_id의 자식 블록 목록 안 after_block_id 다음에 image 추가.

Notion API:
  - blocks.children.append(block_id=parent, children=[image_block], after=after_block_id)
  - image block의 file은 type=file_upload, file_upload={id: ...}
  - caption은 rich_text 배열. 빈 문자열이면 caption 생략.
"""
from __future__ import annotations

import asyncio
from typing import Any

from tools.notion import get_client


async def insert_image_block(
    parent_id: str,
    after_block_id: str,
    file_upload_id: str,
    *,
    caption: str = "",
) -> str:
    """after_block_id 다음에 image block 삽입. 새 block id 반환.

    parent_id 인자는 fallback 용도. 실제 parent는 after_block_id의 진짜 parent를
    동적 resolve해 사용 — LLM이 nested block(컬럼/토글 안)을 가리켜도 안전.
    Notion API: append_children은 parent의 직접 자식만 `after`로 받는다.
    """
    return await asyncio.to_thread(
        _insert_sync, parent_id, after_block_id, file_upload_id, caption
    )


def _insert_sync(
    parent_id: str, after_block_id: str, file_upload_id: str, caption: str,
) -> str:
    client = get_client()

    # after_block_id의 진짜 parent를 retrieve. nested block이면 그 block의 parent를 사용.
    try:
        target = client.blocks.retrieve(after_block_id)
        parent_meta = target.get("parent") or {}
        real_parent_id = (
            parent_meta.get("block_id")
            or parent_meta.get("page_id")
            or parent_id
        )
    except Exception:
        real_parent_id = parent_id   # 조회 실패 시 fallback

    image: dict[str, Any] = {
        "type": "file_upload",
        "file_upload": {"id": file_upload_id},
    }
    if caption:
        image["caption"] = [{"type": "text", "text": {"content": caption}}]

    block: dict[str, Any] = {
        "object": "block",
        "type": "image",
        "image": image,
    }

    resp = client.blocks.children.append(
        block_id=real_parent_id,
        children=[block],
        after=after_block_id,
    )
    results = resp.get("results", [])
    if not results:
        raise RuntimeError(f"image block 생성 실패: {resp}")
    return results[0]["id"]
