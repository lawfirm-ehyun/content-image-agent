"""LLM transport 스위치 (v1.8.3, ENV LLM_TRANSPORT) 단위 테스트.

api transport 본체(_query_json_api)는 anthropic 호출을 monkeypatch 로 대체 —
budget 사후 검증 / max_tokens 잘림 / 빈 응답 semantics 만 검증. 실호출·캐싱
영수증은 scripts/_spike_api_transport.py (§12.9) 영역.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from tools.llm import _common
from tools.llm._common import _query_json_api, llm_transport


# === llm_transport (ENV 파싱) =================================================

def test_default_is_api(monkeypatch):
    # v1.8.3 — §12.9 spike 통과로 default=api 전환 (롤백은 LLM_TRANSPORT=sdk)
    monkeypatch.delenv("LLM_TRANSPORT", raising=False)
    assert llm_transport() == "api"


def test_sdk_rollback_selected(monkeypatch):
    monkeypatch.setenv("LLM_TRANSPORT", "sdk")
    assert llm_transport() == "sdk"
    monkeypatch.setenv("LLM_TRANSPORT", " SDK ")  # 공백/대문자 관용
    assert llm_transport() == "sdk"


def test_empty_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("LLM_TRANSPORT", "")
    assert llm_transport() == "api"


def test_invalid_raises(monkeypatch):
    monkeypatch.setenv("LLM_TRANSPORT", "cli")
    with pytest.raises(RuntimeError, match="미지원"):
        llm_transport()


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
    assert cost == pytest.approx(0.0045)


def test_api_budget_exceeded_raises(monkeypatch):
    # output 1M tokens → $15 > budget $0.30
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
    # cache_read 47K tokens → 47000×$0.30/M = $0.0141 (스킬 캐시 hit 시나리오)
    _patch_call(monkeypatch, '{"ok": true}', _usage(inp=0, out=0, cache_r=47_000))
    _, cost = asyncio.run(_query_json_api("u", "s", max_budget_usd=1.0, timeout_s=10))
    assert cost == pytest.approx(0.0141)
