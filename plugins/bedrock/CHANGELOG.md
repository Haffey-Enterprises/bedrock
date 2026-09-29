# Changelog

The package manifest is the sole authority for the current version. This file
records candidate and released changes; a version heading is not release proof.

## 10.0.0 — bounded agent construction candidate

- Clarify that author-execution-relay routes requests to author executor-facing
  handoffs; direct implementation, build, and deploy tasks retain their domain
  owner even when gated. Routing fixtures and thresholds remain unchanged.

- Add agent-builder 1.0.0 for checked fleet-agent construction; agent-code 2.0.0
  retains LLM mechanism ownership. Portable core advances to 3.0.0.
- Integrate shared Python agent-core 0.2.0 under the Bedrock MIT license. Its
  reproducible wheel ships with agent-builder; projects explicitly install and
  pin the wheel and dependencies in their own virtual environment. Updates
  require project qualification.
- Advance portable agent-execution evidence to 2.0.0: unknown totals remain
  null, known subtotals and reserved exposure remain separate, absent responses
  have no hash, and tool dispatches do not consume model-attempt limits.
- Preserve the accepted one-provider bounded trial as repository history;
  distribute only skill resources and shared Python components. No broader
  provider claim or new specialist trial is implied.
- Cold acceptance, bundled-release coordination, and explicit production
  proceed remain required before release and rollout.

## 9.1.0 — claim-subject discrimination candidate

- Require diagnostic readings to demonstrate that their instrument
  discriminates the claim subject; treat a failed or unavailable control as
  unavailable evidence and require stronger discrimination before corrective
  action.
- Require planned silent-success checks to pair a clean exemplar with a
  known-dirty case that makes the named detector fire.
- Add routing evidence that preserves the boundaries among diagnosis, planned
  testing, and executor-handoff authoring.
- Require cold acceptance before marketplace landing and permit only a merge
  commit on `main`'s first-parent history whose second parent is the accepted
  source commit, with package-byte parity verified before release.

## 9.0.0 — portable-core 2.0 and derived-evidence candidate

- Advance the portable-core and design-review-loop contracts to `2.0.0`, move
  runner-backed workflow ownership to a generic external product binding, and
  require replayable binding, runner, schema, invocation, and fresh-gate
  evidence while preserving runner-free direct and multi-perspective review.
- Make execution relays bind claims to their subjects, derive comparison
  populations and expected state mechanically, discriminate claims before
  narration, and distinguish state changes from summary-only arithmetic or
  transcription defects.
- Reject every noncanonical recursive package-identity carrier consistently
  across synchronization, package governance, and the main validator, including
  fail-before-mutation behavior for identity writes.
- Define Claude Code 2.1.226 as the minimum supported host version, preserve
  exact host identities as execution evidence, and enforce the floor across the
  compatibility matrix, registry, and required CI.
- Retain migration, meaningful-red, deterministic, strict-host, install,
  rule-trigger, and three-draw routing evidence for the aggregate candidate.

## 8.4.0 — consumer-visible identity candidate

- Add a generated, byte-identical package identity carrier to every skill so a
  skill-only host can expose the authoritative manifest version and digest.
- Add deterministic generation, drift rejection, installed-package parity, and
  malformed, missing, stale, divergent, and contract-mutation coverage.
- Advance the Claude adapter contract to 1.1.0 for the compatible identity
  carrier surface; cold acceptance and rollout remain external gates.

## 8.3.0 — instrument-authoring candidate

- Derive relay demands and review charges from their consuming instruments,
  preserving accepted grammar and outcome taxonomies verbatim.
- Add author-time satisfiability, structural measurement, verdict-bearing pins,
  custody/reachability separation, edit-locus-derived touch sets, and premise
  falsification to relay and review-charge authoring.
- Require counterfactual detector proof when a standard defines success as an
  absence, with deterministic positive, negative, and adversarial cases.

## 8.2.0 — rule-trigger reliability candidate

- Require every reusable rule to name and classify its firing event,
  frequency, salience, enforcement, expected failure, and reliability
  disposition.
- Reject internal-state-triggered rules without an instrument, external
  detector, or explicit known-weak disposition.
- Add deterministic trigger-test behavior cases and retain the whole-corpus
  HEB-136 sweep evidence.

## 8.1.0 — package-governance candidate, pending HEB-119 acceptance

- Add enforceable lifecycle, compatibility, migration, rollback, support,
  deprecation, threat-model, rebind, and rollout contracts.
- Add machine-readable package authority, capability, skill-lifecycle, release
  evidence, and rollout-ledger records.
- Add repository/license metadata and installed-package license coverage.
- Add deterministic package-governance validation and required CI.

## 8.0.0 — recovery candidate, not consumer-released

- Correct the frontend portable contract and Haffey React/Vite profile.
- Add browser, accessibility, security, performance, and application-delivery
  seam evidence.
- Retain a 162/162 full routing population with zero excluded selections.

Earlier manifest versions were internal recovery candidates. They are preserved
in Git history and evidence records and are not retroactively represented as
tagged consumer releases.
