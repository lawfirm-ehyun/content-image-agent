"""작업 로그 DB에 row 추가.

PROJECT_CONTEXT §5.3 스키마 + AGENT_GUIDE 절대 룰 #1 (데이터 정확성).

핵심:
  - `작업 ID` (title): "{ISO 일시} | {출처} | {타입}" 형식. 운영팀 검색/정렬 용이.
  - `관련 페이지` (rich_text): page mention 객체로 박음 (relation 속성 없음).
  - `입력(JSON)` (rich_text): JSON 직렬화, separators 공백 없음 (스키마 컨벤션).
"""
from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any, Literal

from tools.notion import get_client, resolve_data_source_id


async def log_metadata(
    log_db_id: str,
    page_id: str,
    page_source: Literal["블로그", "웹"],
    slot_type: str,
    slot_sub_type: str | None,
    generation_method: Literal["template", "gpt-image-2-instant", "gpt-image-2-thinking"],
    input_data: dict[str, Any],
    cost_usd: float,
    attempts: int,
    review_passed: bool,
) -> str:
    """로그 DB에 한 행 추가하고 새 page id 반환.

    log_db_id          : 로그 DB id.
    page_id            : 콘텐츠 페이지 id (mention 변환 대상).
    page_source        : "블로그" | "웹" (한글 select 값).
    slot_type          : "simple_table" | "chart" | ... (운영 select 옵션과 정확히 일치).
    slot_sub_type      : chart 슬롯이면 "line" | "bar" | "donut" | "pie", 아니면 None.
    generation_method  : "template" / AI 메서드 ID.
    input_data         : 템플릿 변수 또는 AI 프롬프트 + block_id 등. JSON 직렬화 가능해야.
    cost_usd           : 슬롯 누적 비용 (number).
    attempts           : 시도 횟수 (1+).
    review_passed      : 셀프 리뷰 (image_review) 통과 여부.
    """
    return await asyncio.to_thread(
        _log_sync,
        log_db_id, page_id, page_source, slot_type, slot_sub_type,
        generation_method, input_data, cost_usd, attempts, review_passed,
    )


def _log_sync(
    log_db_id: str,
    page_id: str,
    page_source: str,
    slot_type: str,
    slot_sub_type: str | None,
    generation_method: str,
    input_data: dict[str, Any],
    cost_usd: float,
    attempts: int,
    review_passed: bool,
) -> str:
    client = get_client()

    # 작업 ID — 운영팀 검색용. ISO 분 단위 + 한글 출처/타입.
    now_iso = datetime.now(UTC).astimezone().strftime("%Y-%m-%dT%H:%M")
    title_text = f"{now_iso} | {page_source} | {slot_type}"

    # input_data를 공백 없는 JSON으로 직렬화 (스키마 컨벤션 — PROJECT_CONTEXT §5.3)
    input_json = json.dumps(input_data, ensure_ascii=False, separators=(",", ":"))

    properties: dict[str, Any] = {
        "작업 ID": {
            "title": [{"type": "text", "text": {"content": title_text}}],
        },
        "출처": {"select": {"name": page_source}},
        "관련 페이지": {
            "rich_text": [
                {"type": "mention", "mention": {"type": "page", "page": {"id": page_id}}},
            ],
        },
        "타입": {"select": {"name": slot_type}},
        "생성 방식": {"select": {"name": generation_method}},
        "입력(JSON)": {
            "rich_text": [{"type": "text", "text": {"content": input_json}}],
        },
        "비용 USD": {"number": cost_usd},
        "시도 횟수": {"number": attempts},
        "셀프 리뷰": {"checkbox": review_passed},
    }
    if slot_sub_type:
        properties["차트 타입"] = {"select": {"name": slot_sub_type}}

    # multi-source DB 대비: parent를 data_source_id로 명시.
    ds_id = resolve_data_source_id(log_db_id)
    if ds_id != log_db_id:
        parent: dict[str, Any] = {"type": "data_source_id", "data_source_id": ds_id}
    else:
        parent = {"database_id": log_db_id}

    created = client.pages.create(parent=parent, properties=properties)
    return created["id"]
