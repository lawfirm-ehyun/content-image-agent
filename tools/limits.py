"""비용·재시도·타임아웃·렌더 한계 단일 source (plan §20.1).

drift 방지 — 새 상수 추가 시 본 모듈에 먼저 정의한 뒤 호출처에서 import.
모델 ID는 `tools/llm/models.py` (LLM 도메인 전용으로 분리).
RunBudget mutable 상태는 `tools/budget.py`.
"""
from __future__ import annotations

from typing import Final

# === cost caps ===
# v1.6.3 단계 갱신 — 5/12 e2e 후속 trigger (analyze $0.52 + AI mix).
# Phase 4 안정화 후 PER_PAGE_CAP_USD $1.20 복귀 목표 (analyze prompt 슬림 + slot_selection 다이어트 후).
PER_PAGE_CAP_USD: Final[float] = 2.50             # v1.6.3 (이전 1.20, analyze 0.80 + review 4×0.30 + AI 2×0.25)
PER_PAGE_TARGET_USD: Final[float] = 1.20          # Phase 4 안정화 목표
PER_RUN_CAP_USD: Final[float] = 8.00              # v1.6.3 (이전 5.00, 5건 × 평균 $1.20-1.60)
PER_SLOT_COST_CAP_USD: Final[float] = 0.30        # v1.6.1 — gpt-image thinking 비용 변동성 대비 (§19.13)
ANALYZE_BUDGET_USD: Final[float] = 0.80           # v1.6.3 (이전 0.50, slot_selection mix 룰로 cache 47K→54K + output 21K)
REVIEW_BUDGET_USD: Final[float] = 0.30
QUERY_JSON_DEFAULT_BUDGET_USD: Final[float] = 0.30

# === retry / attempts ===
PER_SLOT_ATTEMPTS: Final[int] = 3
NOTION_RETRY_MAX_ATTEMPTS: Final[int] = 5         # tenacity stop_after_attempt (§19.3)
NOTION_RETRY_MAX_WAIT_S: Final[float] = 30.0      # exponential backoff 상한
OPENAI_RETRY_MAX_ATTEMPTS: Final[int] = 5         # 신설 v1.6.1 — gpt-image API 429/5xx (§19.12)
OPENAI_RETRY_MAX_WAIT_S: Final[float] = 60.0      # 신설 — thinking 모델 응답 지연 대비

# === llm prompt ===
MAX_USER_PROMPT_CHARS: Final[int] = 20_000        # Windows argv 한계
MAX_BLOCKS_PROMPT_CHARS: Final[int] = 18_000      # analyze 압축 진입 임계값 (§19.8)

# === timeouts ===
QUERY_JSON_TIMEOUT_S: Final[int] = 360
PLAYWRIGHT_FONT_TIMEOUT_MS: Final[int] = 5000
PLAYWRIGHT_PAINT_BUFFER_MS: Final[int] = 200
GPT_IMAGE_TIMEOUT_S: Final[int] = 120             # 신설 v1.6.1 — gpt-image thinking 응답 지연 (§19.12)
OPENAI_RATE_LIMIT_RPS: Final[float] = 1.0         # 신설 v1.6.1 — 보수적 cap (§19.12)

# === webp ===
WEBP_LOSSLESS_DEFAULT: Final[bool] = True
WEBP_METHOD: Final[int] = 6

# === gpt-image 단가표 (v1.6.1 신설, v1.6.4 모델 갱신) ===
# v1.6.4: default 모델 gpt-image-2-2026-04-21 (사용자 5/12 비교 후 결정 — 5종 비교에서 최신 + 톤 OK).
# 단가는 OpenAI docs 확인 필요. gpt-image-1 단가표 fallback (실제 비용은 사후 usage dashboard로 대조).
# model_id ENV override 가능: OPENAI_IMAGE_MODEL_INSTANT / OPENAI_IMAGE_MODEL_THINKING.
GPT_IMAGE_DEFAULT_MODEL: Final[str] = "gpt-image-2-2026-04-21"
GPT_IMAGE_PRICE_USD: Final[dict[tuple[str, str], float]] = {
    # (size, quality) → USD per image. gpt-image-1 단가 기준 — gpt-image-2 단가 미정 시 fallback.
    ("1024x1024", "low"): 0.011,
    ("1024x1024", "medium"): 0.042,
    ("1024x1024", "high"): 0.167,
    ("1024x1536", "low"): 0.016,
    ("1024x1536", "medium"): 0.063,
    ("1024x1536", "high"): 0.25,
    ("1536x1024", "low"): 0.016,
    ("1536x1024", "medium"): 0.063,
    ("1536x1024", "high"): 0.25,
}
