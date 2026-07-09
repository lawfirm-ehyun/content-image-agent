"""콘텐츠 페이지의 `상태` select 속성 변경.

운영 컨벤션 (PROJECT_CONTEXT §5.2):
  - 입력: "이미지 필요"
  - 출력: "이미지 작업 중" (성공/실패 무관, v1.8.5) — 모든 완료 페이지가 사람 검수를
    거침. 검수자가 확인 후 수동으로 "발행 필요" 승격.
  - "이미지 작업 중" 페이지는 cron이 다시 처리하지 않음 (cron 은 "이미지 필요"만 fetch).
  - "발행 필요" 옵션은 수동 승격용으로 존속 (check_notion.py:REQUIRED_STATUS_OPTIONS).
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
