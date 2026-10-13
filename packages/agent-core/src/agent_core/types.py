"""Shared typed primitives used across the core surface."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional, Sequence


class TerminalDisposition(str, Enum):
    """Typed terminal outcomes for an invocation or tool-loop step."""

    SUCCESS = "success"
    BUDGET_EXHAUSTED = "budget_exhausted"
    PARSE_FAILED = "parse_failed"
    SCHEMA_INVALID = "schema_invalid"
    TOOL_DENIED = "tool_denied"
    TOOL_ERROR = "tool_error"
    AUTHORIZATION_REQUIRED = "authorization_required"
    CANCELLED = "cancelled"
    PROVIDER_ERROR = "provider_error"
    UNKNOWN = "unknown"


class ParsePath(str, Enum):
    """How structured output was obtained. Recorded for auditability."""

    DIRECT = "direct"  # raw text was valid JSON matching schema
    SALVAGE_FENCE = "salvage_fence"  # extracted from a single markdown fence
    SALVAGE_FIRST_OBJECT = "salvage_first_object"  # balanced-object salvage (not necessarily document-first)
    FAILED = "failed"


class SideEffectClass(str, Enum):
    """Side-effect classification for tools. Drives authorization requirements."""

    NONE = "none"  # pure / read-only
    LOCAL = "local"  # local mutation (files, memory)
    EXTERNAL = "external"  # network, payments, messages, irreversible actions


@dataclass(frozen=True)
class ToolCapability:
    """Declaration of a tool the agent is allowed to call."""

    name: str
    input_schema: Mapping[str, Any]  # JSON-Schema-like dict (subset)
    side_effect: SideEffectClass = SideEffectClass.NONE
    idempotent: bool = True
    description: str = ""


@dataclass(frozen=True)
class ToolRequest:
    """A single tool-call request emitted by the model (after validation)."""

    request_id: str
    name: str
    arguments: Mapping[str, Any]


@dataclass(frozen=True)
class ToolResult:
    """Correlated result for exactly one ToolRequest."""

    request_id: str
    name: str
    ok: bool
    content: Any
    error: Optional[str] = None
