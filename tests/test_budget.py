"""RunBudget 단위 테스트 (plan §15.2, §20.1)."""
from __future__ import annotations

import pytest

from tools.budget import RunBudget


def test_initial_state():
    b = RunBudget(cap_usd=3.0)
    assert b.spent_usd == 0.0
    assert not b.exceeded()
    assert b.remaining() == 3.0


def test_add_accumulates():
    b = RunBudget(cap_usd=3.0)
    b.add(1.5)
    b.add(1.0)
    assert b.spent_usd == pytest.approx(2.5)
    assert not b.exceeded()
    assert b.remaining() == pytest.approx(0.5)


def test_exceeded_strictly_greater():
    """spent == cap은 exceeded() False — 정확히 cap에 닿은 시점은 통과 허용."""
    b = RunBudget(cap_usd=1.0)
    b.add(1.0)
    assert not b.exceeded()
    b.add(0.01)
    assert b.exceeded()


def test_remaining_floor_at_zero():
    """remaining()은 음수 안 나옴 — over-spent 상태에서도 0.0."""
    b = RunBudget(cap_usd=1.0)
    b.add(2.0)
    assert b.exceeded()
    assert b.remaining() == 0.0


def test_zero_cap():
    b = RunBudget(cap_usd=0.0)
    assert not b.exceeded()
    b.add(0.001)
    assert b.exceeded()


def test_negative_cost_raises():
    b = RunBudget(cap_usd=1.0)
    with pytest.raises(ValueError, match="음수"):
        b.add(-0.1)


# v1.6.1 — anthropic / openai 분리 추적
def test_add_anthropic_split():
    b = RunBudget(cap_usd=5.0)
    b.add_anthropic(0.5)
    b.add_anthropic(0.3)
    assert b.anthropic_usd == pytest.approx(0.8)
    assert b.openai_usd == 0.0
    assert b.spent_usd == pytest.approx(0.8)


def test_add_openai_split():
    b = RunBudget(cap_usd=5.0)
    b.add_openai(0.05)
    b.add_openai(0.15)
    assert b.openai_usd == pytest.approx(0.2)
    assert b.anthropic_usd == 0.0
    assert b.spent_usd == pytest.approx(0.2)


def test_mixed_split_sums_correctly():
    b = RunBudget(cap_usd=5.0)
    b.add_anthropic(0.5)
    b.add_openai(0.1)
    b.add_anthropic(0.3)
    assert b.anthropic_usd == pytest.approx(0.8)
    assert b.openai_usd == pytest.approx(0.1)
    assert b.spent_usd == pytest.approx(0.9)


def test_legacy_add_counts_as_anthropic():
    """기존 add()는 anthropic으로 가정 — backward compatibility."""
    b = RunBudget(cap_usd=5.0)
    b.add(0.5)
    assert b.anthropic_usd == pytest.approx(0.5)
    assert b.openai_usd == 0.0
    assert b.spent_usd == pytest.approx(0.5)


def test_split_negative_cost_raises():
    b = RunBudget(cap_usd=1.0)
    with pytest.raises(ValueError, match="음수"):
        b.add_openai(-0.05)
    with pytest.raises(ValueError, match="음수"):
        b.add_anthropic(-0.05)
