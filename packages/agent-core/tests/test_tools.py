"""Result correlation, allow-list, schema checks."""

import pytest

from agent_core.tools import (
    ToolLoopError,
    ToolRegistry,
    check_capability,
    correlate_results,
)
from agent_core.types import SideEffectClass, ToolCapability, ToolRequest, ToolResult


CAP = ToolCapability(
    name="echo",
    input_schema={
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
    },
    side_effect=SideEffectClass.NONE,
)


def test_allow_list_and_schema():
    reg = ToolRegistry([CAP])
    check_capability(reg, "echo", {"text": "hi"})
    with pytest.raises(ToolLoopError):
        check_capability(reg, "unknown", {})
    with pytest.raises(ToolLoopError):
        check_capability(reg, "echo", {"text": 123})


def test_correlate_happy_path_order():
    reqs = [
        ToolRequest("r1", "echo", {"text": "a"}),
        ToolRequest("r2", "echo", {"text": "b"}),
    ]
    # Results arrive out of order
    results = [
        ToolResult("r2", "echo", True, "b"),
        ToolResult("r1", "echo", True, "a"),
    ]
    ordered = correlate_results(reqs, results)
    assert [r.request_id for r in ordered] == ["r1", "r2"]


def test_correlate_rejects_unknown_and_duplicate():
    reqs = [ToolRequest("r1", "echo", {"text": "a"})]
    with pytest.raises(ToolLoopError):
        correlate_results(reqs, [ToolResult("r99", "echo", True, "x")])
    with pytest.raises(ToolLoopError):
        correlate_results(
            reqs,
            [
                ToolResult("r1", "echo", True, "a"),
                ToolResult("r1", "echo", True, "a"),
            ],
        )


def test_correlate_rejects_name_mismatch():
    reqs = [ToolRequest("r1", "echo", {"text": "a"})]
    with pytest.raises(ToolLoopError):
        correlate_results(reqs, [ToolResult("r1", "other", True, "x")])
