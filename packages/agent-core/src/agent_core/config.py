"""
File-controlled configuration for the mandatory core surface.

Agents load a JSON config file (path supplied by the operator / orchestrator).
The file is the source of truth for the knobs listed below.

Schema (all keys optional; missing keys keep code defaults):

{
  "allow_salvage": false,
  "budget": {
    "max_model_attempts": 8,
    "max_tool_iterations": 16,
    "max_tokens": 128000,
    "max_spend": 1.0,
    "max_wall_seconds": 300.0
  },
  "identity_keys": [
    "agent_id", "session_id", "invocation_id",
    "parent_invocation_id", "run_id", "project_id"
  ]
}

Unknown keys are rejected. max_spend is always US dollars.
Non-finite numbers are rejected.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_core.budget import Budget
from agent_core.evidence import DEFAULT_IDENTITY_KEYS

_ALLOWED_TOP = frozenset({"allow_salvage", "budget", "identity_keys"})
_ALLOWED_BUDGET = frozenset(
    {
        "max_model_attempts",
        "max_tool_iterations",
        "max_tokens",
        "max_spend",
        "max_wall_seconds",
    }
)


@dataclass(frozen=True)
class CoreConfig:
    """Immutable configuration snapshot for one agent process / invocation family."""

    allow_salvage: bool = False
    max_model_attempts: int = 8
    max_tool_iterations: int = 16
    max_tokens: int = 128_000
    max_spend: float = 1.0  # US dollars
    max_wall_seconds: float = 300.0
    identity_keys: tuple[str, ...] = DEFAULT_IDENTITY_KEYS

    def make_budget(self) -> Budget:
        """Fresh Budget instance seeded from this config."""
        return Budget(
            max_model_attempts=self.max_model_attempts,
            max_tool_iterations=self.max_tool_iterations,
            max_tokens=self.max_tokens,
            max_spend=self.max_spend,
            max_wall_seconds=self.max_wall_seconds,
        )


def _as_bool(v: Any, key: str) -> bool:
    if isinstance(v, bool):
        return v
    raise ValueError(f"config key {key!r} must be a boolean, got {type(v).__name__}")


def _as_int(v: Any, key: str) -> int:
    if isinstance(v, bool) or not isinstance(v, int):
        raise ValueError(f"config key {key!r} must be an int, got {type(v).__name__}")
    if v < 0:
        raise ValueError(f"config key {key!r} must be >= 0")
    return v


def _as_float(v: Any, key: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ValueError(f"config key {key!r} must be a number, got {type(v).__name__}")
    fv = float(v)
    if not math.isfinite(fv):
        raise ValueError(f"config key {key!r} must be finite, got {v!r}")
    if fv < 0:
        raise ValueError(f"config key {key!r} must be >= 0")
    return fv


def load_config(path: str | Path) -> CoreConfig:
    """
    Load CoreConfig from a JSON file.

    Raises FileNotFoundError, json.JSONDecodeError, or ValueError on bad shape.
    Unknown keys are rejected. Non-object budget is rejected.
    """
    path = Path(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("config root must be a JSON object")

    unknown = set(raw.keys()) - _ALLOWED_TOP
    if unknown:
        raise ValueError(f"unknown config key(s): {sorted(unknown)}")

    kwargs: dict[str, Any] = {}

    if "allow_salvage" in raw:
        kwargs["allow_salvage"] = _as_bool(raw["allow_salvage"], "allow_salvage")

    if "budget" in raw:
        budget = raw["budget"]
        if not isinstance(budget, dict):
            raise ValueError("config key 'budget' must be an object")
        unknown_b = set(budget.keys()) - _ALLOWED_BUDGET
        if unknown_b:
            raise ValueError(f"unknown budget key(s): {sorted(unknown_b)}")
        for src, dest, caster in (
            ("max_model_attempts", "max_model_attempts", _as_int),
            ("max_tool_iterations", "max_tool_iterations", _as_int),
            ("max_tokens", "max_tokens", _as_int),
            ("max_spend", "max_spend", _as_float),
            ("max_wall_seconds", "max_wall_seconds", _as_float),
        ):
            if src in budget:
                kwargs[dest] = caster(budget[src], f"budget.{src}")

    if "identity_keys" in raw:
        keys = raw["identity_keys"]
        if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
            raise ValueError("config key 'identity_keys' must be a list of strings")
        if not keys:
            raise ValueError("config key 'identity_keys' must be non-empty")
        kwargs["identity_keys"] = tuple(keys)

    return CoreConfig(**kwargs)


def config_to_dict(cfg: CoreConfig) -> dict[str, Any]:
    """Serialise a CoreConfig back to the file schema."""
    return {
        "allow_salvage": cfg.allow_salvage,
        "budget": {
            "max_model_attempts": cfg.max_model_attempts,
            "max_tool_iterations": cfg.max_tool_iterations,
            "max_tokens": cfg.max_tokens,
            "max_spend": cfg.max_spend,
            "max_wall_seconds": cfg.max_wall_seconds,
        },
        "identity_keys": list(cfg.identity_keys),
    }
