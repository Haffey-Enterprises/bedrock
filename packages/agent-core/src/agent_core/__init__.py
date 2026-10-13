"""
agent_core — mandatory shared substrate for every LLM-calling agent.

Version 0.2.0. Provider transport and portable evidence mapping are adapter-owned.

Public surface is intentionally small and stable. Import only from this
package; do not re-implement these invariants inside individual agents.
"""

from agent_core.version import __version__, CORE_VERSION
from agent_core.types import (
    TerminalDisposition,
    ParsePath,
    SideEffectClass,
    ToolCapability,
    ToolRequest,
    ToolResult,
)
from agent_core.structured import (
    StructuredOutputError,
    ParseResult,
    ParseDiagnostics,
    parse_structured,
    stamp_identity,
    RESERVED_IDENTITY_KEYS,
)
from agent_core.budget import (
    Budget,
    BudgetExhausted,
    BudgetSnapshot,
)
from agent_core.tools import (
    ToolRegistry,
    ToolLoopError,
    correlate_results,
    check_capability,
)
from agent_core.evidence import (
    EvidenceRecord,
    InvocationContext,
    emit_evidence,
    DEFAULT_IDENTITY_KEYS,
)
from agent_core.security import (
    SecurityBoundary,
    AuthorizationError,
    ContentKind,
)
from agent_core.config import (
    CoreConfig,
    load_config,
    config_to_dict,
)

__all__ = [
    "__version__",
    "CORE_VERSION",
    "TerminalDisposition",
    "ParsePath",
    "SideEffectClass",
    "ToolCapability",
    "ToolRequest",
    "ToolResult",
    "StructuredOutputError",
    "ParseResult",
    "ParseDiagnostics",
    "parse_structured",
    "stamp_identity",
    "RESERVED_IDENTITY_KEYS",
    "Budget",
    "BudgetExhausted",
    "BudgetSnapshot",
    "ToolRegistry",
    "ToolLoopError",
    "correlate_results",
    "check_capability",
    "EvidenceRecord",
    "InvocationContext",
    "emit_evidence",
    "DEFAULT_IDENTITY_KEYS",
    "SecurityBoundary",
    "AuthorizationError",
    "ContentKind",
    "CoreConfig",
    "load_config",
    "config_to_dict",
]
