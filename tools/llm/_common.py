"""LLM 호출 공통 유틸. claude-agent-sdk query() 직접 호출.

설계 결정 (§12 Week 1-2, plan v1.7.3+):
  - Week 0 spike (b7fe789, scripts/_spike_sdk.py)에서 SDK 0.1.77 + Sonnet 4.6
    + max_turns=1 + setting_sources=[] 가드 하 functional equivalence 확인
    (N=4 cost 0.34-0.64x cheaper, byte-identical simple_table output).
  - 이전 SDK 우회 동기 (default Claude Code agent system prompt 추가 inject,
    max_turns 무시 등으로 토큰 비용 3배+)는 위 가드로 해소.
  - agent loop / hooks / subagents 풀 도입 X (plan §12.6 "처음부터 다 빼지
    말기"). 단발 query() 1회만. 필요해지면 별도 path.

Skills 자동 로드는 사용 안 함. skills/*.md 본문을 system_prompt에 직접 inject (옵션 A).
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

from tools.limits import (
    MAX_USER_PROMPT_CHARS,
    QUERY_JSON_DEFAULT_BUDGET_USD,
    QUERY_JSON_TIMEOUT_S,
)
from tools.llm.models import DEFAULT_MODEL

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"

JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)


def compact_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Notion blocks → LLM이 필요한 최소 정보(id/type/text)만 추출.

    raw blocks는 timestamps/has_children/color 같은 메타 잔뜩 → 일반 페이지 80KB+.
    text 추출 후 5~15KB로 줄어 prompt 한계 안에 들어옴.

    데이터 정확성(절대 룰 #1) — 모든 본문 구조에서 text를 빠짐없이 추출해야 함.
    추출 분기:
      - rich_text 기반 (paragraph/heading/list/quote/callout/toggle/code 등)
      - **table_row.cells** (cells: list[list[rich_text]]) — "셀1 | 셀2 | ..." 형태
      - **table 블록** — v1.3: 마커 1줄로 표시 ("[표 시작: N열, 헤더행 포함]").
        slot_selection이 "본문에 이미 표 있는 영역"을 인지하고 형식 전환 판단하기 위함.
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
        elif bt == "table":
            # v1.3 — LLM에게 본문 표 존재를 알린다. 직후 따라오는 table_row들이 표 데이터.
            width = body.get("table_width") or 0
            has_header = body.get("has_column_header") or False
            text = f"[표 시작: {width}열" + (", 헤더행 포함" if has_header else "") + "]"
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
    max_budget_usd: float = QUERY_JSON_DEFAULT_BUDGET_USD,
    timeout_s: int = QUERY_JSON_TIMEOUT_S,
) -> tuple[Any, float]:
    """claude-agent-sdk query()로 prompt 보내고 JSON 응답 + 비용을 (parsed, cost_usd) 튜플로 반환.

    내부 구현: claude_agent_sdk.query() 1회 호출 (max_turns=1, setting_sources=[]).
    ResultMessage.result에서 응답 텍스트, ResultMessage.total_cost_usd에서 비용 추출.
    ResultMessage.result가 비면 AssistantMessage.content의 TextBlock 합산으로 fallback.

    응답 텍스트가 markdown fence(```json ...```)에 싸여있어도 추출 (_extract_json).
    """
    if len(user_prompt) > MAX_USER_PROMPT_CHARS:
        raise RuntimeError(
            f"user_prompt {len(user_prompt):,} chars > {MAX_USER_PROMPT_CHARS} 한계. "
            "호출 측에서 압축 또는 청크 분할 필요."
        )

    full_system = system_prompt + "\n\n응답은 오직 JSON 한 객체만. 설명/주석 X."

    options = ClaudeAgentOptions(
        model=DEFAULT_MODEL,
        system_prompt=full_system,
        max_budget_usd=max_budget_usd,
        max_turns=1,           # 단발 호출, agent loop X (plan §12.6)
        setting_sources=[],    # CLAUDE.md / settings.json 자동 inject 차단 (옵션 A)
    )

    result_text = ""
    cost = 0.0
    subtype: str | None = None
    is_error = False

    try:
        async with asyncio.timeout(timeout_s):
            async for msg in query(prompt=user_prompt, options=options):
                if isinstance(msg, ResultMessage):
                    cost = float(getattr(msg, "total_cost_usd", 0.0) or 0.0)
                    subtype = msg.subtype
                    is_error = bool(msg.is_error)
                    if msg.result:
                        result_text = msg.result
                elif isinstance(msg, AssistantMessage) and not result_text:
                    # ResultMessage.result가 비는 경우 fallback — TextBlock 합산
                    for blk in msg.content:
                        if isinstance(blk, TextBlock):
                            result_text += blk.text
    except asyncio.TimeoutError as e:
        raise RuntimeError(f"SDK query() timeout {timeout_s}s") from e

    if is_error:
        raise RuntimeError(
            f"SDK query() error: subtype={subtype}, "
            f"result={result_text.strip()[:800]!r}"
        )
    if not result_text:
        raise RuntimeError(f"SDK query() 빈 응답: subtype={subtype}")

    return _extract_json(result_text.strip()), cost


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
