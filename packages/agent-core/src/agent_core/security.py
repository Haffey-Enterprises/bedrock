"""
Security boundary.

Invariants:
  - Model output is untrusted inbound data.
  - Instructions (system / developer) are separated from retrieved / tool content.
  - Side-effecting tools require authorization outside model control.
  - When an authorizer callback is configured, it is invoked on every dispatch
    (no argument-insensitive cache). Name-wide preauthorized grants remain explicit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping, MutableMapping, Optional, Set

from agent_core.types import SideEffectClass, ToolCapability


class ContentKind(str, Enum):
    """Provenance tag for content that may reach the model or leave the agent."""

    INSTRUCTION = "instruction"  # system / developer instructions
    USER = "user"
    TOOL_RESULT = "tool_result"
    RETRIEVED = "retrieved"  # RAG / search / external docs
    MODEL = "model"  # model-generated (untrusted)
    INTERNAL = "internal"


class AuthorizationError(Exception):
    """Raised when a side-effecting tool lacks external authorization."""


@dataclass
class SecurityBoundary:
    """
    Enforces the security boundary for a single agent invocation.

    - tag() keeps instruction content distinct from tool/retrieved content.
    - authorize_tool() must be called before dispatching any tool whose
      side_effect is not NONE.
    - If `authorizer` is set, it is called on every dispatch (no cache of
      argument-sensitive decisions). `preauthorized` / `grant()` are explicit
      name-wide grants that skip the callback.
    """

    # Explicit name-wide grants only (not populated by authorizer results).
    _granted: MutableMapping[str, Any] = field(default_factory=dict, init=False)

    # Optional callback: (capability, arguments) -> token | raises AuthorizationError
    authorizer: Optional[Callable[[ToolCapability, Mapping[str, Any]], Any]] = None

    # Names that are pre-authorized for the whole invocation (name-wide).
    preauthorized: Set[str] = field(default_factory=set)

    def tag(self, kind: ContentKind, content: Any) -> dict[str, Any]:
        """Wrap content with an explicit kind tag."""
        return {"kind": kind.value, "content": content}

    def authorize_tool(
        self,
        capability: ToolCapability,
        arguments: Mapping[str, Any],
    ) -> Any:
        """
        Obtain authorization for a tool call.

        - SideEffectClass.NONE tools are always allowed.
        - preauthorized / grant() names are allowed without calling the authorizer.
        - Otherwise the authorizer is invoked on every call (no result cache).
        """
        name = capability.name
        if capability.side_effect == SideEffectClass.NONE:
            return None
        if name in self.preauthorized or name in self._granted:
            return self._granted.get(name, True)

        if self.authorizer is None:
            raise AuthorizationError(
                f"tool {name!r} has side_effect={capability.side_effect.value} "
                "but no authorizer is configured and it is not preauthorized"
            )

        # Always call — no argument-insensitive cache of authorizer results.
        return self.authorizer(capability, arguments)

    def grant(self, name: str, token: Any = True) -> None:
        """Explicit name-wide grant for this invocation (external decision)."""
        self._granted[name] = token

    def is_authorized(self, name: str) -> bool:
        return name in self.preauthorized or name in self._granted

    def require_authorized(self, name: str) -> None:
        if not self.is_authorized(name):
            raise AuthorizationError(f"tool {name!r} is not authorized")
