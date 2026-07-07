"""§12.9 spike — api transport (anthropic SDK 직접 호출) 검증 (v1.8.3).

두 모드:
  smoke   — 실제 analyze system prompt(스킬 47K+ 토큰)로 API 2회 연속 호출.
            1회차 영수증에 cache_creation, 2회차에 cache_read 가 찍히는지 검증.
            (~$0.5. 캐싱 설정 누락 시 여기서 걸러짐 — 본시험 전 가드.)
  compare — 같은 페이지의 analyze_content 를 sdk / api 두 transport 로 실행,
            슬롯 결정 동등성 + 비용 비교. (~$1.5/페이지)

사용:
  uv run python scripts/_spike_api_transport.py smoke
  uv run python scripts/_spike_api_transport.py compare --page-id <id>
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from tools.llm._common import (  # noqa: E402
    _call_api_sync,
    _cost_from_usage,
    load_skill,
)


def run_smoke() -> None:
    """스킬 system prompt 실물로 2회 호출 — 캐싱 영수증 검증."""
    system = (
        "너는 이현 블로그 이미지 슬롯 결정 어시스턴트다.\n\n"
        "## Slot Selection 스킬\n" + load_skill("meta/slot_selection.md") +
        "\n\n## 비주얼 가이드\n" + load_skill("style/ehyun_visual_guide.md") +
        "\n\n응답은 오직 JSON 한 객체만. 설명/주석 X."
    )
    user = (
        'BLOCKS:[{"idx":0,"type":"heading_2","text":"테스트"},'
        '{"idx":1,"type":"paragraph","text":"스모크 테스트용 더미 본문."}]\n'
        '슬롯이 없으면 {"image_slots": []} 반환.'
    )

    total = 0.0
    for i in (1, 2):
        text, usage, stop = _call_api_sync(user, system)
        cost = _cost_from_usage(usage)
        total += cost
        print(f"--- 호출 {i} ---")
        print(f"  input={usage.input_tokens:,} output={usage.output_tokens:,}")
        print(f"  cache_creation={usage.cache_creation_input_tokens:,} "
              f"cache_read={usage.cache_read_input_tokens:,}")
        print(f"  cost=${cost:.4f} stop={stop} 응답 head={text[:60]!r}")

        if i == 1 and not usage.cache_creation_input_tokens:
            print("  !! FAIL: 1회차 cache_creation=0 — cache_control 미적용?")
            sys.exit(1)
        if i == 2:
            if usage.cache_read_input_tokens:
                print("  ✔ 캐시 hit — 할인 적용 확인")
            else:
                print("  !! FAIL: 2회차 cache_read=0 — 캐싱 미작동")
                sys.exit(1)
    print(f"\nSMOKE PASS — 총 ${total:.4f}")


def _slot_summary(slots: list[dict]) -> list[str]:
    return [
        f"{s.get('type')}{'/' + s['sub_type'] if s.get('sub_type') else ''}"
        f" @after={s.get('position_after_block_id', '?')[:8]}"
        for s in slots
    ]


async def run_compare(page_id: str) -> None:
    """같은 페이지 analyze 를 sdk / api 로 실행해 나란히 비교."""
    from tools.llm.analyze_content import analyze_content
    from tools.notion.get_page_content import get_page_blocks

    blocks = await get_page_blocks(page_id)
    print(f"page {page_id}: {len(blocks)} blocks\n")

    results: dict[str, tuple[list[dict], float]] = {}
    for transport in ("sdk", "api"):
        os.environ["LLM_TRANSPORT"] = transport
        slots, cost = await analyze_content(blocks)
        results[transport] = (slots, cost)
        print(f"--- {transport} --- cost=${cost:.4f} slots={len(slots)}")
        for line in _slot_summary(slots):
            print(f"  {line}")
        print()

    sdk_slots, sdk_cost = results["sdk"]
    api_slots, api_cost = results["api"]
    sdk_types = sorted(s.get("type", "?") for s in sdk_slots)
    api_types = sorted(s.get("type", "?") for s in api_slots)
    print("=== 판정 ===")
    print(f"슬롯 수: sdk={len(sdk_slots)} api={len(api_slots)}")
    print(f"타입 구성: sdk={sdk_types} api={api_types} "
          f"{'(동일)' if sdk_types == api_types else '(차이 — LLM 비결정성 감안해 수동 판단)'}")
    print(f"비용: sdk=${sdk_cost:.4f} api=${api_cost:.4f} "
          f"(api/sdk = {api_cost / sdk_cost:.2f}x)" if sdk_cost else "")
    # 결과 원본 저장 — 수동 검토용
    out = ROOT / f"_spike_compare_{page_id[:8]}.json"
    out.write_text(
        json.dumps({t: {"cost": c, "slots": s} for t, (s, c) in results.items()},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"원본 저장: {out.name}")


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="mode", required=True)
    sub.add_parser("smoke")
    cmp_p = sub.add_parser("compare")
    cmp_p.add_argument("--page-id", required=True)
    args = p.parse_args()

    if args.mode == "smoke":
        run_smoke()
    else:
        asyncio.run(run_compare(args.page_id))


if __name__ == "__main__":
    main()
