"""특정 위치 다음에 image block 삽입.

플로우:
  1. upload_image.py로 file_upload_id 획득.
  2. 본 모듈로 parent_id의 자식 블록 목록 안 after_block_id 다음에 image 추가.

Notion API:
  - blocks.children.append(block_id=parent, children=[image_block], after=after_block_id)
  - image block의 file은 type=file_upload, file_upload={id: ...}
  - caption은 rich_text 배열. 빈 문자열이면 caption 생략.

retry 정책 (plan §20.1):
  - blocks.retrieve는 notion_call (idempotent, 429/5xx 안전).
  - blocks.children.append은 notion_call 제외 (idempotent X — 중복 삽입 위험).
    1회 실패 시 슬롯 폐기가 안전.
"""
from __future__ import annotations

import asyncio
from typing import Any

from tools.notion import get_client, norm_uuid
from tools.notion._retry import notion_call


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
    client = get_client()

    # after_block_id의 진짜 parent를 retrieve. nested block이면 그 block의 parent를 사용.
    # retrieve 실패는 invalid id로 보고 raise — 조용한 fallback이 §19.2 환각 케이스를 가림.
    try:
        target = await notion_call(client.blocks.retrieve, block_id=after_block_id)
    except Exception as e:
        raise RuntimeError(
            f"after_block_id={after_block_id} retrieve 실패 (block 미존재/권한 부족): {e}"
        ) from e
    anchor_id = after_block_id

    # table_row를 after로 받은 경우 — table block은 table_row만 받으므로 image를 직접 append 불가.
    # 한 단계 올려서 table block 자체를 anchor로, table의 parent에 append (실측 운영 버그 대응).
    if target.get("type") == "table_row":
        table_parent_meta = target.get("parent") or {}
        if table_parent_meta.get("type") != "block_id":
            raise RuntimeError(
                f"table_row의 parent가 block_id 아님: {table_parent_meta}"
            )
        table_block_id = table_parent_meta["block_id"]
        target = await notion_call(client.blocks.retrieve, block_id=table_block_id)
        anchor_id = table_block_id

    # §19.2 — ancestor traversal로 처리 페이지 page_id 확인. 실패 = 다른 페이지 block 환각.
    await _verify_ancestor(client, target, expected_page_id=parent_id)

    parent_meta = target.get("parent") or {}
    real_parent_id = (
        parent_meta.get("block_id")
        or parent_meta.get("page_id")
        or parent_id
    )

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

    # append는 retry 제외 (plan §20.1) — idempotent 아니라 중복 삽입 위험.
    resp = await asyncio.to_thread(
        client.blocks.children.append,
        block_id=real_parent_id,
        children=[block],
        after=anchor_id,
    )
    results = resp.get("results", [])
    if not results:
        raise RuntimeError(f"image block 생성 실패: {resp}")
    return results[0]["id"]


async def _verify_ancestor(
    client: Any, start: dict[str, Any], expected_page_id: str, max_depth: int = 6,
) -> None:
    """block의 ancestor 체인을 거슬러 올라가 expected_page_id에 도달하는지 검증 (§19.2).

    LLM이 환각해서 다른 페이지의 block UUID를 던질 경우 → 다른 페이지에 이미지 박힘 방지.
    nested block(column_list > column > toggle > callout > paragraph)을 감안해 6단계까지 추적.
    실패 시 RuntimeError raise — orchestrator가 catch해 슬롯 폐기.
    """
    current = start
    for _depth in range(max_depth):
        parent = current.get("parent") or {}
        ptype = parent.get("type")
        if ptype == "page_id":
            actual = parent.get("page_id")
            if norm_uuid(actual) == norm_uuid(expected_page_id):
                return
            raise RuntimeError(
                f"block_id가 처리 페이지에 없음 (§19.2): "
                f"기대 page={expected_page_id}, 실제 ancestor page={actual}"
            )
        if ptype == "block_id":
            block_id = parent.get("block_id")
            current = await notion_call(client.blocks.retrieve, block_id=block_id)
            continue
        # workspace / database / 그 외 — 본 함수가 다루는 콘텐츠 페이지 ancestor가 아님
        raise RuntimeError(f"block_id가 처리 페이지에 없음 (§19.2): 예상 외 parent type={ptype}")
    raise RuntimeError(f"block_id가 처리 페이지에 없음 (§19.2): ancestor 추적 {max_depth}단계 초과")
