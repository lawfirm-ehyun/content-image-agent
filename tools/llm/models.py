"""LLM 모델 ID 단일 source.

limits.py(숫자 한계)와 직교한 LLM 도메인 전용 — 향후 Haiku 보조 라우팅 등
모델 라우팅 로직이 추가되면 여기로 모인다.

§12 Week 1-2 이후 bundled CLI 경로(CLAUDE_EXE)는 claude-agent-sdk가 내부에서
spawn하므로 production 코드 단일 참조 불필요 — 변수 제거.
"""
from __future__ import annotations

from typing import Final

DEFAULT_MODEL: Final[str] = "claude-sonnet-4-6"
