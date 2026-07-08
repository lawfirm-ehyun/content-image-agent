"""작업 로그 DB에 row 추가.

PROJECT_CONTEXT §5.3 스키마 + AGENT_GUIDE 절대 룰 #1 (데이터 정확성).

핵심:
  - `작업 ID` (title): "{ISO 일시} | {출처} | {타입}" 형식. 운영팀 검색/정렬 용이.
  - `관련 페이지` (rich_text): page mention 객체로 박음 (relation 속성 없음).
  - `입력(JSON)` (rich_text): JSON 직렬화, separators 공백 없음 (스키마 컨벤션).
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal

from tools.notion import get_client, norm_uuid, resolve_data_source_id
from tools.notion._retry import notion_call


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

    created = await notion_call(client.pages.create, parent=parent, properties=properties)
    return created["id"]


async def get_logged_page_ids(log_db_id: str, *, limit: int = 100) -> set[str]:
    """로그 DB 최근 N건에서 **성공 이력이 있는** '관련 페이지' page_id 추출 (§19.1 멱등성).

    cron이 batch 시작 시 1회 호출. 반환된 set에 page_id(정규화)가 있으면 그 페이지는
    이미 이미지가 1장 이상 삽입됨 → skip (중복 삽입 방지).

    v1.8.4 (2026-07-07) — skip 기준을 "로그 행 존재"에서 "**성공 행(셀프 리뷰=True)
    존재**"로 좁힘. 멱등성 가드의 진짜 목적은 "중복 이미지 삽입 방지"인데, 이미지가
    0장 박힌(전부 실패) 페이지까지 skip 하던 게 부작용이었음. 전부 실패 페이지는 삽입된
    이미지가 없어 재처리해도 중복 불가 → 운영자가 상태값만 "이미지 필요"로 되돌리면
    자동 재처리 (로그 수동 삭제 불필요).

    **한계 (의도된 것)**: 일부 성공(1장+ 삽입, 나머지 실패) 페이지는 성공 행이 있어
    여전히 skip — 이미 박힌 이미지 중복 방지. 이 케이스 재처리는 "골라서 다시 그리기"
    별도 트랙 (2026-07-07 사용자 논의, 통째 재처리는 취향 판단 이미지에 부적합).
    """
    client = get_client()
    ds_id = resolve_data_source_id(log_db_id)
    page_size = min(limit, 100)
    sorts = [{"timestamp": "created_time", "direction": "descending"}]

    if ds_id != log_db_id:
        resp = await notion_call(
            client.data_sources.query,
            data_source_id=ds_id, sorts=sorts, page_size=page_size,
        )
    else:
        resp = await notion_call(
            client.databases.query,
            database_id=log_db_id, sorts=sorts, page_size=page_size,
        )

    out: set[str] = set()
    for row in resp.get("results", []):
        props = row.get("properties", {}) or {}
        # 성공 행만 카운트 — 셀프 리뷰 체크박스가 True (이미지 실제 삽입됨) 일 때만.
        # log_metadata 는 review_passed and new_block_id is not None 일 때만 True 로 기록.
        if not (props.get("셀프 리뷰") or {}).get("checkbox"):
            continue
        related = (props.get("관련 페이지") or {}).get("rich_text") or []
        for item in related:
            if item.get("type") != "mention":
                continue
            page_id = ((item.get("mention") or {}).get("page") or {}).get("id")
            if page_id:
                out.add(norm_uuid(page_id))
    return out
