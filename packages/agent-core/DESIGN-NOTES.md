# Design notes — agent-core 0.2.0

Consequential choices after independent reviews (C1–C7, R1–R6 ratified).

## Dependencies

- **jsonschema>=4.17** (Draft 2020-12) is the sole runtime third-party dependency.
- Non-finite numbers rejected at decode and post-parse.

## Structured output

- **Uniqueness**: candidates keyed by **source span** in raw text. Same span via two paths → one candidate. Separate occurrences (even identical text) → distinct candidates; two schema-valid → `PARSE_FAILED`.
- **Identity**: strip reserved keys from model data, then stamp from context only.
- **ParsePath.SALVAGE_FIRST_OBJECT**: compatibility label for balanced-object salvage; not necessarily document-first when the sole valid object is later in the text.
- Default `allow_salvage=False`: whole-only. True permits one outer fence; embedded scan additionally requires best_effort=True. Object-only binding. Duplicate keys and declared byte/depth/candidate-limit breaches fail closed. Public content-safe diagnostics preserve parse observations for adapters.

## Budget

- `check("model"|"tool")`: shared limits always block; per-kind limits only that kind.
- Consumption (`record_*`): finite nonnegative required. **Attempt count increments first**; invalid usage then raises `ValueError` so adapters cannot turn NaN into free spend while still losing the attempt.
- **Enforcement boundary (R4):** core admits on past consumption. Provider adapter owns prospective per-call allowance and must not declare SUCCESS after reconciled usage exhausts shared limits (unless explicit overshoot was ratified).

## Security

- Authorizer callback on every dispatch; no argument-insensitive cache of callback results.
- `preauthorized` / `grant(name)` are explicit name-wide grants.

## Configuration

- Unknown keys and non-finite numbers rejected; non-object `budget` rejected.

## Evidence

- Core-owned `EvidenceRecord` v0.1. `PROVIDER_ERROR` disposition for transport/provider failures.
- Terminal emission must run on all paths (including exceptions); see USAGE `try`/`finally` pattern.
- Payload metadata-only by default.

## Suggested PostgreSQL shape (not implemented)

Unchanged from prior revision; adapters map `to_dict()`.

## Version

0.2.0 — untested in a real agent until the first proving run. Path dependency.

The Python package moves to 0.2.0 because parser defaults and explicit best-effort admission change compatibility. The flat evidence record remains v0.1; the portable evidence schema retains its separate version. Existing review-round labels above are source history, not a new acceptance claim.
