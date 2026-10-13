# Structured-output mechanism contract

Normative continuation of agent-code.

## Structured output: parse, salvage, validate, recover

Model output is untrusted inbound data. Each call site declares a machine-readable generation contract: envelope grammar, strict item schema, identity-stamping rule, recovery policy, and terminal failure disposition.

1. Prefer provider-native constrained output where the selected profile supports it. The portable contract does not assume that capability.
2. Parse the whole expected payload first. Load-bearing calls use whole-only parsing or explicitly permit one outer markdown fence. Reject duplicate keys and declared response-byte/depth-limit breaches with typed failures. Embedded object/array scanning is allowed only at explicitly declared best-effort call sites with bounded candidate enumeration; it must not reinterpret a decoded but schema-invalid whole payload.
3. Accept salvage only when exactly one candidate passes the strict schema. Zero valid candidates fails; two or more valid candidates is ambiguous and fails. Never accept “the first parseable payload.”
4. Identify candidates by **source occurrence (span)** in the raw text where practical: the same span discovered by two paths (for example fence body and balanced scan) is one candidate; two separate occurrences remain two candidates even if their text is identical.
5. Stamp actor identity, invocation id, model, schema version, prompt hash, and attempt number from invocation context—not model claims. A binding may place some of these on the structured output object, in the evidence record, or both; none may be taken from model-claimed fields.
6. Record the parse path (`native`, `whole`, `salvaged`, `failed`), candidate count, validation failures, and the response hash. Raw prompt or completion content is retained only when the call site's data classification, consent, redaction, access, location, and retention policy allow it. Content capture is off by default.
7. Recovery is position-specific. A load-bearing call retries only within the aggregate budget and otherwise aborts or escalates; a best-effort call may drop an item observably. Never fabricate an exit-path value.

Reasoning has schema-specific outlets. Some schemas need no rationale; others permit one or more bounded explanation fields. Do not impose a universal rationale field.

`reference/agent-execution.schema.json` is the minimum portable evidence envelope. Implementations may add namespaced fields but may not weaken its required provenance, accounting, and disposition fields.
