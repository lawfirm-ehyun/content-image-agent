"""LLM 호출 공통 유틸. claude-agent-sdk의 bundled CLI를 직접 invoke (subprocess.run).

설계 결정 (Phase 1):
  - claude-agent-sdk 0.1.x 라인이 우리 use case (단순 1회 LLM 호출)에 비효율 — default
    Claude Code agent system prompt 추가 inject + max_turns 무시 등으로 토큰 비용 3배+.
  - 같은 prompt를 CLI 직접(`claude.exe -p ... --system-prompt ...`)으로 부르면 정상 응답.
  - → SDK 우회. 단 bundled CLI는 그대로 사용하므로 의존성/인증 path는 SDK와 동일.
  - Phase 2/3에 hooks·subagents 필요해지면 SDK 부분 재도입 검토.

Skills 자동 로드는 사용 안 함. skills/*.md 본문을 system_prompt에 직접 inject (옵션 A).
"""
from __future__ import annotations

import asyncio
import json
import re
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"
CLAUDE_EXE = ROOT / ".venv" / "Lib" / "site-packages" / "claude_agent_sdk" / "_bundled" / "claude.exe"

DEFAULT_MODEL = "claude-sonnet-4-6"
JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)

# CLI subprocess의 user prompt argv 길이 한계 — Windows ~32K 한계 + 안전마진.
MAX_USER_PROMPT_CHARS = 20_000


def compact_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Notion blocks → LLM이 필요한 최소 정보(id/type/text)만 추출.

    raw blocks는 timestamps/has_children/color 같은 메타 잔뜩 → 일반 페이지 80KB+.
    text 추출 후 5~15KB로 줄어 prompt 한계 안에 들어옴.

    데이터 정확성(절대 룰 #1) — 모든 본문 구조에서 text를 빠짐없이 추출해야 함.
    추출 분기:
      - rich_text 기반 (paragraph/heading/list/quote/callout/toggle/code 등)
      - **table_row.cells** (cells: list[list[rich_text]]) — "셀1 | 셀2 | ..." 형태
    table 블록 자체는 빈 컨테이너라 무시 (자식 table_row가 처리).
    """
    out: list[dict[str, Any]] = []
    for b in blocks:
        bt = b.get("type")
        if not bt:
            continue
        body = b.get(bt, {}) or {}

        if bt == "table_row":
            cells = body.get("cells") or []
            text = " | ".join(
                "".join(item.get("plain_text", "") for item in cell)
                for cell in cells
            )
        else:
            rt = body.get("rich_text") or []
            text = "".join(item.get("plain_text", "") for item in rt)

        if text.strip():
            out.append({"id": b.get("id"), "type": bt, "text": text})
    return out


def load_skill(rel_path: str) -> str:
    """skills/{rel_path} 본문 읽기. 예: 'meta/slot_selection.md'."""
    return (SKILLS / rel_path).read_text(encoding="utf-8")


async def query_json(
    user_prompt: str,
    system_prompt: str,
    *,
    max_budget_usd: float = 0.30,
    timeout_s: int = 360,    # 큰 본문 + 다중 슬롯 JSON 응답에 LLM 1~3분 소요. 여유 두고 6분.
) -> tuple[Any, float]:
    """Claude CLI에 prompt 보내고 JSON 응답 + 비용을 (parsed, cost_usd) 튜플로 반환.

    내부 구현: claude.exe -p (print mode) + --output-format json.
    JSON 모드 응답은 {"result": "...", "total_cost_usd": ..., ...} 형태.

    응답 텍스트가 markdown fence(```json ...```)에 싸여있어도 추출.
    """
    if len(user_prompt) > MAX_USER_PROMPT_CHARS:
        raise RuntimeError(
            f"user_prompt {len(user_prompt):,} chars > {MAX_USER_PROMPT_CHARS} 한계. "
            "호출 측에서 압축 또는 청크 분할 필요."
        )
    if not CLAUDE_EXE.exists():
        raise RuntimeError(f"bundled Claude CLI 없음: {CLAUDE_EXE}")

    full_system = system_prompt + "\n\n응답은 오직 JSON 한 객체만. 설명/주석 X."

    cmd = [
        str(CLAUDE_EXE),
        "-p",
        "--model", DEFAULT_MODEL,
        "--output-format", "json",
        "--max-budget-usd", f"{max_budget_usd}",
        "--system-prompt", full_system,
        user_prompt,
    ]

    proc = await asyncio.to_thread(
        subprocess.run, cmd,
        capture_output=True, text=True, encoding="utf-8", timeout=timeout_s,
    )

    if proc.returncode != 0:
        # stderr뿐 아니라 stdout도 진단에 포함 — 새 CLI 버전이 에러 정보를 어디 출력할지 모름
        raise RuntimeError(
            f"claude CLI exit {proc.returncode}\n"
            f"stderr: {proc.stderr.strip()[:800]!r}\n"
            f"stdout: {proc.stdout.strip()[:800]!r}"
        )

    # --output-format json: { "result": "...", "total_cost_usd": ..., ... }
    try:
        envelope = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"CLI 응답 envelope JSON 파싱 실패: {e}\n{proc.stdout[:500]}") from e

    result_text = (envelope.get("result") or "").strip()
    cost = float(envelope.get("total_cost_usd") or 0.0)
    return _extract_json(result_text), cost


def _extract_json(text: str) -> Any:
    # 1) markdown fence 안 우선
    m = JSON_FENCE_RE.search(text)
    if m:
        return json.loads(m.group(1))
    # 2) 첫 { 또는 [ 부터 마지막 } 또는 ]까지
    for opener, closer in (("{", "}"), ("[", "]")):
        i = text.find(opener)
        j = text.rfind(closer)
        if i != -1 and j != -1 and j > i:
            try:
                return json.loads(text[i : j + 1])
            except json.JSONDecodeError:
                continue
    # 3) 그대로 시도
    return json.loads(text)
