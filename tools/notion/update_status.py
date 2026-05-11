"""콘텐츠 페이지의 `상태` select 속성 변경.

운영 컨벤션 (PROJECT_CONTEXT §5.2):
  - 입력: "이미지 필요"
  - 출력: "발행 필요" (모든 슬롯 성공 / 슬롯 0개) | "이미지 작업 중" (1개 이상 실패)
  - "이미지 작업 중" 페이지는 cron이 다시 처리하지 않음 (사람 개입 대기).
"""
from __future__ import annotations

from tools.notion import get_client, get_status_property_type
from tools.notion._retry import notion_call


async def update_page_status(
    page_id: str,
    status: str,
    *,
    database_id: str,
    status_property: str = "상태",
) -> None:
    """페이지 status 옵션 변경. select / status 타입 자동 감지 후 페이로드 분기.

    status는 미리 존재하는 옵션이어야 함 (Phase 0 check_notion.py가 검증).
    database_id는 속성 타입 retrieve 위해 필수.
    """
    client = get_client()
    ptype = get_status_property_type(database_id, status_property)  # 'select' | 'status'
    await notion_call(
        client.pages.update,
        page_id=page_id,
        properties={status_property: {ptype: {"name": status}}},
    )
