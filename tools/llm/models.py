"""LLM 모델 ID와 bundled CLI 경로 단일 source.

limits.py(숫자 한계)와 직교한 LLM 도메인 전용 — 향후 Haiku 보조 라우팅 등
모델 라우팅 로직이 추가되면 여기로 모인다.
"""
from __future__ import annotations

from pathlib import Path
from typing import Final

# tools/llm/models.py → repo root
_ROOT = Path(__file__).resolve().parents[2]

# claude-agent-sdk 0.1.x가 .venv에 동봉하는 bundled Claude Code CLI 경로.
# §12 Week 1-2 이후 SDK query()가 내부적으로 이 CLI를 spawn — production 코드에서
# 직접 참조 X. dead reference이지만 cleanup은 별도 코밋으로 미룸 (drift 룰 #7).
CLAUDE_EXE: Final[Path] = (
    _ROOT / ".venv" / "Lib" / "site-packages" / "claude_agent_sdk" / "_bundled" / "claude.exe"
)

DEFAULT_MODEL: Final[str] = "claude-sonnet-4-6"
