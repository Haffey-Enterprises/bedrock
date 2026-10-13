# agent-core 0.2.0 — Usage for specialist agents

The accepted source has one bounded direct-Anthropic specialist trial. New builds
require their own package and consumer checks; other bindings remain unproved.

This package is the sole implementation of the mandatory substrate. Every LLM-calling agent must depend on it; do not re-implement these invariants.

**Evidence record is core-owned for v0.1.** Adapters map `EvidenceRecord.to_dict()` into PostgreSQL (or any external schema). The core does not implement a database layer.

## Install

```bash
python -m pip install -e packages/agent-core
# source development only; agent-builder installs the shipped wheel for consumers
```

Requires Python ≥ 3.10.

## Budget enforcement boundary

`Budget.check` admits based on **past** consumption. Configuring `max_spend` / `max_tokens` / `max_wall_seconds` does **not** by itself keep a one-call agent under the agreed bound.

The **provider adapter** must:

1. Pass a prospective remaining allowance into each provider call (tokens/spend/time).
2. Reconcile actual usage via `record_*` after the call (including failed transport).
3. **Not** emit `SUCCESS` if the reconciled snapshot is exhausted on shared limits, unless an explicit overshoot was ratified before the run.

If a provider cannot honor a chosen bound, surface that limitation before the trial.

## Minimal agent loop sketch (exception-safe)

```python
from agent_core import (
    Budget, BudgetExhausted,
    ToolRegistry, check_capability, correlate_results,
    parse_structured, stamp_identity, StructuredOutputError,
    InvocationContext, emit_evidence,
    SecurityBoundary, AuthorizationError,
    ToolCapability, ToolRequest, ToolResult,
    TerminalDisposition, ParsePath, SideEffectClass,
    load_config, CORE_VERSION, DEFAULT_IDENTITY_KEYS,
)

cfg = load_config("/path/to/agent_config.json")
ctx = InvocationContext(
    agent_id="standards-checker",
    session_id="sess-abc",
    project_id="proj-1",
    run_id="run-1",
    agent_version="0.2.0",
)
budget = cfg.make_budget()
registry = ToolRegistry([
    ToolCapability(
        name="lookup_standard",
        input_schema={
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
            "additionalProperties": False,
        },
        side_effect=SideEffectClass.NONE,
    ),
])
boundary = SecurityBoundary(preauthorized={"lookup_standard"})

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "compliant": {"type": "boolean"},
        "findings": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["compliant"],
    "additionalProperties": False,
}

disposition = TerminalDisposition.UNKNOWN
parse_path = None
final_payload = {}  # metadata-only by default

try:
    while True:
        budget.check("model")

        # Adapter must reserve a proven upper bound before dispatch. These
        # numbers describe this synthetic sketch, not a provider guarantee.
        reserved_tokens, reserved_spend = 1100, 0.006
        try:
            # Provider call only: SDK automatic retries must be disabled.
            raw = '{"compliant": true, "findings": []}'  # placeholder
            actual_tokens, actual_spend = 100, 0.001
        except Exception as transport_err:
            # Count once with conservative exposure, NOT invented zero usage.
            budget.record_model_attempt(tokens=reserved_tokens, spend=reserved_spend)
            disposition = TerminalDisposition.PROVIDER_ERROR
            final_payload = {"error": type(transport_err).__name__,
                             "usage_status": "unknown", "accounting_basis": "reserved_exposure"}
            raise

        try:
            # Invalid reconciliation counts the physical attempt before raising.
            # It must never re-enter the transport handler or record a second one.
            budget.record_model_attempt(tokens=actual_tokens, spend=actual_spend)
        except ValueError:
            disposition = TerminalDisposition.PROVIDER_ERROR
            final_payload = {"error": "usage_reconciliation_failed", "usage_status": "unknown",
                             "reserved_tokens": reserved_tokens, "reserved_spend": reserved_spend}
            raise  # retain the reservation in the adapter and stop dispatch

        try:
            result = parse_structured(
                raw, OUTPUT_SCHEMA, allow_salvage=cfg.allow_salvage
            )
            parse_path = result.parse_path
            data = stamp_identity(
                result.data,
                ctx.identity_map(),
                identity_keys=cfg.identity_keys,  # config controls output stamping
            )
            # Evidence provenance always comes from InvocationContext / emit_evidence;
            # identity_keys only affects which keys are stamped onto model output.
            snap = budget.snapshot()
            if snap.exhausted_shared() is not None:
                disposition = TerminalDisposition.BUDGET_EXHAUSTED
                final_payload = {"exhausted": snap.exhausted_shared(), "output_keys": list(data.keys())}
            else:
                disposition = TerminalDisposition.SUCCESS
                final_payload = {"output_keys": list(data.keys())}
            break
        except StructuredOutputError as e:
            parse_path = e.parse_path
            disposition = TerminalDisposition.PARSE_FAILED
            final_payload = {"parse_error": str(e)}
            break

except BudgetExhausted as e:
    disposition = TerminalDisposition.BUDGET_EXHAUSTED
    final_payload = {"exhausted": e.dimension}
except Exception:
    if disposition == TerminalDisposition.UNKNOWN:
        disposition = TerminalDisposition.PROVIDER_ERROR
    raise
finally:
    # Always emit terminal evidence (success, parse failure, budget, provider error)
    record = emit_evidence(
        ctx,
        disposition,
        parse_path=parse_path,
        budget_snapshot=budget.snapshot(),
        payload=final_payload,
    )
    # persist record.to_dict() via adapter — not done here

print(record.to_dict())
print("core_version:", CORE_VERSION)
```

## Tool dispatch

```python
requests = [
    ToolRequest(request_id="c1", name="lookup_standard", arguments={"id": "ISO-1"}),
]
results = []
for req in requests:
    budget.check("tool")
    budget.record_tool_iteration()
    cap = check_capability(registry, req.name, req.arguments)
    boundary.authorize_tool(cap, req.arguments)
    results.append(ToolResult(req.request_id, req.name, ok=True, content={"text": "..."}))

ordered = correlate_results(requests, results)
```

## File-controlled configuration

```json
{
  "allow_salvage": false,
  "budget": {
    "max_model_attempts": 6,
    "max_tool_iterations": 12,
    "max_tokens": 64000,
    "max_spend": 0.50,
    "max_wall_seconds": 120.0
  },
  "identity_keys": [
    "agent_id", "session_id", "invocation_id",
    "parent_invocation_id", "run_id", "project_id"
  ]
}
```

Unknown keys and non-finite numbers are rejected. `max_spend` is US dollars. Default `allow_salvage` is `false` (whole-only). `true` permits one outer fence, not embedded scanning.

## Parser modes, bounds and diagnostics

The parser accepts top-level objects only. Default is whole-only; `allow_salvage=True` additionally permits a single outer fence. Embedded scanning requires both `allow_salvage=True, best_effort=True` and a declared best-effort call site. A decoded whole payload is never reinterpreted by extracting a nested object after schema failure.

Defaults: 65,536 UTF-8 response bytes, nesting depth 64, at most 64 enumerated salvage spans. A call site may declare other positive limits. Duplicate keys, non-finite constants and limit breaches fail with `StructuredOutputError`; arrays are outside this Python binding. Whitespace is trimmed before source-span comparison. Two separate valid occurrences remain ambiguous even when identical. `SALVAGE_FIRST_OBJECT` is a historical label, not first-candidate selection.

Both results and errors expose `diagnostics`: candidate_count (decoded occurrences), schema_valid_count, validation_failure_count, at most 16 content-safe validation failure codes, and reason. No candidate values, keys or schema error prose appear there. Counts cover the selected grammar; a limit breach prevents a complete candidate count and is identified by its reason, not reported as a clean scan. Use `dataclasses.asdict(result.diagnostics)` to map the metadata into evidence. `raw_text` remains sensitive to capture policy and is never automatically persisted. The adapter computes the response hash from the exact original bytes, supplies provider/model/prompt/schema/attempt identities and preserves unknown usage explicitly.

## What this package deliberately does not do

- No model-provider SDKs (adapters own prospective call bounds and transport)
- No multi-agent orchestration
- No database / PostgreSQL client
- No parallelism, circuit breakers, or MCP negotiation

## Version

Record `agent_core.CORE_VERSION` (`"0.2.0"`) in the fleet interface and evidence records.
