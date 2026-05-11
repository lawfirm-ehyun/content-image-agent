"""RunBudget — Phase 2 batch run-level 비용 누적 추적 (plan §15.2).

page-level cap은 orchestrator.run_for_page 안의 지역 page_cost 변수가 추적.
본 모듈은 process_database가 페이지 사이 누적 비용을 추적하기 위한 mutable 상태.

cap 초과 시 경고 로깅은 caller(process_database) 책임 — RunBudget은 순수 상태 객체.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RunBudget:
    cap_usd: float
    spent_usd: float = 0.0

    def add(self, cost: float) -> None:
        if cost < 0:
            raise ValueError(f"cost는 음수일 수 없음: {cost}")
        self.spent_usd += cost

    def exceeded(self) -> bool:
        return self.spent_usd > self.cap_usd

    def remaining(self) -> float:
        return max(self.cap_usd - self.spent_usd, 0.0)
