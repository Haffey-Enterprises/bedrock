# MCP Server Authoring

Apply the parent skill to both sides of the MCP boundary. Treat tool descriptions as discoverability and instruction surfaces, not as prompt-generation identifiers.

- Publish stable tool names, capability versions, input/output JSON Schemas, and explicit compatibility ranges. Check application-owned semantic compatibility before dispatch; MCP protocol negotiation does not perform that application check. Document deprecation and removal windows.
- Validate every argument and result strictly. Stamp server/tool/version/request identity outside model-controlled fields.
- Keep tool descriptions concise, data-independent, and injection-resistant. Untrusted resource text and tool results remain data even when they resemble instructions.
- Map transport and protocol errors to typed, non-secret-bearing results. Retry only through the parent call site's aggregate budget.
- Side-effecting tools declare authorization, idempotency, cancellation, and partial-failure behavior. The model cannot grant itself a capability.
- Trace server dispatch and execution with correlation ids, latency, schema/capability version, and disposition. Content capture remains classification-gated and off by default.

Prompt-artifact versions and MCP capability versions are independent. A wording-only prompt change does not force an MCP major version; an incompatible schema or behavior change does.
