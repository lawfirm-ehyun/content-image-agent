"""Week 0 SDK spike — claude-agent-sdk vs claude.exe subprocess functional equivalence.

§12.4 가드 1 (plan v1.7.3) 4 checks:
  1. SDK가 Sonnet 4.6 호출 OK
  2. exact_korean_strings 1자 보존 (절대 룰 #1 인프라)
  3. cost_usd float surfaced (token-ledger 호환 가능 여부)
  4. skill markdown system_prompt inject (옵션 A)

Usage:
  python scripts/_spike_sdk.py --capture   # subprocess(claude.exe)로 baseline 1회 캡처
  python scripts/_spike_sdk.py             # SDK 호출 + 4 checks

Production 코드 0 touch. tools.llm.{_common,models}는 read-only import.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from tools.llm._common import _extract_json, load_skill, query_json  # noqa: E402
from tools.llm.models import DEFAULT_MODEL  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "spike_sdk_baseline.json"


def _build_prompts(fix: dict[str, Any]) -> tuple[str, str]:
    """tools/llm/analyze_content.py:42 와 동일 prompt 빌드."""
    inp = fix["input"]
    blocks_compact = json.dumps(inp["blocks"], ensure_ascii=False, separators=(",", ":"))
    user_prompt = (
        "다음은 Notion 페이지의 모든 block(JSON 배열)이다. "
        "본 스킬 룰에 따라 image_slots를 결정하고 JSON 객체로 반환하라.\n\n"
        f"BLOCKS:\n{blocks_compact}\n\n"
        '응답 스키마: {"image_slots": [...]}'
    )
    skill_md = "".join(f"\n\n## {p}\n" + load_skill(p) for p in inp["system_skills"])
    system_prompt = (
        "너는 이현 블로그 이미지 슬롯 결정 어시스턴트다. "
        "본문에 명시된 데이터만 추출하고 추측·의역은 절대 금지." + skill_md
    )
    return user_prompt, system_prompt


async def _capture_baseline() -> int:
    fix = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if fix.get("captured_baseline") is not None:
        ts = fix["captured_baseline"].get("captured_at")
        print(f"[skip] captured_baseline 이미 존재 (captured_at={ts}).")
        print("       재캡처하려면 fixture에서 captured_baseline을 null로 되돌리고 재실행.")
        return 0
    user, system = _build_prompts(fix)
    budget = float(fix["input"]["max_budget_usd"])
    print(f"[capture] subprocess query_json 호출 — model={DEFAULT_MODEL}, "
          f"cap=${budget:.2f}, user={len(user)} chars, system={len(system)} chars")
    parsed, cost = await query_json(user, system, max_budget_usd=budget)
    fix["captured_baseline"] = {
        "output": parsed,
        "cost_usd": cost,
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": DEFAULT_MODEL,
        "method": "subprocess (claude.exe via tools.llm._common.query_json)",
    }
    FIXTURE.write_text(json.dumps(fix, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shape = list(parsed.keys()) if isinstance(parsed, dict) else f"<{type(parsed).__name__}>"
    print(f"[capture] saved. cost=${cost:.4f}, output_shape={shape}")
    return 0


async def _sdk_query(
    user_prompt: str, system_prompt: str, *, model: str, max_budget_usd: float
) -> tuple[Any, float, dict[str, Any]]:
    """claude-agent-sdk query() 1회 호출 → (parsed_json, cost_usd, diag)."""
    from claude_agent_sdk import (  # noqa: PLC0415  (지연 import — SDK 부재 시 catch 가능)
        AssistantMessage,
        ClaudeAgentOptions,
        ResultMessage,
        TextBlock,
        query,
    )

    options = ClaudeAgentOptions(
        model=model,
        system_prompt=system_prompt + "\n\n응답은 오직 JSON 한 객체만. 설명/주석 X.",
        max_budget_usd=max_budget_usd,
        max_turns=1,           # 단발 호출, agent loop X (Week 1-2에 풀 검토)
        setting_sources=[],    # CLAUDE.md / settings.json 자동 inject 차단 (옵션 A 검증 위해)
    )
    result_text = ""
    cost = 0.0
    diag: dict[str, Any] = {"messages": []}

    async for msg in query(prompt=user_prompt, options=options):
        diag["messages"].append(type(msg).__name__)
        if isinstance(msg, ResultMessage):
            cost = float(getattr(msg, "total_cost_usd", 0.0) or 0.0)
            diag["subtype"] = msg.subtype
            diag["is_error"] = msg.is_error
            # ResultMessage.result에 최종 텍스트가 들어옴 (CLI envelope.result와 동치)
            if msg.result:
                result_text = msg.result
        elif isinstance(msg, AssistantMessage) and not result_text:
            # ResultMessage가 result를 안 채우는 경우 fallback — TextBlock 합산
            for blk in msg.content:
                if isinstance(blk, TextBlock):
                    result_text += blk.text

    return _extract_json(result_text), cost, diag


async def _run_checks() -> int:
    fix = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if fix.get("captured_baseline") is None:
        print("[error] captured_baseline 없음. 먼저 `python scripts/_spike_sdk.py --capture` 실행.",
              file=sys.stderr)
        return 2

    user, system = _build_prompts(fix)
    model = fix["input"]["model"]
    budget = float(fix["input"]["max_budget_usd"])
    preserve = fix["expected_facts"]["preserve_strings"]
    baseline_cost = float(fix["captured_baseline"]["cost_usd"])

    results: list[tuple[str, bool, str]] = []

    # check 1 — SDK 호출
    try:
        sdk_out, sdk_cost, diag = await _sdk_query(
            user, system, model=model, max_budget_usd=budget
        )
        ok1 = not diag.get("is_error")
        detail1 = f"messages={diag['messages']}, subtype={diag.get('subtype')}, is_error={diag.get('is_error')}"
        results.append(("check 1 — SDK 호출 (Sonnet 4.6)", ok1, detail1))
        if not ok1:
            return _print_results(results)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        results.append(("check 1 — SDK 호출 (Sonnet 4.6)", False, f"{type(exc).__name__}: {exc}"))
        return _print_results(results)

    # check 2 — exact_korean_strings 1자 보존
    blob = json.dumps(sdk_out, ensure_ascii=False)
    missing = [s for s in preserve if s not in blob]
    results.append(("check 2 — exact_korean_strings 1자 보존",
                    not missing,
                    "all preserved" if not missing else f"missing: {missing}"))
    if missing: print("\n[diag] SDK output (check 2 FAIL 진단용):\n" + json.dumps(sdk_out, ensure_ascii=False, indent=2))

    # check 3 — cost_usd float surfaced
    ratio = (sdk_cost / baseline_cost) if baseline_cost > 0 else float("nan")
    results.append(("check 3 — cost_usd float surfaced",
                    isinstance(sdk_cost, float) and sdk_cost > 0.0,
                    f"sdk=${sdk_cost:.4f} / baseline=${baseline_cost:.4f} (ratio={ratio:.2f}x)"))

    # check 4 — skill markdown system_prompt inject (옵션 A)
    injected = [(p, load_skill(p).strip()[:80] in system) for p in fix["input"]["system_skills"]]
    ok4 = all(ok for _, ok in injected)
    results.append(("check 4 — skill markdown system_prompt inject (옵션 A)",
                    ok4,
                    f"injected={[p for p, ok in injected if ok]}, missing={[p for p, ok in injected if not ok]}"))

    return _print_results(results)


def _print_results(results: list[tuple[str, bool, str]]) -> int:
    print()
    print("=" * 72)
    for name, ok, detail in results:
        print(f"{'[PASS]' if ok else '[FAIL]'} {name}")
        print(f"        {detail}")
    print("=" * 72)
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"summary: {'ALL PASS' if passed == total else 'FAILED'} ({passed}/{total})")
    return 0 if passed == total else 1


async def _amain() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--capture", action="store_true",
        help="subprocess(claude.exe) 경로로 baseline 캡처 (1회용)",
    )
    args = parser.parse_args()
    return await (_capture_baseline() if args.capture else _run_checks())


if __name__ == "__main__":
    sys.exit(asyncio.run(_amain()))
