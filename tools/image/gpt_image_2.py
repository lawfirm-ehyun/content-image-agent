"""OpenAI gpt-image API wrapper — instant / thinking 두 함수 노출.

v1.6.1 신설 (plan §12 P3.2).

설계:
  - **자연어 prompt 우선** (plan §7.0 v1.6.2 사상). hex/픽셀 토큰 over-constraint 금지.
  - **모델 ID는 ENV로 override 가능** — 신모델 출시 시 코드 수정 없이 전환:
      OPENAI_IMAGE_MODEL_INSTANT (default: GPT_IMAGE_DEFAULT_MODEL)
      OPENAI_IMAGE_MODEL_THINKING (default: GPT_IMAGE_DEFAULT_MODEL)
  - **tenacity backoff** (§19.12) — 429 / 5xx / Timeout 최대 5회.
  - **에러 sanitize** (§19.15) — raw response.text 노출 X. 정형화된 메시지만.
  - **비용 추정** — OpenAI 응답에 단가 명시 X → `tools/limits.GPT_IMAGE_PRICE_USD` 테이블 기반.
    실제 비용은 사후 OpenAI usage dashboard로 대조 권장.

quality 의미 (v1.6.1):
  - instant = "medium" (~$0.042 @ 1024x1024). 분위기·일러스트 적합.
  - thinking = "high" (~$0.167 @ 1024x1024). 텍스트 정확성·세밀함 필요한 카드 (kakao_dialogue 등).
"""
from __future__ import annotations

import base64
import logging
import os
from dataclasses import dataclass
from typing import Final, Literal

from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    RateLimitError,
)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from tools.limits import (
    GPT_IMAGE_DEFAULT_MODEL,
    GPT_IMAGE_PRICE_USD,
    GPT_IMAGE_TIMEOUT_S,
    OPENAI_RETRY_MAX_ATTEMPTS,
    OPENAI_RETRY_MAX_WAIT_S,
)

logger = logging.getLogger(__name__)

ImageSize = Literal["1024x1024", "1024x1536", "1536x1024"]
ImageQuality = Literal["low", "medium", "high"]


_RETRYABLE = (RateLimitError, APITimeoutError, APIConnectionError)


# ============================================================================
# 결과 타입
# ============================================================================


@dataclass(frozen=True)
class ImageResult:
    """gpt-image 호출 결과.

    png_bytes  : PNG 바이너리 (base64 디코딩 완료).
    cost_usd   : 추정 비용 (단가표 기반).
    model_id   : 실제 호출에 쓴 모델 ID.
    size       : 응답 이미지 size.
    quality    : 응답 이미지 quality.
    revised_prompt : OpenAI가 자동 수정한 prompt (있으면). 디버깅용.
    """

    png_bytes: bytes
    cost_usd: float
    model_id: str
    size: ImageSize
    quality: ImageQuality
    revised_prompt: str | None = None


# ============================================================================
# 단가 추정
# ============================================================================


def estimate_cost(size: ImageSize, quality: ImageQuality) -> float:
    """단가표 lookup. 미정 조합이면 0.0 반환 + warning."""
    price = GPT_IMAGE_PRICE_USD.get((size, quality))
    if price is None:
        logger.warning(
            "gpt-image 단가표에 없는 조합: size=%s quality=%s — 비용 추정 0.0 처리",
            size, quality,
        )
        return 0.0
    return price


# ============================================================================
# 클라이언트
# ============================================================================


_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    """프로세스 단위 lazy singleton."""
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            # §19.15 fail-fast — orchestrator 진입점에서 미리 검증 권장.
            raise RuntimeError("OPENAI_API_KEY가 환경변수에 없음 (§19.15 fail-fast)")
        _client = AsyncOpenAI(api_key=api_key, timeout=GPT_IMAGE_TIMEOUT_S)
    return _client


def _resolve_model_id(quality: ImageQuality) -> str:
    """ENV override 우선, 없으면 GPT_IMAGE_DEFAULT_MODEL."""
    if quality == "high":  # thinking 경로
        env_key = "OPENAI_IMAGE_MODEL_THINKING"
    else:  # low / medium = instant 경로
        env_key = "OPENAI_IMAGE_MODEL_INSTANT"
    return os.environ.get(env_key, "").strip() or GPT_IMAGE_DEFAULT_MODEL


def _sanitize_error(exc: Exception) -> str:
    """OpenAI 에러를 정형 메시지로 — raw response.text 누설 차단 (§19.15)."""
    if isinstance(exc, AuthenticationError):
        return "OpenAI API auth failure (key invalid/expired)"
    if isinstance(exc, RateLimitError):
        return "OpenAI rate limit exceeded"
    if isinstance(exc, APITimeoutError):
        return f"OpenAI API timeout (>{GPT_IMAGE_TIMEOUT_S}s)"
    if isinstance(exc, APIConnectionError):
        return "OpenAI API connection error"
    if isinstance(exc, APIError):
        status = getattr(exc, "status_code", "?")
        return f"OpenAI API error: HTTP {status}"
    return f"OpenAI unknown error: {type(exc).__name__}"


# ============================================================================
# 핵심 호출
# ============================================================================


_RETRY_DECORATOR: Final = retry(
    retry=retry_if_exception_type(_RETRYABLE),
    stop=stop_after_attempt(OPENAI_RETRY_MAX_ATTEMPTS),
    wait=wait_exponential(multiplier=2, min=2, max=OPENAI_RETRY_MAX_WAIT_S),
    reraise=True,
)


@_RETRY_DECORATOR
async def _generate_raw(
    prompt: str,
    *,
    model_id: str,
    size: ImageSize,
    quality: ImageQuality,
) -> ImageResult:
    """OpenAI images.generate 호출 + 결과 dataclass 변환. tenacity로 429/5xx retry."""
    client = get_client()
    resp = await client.images.generate(
        model=model_id,
        prompt=prompt,
        size=size,
        quality=quality,
        n=1,
        # response_format default — gpt-image-1은 b64_json 직접 반환 (URL 옵션 없음).
    )
    data = resp.data[0]
    b64 = getattr(data, "b64_json", None)
    if not b64:
        raise RuntimeError("OpenAI 응답에 b64_json 없음 — API spec 변경 가능성")
    png_bytes = base64.b64decode(b64)
    return ImageResult(
        png_bytes=png_bytes,
        cost_usd=estimate_cost(size, quality),
        model_id=model_id,
        size=size,
        quality=quality,
        revised_prompt=getattr(data, "revised_prompt", None),
    )


# ============================================================================
# 공개 API
# ============================================================================


_OPENAI_ERRORS = (
    AuthenticationError,
    RateLimitError,
    APITimeoutError,
    APIConnectionError,
    APIError,
)


async def generate_instant(
    prompt: str,
    *,
    size: ImageSize = "1024x1024",
    quality: ImageQuality = "medium",
) -> ImageResult:
    """가벼운 일러스트·분위기 카드용 (illustration 등).

    quality=medium @ 1024x1024 ≈ $0.042/장. 60s 이내 응답 기대.
    """
    model_id = _resolve_model_id(quality)
    try:
        return await _generate_raw(prompt, model_id=model_id, size=size, quality=quality)
    except _OPENAI_ERRORS as e:
        # OpenAI 측 에러만 sanitize. config 에러 (OPENAI_API_KEY 누락 등)는 원본 그대로 raise.
        raise RuntimeError(_sanitize_error(e)) from e


async def generate_thinking(
    prompt: str,
    *,
    size: ImageSize = "1024x1024",
    quality: ImageQuality = "high",
) -> ImageResult:
    """텍스트 정확성·세밀함 필요한 카드용 (kakao_dialogue, document_excerpt 등).

    quality=high @ 1024x1024 ≈ $0.167/장. 60-120s 응답 기대.
    """
    model_id = _resolve_model_id(quality)
    try:
        return await _generate_raw(prompt, model_id=model_id, size=size, quality=quality)
    except _OPENAI_ERRORS as e:
        raise RuntimeError(_sanitize_error(e)) from e
