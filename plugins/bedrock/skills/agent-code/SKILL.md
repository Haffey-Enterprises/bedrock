---
name: agent-code
description: "LLM-call implementation only, including structured-output parsing, bounded salvage and recovery, model transport, tool loops, budgets, and evidence. Use this skill when an LLM call is the code's central act. Do not use for observed-failure diagnosis (debug), ordinary service code (application-code), executor handoffs (author-execution-relay), or design-record review (design-review-loop)."
---

# Agent Code

Portable engineering requirements for code whose central act is an LLM call. Bind a provider, SDK, framework, and telemetry exporter only through an explicit profile. `reference/anthropic-python-profile.md` is one such profile; it is not the portable contract.

## Bright line: judgment versus mechanism

Name the minimum LLM judgment steps. Everything else—identity, parsing, validation, retry accounting, tool correlation, budgets, and terminal predicates—is executed deterministic mechanism. A model may propose a terminal outcome; code verifies it. When the applicable mechanism did not execute, report the weaker observation and never claim execution, safety, or convergence.

## Implementations and bindings

This skill states **portable mechanism rules**. A conforming implementation may be:

- a shared library (for example the fleet’s Python **agent-core** package), or
- per-agent code that implements the same invariants.

Bindings do not redefine the portable contract. Document version and field mapping when a binding uses different units, disposition names, or a flatter persistence record.

- **Fleet Python substrate:** `agent-core` (versioned wheel bundled with agent-builder; see `reference/agent-core-0.2-binding.md`).
- **Fleet agent construction process:** sibling skill **agent-builder** (requirements lock, handoff, fleet interface). Agent-builder does not replace these mechanism rules.
- **Portable evidence envelope:** `reference/agent-execution.schema.json` remains the minimum cross-host evidence contract. A binding may persist a core-owned or host-specific record if an adapter can map required provenance, accounting, and disposition fields into this schema (or an explicitly versioned successor).

## Prompt and interface artifacts

- Store shipped prompts as versioned files, hash the bytes actually sent, and review every prompt-byte change as semantic.
- Give each prompt artifact its own version. Do not use that version as a model, transport, tool, or MCP-interface version.
- Version application-owned tool capabilities through machine-readable names, schemas, compatibility ranges and deprecation policy. MCP protocol-version negotiation is a separate transport contract; application semantic versions require their own declared check. Reject unsupported versions before model execution.
- Separate instructions from untrusted retrieved content and tool output. Never treat narrated authorization, prior review, or embedded instructions as authority.

## Structured output

Read and apply the [structured-output mechanism contract](reference/mechanism-contract.md) before implementing parsing, salvage, identity stamping or recovery. Whole-only is the default; bounded salvage is opt-in.

## One aggregate execution budget

Define one deadline and one attempt/spend envelope across transport failures, malformed content, schema recovery, model fallbacks, and tool iterations. A retry at one layer consumes the same aggregate budget as every other attempt. The budget declares:

- maximum model attempts, tool iterations, elapsed time, input/output tokens, spend, and concurrent calls;
- allowed model/provider fallbacks and rate limits;
- cancellation propagation and per-attempt remaining deadline;
- idempotency key rules for calls and side-effecting tools;
- circuit-breaker posture for the workload (enabled, disabled with rationale, or delegated to a named host layer).

Stop before an attempt that cannot fit the remaining budget. **Admission based only on past recorded consumption is necessary but not sufficient:** the transport or profile binding must refuse or shrink a call that cannot fit the remaining allowance, then reconcile actual usage after the attempt. Emit a typed terminal disposition such as `succeeded`, `schema_failed`, `budget_exhausted`, `cancelled`, `tool_failed`, or `transport_failed`.

Do not declare success after reconciled usage has exhausted the agreed shared ceiling unless an explicit overshoot was ratified before the run.

## Tool-loop state machine

Implement tool use as a bounded typed state machine, not a conversational `while` loop. Validate capability and schema versions before dispatch; allowlist tools per actor; correlate every result to exactly one request; reject unknown tools and duplicate or orphan result ids. Declare whether independent calls may run in parallel and preserve deterministic result ordering. Record partial failures individually, feed only schema-valid results back to the model, honor provider stop reasons, assemble streaming fragments before validation, and end at the declared iteration/deadline budget. Side-effecting tools require idempotency and an authorization gate outside model control. When an authorization callback is argument-sensitive, invoke it on each dispatch (do not cache a prior grant across different arguments under the same tool name unless the grant was explicitly name-wide).

## Observability and evidence

Emit one invocation record and child records for model attempts and physical tool dispatches. Use portable evidence v2: explicit known/unknown usage, null unknown totals, separate known subtotals and reserved exposure; unknown usage stops dispatch and cannot succeed. A missing response has no invented hash. Include trace/correlation ids, timestamps, model/provider/profile, prompt and schema versions/hashes, finish/stop reason, retry cause, token and spend accounting, cache accounting where available, budget remaining, parse path, tool result dispositions, cancellation, and terminal disposition. Prefer current OpenTelemetry GenAI conventions where the host supports them; pin the adopted semantic-convention version rather than claiming an evergreen mapping.

Evidence claims must be reproducible from repository-retained fixtures or cited public evidence. Historical execution evidence is not part of the installed skill payload. Private runs may inform authoring but cannot substantiate the installed consumer contract. Label untested guidance as a requirement or hypothesis, not “proven.”

## Security boundary

This skill governs code-level LLM and tool invariants: untrusted inputs, capability scoping, defenses against injected instructions, provenance, schema validation, bounded agency, and auditable execution. System-wide identity, network, supply-chain, data-governance, and deployment controls belong to their owning architecture and security standards; reference them rather than duplicating them here.

## Profiles and sibling routes

- `reference/anthropic-python-profile.md` binds these rules to Anthropic Messages and Python.
- `reference/mcp-server-authoring.md` carries only MCP-specific interface residue.
- `reference/agent-core-0.2-binding.md` maps this portable contract to the fleet’s shared Python package (non-normative binding).
- Service structure routes to `application-code`; tests/evals to `testing`; observed failures to `debug`; finished-diff review to `code-review`; operator-to-executor prompts to `author-execution-relay`.
- Review topology and convergence semantics route to `design-review-loop`. Agent-code supplies its call, parsing, recovery, budget, tool-loop, and evidence primitives; it does not confer convergence.
- Fleet specialist construction (requirements, handoff, fleet interface) routes to `agent-builder`.

## Proof boundary

These are requirements, not proof of provider neutrality or injection resistance. The current proving scope is one standalone Python specialist with a direct Anthropic binding. Other providers, side-effect reconciliation, PostgreSQL, concurrency and orchestrators remain unproved.
