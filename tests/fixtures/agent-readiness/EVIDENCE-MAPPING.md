# Core-to-evidence mapping 1.0.0

The canonical JSONL lines are constructed by external `agent_core.emit_evidence`, yielding the core-owned EvidenceRecord v0.1. The adapter adds a namespaced payload without replacing identity/budget/parser/tool mechanisms. `evidence_ref` identifies a file and core-generated record_id, or an explicit emergency stderr record.

| Required meaning | Exact source and persisted location |
| --- | --- |
| Actor/invocation/session/project/run/version | Caller-owned InvocationContext; core fields agent_id, invocation_id, session_id, project_id, run_id, agent_version, core_version |
| Record identity/time | Core-generated record_id, timestamp_utc |
| Model/profile/provider | Trusted config; payload.model, payload.profile, payload.provider; never model-claimed identity |
| Prompt identity | Actual system bytes in each payload.request.system; invocation payload.prompt_version and prompt_sha256 |
| Output schema | Versioned task schema bytes; payload.schema_version and schema_sha256; native grammar schema is captured in exact request output_config |
| Ordered requests | campaign.jsonl preflight_dispatch/reserve in append order, request and canonical request_sha256; matching model_attempt child has request/hash |
| Physical attempts | One reserve event and one usage event for each create; core record_model_attempt called once, including fault/unknown; attempt and attempt_id on child |
| Provider finish/stop and response | Child payload.stop_reason, response.id/request_id/model/content/usage and response_sha256; unknown blocks retain type only; raw SDK errors/headers/reasoning never captured |
| Parser observations | Core parse_path plus payload.parse_diagnostics via dataclasses.asdict(ParseDiagnostics); original final text hash in response_text_sha256; model_text_sanitized records hygiene transformation |
| Usage and spend | Core flattened tokens_used/spend_used are actual usage plus any retained reservation; payload.known_usage stores known input/output/microdollar subtotal and usage_status explicitly distinguishes unknown |
| Remaining allowance | payload.budget_remaining and campaign_snapshot are core snapshots: used and maximum values, elapsed seconds; subtraction derives remaining, never an independent mechanism |
| Tools | Real tool_dispatch journal event before local execution; core check_capability/SecurityBoundary/correlate_results; tool_execution child contains request/result, capability version, actual_dispatch and disposition |
| Failed tool persistence | payload.failed_tool_observation records actual dispatch/execution and failure when child cannot persist; no fabricated success result |
| Child correlation | Core records share invocation_id; terminal payload.children lists their record_ids |
| Cancellation/transport failures | Core cancelled/provider_error/budget_exhausted disposition; fixed error_code, explicit unknown usage, retained reservation; no raw exception body |
| Terminal result | Core disposition plus invocation payload.error_code; returned task_result is null on every failure; emergency corrections explicitly supersede prior records with supersedes_record_id and prior_record_persistence |

Portable agent-execution 1.0.0 mapping: core success→succeeded; parse_failed/schema_invalid→schema_failed; provider_error→transport_failed; tool_error/tool_denied→tool_failed; budget_exhausted and cancelled retain names. Direct parse→whole, core salvage paths→salvaged, absent/failed parse→failed. `attempts` maps the model_attempt/tool_execution children in persisted order, with ordinal, kind and child disposition. Prompt and output_schema map version/hash pairs. Core spend dollars converts to integer microdollars; budget deadlines map sixty seconds to 60000 milliseconds. The single core combined-token limit is 500000; per-call output is 1024 and per-invocation maximum output is 3072. Both the combined bound and prospective reservations remain visible in config and snapshots.

For known usage, payload.known_usage maps to portable usage directly. For unknown usage the original portable schema cannot truthfully express null/unknown consumption. This trial does not emit a falsely conforming portable object: preserve the core record with usage_status unknown, known subtotals and retained-reservation exposure. A future explicitly versioned portable schema amendment is required before claiming complete portable serialization of unknown usage. No PostgreSQL export or OpenTelemetry conformance is claimed.

Request hashes use compact UTF-8 JSON serialization of the application parameter object; native MockTransport asserts the SDK-generated body carries those exact values (including temperature via extra_body). They are logical request hashes, not hashes of authorization headers or raw HTTP wire bytes. Response hashes on children cover the sanitized permitted-content projection; original_text_block_sha256 preserves each original text block hash before sanitization, and final response_text_sha256 covers original final text. Assistant history is reused only from the sanitized projection. Forbidden terms never appear in returned task text or persisted content.
