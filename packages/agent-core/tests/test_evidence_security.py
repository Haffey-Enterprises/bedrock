"""Evidence emission and security boundary (per-dispatch auth)."""

import pytest

from agent_core.budget import Budget
from agent_core.evidence import InvocationContext, emit_evidence
from agent_core.security import AuthorizationError, ContentKind, SecurityBoundary
from agent_core.types import ParsePath, SideEffectClass, TerminalDisposition, ToolCapability
from agent_core.version import CORE_VERSION


def test_evidence_record_shape():
    ctx = InvocationContext(
        agent_id="agent-a",
        session_id="sess-1",
        invocation_id="inv-1",
        agent_version="0.2.0",
        project_id="proj-1",
        run_id="run-1",
    )
    b = Budget()
    b.record_model_attempt(tokens=42, spend=0.01)
    snap = b.snapshot()
    rec = emit_evidence(
        ctx,
        TerminalDisposition.SUCCESS,
        parse_path=ParsePath.DIRECT,
        budget_snapshot=snap,
        payload={"note": "ok"},
    )
    d = rec.to_dict()
    assert d["agent_id"] == "agent-a"
    assert d["core_version"] == CORE_VERSION
    assert d["disposition"] == "success"
    assert d["parse_path"] == "direct"
    assert d["tokens_used"] == 42
    assert d["project_id"] == "proj-1"
    assert d["run_id"] == "run-1"
    assert d["payload"]["note"] == "ok"


def test_side_effect_requires_auth():
    boundary = SecurityBoundary()
    pure = ToolCapability("read", {"type": "object"}, side_effect=SideEffectClass.NONE)
    risky = ToolCapability(
        "send_email", {"type": "object"}, side_effect=SideEffectClass.EXTERNAL
    )
    assert boundary.authorize_tool(pure, {}) is None
    with pytest.raises(AuthorizationError):
        boundary.authorize_tool(risky, {})
    boundary.grant("send_email")
    assert boundary.authorize_tool(risky, {}) is True


def test_authorizer_called_every_dispatch():
    calls = []

    def auth(cap, args):
        calls.append((cap.name, dict(args)))
        if args.get("target") == "B":
            raise AuthorizationError("B denied")
        return "token-A"

    boundary = SecurityBoundary(authorizer=auth)
    cap = ToolCapability("write", {"type": "object"}, side_effect=SideEffectClass.LOCAL)
    assert boundary.authorize_tool(cap, {"target": "A"}) == "token-A"
    assert boundary.authorize_tool(cap, {"target": "A"}) == "token-A"  # called again
    assert len(calls) == 2
    with pytest.raises(AuthorizationError):
        boundary.authorize_tool(cap, {"target": "B"})
    assert len(calls) == 3


def test_content_tagging():
    sb = SecurityBoundary()
    tagged = sb.tag(ContentKind.INSTRUCTION, "You are helpful.")
    assert tagged["kind"] == "instruction"
