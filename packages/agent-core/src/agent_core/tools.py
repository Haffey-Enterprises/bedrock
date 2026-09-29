"""
Basic tool-loop invariants.

- Capability / schema checks before dispatch
- Result correlation to exactly one request
- Allow-list (only registered tools)
- Deterministic result ordering
- No unbounded conversational while-loop (enforced by Budget)
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from agent_core.structured import _validate, StructuredOutputError
from agent_core.types import (
    SideEffectClass,
    ToolCapability,
    ToolRequest,
    ToolResult,
)


class ToolLoopError(Exception):
    """Invariant violation in the tool loop."""


class ToolRegistry:
    """
    Allow-list of tools. Only names present in the registry may be dispatched.
    """

    def __init__(self, capabilities: Sequence[ToolCapability] | None = None):
        self._caps: dict[str, ToolCapability] = {}
        if capabilities:
            for c in capabilities:
                self.register(c)

    def register(self, capability: ToolCapability) -> None:
        if not capability.name:
            raise ToolLoopError("tool name must be non-empty")
        self._caps[capability.name] = capability

    def get(self, name: str) -> Optional[ToolCapability]:
        return self._caps.get(name)

    def names(self) -> frozenset[str]:
        return frozenset(self._caps)

    def __contains__(self, name: str) -> bool:
        return name in self._caps


def check_capability(
    registry: ToolRegistry,
    name: str,
    arguments: Mapping[str, Any],
) -> ToolCapability:
    """
    Pre-dispatch checks:
      1. name is on the allow-list
      2. arguments conform to the declared input_schema
    Raises ToolLoopError on failure.
    """
    cap = registry.get(name)
    if cap is None:
        raise ToolLoopError(f"tool {name!r} is not on the allow-list")
    try:
        _validate(arguments, cap.input_schema)
    except StructuredOutputError as e:
        raise ToolLoopError(f"arguments for {name!r} failed schema: {e}") from e
    return cap


def correlate_results(
    requests: Sequence[ToolRequest],
    results: Sequence[ToolResult],
) -> list[ToolResult]:
    """
    Correlate results to exactly one request each.

    Rules:
      - Every result.request_id must match exactly one request
      - Duplicate result request_ids are rejected
      - Missing results are not synthesised; caller decides policy
      - Returned list is ordered by the original request order (deterministic)
    """
    req_by_id = {r.request_id: r for r in requests}
    if len(req_by_id) != len(requests):
        raise ToolLoopError("duplicate request_id in requests")

    seen: set[str] = set()
    by_id: dict[str, ToolResult] = {}
    for res in results:
        if res.request_id not in req_by_id:
            raise ToolLoopError(
                f"result request_id {res.request_id!r} does not match any request"
            )
        if res.request_id in seen:
            raise ToolLoopError(
                f"duplicate result for request_id {res.request_id!r}"
            )
        seen.add(res.request_id)
        # Name must match the original request
        if res.name != req_by_id[res.request_id].name:
            raise ToolLoopError(
                f"result name {res.name!r} does not match request "
                f"{req_by_id[res.request_id].name!r} for id {res.request_id!r}"
            )
        by_id[res.request_id] = res

    # Deterministic order = original request order; only include matched results
    ordered = [by_id[r.request_id] for r in requests if r.request_id in by_id]
    return ordered
