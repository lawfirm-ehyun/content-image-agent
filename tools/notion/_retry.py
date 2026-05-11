"""Notion SDK 호출 retry wrapper (plan §19.3, §20.1).

notion-client 3.x는 자체 backoff가 없음 — Phase 2 cron 진입 시 페이지당 6~20 호출이
짧은 윈도우에 쏠리면 429/5xx 발생. tenacity AsyncRetrying으로 지수 백오프 재시도.

호출 패턴 (호출자 책임):
    result = await notion_call(client.pages.retrieve, page_id=pid)

retry 대상:
  - RateLimited (429)
  - InternalServerError / ServiceUnavailable (5xx)
  - RequestTimeoutError (httpx 타임아웃)
  - httpx.HTTPStatusError 429/500/502/503/504 (multi-source 우회 path fallback)

retry 제외 (즉시 raise):
  - Unauthorized / ObjectNotFound / ValidationError / InvalidRequest 등 4xx
  - file_uploads.send (multipart 부분 재업로드 안전 X — 호출자가 notion_call 우회)
  - blocks.children.append (idempotent X — 1회 실패 시 슬롯 폐기 안전)
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

import httpx
from notion_client.errors import (
    APIErrorCode,
    APIResponseError,
    HTTPResponseError,
    RequestTimeoutError,
)
from tenacity import (
    AsyncRetrying,
    before_sleep_log,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from tools.limits import NOTION_RETRY_MAX_ATTEMPTS, NOTION_RETRY_MAX_WAIT_S

logger = logging.getLogger(__name__)

_RETRYABLE_API_CODES = {
    APIErrorCode.RateLimited,
    APIErrorCode.InternalServerError,
    APIErrorCode.ServiceUnavailable,
}
_RETRYABLE_HTTP_STATUS = {429, 500, 502, 503, 504}


def _is_retryable(exc: BaseException) -> bool:
    """429/5xx만 재시도. 4xx auth/validation은 즉시 raise."""
    if isinstance(exc, RequestTimeoutError):
        return True
    if isinstance(exc, APIResponseError):
        return exc.code in _RETRYABLE_API_CODES
    if isinstance(exc, HTTPResponseError):
        # APIResponseError가 아닌 HTTP 에러 (e.g. multi-source httpx fallback)
        return exc.status in _RETRYABLE_HTTP_STATUS
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRYABLE_HTTP_STATUS
    return False


async def notion_call(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Notion SDK 호출을 asyncio.to_thread + tenacity 지수 백오프로 감싼다.

    SDK는 sync 함수만 노출 → to_thread로 비동기화. retry 안에 to_thread를 둬서
    backoff sleep이 event loop을 점유하지 않게 한다 (asyncio.sleep 사용).
    """
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(NOTION_RETRY_MAX_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=1, max=NOTION_RETRY_MAX_WAIT_S),
        retry=retry_if_exception(_is_retryable),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    ):
        with attempt:
            return await asyncio.to_thread(fn, *args, **kwargs)
