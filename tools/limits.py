"""비용·재시도·타임아웃·렌더 한계 단일 source (plan §20.1).

drift 방지 — 새 상수 추가 시 본 모듈에 먼저 정의한 뒤 호출처에서 import.
모델 ID는 `tools/llm/models.py` (LLM 도메인 전용으로 분리).
RunBudget mutable 상태는 `tools/budget.py`.
"""
from __future__ import annotations

from typing import Final

# === cost caps ===
# Phase 1 검증 단계 한정 — 안정화 후 plan §13 기준 0.30 복귀 목표.
# v1.3 슬롯 룰 강화 후 실측: analyze ~$0.37 + review x 2슬롯 ~$0.30 = 합 ~$0.97/페이지.
# 슬롯 3개 케이스 대비 cap $1.50 (analyze 0.50 + review x 3 x 0.30 = 1.40 안전 마진).
PER_PAGE_CAP_USD: Final[float] = 1.50            # orchestrator.py:46에서 이동
PER_PAGE_TARGET_USD: Final[float] = 0.30          # 신설 (Phase 2 비용 최적화 목표)
PER_RUN_CAP_USD: Final[float] = 3.00              # 신설 (CLAUDE.md 운영 사실)
ANALYZE_BUDGET_USD: Final[float] = 0.50           # tools/llm/analyze_content.py:86에서 이동
REVIEW_BUDGET_USD: Final[float] = 0.30            # tools/llm/review.py:41에서 이동
QUERY_JSON_DEFAULT_BUDGET_USD: Final[float] = 0.30  # tools/llm/_common.py:81에서 이동

# === retry / attempts ===
PER_SLOT_ATTEMPTS: Final[int] = 3                 # orchestrator.py:47에서 이동
NOTION_RETRY_MAX_ATTEMPTS: Final[int] = 5         # 신설 — tenacity stop_after_attempt (§19.3)
NOTION_RETRY_MAX_WAIT_S: Final[float] = 30.0      # 신설 — exponential backoff 상한

# === llm prompt ===
# CLI subprocess의 user prompt argv 길이 한계 — Windows ~32K 한계 + 안전마진.
MAX_USER_PROMPT_CHARS: Final[int] = 20_000        # tools/llm/_common.py:29에서 이동
# analyze_content 입력 본문 압축 모드 진입 임계값 (§19.8).
MAX_BLOCKS_PROMPT_CHARS: Final[int] = 18_000      # tools/llm/analyze_content.py:17에서 이동

# === timeouts ===
QUERY_JSON_TIMEOUT_S: Final[int] = 360            # tools/llm/_common.py:82에서 이동
PLAYWRIGHT_FONT_TIMEOUT_MS: Final[int] = 5000     # tools/render/template_render.py:88에서 이동
PLAYWRIGHT_PAINT_BUFFER_MS: Final[int] = 200      # tools/render/template_render.py:90에서 이동

# === webp ===
WEBP_LOSSLESS_DEFAULT: Final[bool] = True         # tools/image/webp_converter.py:20에서 이동
WEBP_METHOD: Final[int] = 6                       # tools/image/webp_converter.py:42에서 이동
