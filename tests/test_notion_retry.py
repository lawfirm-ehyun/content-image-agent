"""tools.notion._retry.notion_call 동작 테스트 (plan §19.3, §20.1).

mock client로 retry 시나리오 검증 — 실제 Notion API 호출 X.
"""
from __future__ import annotations

import httpx
import pytest
from notion_client.errors import (
    APIErrorCode,
    APIResponseError,
    HTTPResponseError,
    RequestTimeoutError,
)

from tools.notion._retry import _is_retryable, notion_call


def _make_api_error(code: APIErrorCode, status: int) -> APIResponseError:
    err = APIResponseError(
        response=httpx.Response(status, request=httpx.Request("GET", "https://api.notion.com")),
        body={"code": code.value, "message": "test"},
        code=code,
    )
    # APIResponseError가 SDK 버전마다 시그니처 차이가 있을 수 있어 폴백.
    return err


def _make_http_error(status: int) -> HTTPResponseError:
    return HTTPResponseError(
        code="server_error",
        status=status,
        message="test",
        headers=httpx.Headers(),
        raw_body_text="",
    )


# --- _is_retryable 단위 ---

def test_is_retryable_request_timeout():
    assert _is_retryable(RequestTimeoutError("timeout"))


def test_is_retryable_rate_limited():
    err = _make_http_error(429)
    err.code = APIErrorCode.RateLimited  # APIResponseError 시그니처 폴백 시 직접 세팅
    # HTTPResponseError 자체로도 429면 retry
    assert _is_retryable(err)


def test_is_retryable_internal_server_error():
    assert _is_retryable(_make_http_error(500))


def test_is_retryable_service_unavailable():
    assert _is_retryable(_make_http_error(503))


def test_is_retryable_unauthorized_not_retry():
    assert not _is_retryable(_make_http_error(401))


def test_is_retryable_not_found_not_retry():
    assert not _is_retryable(_make_http_error(404))


def test_is_retryable_validation_error_not_retry():
    assert not _is_retryable(_make_http_error(400))


def test_is_retryable_unrelated_exception():
    assert not _is_retryable(ValueError("unrelated"))


def test_is_retryable_httpx_status_error():
    resp = httpx.Response(503, request=httpx.Request("GET", "https://api.notion.com"))
    err = httpx.HTTPStatusError("503", request=resp.request, response=resp)
    assert _is_retryable(err)


# --- notion_call 통합 ---

async def test_notion_call_success_first_try():
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        return {"ok": True}

    result = await notion_call(fn)
    assert result == {"ok": True}
    assert calls["n"] == 1


async def test_notion_call_retries_on_503_then_succeeds():
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] < 2:
            raise _make_http_error(503)
        return {"ok": True}

    result = await notion_call(fn)
    assert result == {"ok": True}
    assert calls["n"] == 2


async def test_notion_call_no_retry_on_404():
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise _make_http_error(404)

    with pytest.raises(HTTPResponseError):
        await notion_call(fn)
    assert calls["n"] == 1  # 첫 호출만, retry 안 함


async def test_notion_call_gives_up_after_max_attempts():
    """5회 모두 5xx면 reraise — tenacity reraise=True 동작 확인."""
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise _make_http_error(500)

    with pytest.raises(HTTPResponseError):
        await notion_call(fn)
    # NOTION_RETRY_MAX_ATTEMPTS = 5
    assert calls["n"] == 5
