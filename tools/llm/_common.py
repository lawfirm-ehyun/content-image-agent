"""LLM 호출 공통 유틸 — anthropic SDK 직접 호출 단일 경로 (v1.8.7).

anthropic SDK `messages.stream()` 직접 호출 — vision_review.py 와 같은 path.
전달 한계 없음 = 긴 글 무손실. prompt caching 은 system block cache_control 로
명시 (§12.9 spike 영수증: 2회차 cache_read $0.045 → $0.004).

v1.8.7 이전엔 claude-agent-sdk(claude.exe subprocess) 경로를 `LLM_TRANSPORT=sdk`
롤백용으로 병행했으나 제거했다. 사유: (a) v1.8.3 이후 한 번도 실행된 적 없는
미검증 경로라 비상시 처음 밟게 되고, (b) 애초에 긴 글이 잘리는 결함(전달 통로
~20KB)이 그 경로를 버린 이유라 비상구로 기능하지 못하며, (c) 같은 벤더 같은 API
를 두드리므로 장애 이중화도 아니고, (d) claude-agent-sdk → mcp → PyJWT →
cryptography 체인이 Dependabot 경보 23건을 끌고 왔다. 복구는 git 이력에서.

Skills 자동 로드는 사용 안 함. skills/*.md 본문을 system_prompt에 직접 inject (옵션 A).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Final

from tools.limits import (
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

# Sonnet 5.5 pricing (USD/M tokens) — vision_review.py `_SONNET_55_RATE` 와 동일 값.
# (vision 은 §12 결정과 직교한 별 path 라 상수 공유 대신 각자 정의 — 값 변경 시 둘 다 동기.)
_SONNET_55_RATE: Final[dict[str, float]] = {
    "input": 2.0,
    "output": 10.0,
    "cache_creation": 2.50,
    "cache_read": 0.20,
}

_JSON_ONLY_SUFFIX: Final[str] = "\n\n응답은 오직 JSON 한 객체만. 설명/주석 X."


def assert_api_transport() -> None:
    """ENV `LLM_TRANSPORT` 가 환경에 남아 있으면 즉시 실패시킨다 (v1.8.7).

    sdk transport 제거 후, 과거 롤백 수단이던 `LLM_TRANSPORT=sdk` 가 남아 있으면
    "롤백했는데 아무 일도 안 일어나는" 침묵 실패가 된다. 조용히 무시하지 않고
    명시적으로 터뜨려 운영자가 알아차리게 한다.
    """
    val = os.environ.get(LLM_TRANSPORT_ENV, "").strip().lower()
    if val and val != "api":
        raise RuntimeError(
            f"{LLM_TRANSPORT_ENV}={val!r} 는 v1.8.7 에서 제거됐다 "
            "(claude-agent-sdk 의존성 삭제 — api 가 유일한 transport). 이 ENV 를 지울 것."
        )


def _cost_from_usage(usage: Any) -> float:
    """anthropic.Usage → cost_usd 환산 (Sonnet 5.5 rate)."""
    inp = getattr(usage, "input_tokens", 0) or 0
    out = getattr(usage, "output_tokens", 0) or 0
    cache_w = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cache_r = getattr(usage, "cache_read_input_tokens", 0) or 0
    return (
        inp * _SONNET_55_RATE["input"]
        + out * _SONNET_55_RATE["output"]
        + cache_w * _SONNET_55_RATE["cache_creation"]
        + cache_r * _SONNET_55_RATE["cache_read"]
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
        # Sonnet 5.5 는 thinking default ON(adaptive) + effort default high — 4.6(thinking 없음)
        # 대비 output 토큰이 늘어 §6 budget(analyze $0.80 / review $0.30) 압박. 사실 추출
        # 과제라 medium 이면 충분, 품질 미달 관측 시 high 로 상향 (v1.8.6).
        output_config={"effort": "medium"},
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

    anthropic SDK 직접 호출 + prompt caching (v1.8.7 transport 단일). 전달 한계 없음.

    응답 텍스트가 markdown fence(```json ...```)에 싸여있어도 추출 (_extract_json).
    """
    assert_api_transport()
    full_system = system_prompt + _JSON_ONLY_SUFFIX
    return await _query_json_api(
        user_prompt, full_system,
        max_budget_usd=max_budget_usd, timeout_s=timeout_s,
    )


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
