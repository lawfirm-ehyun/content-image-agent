"""Phase 1 e2e: 한 페이지 수동 trigger.

사용법:
  uv run python scripts/test_phase1.py <PAGE_ID> --source 블로그
  uv run python scripts/test_phase1.py <PAGE_ID> --source 웹

전제조건:
  - .env 에 NOTION_TOKEN, ANTHROPIC_API_KEY, NOTION_DB_LOG 채워짐.
  - 페이지가 콘텐츠 DB에 존재 + integration이 connect됨.
  - 페이지 status가 "이미지 필요"일 필요는 없음 (수동 trigger).

출력:
  - 슬롯별 결과 + 페이지 합계 비용 + 최종 status를 stdout에 보고.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# Windows PowerShell 기본 콘솔이 cp949라 한국어/em-dash 출력 시 깨짐 → UTF-8 강제.
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# scripts/ 에서 직접 실행될 때 프로젝트 루트를 sys.path에 노출
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

from orchestrator import run_for_page  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Phase 1 e2e — 한 페이지 처리")
    p.add_argument("page_id", help="콘텐츠 DB의 page id (URL fragment 32자 hex)")
    p.add_argument(
        "--source",
        choices=["블로그", "웹"],
        required=True,
        help="페이지 출처. 로그 DB의 '출처' select 값과 일치해야 함.",
    )
    return p.parse_args()


async def main() -> int:
    load_dotenv()
    args = _parse_args()

    log_db_id = os.environ.get("NOTION_DB_LOG", "").strip()
    if not log_db_id:
        print("[FAIL] .env에 NOTION_DB_LOG가 비어있음", file=sys.stderr)
        return 2

    print(f"[RUN] page_id={args.page_id} source={args.source}")
    result = await run_for_page(args.page_id, args.source, log_db_id)

    print()
    print(f"=== 결과 ===")
    print(f"슬롯: {result.slots_passed}/{result.slots_total} 통과 ({result.slots_failed} 실패)")
    print(f"비용: ${result.cost_usd:.4f}")
    print(f"최종 status: {result.final_status}")
    print()
    for i, r in enumerate(result.slot_results, 1):
        mark = "OK" if r.passed else "FAIL"
        sub = f"({r.sub_type})" if r.sub_type else ""
        print(f"  [{mark}] #{i} {r.type}{sub}  attempts={r.attempts}  ${r.cost_usd:.4f}")
        for issue in r.issues:
            print(f"        - {issue}")

    return 0 if result.slots_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
