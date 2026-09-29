# HEB-154 integration map — proposed decisions

Recommendation: integrate the accepted corrected candidate with minimal mechanism changes, prove the separate Python installation, and retain HEB-154 as one component of the HEB-161 bundle. No source edit is made before the decisions below.

## Verified starting point

Fresh-fetched main and isolated checkout base: `2ab76b447cdb1a975c801e6833682c0c1f94cef0`, package manifest `9.1.0`.
Checkout: `/Users/thaffey/.codex/worktrees/heb-154-integration/bedrock` (managed, initially clean detached checkout). No attached reusable worktree existed in this chat. Other registered checkouts were not assumed free. Create `codex/heb-154-integration` before implementation.

The complete corrected-candidate path set and every SHA-256 match the frozen candidate manifest. A deliberately false digest in a disposable manifest was rejected. The proof archive matches `7e574fa699fcd855b67f535627a9d22c1ad7b526694d3fce2dabd42d42232fdc` and remains unchanged. See input-verification.json. Private-term candidate scan had no hit and its injected-term control fired; no term is retained.

The old proving checkout is preserved. preserved-checkout-inventory.json records all Git-reported tracked/untracked changed paths and their bytes; ignored files are excluded. This is a mechanical inventory, not a semantic review of the old campaign. Do not stage or clean it.

## Decisions for Tad

**D1 — Separate library distribution.** Recommend `packages/agent-core/` as one separately installable Python distribution in this repository. Build a wheel from the reviewed source and install it into a consumer virtual environment, with exact source/wheel identity and a hash-pinned qualified dependency closure. Published installation points to the accepted Bedrock source/tag and subdirectory, never a Working path or a mutable package-index name. Candidate probes use a disposable environment. The plugin does not run pip or modify a global Python environment. `agent-builder` requires the library; portable `agent-code` retains its alternative conforming-implementation seam. Keep provider SDKs and persistence outside the core. Preserve Python >=3.10 / jsonschema>=4.17 compatibility declarations initially, but test the declared minimum and qualified interpreter before claiming installation support. Any unreachable matrix row is unavailable, not passed. This choice is substantive because plugin installation alone will not satisfy agent-builder's executable prerequisite. Extend acceptance/landing identity checks to cover the separate library source as well as marketplace/plugin bytes. No new package registry, automatic updater, or provisioning service.

**D2 — Library license.** The supplied pyproject says `Proprietary`; Bedrock's repository and manifest say MIT. Recommend distributing this library under Bedrock's MIT license if Tad authorizes that treatment of the supplied source. Preserve the imported metadata until that decision. This is a distribution-rights choice, not a routine packaging correction.

**D3 — Truthful portable unknown usage.** Recommend a narrowly scoped successor portable evidence schema with explicit known/unknown status. Known totals are measured nonnegative integers; unknown totals are null. Preserve known subtotals and outstanding reserved exposure in separate fields, plus an unknown reason. Never relabel reservation as consumption or encode unknown as zero. Unknown usage stops further dispatch and cannot accompany succeeded. Missing response on a pre-call failure is explicit absence, not a synthetic response hash. Count model attempts and physical tool dispatches separately; retain the zero-model false-success and one-model/one-tool positive controls. Core EvidenceRecord v0.1 remains unchanged; mapping is adapter-owned. This changes a public evidence contract and therefore requires versioned migration.

**D4 — Routing and versions.** Recommend agent-builder as the primary route for a requested checked fleet specialist and handoff; agent-code remains the mechanism authority and primary route for bounded LLM-call implementation/conformance. Testing, diagnosis and finished-diff review retain their owners. Add machine-readable, versioned sibling/core dependencies and explicit unavailable behavior. Derive: agent-code contract 1.0.0 -> 2.0.0, new agent-builder contract 1.0.0, portable evidence schema 1.0.0 -> 2.0.0, package portable-core 2.0.0 -> 3.0.0, Bedrock 9.1.0 -> 10.0.0 candidate. These follow the new evidence break/routing split, not the historical ticket targets. Python implementation remains 0.2.0 and core evidence shape v0.1 unless implementation changes independently warrant a bump. Claude adapter and generator contracts remain unchanged unless their actual format changes. Amend ADR/routing/migration authorities coherently without altering the product-owned orchestration principle. Fourteen routable skills means new exact inventory and generated carriers. The supplied agent-code entrypoint exceeds the repository budget by a whitespace-word count; move detail into a bundled reference with no normative loss rather than enlarge the budget.

**D5 — Bundle boundary.** Recommend complete HEB-154 integration, offline/installation proof and independent review on its isolated branch; feed that candidate into HEB-161. Do not claim the bundle accepted or update production yet. Fresh ticket metadata has HEB-153 and HEB-159 Planned, HEB-160 Planned, HEB-155 In Progress; their implementation is outside this request. HEB-151 is Done and current main implements pre-merge acceptance. HEB-161 remains Todo and still includes these components. A separate HEB-154 release would change the bundled-release disposition and needs a separate decision. HEB-119's Done status reflects historical v8.1.0 acceptance, not acceptance of this candidate.

**D6 — Live routing gate authorization.** Recommend authorize only the existing package routing evaluations as a separate release-validation budget: one PR-profile run and one release-profile run, maximum USD 3 each / USD 6 aggregate, no automatic repair reruns without a new disposition. This does not reopen the eight-case trial. The kickoff currently prohibits new live calls, while GitHub requires live-routing and the workflow runs it automatically for every PR. Therefore keep PR creation/update pending until this conflict is resolved. If the prohibition remains absolute, complete local offline integration/review and record live-routing, PR and release acceptance as blocked; do not disable or fake the gate. Recheck final command/model/population and aggregate ceiling before launch; any conflict stops launch. Ordinary CI's required Docker/Terraform checks do not authorize resuming the parked local Docker/APFS experiment.

## Edit map

`proposed-file-map.json` is the exact proposed destination list, with source paths/digests and each edit's basis. It is not yet a staging allowlist. After ratification, remove unused conditional paths and reconcile the complete final diff before staging.

| Work | Source / authority | Destination and purpose |
|---|---|---|
| Portable rules and references | Corrected agent-code, R1/R3/F1-F3 | plugins/bedrock/skills/agent-code; preserve whole-first parser policy and explicit proof limits; resolve D3 and size budget |
| Construction process | Corrected agent-builder, R1/R2 | plugins/bedrock/skills/agent-builder; replace obsolete never-tested/copy-install narration with bounded proof and real dependency contract |
| Shared implementation and tests | Complete corrected agent_core_pkg | Proposed packages/agent-core; retain parser/accounting/diagnostic regression cases and separate identities |
| Test consumer | Trial artifact manifest, build-use trace and regression suite | tests/fixtures/agent-readiness; adapt bootstrap/import identity for clean installed core; retain SDK and evidence-persistence controls; no live execution |
| Portable evidence semantics | R1 truthfulness, original B1 controls, D3 | Schema, validate_agent_review_contracts.py, fixture definitions and focused tests |
| Installation and dependencies | D1, current self-containment contract | Library build/lock files, declared dependency records, clean-install verifier and wrong-package/missing-install controls |
| Routing and compatibility | R1 split, D4, current lifecycle/ADR | Architecture, migration, registry, compatibility, quickstart, exact-inventory validators and routing fixtures |
| Package transaction | Manifest sole authority, D4 | Manifest/changelog/catalog metadata; regenerate all identity carriers with existing tooling; regenerate inventory |
| Proof and closure | R1-R3, accepted trial, current gates | New docs/evidence/heb-154/integration records; historical files unchanged; exact integrated identities and failures/retests retained |

Provider adapters still own SDK status/usage normalization, prospective reservations, request/response identity, evidence mapping/persistence, cancellation and verified terminal predicates. The core constructs records; it does not itself prove terminal truth. PostgreSQL, concurrency, write/reconciliation, other providers and fleet readiness remain unproved.

## Fourteen AC2 dispositions

These are reconciliation of ratified R1-R3, not new waivers. Retained trial claims apply only to their exact subjects. New integrated bytes require fresh tests.

| Original obligation | Ratified disposition and retained proof | Remaining integration proof |
|---|---|---|
| AC2-schema-negative | R1 replaces old v2 layout; retain malformed/contradictory evidence rejection | D3 schema + semantic invalid controls |
| AC2-schema-positive | R1 replaces layout; retain valid model-only and model-plus-tool behavior | Reproduce original false rejection against integrated validator |
| AC2-budget-joint | Retained; F2 repair and trial reservation/unknown-usage controls | Core + adapter regression suite against installed bytes |
| AC2-terminal-truth | Retained, adapter-owned; trial no-result-on-failure and emergency supersession controls | Zero-attempt/unknown/truncation/persistence controls, public evidence validation |
| AC2-side-effect-unknown | R2 excludes writes/reconciliation from adoption claim; unsafe retry prohibition retained | No new write campaign; explicit unproved boundary |
| AC2-salvage-bounds | R3 retained; F1/F3 + independent quote/depth first failure and repair | Full parser regression set against integrated source/wheel |
| AC2-profile-complete | R1/R2 replace three schema-bound profiles with exact Anthropic trial binding | Accurate shipped profile, source/dependency identity, no broad-provider claim |
| AC2-profile-live | R2 replacement trial accepted, two smokes + six held-out, one draw each | No further trial calls; retained evidence only |
| AC2-context-integrity | Retained trial logical request hashes/order, SDK wire mock and sanitized reuse | Replay exact SDK/body/order controls; retain provider-added-byte visibility limit |
| AC2-provenance-total | R1 replaces general total-provenance machinery | Pin authorities/dependencies for actual integrated claims and install proof |
| AC2-otel-pin | R1 excludes exporter/mapping proof; future selected mapping still must be pinned | Explicit unavailable/not-claimed status |
| AC2-routing | Retained and open | New route's positive/negative/collision/prose population; D6 live gate |
| AC2-consumer | R2 replaces fulfillment/two-provider campaign; accepted specialist trial with disclosed interventions | Portable clean install and offline consumer replay; no expanded task-quality claim |
| AC2-cold-review | Repaired mechanism review + operator trial acceptance retained | Independent finished-delta review and HEB-119 cold acceptance of composed candidate |

Proof pointers: current-package-review/assessment.md, ratification.md, proposed-trial.md; correction-evidence/candidate-manifest.json, correction-result.md, closure-review.json (including first depth failure); trial-agent/BUILD-USE-TRACE.md, EVIDENCE-MAPPING.md, artifact-manifest.json, dependency-identity.json and offline-observations/run-1 through run-10; attended-live/bounded-trial-result.md/.json and operator-ratifications.jsonl. All sit under the supplied Working roots; durable immutable proof is the pinned accepted-bounded-trial archive. No original proof is rewritten.

## Gate and read boundaries

Read whole: kickoff; local and current-main orientation; recall bedrock sheet; current lifecycle/manifest/registry/compatibility; applicable validation definitions and CI workflow; current ADR/routing/migration; supplied assessment/ratification/trial/correction/closure/manifest; every corrected candidate file; named trial manifests, builder trace, handoff, evidence mapping, test logs; accepted result and operator ratifications; session-close retrospective and tracker update. HEB-154's latest disposition and all returned comments, HEB-161's full description/relations and empty comment population, HEB-119's contract and latest historical acceptance comment were read. Nonempty HEB-154 comments provide a positive connector control for HEB-161's empty result.

Partial/excluded: historical portions of HEB-154's long ticket, HEB-119's older comments, detailed HEB-155 design, old proving checkout content, recursive unrelated skill bodies, trial implementation source and downstream gate programs beyond focused discovery. Large combined outputs were partial reads; relevant authorities above were recovered separately. Existing run-4 pytest log itself contains an abbreviated diagnostic list; no missing text was reconstructed. Gate programs and adapted trial source must be read whole and pinned before execution/edits. No whole-repository review is claimed.

Current Git protections require deterministic and live-routing, strict freshness, and apply to admins. GitHub permits merge commits (also squash/rebase in UI); repository release contract permits only the accepted-source-preserving merge commit. No branch rules returned; branch-protection endpoint was positive. Native sandbox network failure was followed by a successful approved read; no capability gap inferred. Git is not shallow; no tracked submodule/attribute entries; global LFS configuration exists but no tracked filter assignment was found. No active hooks appeared in the common hooks directory; no signing or sparse-checkout configuration appeared in the scoped configuration population. Preserve all settings and recheck before mutation.

After D1-D6: integrate -> clean wheel + source/adapter regressions -> deterministic/strict-host/isolated install/routing gates -> independent review -> intended commit/PR -> composed HEB-161 freeze -> HEB-119 cold acceptance -> explicit proceed -> merge-commit landing/equivalence -> immutable tag/release -> fresh-session supported-surface rollout. Every gate records confirmed/falsified/unavailable, exact source/dependency/fixture subject, discrimination control, literal result and durable pointer. Historical test counts cannot fill a new gate.

Current stopping point is substantive decisions, as explicitly requested by the kickoff. No commit, PR, installed-cache edit, model API call or production update has occurred. Existing proof cleanup is unauthorized. Previous retrospective/harvest is complete and will not be duplicated.
