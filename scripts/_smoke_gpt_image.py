"""gpt-image 실호출 smoke 테스트.

v1.6.1 신설. 실제 OpenAI API에 1회 호출해서 PNG를 저장. 비용 ~$0.04 (instant medium).

사용법:
  uv run python scripts/_smoke_gpt_image.py
  uv run python scripts/_smoke_gpt_image.py --quality high  # ~$0.17 (thinking)

전제: .env에 OPENAI_API_KEY 채워짐.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

from tools.render.ai_render import render_ai_card  # noqa: E402


async def smoke_illustration(out_path: Path) -> None:
    """라인 일러스트 1장 — illustration 카드 prompt path 실호출."""
    data = {
        "scene": "한국 법무법인 사무실 책상 앞에서 서류를 들고 고민하는 직장인의 옆모습",
        "mood": "고민",
        "accent_target": "서류 표지",
        "alt_text": "법률 상담 전 서류를 검토하는 모습",
    }
    print(f"[SMOKE] illustration 생성 시작 → {out_path}")
    result = await render_ai_card("illustration", data, out_path)
    print(f"[OK] {out_path} ({len(result.png_bytes)} bytes)")
    print(f"     model={result.model_id} size={result.size} quality={result.quality}")
    print(f"     cost=${result.cost_usd:.4f}")
    if result.revised_prompt:
        print(f"     revised_prompt: {result.revised_prompt[:200]}...")


async def smoke_kakao(out_path: Path) -> None:
    """kakao_dialogue 1장 — thinking 모델 실호출."""
    data = {
        "title": "음주측정 후 첫 상담",
        "messages": [
            {"sender_label": "의뢰인", "text": "변호사님, 어제 음주측정에 걸렸습니다.", "time": "오전 9:10"},
            {"sender_label": "변호사", "text": "수치가 얼마였나요? 초범이신가요?", "time": "오전 9:12"},
        ],
        "source": "본 사연은 실제 의뢰인 사연을 각색했습니다",
    }
    print(f"[SMOKE] kakao_dialogue 생성 시작 → {out_path}")
    result = await render_ai_card("kakao_dialogue", data, out_path)
    print(f"[OK] {out_path} ({len(result.png_bytes)} bytes)")
    print(f"     model={result.model_id} size={result.size} quality={result.quality}")
    print(f"     cost=${result.cost_usd:.4f}")


async def main() -> int:
    parser = argparse.ArgumentParser(description="gpt-image smoke")
    parser.add_argument(
        "--card",
        choices=["illustration", "kakao_dialogue"],
        default="illustration",
        help="테스트할 카드 종류. default illustration (저비용)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(".bkit/smoke"),
        help="결과 저장 디렉터리",
    )
    args = parser.parse_args()

    load_dotenv()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    if args.card == "illustration":
        await smoke_illustration(args.out_dir / "smoke_illustration.png")
    else:
        await smoke_kakao(args.out_dir / "smoke_kakao.png")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
