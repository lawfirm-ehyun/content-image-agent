"""Phase 4.3 4.3 Done #2 격리 검증 — text_rule=zero 텍스트 환각 폐기 동작 확인.

plan §14.6 4.3 Done #2 "텍스트 환각 의도적 시뮬레이션 1건 → 폐기 동작 확인":
실제 gpt-image 호출 없이 (cost $0) 기존 텍스트 다량 이미지를 vision_review 에
직접 통과시켜 verdict.passed=False / reason 정확 명시를 확인.

흐름:
  tests/fixtures/v1_6_4_chart_baseline/chart_bar.png (텍스트 다량 차트)
  → vision_review(text_rule="zero")
  → verdict.passed=False (text_pixels_pct ≥ 1.0 AND ocr_tokens ≥ 3 트리거)

이 스크립트 = 재현 가능 검증 path. 4.3 운영 자연 cover 진행 전 spot-check 용.

CLI:
  uv run python scripts/_check_vision_dispose.py
    → 기본 chart_bar.png 검증
  uv run python scripts/_check_vision_dispose.py --image-path <local.png|.webp>
    → 임의 이미지 검증 (운영 e2e 후 spot-check)

Production 0 touch. tools.render.vision_review read-only import.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
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

from tools.render.vision_review import vision_review  # noqa: E402

_DEFAULT_IMAGE = ROOT / "tests" / "fixtures" / "v1_6_4_chart_baseline" / "chart_bar.png"


async def _amain(args: argparse.Namespace) -> int:
    img = Path(args.image_path) if args.image_path else _DEFAULT_IMAGE
    if not img.is_file():
        print(f"[fail] image_path 부재: {img}")
        return 2

    print(f"[input] {img}")
    print(f"        size  = {img.stat().st_size:,} bytes")

    verdict, cost_usd = await vision_review(img, text_rule="zero")

    print()
    print("=" * 70)
    print("Phase 4.3 4.3 Done #2 격리 검증 — text_rule=zero 폐기 동작")
    print("=" * 70)
    print(f"cost_usd : ${cost_usd:.6f}")
    print()
    print("--- verdict ---")
    print(json.dumps(verdict, ensure_ascii=False, indent=2))
    print()
    print("--- gate #2 ---")
    expected_pass = False  # 텍스트 다량 → text_rule=zero 폐기 예상
    actual_pass = verdict["passed"]
    is_default = args.image_path is None
    if is_default:
        print(f"  image           : default chart_bar.png (텍스트 다량 차트)")
        print(f"  expected.passed : {expected_pass} (text_rule=zero → 폐기)")
        print(f"  actual.passed   : {actual_pass}")
        print(f"  result          : {'PASS' if actual_pass == expected_pass else 'FAIL'}")
        return 0 if actual_pass == expected_pass else 1
    else:
        print(f"  image           : {img.name} (사용자 지정)")
        print(f"  actual.passed   : {actual_pass}")
        print(f"  reason          : {verdict['reason'] or '(no reason — passed)'}")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--image-path",
        help=f"검증할 PNG/WebP 경로. 미지정 시 {_DEFAULT_IMAGE.relative_to(ROOT)}",
    )
    args = parser.parse_args()

    try:
        return asyncio.run(_amain(args))
    except KeyboardInterrupt:
        print("\n[abort] 사용자 중단")
        return 130
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
