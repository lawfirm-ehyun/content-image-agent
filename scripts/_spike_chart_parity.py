"""Week 3a 회귀 검증 — master_chart 렌더 vs v1.6.4 baseline SHA256 4/4 동일.

plan §12.2 회귀 검증 방법: "4 sub-type 각 sample input 픽스처 → pre-refactor 렌더 PNG
저장 → post-refactor 렌더 PNG → SHA 비교. 차이 0 → 통과."

baseline 락 commit: 308d98e (tests/fixtures/v1_6_4_chart_baseline/*.{json,png}).
본 스크립트는 같은 input JSON으로 ChartSpec + render_chart(master_chart.html) 렌더 →
새 PNG의 SHA256과 baseline의 sha256 비교. 4/4 일치 = Week 3a 통과.

Usage:
  python scripts/_spike_chart_parity.py            # 기본 (tmp dir에 렌더 후 비교)
  python scripts/_spike_chart_parity.py --keep     # 비교용 PNG 보존 (mismatch diff 분석)

Production 코드 0 touch. tools.render.chart_render는 read-only import.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from tools.render.chart_render import ChartSpec, render_chart  # noqa: E402

FIXTURE_DIR = ROOT / "tests" / "fixtures" / "v1_6_4_chart_baseline"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


async def _verify_one(
    fixture_path: Path, out_dir: Path
) -> tuple[str, bool, str, str, str]:
    """1개 fixture 처리. (name, match?, baseline_sha, new_sha, detail) 반환."""
    name = fixture_path.stem
    fix = json.loads(fixture_path.read_text(encoding="utf-8"))
    captured = fix.get("captured_baseline")
    if not captured:
        return (name, False, "", "", "no captured_baseline in fixture")
    baseline_sha = captured["sha256"]
    baseline_bytes = captured["png_bytes"]

    spec = ChartSpec(sub_type=fix["sub_type"], **fix["input"])
    out_path = out_dir / f"{name}.png"
    await render_chart(spec, out_path)
    new_sha = _sha256(out_path)
    new_bytes = out_path.stat().st_size

    match = new_sha == baseline_sha
    detail = (
        f"baseline={baseline_bytes}B sha={baseline_sha[:12]} / "
        f"new={new_bytes}B sha={new_sha[:12]}"
    )
    return (name, match, baseline_sha, new_sha, detail)


async def _amain() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--keep", action="store_true",
        help="비교용 PNG를 tests/fixtures/_parity_out/ 에 보존 (mismatch diff 분석용)",
    )
    args = parser.parse_args()

    fixtures = sorted(FIXTURE_DIR.glob("chart_*.json"))
    if not fixtures:
        print(f"[error] no chart_*.json in {FIXTURE_DIR}", file=sys.stderr)
        return 2

    if args.keep:
        out_dir = ROOT / "tests" / "fixtures" / "_parity_out"
        out_dir.mkdir(exist_ok=True)
        ctx = None  # use out_dir directly
    else:
        ctx = tempfile.TemporaryDirectory(prefix="chart_parity_")
        out_dir = Path(ctx.name)

    print(f"baseline dir: {FIXTURE_DIR.relative_to(ROOT)}")
    print(f"render out  : {out_dir if args.keep else '(tmp)'}")
    print(f"fixtures    : {[f.name for f in fixtures]}")
    print("-" * 72)

    try:
        results = []
        for f in fixtures:
            name, match, b_sha, n_sha, detail = await _verify_one(f, out_dir)
            flag = "[PASS]" if match else "[FAIL]"
            print(f"{flag} {name}: {detail}")
            results.append((name, match))
    finally:
        if ctx is not None:
            ctx.cleanup()

    print("-" * 72)
    passed = sum(1 for _, m in results if m)
    total = len(results)
    if passed == total:
        print(f"summary: ALL PASS ({passed}/{total}) — Week 3a 회귀 0 — commit OK")
        return 0
    print(
        f"summary: FAILED ({passed}/{total}) — mismatch 발생. "
        "--keep로 재실행 후 PNG diff 분석 필요."
    )
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_amain()))
