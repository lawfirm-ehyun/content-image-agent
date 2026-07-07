"""LLM 호출 공통 유틸 — transport 이중화 (v1.8.3).

transport 선택 (ENV `LLM_TRANSPORT`):
  - "sdk": claude-agent-sdk query() — claude.exe subprocess wrapper.
    §12 Week 1-2 spike (b7fe789) 로 채택된 기존 경로. **전달 통로 한계**
    (Windows argv/stdin ~20KB) 때문에 긴 본문은 §19.8 압축으로 잘림.
  - "api": anthropic SDK messages.create() 직접 호출 — vision_review.py 와
    같은 path. 전달 한계 없음 = 긴 글 무손실. prompt caching 은 system block
    cache_control 로 명시 (sdk 는 자동이었음 — 놓치면 스킬 47K+ 토큰 매 호출
    재과금이므로 §12.9 spike 로 영수증 검증 후 전환).

sdk path 설계 결정 (§12 Week 1-2, plan v1.7.3+):
  - max_turns=1 + setting_sources=[] 가드 하 functional equivalence 확인
    (N=4 cost 0.34-0.64x cheaper, byte-identical simple_table output).
  - agent loop / hooks / subagents 풀 도입 X (plan §12.6). 단발 query() 1회만.

Skills 자동 로드는 사용 안 함. skills/*.md 본문을 system_prompt에 직접 inject (옵션 A).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Final, Literal

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

from tools.limits import (
    MAX_USER_PROMPT_CHARS,
    QUERY_JSON_API_MAX_TOKENS,
    QUERY_JSON_DEFAULT_BUDGET_USD,
    QUERY_JSON_TIMEOUT_S,
)
from tools.llm.models import DEFAULT_MODEL

logger = logging.getLogger(__name__)

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


# === transport 선택 (v1.8.3) =================================================

LLM_TRANSPORT_ENV: Final[str] = "LLM_TRANSPORT"
_VALID_TRANSPORTS: Final[frozenset[str]] = frozenset({"sdk", "api"})

# Sonnet 4.6 pricing (USD/M tokens) — vision_review.py `_SONNET_46_RATE` 와 동일 값.
# (vision 은 §12 결정과 직교한 별 path 라 상수 공유 대신 각자 정의 — 값 변경 시 둘 다 동기.)
_SONNET_46_RATE: Final[dict[str, float]] = {
    "input": 3.0,
    "output": 15.0,
    "cache_creation": 3.75,
    "cache_read": 0.30,
}

_JSON_ONLY_SUFFIX: Final[str] = "\n\n응답은 오직 JSON 한 객체만. 설명/주석 X."


def llm_transport() -> Literal["sdk", "api"]:
    """ENV `LLM_TRANSPORT` 로 전송 경로 결정. default "api" (v1.8.3, 2026-07-06).

    §12.9 spike 통과로 default 전환: smoke 캐싱 영수증 OK (2회차 cache_read 11,832
    tokens, $0.045→$0.004) + 252블록 페이지 compare 슬롯 동등 · 비용 0.23x.
    운영 롤백: ENV `LLM_TRANSPORT=sdk` (코드 변경 불필요).
    """
    val = os.environ.get(LLM_TRANSPORT_ENV, "api").strip().lower() or "api"
    if val not in _VALID_TRANSPORTS:
        raise RuntimeError(
            f"{LLM_TRANSPORT_ENV}={val!r} 미지원 (허용: {sorted(_VALID_TRANSPORTS)})"
        )
    return val  # type: ignore[return-value]


def _cost_from_usage(usage: Any) -> float:
    """anthropic.Usage → cost_usd 환산 (Sonnet 4.6 rate)."""
    inp = getattr(usage, "input_tokens", 0) or 0
    out = getattr(usage, "output_tokens", 0) or 0
    cache_w = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cache_r = getattr(usage, "cache_read_input_tokens", 0) or 0
    return (
        inp * _SONNET_46_RATE["input"]
        + out * _SONNET_46_RATE["output"]
        + cache_w * _SONNET_46_RATE["cache_creation"]
        + cache_r * _SONNET_46_RATE["cache_read"]
    ) / 1_000_000


def _call_api_sync(user_prompt: str, full_system: str) -> tuple[str, Any, str | None]:
    """anthropic SDK sync 호출. (result_text, usage, stop_reason) 반환.

    prompt caching: system 전체(스킬 markdown 47K+ 토큰)를 cache block 1개로 표시.
    같은 call site(analyze / review×카드타입)끼리 cache 공유 — TTL 5분, 페이지/슬롯
    연쇄 처리 패턴에서 2회차부터 cache_read 로 ~10x 절감. 영수증 검증은 §12.9 spike.
    """
    from anthropic import Anthropic  # lazy import — sdk transport 만 쓰는 환경 고려

    client = Anthropic()
    # max_tokens 32K 는 SDK 가 "10분 초과 가능 작업 = streaming 필수" 로 강제 →
    # stream 으로 받고 최종 메시지만 취함 (동작 동일, timeout 은 호출자 asyncio.timeout).
    with client.messages.stream(
        model=DEFAULT_MODEL,
        max_tokens=QUERY_JSON_API_MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": full_system,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_prompt}],
    ) as stream:
        resp = stream.get_final_message()
    result_text = ""
    for block in resp.content:
        text = getattr(block, "text", None)
        if text:
            result_text += text
    return result_text, resp.usage, resp.stop_reason


async def _query_json_api(
    user_prompt: str,
    full_system: str,
    *,
    max_budget_usd: float,
    timeout_s: int,
) -> tuple[Any, float]:
    """api transport 본체. (parsed, cost_usd) 반환.

    budget 은 사후 검증 — sdk 와 달리 중단이 불가하므로 단일 호출 초과분은 지출됨.
    초과 시 RuntimeError raise 로 sdk 의 error_max_budget_usd 와 같은 폐기 semantics 유지.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("query_json(api): ANTHROPIC_API_KEY 미설정. .env 확인.")

    async with asyncio.timeout(timeout_s):
        result_text, usage, stop_reason = await asyncio.to_thread(
            _call_api_sync, user_prompt, full_system,
        )

    cost = _cost_from_usage(usage)
    logger.info(
        "query_json(api): cost=$%.4f in=%s out=%s cache_w=%s cache_r=%s stop=%s",
        cost,
        getattr(usage, "input_tokens", "?"), getattr(usage, "output_tokens", "?"),
        getattr(usage, "cache_creation_input_tokens", "?"),
        getattr(usage, "cache_read_input_tokens", "?"),
        stop_reason,
    )

    if stop_reason == "max_tokens":
        raise RuntimeError(
            f"query_json(api): 응답이 max_tokens({QUERY_JSON_API_MAX_TOKENS})에서 잘림 — "
            "JSON 불완전. 슬롯/페이지 폐기 대상."
        )
    if not result_text.strip():
        raise RuntimeError(f"query_json(api): 빈 응답 (stop_reason={stop_reason!r})")
    if cost > max_budget_usd:
        raise RuntimeError(
            f"query_json(api): cost ${cost:.4f} > budget ${max_budget_usd:.2f} "
            "(사후 검증 — 단일 호출 초과분은 지출됨)"
        )

    return _extract_json(result_text.strip()), cost


async def query_json(
    user_prompt: str,
    system_prompt: str,
    *,
    max_budget_usd: float = QUERY_JSON_DEFAULT_BUDGET_USD,
    timeout_s: int = QUERY_JSON_TIMEOUT_S,
) -> tuple[Any, float]:
    """prompt 를 LLM 에 보내고 JSON 응답 + 비용을 (parsed, cost_usd) 튜플로 반환.

    transport (ENV `LLM_TRANSPORT`, v1.8.3):
      - "sdk" (default): claude_agent_sdk.query() 1회 (max_turns=1, setting_sources=[]).
        user_prompt 20K 한계 (전달 통로 제약) — 호출 측 압축 필요.
      - "api": anthropic SDK 직접 호출 + prompt caching. 전달 한계 없음.

    응답 텍스트가 markdown fence(```json ...```)에 싸여있어도 추출 (_extract_json).
    """
    full_system = system_prompt + _JSON_ONLY_SUFFIX

    if llm_transport() == "api":
        return await _query_json_api(
            user_prompt, full_system,
            max_budget_usd=max_budget_usd, timeout_s=timeout_s,
        )

    # === sdk transport (기존 경로) — 전달 통로 20K 한계 ===
    if len(user_prompt) > MAX_USER_PROMPT_CHARS:
        raise RuntimeError(
            f"user_prompt {len(user_prompt):,} chars > {MAX_USER_PROMPT_CHARS} 한계. "
            "호출 측에서 압축 또는 청크 분할 필요."
        )

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
