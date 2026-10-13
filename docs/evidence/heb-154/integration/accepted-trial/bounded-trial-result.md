# Bounded live trial result

Recorded 2026-09-29 07:36:40 -0400, America/New_York, from native shell.

**Accepted by Tad at 2026-09-29 07:40:57 -0400, America/New_York: final-case pass and this named bounded trial.**

All two development smokes and six frozen held-out cases ran once and matched their declared readiness, missing-rule sets and grounded explanations. This supports one corrected build on one direct Anthropic binding, not statistical reliability or fleet readiness.

| Case | Result | Missing rule | Ratified verdict |
|---|---|---|---|
| dev-complete | ready | None | Pass |
| dev-vague | needs_clarification | R-ACCEPTANCE | Pass |
| eval-complete | ready | None | Pass |
| eval-objective | needs_clarification | R-OBJECTIVE | Pass |
| eval-acceptance | needs_clarification | R-ACCEPTANCE | Pass |
| eval-conflict | needs_clarification | R-CONSISTENCY | Pass |
| eval-hostile | ready | None | Pass |
| eval-approval | needs_clarification | R-ACCEPTANCE | Pass |

Build-use verdict: pass with disclosed root interventions, per BUILD-USE-TRACE.md. The fresh builder used the actual external corrected core. Program verdict: 57 core tests and 91 trial-agent tests passed; complete live request, tool, usage, parse and terminal evidence reconciles. Task verdict: every held-out case meets its frozen expected result and explanation criteria.

Recorded model usage: 21,656 input + 2,902 output tokens = 24,558 total; $0.036166. Eight invocations, 16 model calls, 16 token-count preflights, eight actual policy executions, 32 unique evidence records. Dollar figures use reported usage and the pinned rates; they are not a billing-statement audit.

The original 90-minute build/evaluate and initial 15-minute live windows expired and were surfaced. Explicit timing amendments authorize the fresh live window and 30-minute continuation; original evidence remains unchanged and cumulative call, token and spend limits were carried forward. No failed case was rerun and no extra draw occurred.

The eight-case limit is now exhausted; no further live invocation is authorized. Final-case pass and bounded-trial acceptance are ratified. Integration, ticket closure and release gates remain separate.

Detailed records: bounded-trial-result.json, each *-review.json, operator-ratifications.jsonl, continuation-amendment.json, and the two preserved live ledger directories. Offline first failures, interventions and synthetic mock provenance corrections remain in the frozen handoff.
