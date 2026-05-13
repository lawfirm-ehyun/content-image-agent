"""Week 3b parametric distinct 검증 — bar 1 데이터셋 × 3 조합 → visually distinct 2/3+ (plan §12.4 가드 2 (a) preview).

formal Week 4 e2e는 production 본문 데이터로 별도 진행. 본 스크립트는 **preview 자산** —
parametric 손잡이 2개 (orientation, emphasis_index)가 실제 시각 차이를 만들어내는지
spike 컨벤션으로 빠르게 확인.

조합 선정 (plan §12.4 distinct 판정 — orientation 변경 OR emphasis 위치 변경 OR 둘 다):
  A) orientation=vertical, emphasis_index=None  — Week 3a baseline 동작
  B) orientation=vertical, emphasis_index=2     — emphasis 위치 변경
  C) orientation=horizontal, emphasis_index=None — orientation 변경
→ 3쌍 비교 (A vs B, A vs C, B vs C) 모두 distinct 기대.

distinct 판정 메커니즘: PNG SHA256 다르면 distinct (plan §12.4 정의의 mechanical proxy).
실제 시각 차이 → 픽셀 변동 → SHA 차이. SHA 동일 = byte-identity = visually 동일.

합격선: 3쌍 중 2쌍 이상 distinct (2/3+).
미달 시 §12.5 — parametric vocab 확장 X, composition primitive 검토 진입.

Usage:
  python scripts/_spike_chart_distinct.py            # 기본 (tmp dir 렌더)
  python scripts/_spike_chart_distinct.py --keep     # PNG 보존 (시각 검수용)

Production 코드 0 touch. tools.render.chart_render는 read-only import.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import itertools
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from tools.render.chart_render import ChartSpec, render_chart  # noqa: E402


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


# bar 시계열 (parity baseline과 동일 shape, 본문 사실 시뮬레이션).
# 4 포인트 → emphasis_index=2 유효.
_BAR_INPUT = dict(
    title="연도별 발생 건수",
    labels=["2021", "2022", "2023", "2024"],
    values=[28988.0, 29258.0, 24252.0, 33581.0],
    point_labels=["28,988건", "29,258건", "24,252건", "33,581건"],
    y_unit="(건)",
    source="출처: 경찰청 (가상 데이터)",
)

_VARIANTS = [
    ("A_vertical_none",       dict(orientation="vertical",   emphasis_index=None)),
    ("B_vertical_emphasis2",  dict(orientation="vertical",   emphasis_index=2)),
    ("C_horizontal_none",     dict(orientation="horizontal", emphasis_index=None)),
]


async def _render_variants(out_dir: Path) -> list[tuple[str, str]]:
    """3 variant 렌더 → [(name, sha256), ...]."""
    results: list[tuple[str, str]] = []
    for name, params in _VARIANTS:
        spec = ChartSpec(sub_type="bar", **_BAR_INPUT, **params)
        out_path = out_dir / f"{name}.png"
        await render_chart(spec, out_path)
        sha = _sha256(out_path)
        size = out_path.stat().st_size
        print(f"  rendered {name}: {size}B sha={sha[:12]}")
        results.append((name, sha))
    return results


async def _amain() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--keep", action="store_true",
        help="비교용 PNG를 tests/fixtures/_distinct_out/ 에 보존 (시각 검수용)",
    )
    args = parser.parse_args()

    if args.keep:
        out_dir = ROOT / "tests" / "fixtures" / "_distinct_out"
        out_dir.mkdir(exist_ok=True)
        ctx = None
    else:
        ctx = tempfile.TemporaryDirectory(prefix="chart_distinct_")
        out_dir = Path(ctx.name)

    print(f"render out: {out_dir if args.keep else '(tmp)'}")
    print(f"variants  : {[v[0] for v in _VARIANTS]}")
    print("-" * 72)

    try:
        results = await _render_variants(out_dir)
    finally:
        if ctx is not None:
            ctx.cleanup()

    print("-" * 72)
    print("pairwise distinct (SHA256 차이):")
    pairs = list(itertools.combinations(results, 2))
    distinct_count = 0
    for (n1, s1), (n2, s2) in pairs:
        flag = "[DISTINCT]" if s1 != s2 else "[SAME]"
        if s1 != s2:
            distinct_count += 1
        print(f"  {flag} {n1} vs {n2}")

    total = len(pairs)
    print("-" * 72)
    if distinct_count >= 2:
        print(f"summary: PASS ({distinct_count}/{total} distinct) — Week 3b parametric 작동 확인")
        return 0
    print(
        f"summary: FAIL ({distinct_count}/{total} distinct, 2/3 미달) — "
        "§12.5 composition primitive 분기 검토 필요"
    )
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_amain()))
