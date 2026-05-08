"""Notion 도구 공통 유틸. lazy client + data_source 해석.

설계 결정:
  - notion-client 3.0이 file_uploads / data_sources 모두 풀 지원 → SDK 통일.
  - SDK는 sync. async 컨벤션 위해 호출 측에서 asyncio.to_thread()로 감쌈.
  - Notion-Version은 SDK default "2025-09-03" (multi-source DB 대응) 사용.
"""
from __future__ import annotations

import os
from functools import lru_cache

from notion_client import Client


class NotionConfigError(RuntimeError):
    """NOTION_TOKEN 누락 등 환경설정 문제."""


@lru_cache(maxsize=1)
def get_client() -> Client:
    """싱글톤 Client. 첫 호출 시 NOTION_TOKEN 검증."""
    token = os.environ.get("NOTION_TOKEN", "").strip()
    if not token:
        raise NotionConfigError("NOTION_TOKEN 가 .env / 환경변수에 없음")
    return Client(auth=token)


def resolve_data_source_id(database_id: str) -> str:
    """database_id → primary data_source_id.

    multi-source DB이면 data_sources[0].id, single-source면 database_id 그대로.
    Phase 1 콘텐츠/로그 DB는 모두 single-source 가정이지만 운영 도중 multi-source
    전환 가능성 있어 일관 처리.
    """
    db = get_client().databases.retrieve(database_id)
    data_sources = db.get("data_sources") or []
    if data_sources:
        return data_sources[0]["id"]
    return database_id


@lru_cache(maxsize=8)
def get_status_property_type(database_id: str, property_name: str = "상태") -> str:
    """`상태` 속성이 'select' 타입인지 'status' 타입인지 확인. notion API에서
    update/filter 페이로드 키가 다르므로 호출 측에서 분기 필요.

    PROJECT_CONTEXT §5.2 운영 컨벤션이 select/status 모두 허용 — 실제 DB가 어느 쪽인지
    schema retrieve로 확정.
    """
    import httpx  # 지연 import (multi-source 처리에만 필요)

    client = get_client()
    db = client.databases.retrieve(database_id)
    props = db.get("properties") or {}

    # multi-source면 properties가 비어있고 data_source에서 가져와야 함
    if not props:
        ds_id = resolve_data_source_id(database_id)
        token = os.environ["NOTION_TOKEN"].strip()
        r = httpx.get(
            f"https://api.notion.com/v1/data_sources/{ds_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "Notion-Version": "2025-09-03",
            },
            timeout=30,
        )
        r.raise_for_status()
        props = r.json().get("properties") or {}

    prop = props.get(property_name)
    if not prop:
        raise KeyError(f"DB {database_id} 에 '{property_name}' 속성 없음")
    ptype = prop["type"]
    if ptype not in {"select", "status"}:
        raise ValueError(
            f"'{property_name}' 속성 타입이 select/status가 아님: {ptype!r}"
        )
    return ptype
