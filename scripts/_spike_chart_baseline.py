"""Week 3a chart 통합 사전 가드 — v1.6.4 chart_line/bar/donut/pie baseline 캡처.

§12.4 가드 2 (b) "master_chart 결과가 v1.6.4 chart_line/donut/pie와 시각/사실 동일"
검증을 위해 **통합 시작 전** 4 sub-type의 baseline PNG + sha256을 락한다.
plan §12.2 회귀 검증 방법(SHA 또는 OCR text diff 비교, 차이 0 = 통과)의 baseline 자산.

캡처 후 master_chart 통합이 끝나면 같은 입력 JSON으로 master_chart 렌더 → 새 PNG sha256
vs 본 baseline 비교. 동일하면 회귀 0.

Usage:
  python scripts/_spike_chart_baseline.py            # 캡처 (이미 차 있으면 skip)
  python scripts/_spike_chart_baseline.py --force    # 강제 재캡처

Production 코드 0 touch. tools.render.chart_render는 read-only import.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from tools.render.chart_render import ChartSpec, render_chart  # noqa: E402

FIXTURE_DIR = ROOT / "tests" / "fixtures" / "v1_6_4_chart_baseline"

# 캡처 시점 의미: 본 fixture의 captured_baseline.git_commit이 baseline 식별자.
# Week 3a 통합 후 본 스크립트는 master_chart path로 동작 — git_commit이 a12f666이면
# v1.6.4 chart_*.html 렌더 결과, 308d98e 이후면 master_chart 렌더 결과.
# 두 SHA가 동일하면 master_chart가 v1.6.4 byte-identical (=Week 3a 통과 증명).


def _git_head() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, stderr=subprocess.DEVNULL
        )
        return out.decode().strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "<unknown>"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


async def _capture_one(fixture_path: Path, *, force: bool) -> tuple[str, bool, str]:
    """1개 fixture 처리. (name, captured?, detail) 반환."""
    name = fixture_path.stem
    fix = json.loads(fixture_path.read_text(encoding="utf-8"))
    sub_type = fix["sub_type"]
    if sub_type not in ("line", "bar", "donut", "pie"):
        return (name, False, f"unknown sub_type={sub_type!r}")

    if not force and fix.get("captured_baseline") is not None:
        ts = fix["captured_baseline"].get("captured_at")
        return (name, False, f"skip (already captured at {ts})")

    spec = ChartSpec(sub_type=sub_type, **fix["input"])
    png_path = FIXTURE_DIR / f"{name}.png"
    await render_chart(spec, png_path)
    if not png_path.exists() or png_path.stat().st_size == 0:
        return (name, False, f"render produced empty/missing PNG: {png_path}")

    fix["captured_baseline"] = {
        "png_path": png_path.name,
        "png_bytes": png_path.stat().st_size,
        "sha256": _sha256(png_path),
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_commit": _git_head(),
    }
    fixture_path.write_text(
        json.dumps(fix, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return (
        name,
        True,
        f"captured — {fix['captured_baseline']['png_bytes']} bytes, "
        f"sha={fix['captured_baseline']['sha256'][:12]}…",
    )


async def _amain() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--force", action="store_true",
        help="기존 captured_baseline이 있어도 재캡처 (baseline 손상 주의 — 통합 시작 후 X)",
    )
    args = parser.parse_args()

    fixtures = sorted(FIXTURE_DIR.glob("chart_*.json"))
    if not fixtures:
        print(f"[error] no chart_*.json fixtures in {FIXTURE_DIR}", file=sys.stderr)
        return 2

    print(f"baseline dir: {FIXTURE_DIR.relative_to(ROOT)}")
    print(f"git HEAD: {_git_head()[:12]}")
    print(f"fixtures: {[f.name for f in fixtures]}")
    print("-" * 72)

    results = []
    for f in fixtures:
        name, captured, detail = await _capture_one(f, force=args.force)
        flag = "[NEW]" if captured else "[SKIP]"
        print(f"{flag} {name}: {detail}")
        results.append((name, captured, detail))

    print("-" * 72)
    new = sum(1 for _, c, _ in results if c)
    total = len(results)
    print(f"summary: {new}/{total} captured, {total - new} skipped")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_amain()))
