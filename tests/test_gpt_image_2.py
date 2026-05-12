"""gpt_image_2 wrapper 단위 테스트 — 실제 OpenAI 호출 없이 mock으로 검증.

v1.6.1 신설 (plan §12 P3.2). 실호출 smoke는 scripts/_smoke_gpt_image.py에 분리.
"""
from __future__ import annotations

import base64
from unittest.mock import AsyncMock, patch

import pytest
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)

from tools.image.gpt_image_2 import (
    _resolve_model_id,
    _sanitize_error,
    estimate_cost,
    generate_instant,
    generate_thinking,
)
from tools.limits import GPT_IMAGE_DEFAULT_MODEL


# ============================================================================
# 단가 추정
# ============================================================================


def test_estimate_cost_known_combo():
    assert estimate_cost("1024x1024", "medium") == pytest.approx(0.042)
    assert estimate_cost("1024x1024", "high") == pytest.approx(0.167)
    assert estimate_cost("1024x1536", "high") == pytest.approx(0.25)


def test_estimate_cost_unknown_returns_zero():
    # 잘못된 조합은 0.0 + warning (raise X — 호출은 계속됨)
    assert estimate_cost("9999x9999", "medium") == 0.0  # type: ignore[arg-type]


# ============================================================================
# 모델 ID resolve
# ============================================================================


def test_resolve_model_id_default(monkeypatch):
    monkeypatch.delenv("OPENAI_IMAGE_MODEL_INSTANT", raising=False)
    monkeypatch.delenv("OPENAI_IMAGE_MODEL_THINKING", raising=False)
    assert _resolve_model_id("medium") == GPT_IMAGE_DEFAULT_MODEL
    assert _resolve_model_id("high") == GPT_IMAGE_DEFAULT_MODEL


def test_resolve_model_id_env_override(monkeypatch):
    monkeypatch.setenv("OPENAI_IMAGE_MODEL_INSTANT", "gpt-image-X-instant")
    monkeypatch.setenv("OPENAI_IMAGE_MODEL_THINKING", "gpt-image-X-thinking")
    assert _resolve_model_id("low") == "gpt-image-X-instant"
    assert _resolve_model_id("medium") == "gpt-image-X-instant"
    assert _resolve_model_id("high") == "gpt-image-X-thinking"


def test_resolve_model_id_blank_env_falls_back(monkeypatch):
    monkeypatch.setenv("OPENAI_IMAGE_MODEL_THINKING", "   ")  # whitespace
    assert _resolve_model_id("high") == GPT_IMAGE_DEFAULT_MODEL


# ============================================================================
# 에러 sanitize (§19.15)
# ============================================================================


def test_sanitize_auth_error():
    # AuthenticationError는 OpenAI SDK가 response 인자를 요구 — 인스턴스화 우회.
    exc = AuthenticationError.__new__(AuthenticationError)
    assert "auth failure" in _sanitize_error(exc)


def test_sanitize_rate_limit():
    exc = RateLimitError.__new__(RateLimitError)
    assert "rate limit" in _sanitize_error(exc).lower()


def test_sanitize_timeout():
    exc = APITimeoutError.__new__(APITimeoutError)
    assert "timeout" in _sanitize_error(exc).lower()


def test_sanitize_connection_error():
    exc = APIConnectionError.__new__(APIConnectionError)
    assert "connection" in _sanitize_error(exc).lower()


def test_sanitize_does_not_leak_raw_text():
    """원본 메시지에 'API key sk-xxx' 같은 민감 정보 누설 안 됨 검증."""
    exc = AuthenticationError.__new__(AuthenticationError)
    msg = _sanitize_error(exc)
    assert "sk-" not in msg
    assert "Bearer" not in msg


# ============================================================================
# generate_instant / generate_thinking — mock으로 OpenAI 호출 검증
# ============================================================================


def _make_mock_response(b64_png: str, revised_prompt: str | None = None):
    """OpenAI SDK 응답 형태를 흉내내는 mock object."""
    data_item = AsyncMock()
    data_item.b64_json = b64_png
    data_item.revised_prompt = revised_prompt
    resp = AsyncMock()
    resp.data = [data_item]
    return resp


@pytest.mark.asyncio
async def test_generate_instant_returns_result(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-stub")
    # 1×1 투명 PNG (가장 작은 유효 PNG)
    tiny_png = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000d49444154789c63000100000005000100"
        "0d0a2db40000000049454e44ae426082"
    )
    b64 = base64.b64encode(tiny_png).decode()

    fake_client = AsyncMock()
    fake_client.images.generate = AsyncMock(return_value=_make_mock_response(b64))

    with patch("tools.image.gpt_image_2.get_client", return_value=fake_client):
        result = await generate_instant("a test prompt", size="1024x1024", quality="medium")

    assert result.png_bytes == tiny_png
    assert result.cost_usd == pytest.approx(0.042)
    assert result.size == "1024x1024"
    assert result.quality == "medium"
    assert result.model_id == GPT_IMAGE_DEFAULT_MODEL

    fake_client.images.generate.assert_called_once()
    call_kwargs = fake_client.images.generate.call_args.kwargs
    assert call_kwargs["prompt"] == "a test prompt"
    assert call_kwargs["size"] == "1024x1024"
    assert call_kwargs["quality"] == "medium"


@pytest.mark.asyncio
async def test_generate_thinking_uses_high_quality(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-stub")
    b64 = base64.b64encode(b"fake_png_bytes").decode()
    fake_client = AsyncMock()
    fake_client.images.generate = AsyncMock(return_value=_make_mock_response(b64))

    with patch("tools.image.gpt_image_2.get_client", return_value=fake_client):
        result = await generate_thinking("thinking prompt", size="1024x1536", quality="high")

    assert result.cost_usd == pytest.approx(0.25)
    assert result.quality == "high"
    call_kwargs = fake_client.images.generate.call_args.kwargs
    assert call_kwargs["quality"] == "high"
    assert call_kwargs["size"] == "1024x1536"


@pytest.mark.asyncio
async def test_generate_raises_when_no_b64(monkeypatch):
    """OpenAI 응답에 b64_json 없으면 RuntimeError로 변환."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-stub")
    fake_client = AsyncMock()
    fake_client.images.generate = AsyncMock(return_value=_make_mock_response(None))  # type: ignore[arg-type]

    with patch("tools.image.gpt_image_2.get_client", return_value=fake_client):
        with pytest.raises(RuntimeError):
            await generate_instant("prompt")


@pytest.mark.asyncio
async def test_no_api_key_raises(monkeypatch):
    """OPENAI_API_KEY 없으면 fail-fast (§19.15)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    # 싱글톤 reset
    import tools.image.gpt_image_2 as mod
    mod._client = None
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        await generate_instant("prompt")
