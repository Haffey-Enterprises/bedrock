# Compatibility and support matrix

Support is bounded by the declared requirements below. Retained evidence must
exercise each minimum and record the exact identity of every execution.

| Surface | Support requirement | Distribution and reload behavior | Evidence | Status |
|---|---|---|---|---|
| Claude Code | >=2.1.226 | Refresh/update marketplace, update plugin, then start a new session. | strict validation and isolated install/reload at the minimum version in required CI | supported |
| Claude.ai / Cowork | Hosted service observed 2026-08-27 | Marketplace changes take effect in the next new session; the host exposes skill-local supporting files but not the package-root manifest. | v8.3.0 fresh-session and full-client-restart probes proved 13 skills and current content while package version remained unavailable; HEB-140's retained v8.4.0 final release evidence and rollout ledger record release acceptance and successful two-surface verification through the generated skill-local carrier | supported |
| Codex/OpenAI adapter | None | No adapter is distributed. | none | unsupported |
| Cursor adapter | None | No adapter is distributed. | none | unsupported |
| External product runner-backed review | No package binding | Requires a product-owned workflow binding and versioned runner with compatible schemas, exact invocation, and fresh gate evidence. | none in this package | unavailable; direct and multi-perspective profiles remain supported |

The portable skill core has contract version `3.0.0`; the distributed Claude
adapter contract has version `1.1.0`. These are compatibility identities, not
the package version. The manifest remains the package-version authority.

Portable-core 2.0 moves workflow meaning, actor rosters, authority assignments,
state transitions, retries, budgets, durable execution, and operational posture
to the consuming product. The former product-specific runner reference is
replaced by a generic external binding contract. Direct and multi-perspective
review require no runner. Consumers of the former bundled reference path must
select the generic binding and supply their own declared runner evidence; no
existing product implementation is promoted or mapped automatically.

Support covers installation, discovery, deterministic package validation, and
the declared skill contracts on verified rows. It does not promise incident
response, production operations, regulatory compliance, or cross-agent
security assurance; see the product coverage map and threat model.

The Claude Code capability is a minimum-version contract. Exact versions in
skill `verified_hosts` rows, CI logs, and retained reports identify individual
executions; they neither narrow nor expand the supported minimum. Required CI
pins the minimum so the oldest supported host remains exercised.

A host below the declared minimum, an observed incompatibility at or above the
minimum, a manifest-schema change, a routing-adapter change, or a generated
carrier format change invalidates the corresponding evidence until it is
reconciled and rerun. A host upgrade at or above the minimum does not by itself
invalidate support. Unsupported surfaces fail closed: name the missing adapter
or capability and do not claim compatibility by similarity.

## HEB-154 breaking migration

The candidate adds agent-builder 1.0.0 as primary owner for checked fleet
specialists; agent-code 2.0.0 remains the mechanism authority. Existing explicit
agent-code calls remain valid for LLM-call implementation. Agent-builder checks
its agent-code sibling identity and installs bundled agent-core 0.2.0 into the
consumer project environment before implementation. Python >=3.10 and compatible
pinned third-party wheels are required for that operation; absence stops it.
Plugin loading alone does not prove Python execution support.

Portable evidence 1.0.0 consumers must migrate to 2.0.0: unknown totals become
null with explicit status/reason, known subtotal and reserved exposure remain
separate, and absent responses have no invented hash. Count model attempts and
physical tool dispatches independently. The core-owned EvidenceRecord v0.1 is
unchanged and still requires adapter mapping. No automatic v1 reinterpretation
or mixed-version evidence pooling is supported.

Bedrock 10.0.0 remains a candidate pending composed release acceptance. Rollback
retains the prior accepted plugin and the project's prior dependency lock;
plugin rollback does not mutate deployed project environments. New wheel and
host claims require the corresponding installation evidence. The historical
one-provider trial does not prove other providers, side-effect reconciliation,
PostgreSQL, parallel execution, or fleet orchestration.
