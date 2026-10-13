"""Budget kind-specific admission and exhaustion."""

import pytest

from agent_core.budget import Budget, BudgetExhausted
from agent_core.types import TerminalDisposition


def test_model_attempt_exhaustion():
    b = Budget(
        max_model_attempts=2,
        max_tool_iterations=10,
        max_tokens=10_000,
        max_spend=10.0,
        max_wall_seconds=60.0,
    )
    b.check("model")
    b.record_model_attempt(tokens=10)
    b.check("model")
    b.record_model_attempt(tokens=10)
    with pytest.raises(BudgetExhausted) as ei:
        b.check("model")
    assert ei.value.dimension == "model_attempts"
    assert ei.value.snapshot.disposition == TerminalDisposition.BUDGET_EXHAUSTED


def test_tool_zero_does_not_block_model():
    b = Budget(max_model_attempts=2, max_tool_iterations=0)
    b.check("model")  # must not raise
    with pytest.raises(BudgetExhausted) as ei:
        b.check("tool")
    assert ei.value.dimension == "tool_iterations"


def test_model_exhausted_still_allows_tool():
    b = Budget(max_model_attempts=1, max_tool_iterations=2)
    b.record_model_attempt()
    with pytest.raises(BudgetExhausted):
        b.check("model")
    b.check("tool")  # still ok


def test_token_and_spend_shared():
    b = Budget(max_tokens=100, max_spend=0.5, max_model_attempts=100)
    b.record_tokens(50)
    b.record_spend(0.4)
    b.check("model")
    b.record_spend(0.2)
    with pytest.raises(BudgetExhausted) as ei:
        b.check("model")
    assert ei.value.dimension == "spend"


def test_rejects_nan_limits():
    with pytest.raises(ValueError):
        Budget(max_spend=float("nan"))
    with pytest.raises(ValueError):
        Budget(max_wall_seconds=float("inf"))


def test_invalid_spend_increments_attempt_then_raises():
    b = Budget(max_model_attempts=5, max_spend=1.0)
    with pytest.raises(ValueError, match="finite|>= 0|number"):
        b.record_model_attempt(tokens=1, spend=float("nan"))
    assert b.model_attempts == 1  # counted before raise
    assert b.snapshot().spend_used == 0.0  # not mutated with nan


def test_negative_spend_rejected():
    b = Budget()
    with pytest.raises(ValueError):
        b.record_spend(-0.01)
    with pytest.raises(ValueError):
        b.record_tokens(-1)
