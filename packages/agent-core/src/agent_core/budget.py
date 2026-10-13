"""
Aggregate execution budget.

One budget covers model attempts, tool iterations, wall time, tokens and spend.
Admission is kind-specific for per-kind limits; shared limits always apply.
Typed terminal dispositions on exhaustion.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Literal, Optional

from agent_core.types import TerminalDisposition

OperationKind = Literal["model", "tool"]


class BudgetExhausted(Exception):
    """Raised when any applicable budget dimension is exhausted."""

    def __init__(self, dimension: str, snapshot: "BudgetSnapshot"):
        self.dimension = dimension
        self.snapshot = snapshot
        super().__init__(f"budget exhausted on {dimension}: {snapshot}")



def _require_usage_int(name: str, value: int | float) -> int:
    """Finite nonnegative integer value; raises ValueError otherwise."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number, got {type(value).__name__}")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value!r}")
    if value < 0:
        raise ValueError(f"{name} must be >= 0, got {value!r}")
    if isinstance(value, float) and not value.is_integer():
        raise ValueError(f"{name} must be an integer, got {value!r}")
    return int(value)


def _require_usage_float(name: str, value: int | float) -> float:
    """Finite nonnegative float for consumption; raises ValueError otherwise."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number, got {type(value).__name__}")
    fv = float(value)
    if not math.isfinite(fv):
        raise ValueError(f"{name} must be finite, got {value!r}")
    if fv < 0:
        raise ValueError(f"{name} must be >= 0, got {value!r}")
    return fv

def _require_finite_nonneg(name: str, value: float | int) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number, got {type(value).__name__}")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value!r}")
    if value < 0:
        raise ValueError(f"{name} must be >= 0, got {value!r}")


@dataclass(frozen=True)
class BudgetSnapshot:
    """Immutable view of current consumption vs limits."""

    model_attempts: int
    max_model_attempts: int
    tool_iterations: int
    max_tool_iterations: int
    tokens_used: int
    max_tokens: int
    spend_used: float
    max_spend: float
    elapsed_seconds: float
    max_wall_seconds: float
    disposition: TerminalDisposition = TerminalDisposition.SUCCESS

    def exhausted_shared(self) -> Optional[str]:
        if self.tokens_used >= self.max_tokens:
            return "tokens"
        if self.spend_used >= self.max_spend:
            return "spend"
        if self.elapsed_seconds >= self.max_wall_seconds:
            return "wall_time"
        return None

    def exhausted_for(self, kind: OperationKind) -> Optional[str]:
        shared = self.exhausted_shared()
        if shared is not None:
            return shared
        if kind == "model" and self.model_attempts >= self.max_model_attempts:
            return "model_attempts"
        if kind == "tool" and self.tool_iterations >= self.max_tool_iterations:
            return "tool_iterations"
        return None


@dataclass
class Budget:
    """
    Mutable aggregate budget. Thread-unsafe by design (single-threaded agent loop).

    Call check("model") or check("tool") before the corresponding operation.
    Shared limits (tokens, spend, wall time) always block; per-kind limits
    only block that kind. Call record_* after the action (including failed transport).
    """

    max_model_attempts: int = 8
    max_tool_iterations: int = 16
    max_tokens: int = 128_000
    max_spend: float = 1.0  # US dollars
    max_wall_seconds: float = 300.0

    _model_attempts: int = field(default=0, init=False, repr=False)
    _tool_iterations: int = field(default=0, init=False, repr=False)
    _tokens_used: int = field(default=0, init=False, repr=False)
    _spend_used: float = field(default=0.0, init=False, repr=False)
    _started_at: float = field(default_factory=time.monotonic, init=False, repr=False)

    def __post_init__(self) -> None:
        _require_finite_nonneg("max_spend", self.max_spend)
        _require_finite_nonneg("max_wall_seconds", self.max_wall_seconds)
        # Accept integral floats, but never truncate fractional limits.
        object.__setattr__(self, "max_model_attempts", _require_usage_int("max_model_attempts", self.max_model_attempts))
        object.__setattr__(self, "max_tool_iterations", _require_usage_int("max_tool_iterations", self.max_tool_iterations))
        object.__setattr__(self, "max_tokens", _require_usage_int("max_tokens", self.max_tokens))

    def snapshot(self) -> BudgetSnapshot:
        elapsed = time.monotonic() - self._started_at
        snap = BudgetSnapshot(
            model_attempts=self._model_attempts,
            max_model_attempts=self.max_model_attempts,
            tool_iterations=self._tool_iterations,
            max_tool_iterations=self.max_tool_iterations,
            tokens_used=self._tokens_used,
            max_tokens=self.max_tokens,
            spend_used=self._spend_used,
            max_spend=self.max_spend,
            elapsed_seconds=elapsed,
            max_wall_seconds=self.max_wall_seconds,
        )
        # Disposition exhausted if any shared or any kind is at limit
        if (
            snap.exhausted_shared() is not None
            or snap.model_attempts >= snap.max_model_attempts
            or snap.tool_iterations >= snap.max_tool_iterations
        ):
            return BudgetSnapshot(
                **{**snap.__dict__, "disposition": TerminalDisposition.BUDGET_EXHAUSTED}
            )
        return snap

    def check(self, kind: OperationKind = "model") -> BudgetSnapshot:
        """
        Raise BudgetExhausted if the next operation of `kind` is not permitted.

        Shared limits always apply. Per-kind limits apply only to that kind,
        so a tool-exhausted budget can still admit a model attempt and vice versa.
        """
        if kind not in ("model", "tool"):
            raise ValueError(f"kind must be 'model' or 'tool', got {kind!r}")
        snap = self.snapshot()
        dim = snap.exhausted_for(kind)
        if dim is not None:
            raise BudgetExhausted(dim, snap)
        return snap

    def record_model_attempt(self, tokens: int = 0, spend: float = 0.0) -> None:
        """Count a model attempt; then apply usage. Invalid usage raises after the count."""
        self._model_attempts += 1
        try:
            tok = _require_usage_int("tokens", tokens)
            spd = _require_usage_float("spend", spend)
        except ValueError:
            raise
        self._tokens_used += tok
        self._spend_used += spd

    def record_tool_iteration(self) -> None:
        self._tool_iterations += 1

    def record_tokens(self, tokens: int) -> None:
        tok = _require_usage_int("tokens", tokens)
        self._tokens_used += tok

    def record_spend(self, amount: float) -> None:
        spd = _require_usage_float("spend", amount)
        self._spend_used += spd

    @property
    def model_attempts(self) -> int:
        return self._model_attempts

    @property
    def tool_iterations(self) -> int:
        return self._tool_iterations
