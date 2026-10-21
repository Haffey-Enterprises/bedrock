# agent-core 0.2.1 — binding to agent-code (non-normative)

This page maps the portable **agent-code** contract to the fleet’s shared Python package **agent-core 0.2.1**. It does not amend agent-code. Where the binding is narrower or uses different vocabulary, adapters must preserve portable meaning when emitting cross-host evidence.

The 0.2.1 distribution corrects company-only license notices and its version identity;
mechanism behavior and evidence schemas are unchanged from 0.2.0.

## Role

| Artifact | Role |
|----------|------|
| agent-code | Portable mechanism rules |
| agent-core 0.2.1 | One Python implementation of a ratified subset (fleet wheel dependency) |
| agent-builder | Process for building specialists that **depend on** agent-core |
| `agent-execution.schema.json` | Minimum portable evidence envelope |

agent-core’s `EvidenceRecord` is **core-owned for v0.1** (fleet persistence). It is not a drop-in replacement for the portable schema. Map required fields through an adapter before claiming portable conformance.

## Disposition vocabulary

| agent-code / agent-execution | agent-core `TerminalDisposition` |
|------------------------------|----------------------------------|
| `succeeded` | `success` |
| `schema_failed` | `parse_failed` or `schema_invalid` |
| `budget_exhausted` | `budget_exhausted` |
| `transport_failed` | `provider_error` |
| `tool_failed` | `tool_error` / `tool_denied` |
| `cancelled` | `cancelled` |
| `escalated` | (not in core; use payload or host extension) |

## Parse path vocabulary

| agent-code | agent-core `ParsePath` |
|------------|-------------------------|
| `native` | (profile/provider; not a separate core path) |
| `whole` | `direct` |
| `salvaged` | `salvage_fence` or `salvage_first_object` |
| `failed` | `failed` |

`salvage_first_object` is a compatibility label for **balanced-object salvage**, not a guarantee that the chosen span was first in document order when uniqueness selected the sole valid object.

## Units and budget fields

| Portable | agent-core 0.2.1 |
|----------|------------------|
| Spend | US dollars (`max_spend` / `spend_used`); convert to/from micros in adapters |
| Deadline | `max_wall_seconds` (monotonic elapsed) vs portable `deadline_ms` |
| Tokens | Single `tokens_used` vs portable input/output split |
| Concurrency | Not enforced in core (single-threaded loop by design) |

**Prospective bounds:** `Budget.check` admits on past consumption. The **provider adapter** must apply remaining allowance to each call and must not declare `success` after reconciled usage exhausts shared limits unless overshoot was explicitly ratified.

## Identity stamping

agent-code requires context-sourced stamps including actor, invocation id, model, schema version, prompt hash, and attempt number. agent-core 0.2.1 stamps fleet identity on output (`agent_id`, `session_id`, `invocation_id`, `parent_invocation_id`, `run_id`, `project_id`) after stripping reserved keys from model data. Model, prompt hash, schema version, and per-attempt detail belong in the **profile/adapter** and/or evidence `payload` until a later core version lifts them into first-class fields. They must still not be taken from model claims.

## Structured output (aligned behavior)

- Top-level objects only; portable array grammar is outside this binding.
- Whole-only by default; optional single outer fence; embedded scan only with explicit best_effort=True and allow_salvage=True. Whole decoding takes precedence over candidate extraction.
- Reject duplicate keys and byte/depth/candidate-limit breaches as typed failures. Defaults: 65,536 response UTF-8 bytes, depth 64, 64 enumerated spans.
- ParseResult and StructuredOutputError expose diagnostics with candidate_count, schema_valid_count, validation_failure_count, up to 16 content-safe validation failure codes and reason; adapters map these without re-parsing. Counts cover decoded occurrences of the selected grammar; resource breaches mean the scan did not complete. Response hashes remain adapter-owned.
- Strict schema validation (jsonschema Draft 2020-12 in core).
- Content capture off by default; metadata-oriented evidence payload in USAGE examples.

## What agent-core intentionally omits

Provider SDKs, multi-agent orchestration, PostgreSQL clients, parallelism, circuit breakers, full MCP negotiation, and OpenTelemetry exporters. Those stay in profiles, adapters, or optional extensions ratified separately.

## Version

Binding written for **agent-core 0.2.1**. Revisit this page when core major/minor mechanism surface changes.

## Portable evidence v2 mapping

The adapter records physical model attempts and tool dispatches separately. Tool
rows include their logical tool iteration. A tool dispatch does not consume the
model-attempt ceiling. Preserve input/output token splits and convert USD to
integer micros with a declared rounding policy.

Known totals equal `known_subtotal` and have zero `reserved_exposure`. Unknown
usage has null totals, an explanation, the known subtotal and outstanding reserved
exposure in separate fields. It stops further dispatch and cannot be `succeeded`.
Do not reinterpret core conservative reservation counters as measured consumption.
An absent response maps to `response_status: absent`, null response hash,
`path: failed` and zero candidates. A success requires an actual model attempt and
one schema-valid candidate (`schema_valid_count`), while `candidate_count` preserves
all decoded candidates. A permitted salvage can inspect several candidates and
accept exactly one schema-valid candidate. Schema validity alone does not prove task completion.
