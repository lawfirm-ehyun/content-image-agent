"""특정 status를 가진 콘텐츠 페이지 목록 fetch.

콘텐츠 DB(블로그/웹)에서 `상태` select 속성 = 특정 값 페이지를 가져온다.
multi-source DB이면 data_source.query, single-source이면 databases.query.
"""
from __future__ import annotations

from typing import Any

from tools.notion import get_client, get_status_property_type, resolve_data_source_id
from tools.notion._retry import notion_call


async def fetch_pages_by_status(
    database_id: str,
    status: str,
    *,
    status_property: str = "상태",
    limit: int = 5,
) -> list[dict[str, Any]]:
    """status가 일치하는 페이지를 최대 limit개 fetch. raw page dict 리스트 반환.

    database_id    : 콘텐츠 DB의 id (URL fragment).
    status         : "이미지 필요" 등. 옵션 이름과 정확히 일치해야 함.
    status_property: 상태 속성 이름. 운영 컨벤션 default = "상태".
    limit          : 최대 페이지 수 (Notion page_size 한도 100).
    """
    client = get_client()
    ds_id = resolve_data_source_id(database_id)
    ptype = get_status_property_type(database_id, status_property)
    filter_obj = {"property": status_property, ptype: {"equals": status}}
    page_size = min(limit, 100)

    if ds_id != database_id:
        result = await notion_call(
            client.data_sources.query,
            data_source_id=ds_id, filter=filter_obj, page_size=page_size,
        )
    else:
        result = await notion_call(
            client.databases.query,
            database_id=database_id, filter=filter_obj, page_size=page_size,
        )
    return result.get("results", [])
