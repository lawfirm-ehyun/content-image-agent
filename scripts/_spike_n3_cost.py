"""§12 Week 1-2 — production 1페이지 SDK path cost N≥3 측정 (plan §12.1 약속).

Week 0 spike(`scripts/_spike_sdk.py`)는 synthetic fixture (`tests/fixtures/spike_sdk_baseline.json`)
위에서 N=4 SDK vs subprocess 비교. plan §12.1 노트:
  "단정 X. Week 1-2 통합 시 실제 본문 + cache hit 포함 N≥3 재측정 예정."

이 스크립트가 그 약속 이행 — `analyze_content` (production path, 이미 SDK로 갈아낌)을
"이미지 필요" 첫 페이지에 N=3 호출. 이미지 생성 / 노션 업데이트 / 로그 기록 X.
페이지/슬롯/노션 cap 0 touch.

Usage:
  python scripts/_spike_n3_cost.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

try:
    from dotenv import load_dotenv  # noqa: PLC0415
    load_dotenv(dotenv_path=ROOT / ".env")
except ImportError:
    pass

from tools.llm._common import compact_blocks  # noqa: E402
from tools.llm.analyze_content import analyze_content  # noqa: E402
from tools.notion.fetch_pages import fetch_pages_by_status  # noqa: E402
from tools.notion.get_page_content import get_page_blocks  # noqa: E402


async def _amain() -> int:
    blog_db = os.environ["NOTION_DB_BLOG"].strip()
    web_db = os.environ["NOTION_DB_WEB"].strip()

    pages = await fetch_pages_by_status(blog_db, status="이미지 필요", limit=1)
    src = "블로그"
    if not pages:
        pages = await fetch_pages_by_status(web_db, status="이미지 필요", limit=1)
        src = "웹"
    if not pages:
        print("[skip] '이미지 필요' 페이지 없음 (블로그/웹). 측정 보류.")
        return 2

    page = pages[0]
    page_id = page["id"]
    props = page.get("properties") or {}
    title_prop = props.get("이름") or props.get("Name") or {}
    title = "".join(t.get("plain_text", "") for t in (title_prop.get("title") or [])) or "(no title)"
    print(f"[page] src={src}, id={page_id}, title={title[:60]}")

    blocks = await get_page_blocks(page_id)
    compacted = compact_blocks(blocks)
    text_chars = sum(len(b.get("text", "")) for b in compacted)
    print(f"[blocks] raw={len(blocks)}, compacted={len(compacted)}, text~{text_chars} chars")

    costs: list[float | None] = []
    durations: list[float] = []
    slot_types: list[list[str] | None] = []
    for i in range(1, 4):
        t0 = time.monotonic()
        try:
            slots, cost = await analyze_content(blocks)
            dt = time.monotonic() - t0
            costs.append(cost)
            durations.append(dt)
            types = [s.get("type") for s in slots]
            slot_types.append(types)
            print(f"[N={i}] cost=${cost:.4f}, dt={dt:.1f}s, slots={len(slots)} ({types})")
        except Exception as e:  # noqa: BLE001
            dt = time.monotonic() - t0
            costs.append(None)
            durations.append(dt)
            slot_types.append(None)
            print(f"[N={i}] FAIL dt={dt:.1f}s: {type(e).__name__}: {str(e)[:300]}")

    print()
    print("=" * 72)
    good = [c for c in costs if c is not None]
    print(f"summary  page={page_id[:8]} src={src} text~{text_chars}c")
    if good:
        avg = sum(good) / len(good)
        print(f"  N={len(good)}/{len(costs)} success, costs={[f'${c:.4f}' for c in good]}")
        print(f"  mean=${avg:.4f}, min=${min(good):.4f}, max=${max(good):.4f}")
        if len(good) >= 2:
            ratio = min(good) / max(good)
            print(f"  cache ratio min/max = {ratio:.2f}x (낮을수록 cache hit 효과 큼)")
        total = sum(good)
        print(f"  total spend N={len(good)} = ${total:.4f}")
    else:
        print("  N=0 success — 측정 실패")
    print("=" * 72)
    return 0 if good else 1


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(_amain()))
    except Exception:
        traceback.print_exc()
        sys.exit(1)
