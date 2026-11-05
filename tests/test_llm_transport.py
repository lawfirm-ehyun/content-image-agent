"""LLM 호출 경로 (anthropic SDK 직접 호출) 단위 테스트.

v1.8.7 에서 claude-agent-sdk(sdk transport)를 제거해 경로가 하나로 줄었다.
남은 ENV 검사는 `assert_api_transport` — 과거 롤백 수단이던 `LLM_TRANSPORT=sdk`
가 환경에 남아 있을 때 침묵하지 않고 터지는지만 본다.

api 본체(_query_json_api)는 anthropic 호출을 monkeypatch 로 대체 — budget 사후
검증 / max_tokens 잘림 / 빈 응답 semantics 만 검증. 실호출·캐싱 영수증은
scripts/_spike_api_transport.py (§12.9) 영역.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from tools.llm import _common
from tools.llm._common import _query_json_api, assert_api_transport


# === assert_api_transport (stale ENV 가드, v1.8.7) ===========================

def test_no_env_passes(monkeypatch):
    monkeypatch.delenv("LLM_TRANSPORT", raising=False)
    assert_api_transport()  # 아무것도 안 함


def test_api_value_passes(monkeypatch):
    # 명시적으로 api 라고 적어둔 환경은 그대로 통과 (의미가 일치하므로).
    monkeypatch.setenv("LLM_TRANSPORT", " API ")
    assert_api_transport()


def test_empty_passes(monkeypatch):
    monkeypatch.setenv("LLM_TRANSPORT", "")
    assert_api_transport()


def test_stale_sdk_rollback_raises(monkeypatch):
    """제거된 sdk 롤백을 시도하면 침묵하지 않고 터져야 한다 (운영자 오인 차단)."""
    monkeypatch.setenv("LLM_TRANSPORT", "sdk")
    with pytest.raises(RuntimeError, match="v1.8.7"):
        assert_api_transport()


def test_unknown_value_raises(monkeypatch):
    monkeypatch.setenv("LLM_TRANSPORT", "cli")
    with pytest.raises(RuntimeError, match="v1.8.7"):
        assert_api_transport()


# === _query_json_api semantics (anthropic 호출 mock) ==========================

def _usage(inp=100, out=50, cache_w=0, cache_r=0) -> SimpleNamespace:
    return SimpleNamespace(
        input_tokens=inp, output_tokens=out,
        cache_creation_input_tokens=cache_w, cache_read_input_tokens=cache_r,
    )


def _patch_call(monkeypatch, text: str, usage: Any, stop_reason: str | None = "end_turn"):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(
        _common, "_call_api_sync", lambda up, fs: (text, usage, stop_reason),
    )


def test_api_parses_json_and_cost(monkeypatch):
    _patch_call(monkeypatch, '{"image_slots": []}', _usage(inp=1000, out=100))
    parsed, cost = asyncio.run(
        _query_json_api("u", "s", max_budget_usd=1.0, timeout_s=10)
    )
    assert parsed == {"image_slots": []}
    # 1000×$3/M + 100×$15/M = $0.0045
    assert cost == pytest.approx(0.003)


def test_api_budget_exceeded_raises(monkeypatch):
    # output 1M tokens → $10 > budget $0.30
    _patch_call(monkeypatch, '{"ok": true}', _usage(out=1_000_000))
    with pytest.raises(RuntimeError, match="budget"):
        asyncio.run(_query_json_api("u", "s", max_budget_usd=0.30, timeout_s=10))


def test_api_max_tokens_truncation_raises(monkeypatch):
    _patch_call(monkeypatch, '{"truncat', _usage(), stop_reason="max_tokens")
    with pytest.raises(RuntimeError, match="max_tokens"):
        asyncio.run(_query_json_api("u", "s", max_budget_usd=1.0, timeout_s=10))


def test_api_empty_response_raises(monkeypatch):
    _patch_call(monkeypatch, "   ", _usage())
    with pytest.raises(RuntimeError, match="빈 응답"):
        asyncio.run(_query_json_api("u", "s", max_budget_usd=1.0, timeout_s=10))


def test_api_missing_key_fails_fast(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        asyncio.run(_query_json_api("u", "s", max_budget_usd=1.0, timeout_s=10))


def test_cache_read_cost_rate(monkeypatch):
    # cache_read 47K tokens → 47000×$0.20/M = $0.0094 (스킬 캐시 hit 시나리오)
    _patch_call(monkeypatch, '{"ok": true}', _usage(inp=0, out=0, cache_r=47_000))
    _, cost = asyncio.run(_query_json_api("u", "s", max_budget_usd=1.0, timeout_s=10))
    assert cost == pytest.approx(0.0094)
