"""Phase 0 게이트: Notion 연결/스키마 검증.

.env에 NOTION_TOKEN + NOTION_DB_BLOG/WEB/LOG 채운 후 한 번 실행.

검증 항목:
1. NOTION_TOKEN으로 3개 DB retrieve 가능 (read 권한 + integration connect)
2. 각 DB title/속성 출력 → 매핑이 맞는지 사람이 시각 확인
3. 콘텐츠 DB(블로그/웹)의 `상태` select 옵션:
   `이미지필요`, `발행필요`, `이미지 작업 중` 모두 존재하는지
4. 로그 DB가 실제 운영 컨벤션 + 권장 보강 속성을 가지는지

Notion multi-source database 대응: properties는 data_sources[0]에서 가져옴.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from dotenv import load_dotenv
from notion_client import Client

NOTION_API_VERSION = "2025-09-03"  # multi-source database 지원 버전

# 로그 DB 필수 스키마 (실제 운영 컨벤션 align됨, 2026-05-06)
LOG_DB_REQUIRED_SCHEMA: dict[str, str] = {
    "작업 ID": "title",
    "출처": "select",
    "관련 페이지": "rich_text",
    "타입": "select",
    "차트 타입": "select",
    "생성 방식": "select",
    "입력(JSON)": "rich_text",
    "비용 USD": "number",
    "시도 횟수": "number",
    "셀프 리뷰": "checkbox",
    "생성 일시": "created_time",
}

# Phase 4 학습 루프용 권장 속성 (없으면 WARN, 있으면 베스트)
LOG_DB_RECOMMENDED_SCHEMA: dict[str, str] = {
    "사람이 교체함": "checkbox",  # Phase 4 학습 시그널의 핵심
    "결과 이미지": "files",  # 이미지 사본 (옵션)
}

# 콘텐츠 DB의 상태 select 옵션 (실제 운영 컨벤션 align됨, 2026-05-06)
# 운영팀이 노션에서 사용하는 표기는 띄어쓰기 포함. 코드/계획서가 운영 현실 따라감.
REQUIRED_STATUS_OPTIONS = {"이미지 필요", "발행 필요", "이미지 작업 중"}

# 콘텐츠 DB의 상태 속성명 후보 (실제 컨벤션 우선)
STATUS_PROPERTY_CANDIDATES = ["상태", "status", "Status"]


@dataclass
class DbReport:
    env_var: str
    db_id: str
    title: str
    properties: dict[str, str]  # name → type
    data_source_id: str | None = None  # multi-source인 경우
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _fetch_data_source(token: str, ds_id: str) -> dict:
    """multi-source database의 data_source retrieve (raw httpx).

    notion-client 3.0이 아직 data_sources 엔드포인트를 노출 안 해서 직접 호출.
    근본 처리를 위해 SDK가 지원되는 버전이 나오면 client 메서드로 대체할 것.
    """
    r = httpx.get(
        f"https://api.notion.com/v1/data_sources/{ds_id}",
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_API_VERSION,
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def _retrieve_db(client: Client, token: str, env_var: str) -> DbReport | None:
    db_id = os.environ.get(env_var, "").strip()
    if not db_id:
        print(f"  [SKIP] {env_var} 가 .env에 비어 있음")
        return None
    try:
        db = client.databases.retrieve(db_id)
    except Exception as e:
        print(f"  [FAIL] {env_var}={db_id} retrieve 실패: {e}")
        return None

    title = "".join(t.get("plain_text", "") for t in db.get("title", []))
    props_raw = db.get("properties", {}) or {}
    data_source_id: str | None = None

    # multi-source 처리: properties가 비어있고 data_sources가 있으면 거기서 가져옴
    data_sources = db.get("data_sources", []) or []
    if not props_raw and data_sources:
        if len(data_sources) > 1:
            print(
                f"  [WARN] {env_var}: multi-source DB에 data_source가 {len(data_sources)}개. "
                f"첫 번째만 사용 ('{data_sources[0].get('name', '')}')"
            )
        data_source_id = data_sources[0]["id"]
        try:
            ds = _fetch_data_source(token, data_source_id)
            props_raw = ds.get("properties", {}) or {}
        except Exception as e:
            print(f"  [FAIL] {env_var} data_source retrieve 실패: {e}")
            return None

    props = {name: meta["type"] for name, meta in props_raw.items()}
    return DbReport(
        env_var=env_var,
        db_id=db_id,
        title=title,
        properties=props,
        data_source_id=data_source_id,
    )


def _check_status_options(db: DbReport, client: Client, token: str) -> None:
    """콘텐츠 DB의 상태 select 옵션 검증."""
    if db.data_source_id:
        full = _fetch_data_source(token, db.data_source_id)
    else:
        full = client.databases.retrieve(db.db_id)
    props = full.get("properties", {}) or {}

    status_prop = None
    found_name = None
    for cand in STATUS_PROPERTY_CANDIDATES:
        if cand in props:
            status_prop = props[cand]
            found_name = cand
            break

    if status_prop is None:
        db.issues.append(f"상태 속성 없음 (찾은 후보: {STATUS_PROPERTY_CANDIDATES})")
        return

    ptype = status_prop["type"]
    if ptype == "select":
        options = {o["name"] for o in status_prop["select"]["options"]}
    elif ptype == "status":
        options = {o["name"] for o in status_prop["status"]["options"]}
    else:
        db.issues.append(f"'{found_name}' 속성 타입이 select/status가 아님: {ptype}")
        return
    missing = REQUIRED_STATUS_OPTIONS - options
    if missing:
        db.issues.append(f"'{found_name}' 옵션 누락: {sorted(missing)} (현재: {sorted(options)})")


def _check_log_schema(db: DbReport) -> None:
    """로그 DB 스키마 검증 — 필수 + 권장."""
    for prop_name, expected_type in LOG_DB_REQUIRED_SCHEMA.items():
        actual_type = db.properties.get(prop_name)
        if actual_type is None:
            db.issues.append(f"필수 속성 누락: '{prop_name}' (expected {expected_type})")
        elif actual_type != expected_type:
            db.issues.append(
                f"필수 속성 타입 불일치: '{prop_name}' expected={expected_type}, actual={actual_type}"
            )

    for prop_name, expected_type in LOG_DB_RECOMMENDED_SCHEMA.items():
        actual_type = db.properties.get(prop_name)
        if actual_type is None:
            db.warnings.append(
                f"권장 속성 누락: '{prop_name}' ({expected_type}) — Phase 4 학습 루프에 사용"
            )
        elif actual_type != expected_type:
            db.warnings.append(
                f"권장 속성 타입 불일치: '{prop_name}' expected={expected_type}, actual={actual_type}"
            )


def _classify(reports: list[DbReport]) -> dict[str, DbReport]:
    """DB 분류: schema 시그니처 우선, title은 fallback.

    schema-first인 이유: 한국어 substring 매칭이 위험함.
    예: "로그" in "블로그" → True (블로그가 로그로 잘못 분류됨).
    schema 시그니처는 unique한 속성 조합으로 매칭하므로 robust.

    분류 순서: log → blog → web (로그가 가장 unique한 시그니처를 가짐).
    """
    classified: dict[str, DbReport] = {}
    remaining = list(reports)

    # 1순위: 로그 DB — schema 시그니처 (가장 robust)
    log_signature = ["작업 ID", "출처", "관련 페이지", "타입"]
    for r in list(remaining):
        if all(prop in r.properties for prop in log_signature):
            classified["log"] = r
            remaining.remove(r)
            break

    # log fallback: schema로 못 잡으면 title의 specific 키워드
    if "log" not in classified:
        for r in list(remaining):
            # "로그"만 매칭하면 "블로그"에 substring 매칭됨. 더 specific하게.
            if "작업 로그" in r.title or "이미지 로그" in r.title:
                classified["log"] = r
                remaining.remove(r)
                break

    # 2순위: 블로그
    for r in list(remaining):
        if "블로그" in r.title or "인블로그" in r.title or "blog" in r.title.lower():
            classified["blog"] = r
            remaining.remove(r)
            break

    # 3순위: 웹
    for r in list(remaining):
        if "웹" in r.title or "ai.kr" in r.title.lower() or "web" in r.title.lower():
            classified["web"] = r
            remaining.remove(r)
            break

    return classified


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    load_dotenv(repo_root / ".env")

    token = os.environ.get("NOTION_TOKEN", "").strip()
    if not token:
        print("[FAIL] NOTION_TOKEN이 .env에 없음")
        return 1

    client = Client(auth=token, notion_version=NOTION_API_VERSION)

    print("=" * 60)
    print("Phase 0 게이트 — Notion DB 검증")
    print("=" * 60)

    print("\n[1/4] 3개 DB retrieve 시도")
    reports: list[DbReport] = []
    for env_var in ["NOTION_DB_BLOG", "NOTION_DB_WEB", "NOTION_DB_LOG"]:
        r = _retrieve_db(client, token, env_var)
        if r:
            reports.append(r)
            ds_marker = f" data_source={r.data_source_id[:8]}..." if r.data_source_id else ""
            print(f"  [OK ] {env_var}: '{r.title}' ({len(r.properties)} 속성){ds_marker}")

    if len(reports) < 3:
        print(f"\n[FAIL] 3개 중 {len(reports)}개만 retrieve. .env 확인 + integration connect 확인.")
        return 1

    print("\n[2/4] DB 자동 분류 (title 키워드 + schema 시그니처)")
    classified = _classify(reports)
    for kind in ("blog", "web", "log"):
        r = classified.get(kind)
        if r:
            print(f"  [{kind:>4}] {r.env_var} → '{r.title}'")
        else:
            print(f"  [{kind:>4}] 자동 식별 실패")

    print("\n[3/4] 콘텐츠 DB '상태' 옵션 검증")
    for kind in ("blog", "web"):
        r = classified.get(kind)
        if r is None:
            continue
        try:
            _check_status_options(r, client, token)
        except Exception as e:
            r.issues.append(f"상태 옵션 검증 중 예외: {e}")
        if r.issues:
            for issue in r.issues:
                print(f"  [FAIL] {kind}: {issue}")
        else:
            print(f"  [OK ] {kind}: 상태 옵션 OK")

    print("\n[4/4] 로그 DB 스키마 검증 (실제 컨벤션 + 권장)")
    log = classified.get("log")
    if log is None:
        print("  [SKIP] 로그 DB 식별 안 됨")
    else:
        _check_log_schema(log)
        if log.issues:
            print("  [FAIL] 로그 DB 필수 속성 문제:")
            for issue in log.issues:
                print(f"         - {issue}")
        else:
            print("  [OK ] 로그 DB 필수 스키마 OK")
        if log.warnings:
            print("  [WARN] 로그 DB 권장 속성 보강 권고 (Phase 4 학습 루프용):")
            for warning in log.warnings:
                print(f"         - {warning}")

    print("\n" + "=" * 60)
    has_issues = any(r.issues for r in reports)
    has_unmapped = "blog" not in classified or "web" not in classified or "log" not in classified
    if not has_issues and not has_unmapped:
        print("✓ Phase 0 게이트 통과")
        if any(r.warnings for r in reports):
            print("  (권장 보강 항목은 Phase 4 진입 전까지 처리 권고)")
        return 0
    else:
        print("✗ Phase 0 게이트 실패 — 위 issue 처리 후 재실행")
        return 1


if __name__ == "__main__":
    sys.exit(main())
