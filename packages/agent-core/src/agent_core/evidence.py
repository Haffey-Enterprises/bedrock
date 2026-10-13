"""
Evidence / invocation record emission.

Record shape is designed for clean PostgreSQL persistence with session-level
traceability. This module does not implement the database layer.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from agent_core.types import ParsePath, TerminalDisposition
from agent_core.version import CORE_VERSION

# Identity keys stamped onto structured outputs and recorded in evidence.
# project_id / run_id correlate invocations to a fleet project and a single run.
DEFAULT_IDENTITY_KEYS = (
    "agent_id",
    "session_id",
    "invocation_id",
    "parent_invocation_id",
    "run_id",
    "project_id",
)


@dataclass(frozen=True)
class InvocationContext:
    """
    Identity and provenance supplied by the caller (never by the model).
    Required fields are stamped onto structured outputs and evidence records.
    """

    agent_id: str
    session_id: str
    invocation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_invocation_id: Optional[str] = None
    run_id: Optional[str] = None
    project_id: Optional[str] = None
    agent_version: str = "0.0.0"
    extra: Mapping[str, Any] = field(default_factory=dict)

    def identity_map(self) -> dict[str, Any]:
        """All identity fields that have a non-None value."""
        m: dict[str, Any] = {
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "invocation_id": self.invocation_id,
        }
        if self.parent_invocation_id is not None:
            m["parent_invocation_id"] = self.parent_invocation_id
        if self.run_id is not None:
            m["run_id"] = self.run_id
        if self.project_id is not None:
            m["project_id"] = self.project_id
        return m


@dataclass
class EvidenceRecord:
    """
    Canonical evidence / invocation record.

    All required provenance fields are present so a later PostgreSQL writer
    can insert without additional synthesis. Optional fields may be null.

    spend_used is in US dollars.
    """

    # Required provenance
    record_id: str
    agent_id: str
    session_id: str
    invocation_id: str
    core_version: str
    timestamp_utc: str  # ISO-8601
    disposition: str  # TerminalDisposition value

    # Structured-output provenance
    parse_path: Optional[str] = None

    # Budget snapshot (flattened for easy column mapping)
    model_attempts: Optional[int] = None
    tool_iterations: Optional[int] = None
    tokens_used: Optional[int] = None
    spend_used: Optional[float] = None  # US dollars
    elapsed_seconds: Optional[float] = None

    # Linkage / correlation
    parent_invocation_id: Optional[str] = None
    run_id: Optional[str] = None
    project_id: Optional[str] = None
    agent_version: Optional[str] = None

    # Free-form payload (tool calls, model messages summary, etc.)
    # Keep JSON-serialisable; do not put secrets here.
    payload: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Flat dict ready for JSON serialisation or ORM mapping."""
        return asdict(self)


def emit_evidence(
    context: InvocationContext,
    disposition: TerminalDisposition,
    *,
    parse_path: Optional[ParsePath] = None,
    budget_snapshot: Any = None,
    payload: Optional[Mapping[str, Any]] = None,
) -> EvidenceRecord:
    """
    Construct an EvidenceRecord from invocation context and run outcome.

    Call this at every terminal point (success or failure). The returned
    record is the unit that a later persistence layer writes to PostgreSQL.
    """
    ts = datetime.now(timezone.utc).isoformat()
    record = EvidenceRecord(
        record_id=str(uuid.uuid4()),
        agent_id=context.agent_id,
        session_id=context.session_id,
        invocation_id=context.invocation_id,
        core_version=CORE_VERSION,
        timestamp_utc=ts,
        disposition=disposition.value,
        parse_path=parse_path.value if parse_path is not None else None,
        parent_invocation_id=context.parent_invocation_id,
        run_id=context.run_id,
        project_id=context.project_id,
        agent_version=context.agent_version,
        payload=dict(payload or {}),
    )

    if budget_snapshot is not None:
        record.model_attempts = getattr(budget_snapshot, "model_attempts", None)
        record.tool_iterations = getattr(budget_snapshot, "tool_iterations", None)
        record.tokens_used = getattr(budget_snapshot, "tokens_used", None)
        record.spend_used = getattr(budget_snapshot, "spend_used", None)
        record.elapsed_seconds = getattr(budget_snapshot, "elapsed_seconds", None)

    return record
