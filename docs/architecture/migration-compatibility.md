# Bedrock portable-core migration and compatibility notes

**Status:** ACCEPTED
**Version:** 3.0.0
**Date:** 2026-09-29
**Governing principle:** [ADR-001](../adr/ADR-001-portable-core-and-surface-adapter-architecture.md)

**Coverage boundary:** [Bedrock product coverage map](coverage-map.md)

## 1. Current state

The candidate is a Claude plugin with fifteen skill directories and a bundled separately versioned Python core. The repository has deterministic structure and routing validation, a clean-install smoke test, and a deterministic safety-contract validator with regression fixtures for the initial safety tranche. Registry and compatibility records declare core/adapter identities and capabilities. Separate Codex/OpenAI and Cursor adapters remain outside this candidate.

The current skill names are the compatibility anchors for this migration. Existing names and explicit invocations remain valid while content is separated into portable contracts and profiles.

## 2. Target compatibility model

The generated compatibility manifest will identify:

| Identity | Meaning |
|---|---|
| Core contract version | Version of portable skill identity, routing, authority, input/output/evidence, and safety semantics. |
| Actor contract version | Version of the bounded operation a recipe invokes, including its authority and result schema. |
| Product workflow binding | Product-owned identity for actor bindings, transitions, artifacts, operator gates, assurance profiles, and completion semantics. |
| Product execution capability | Product-owned durable-execution features required by its workflow binding. |
| Adapter name and version | Version of one host's registration, capability mapping, enhancements, permissions, and degraded behavior. |
| Package version | Version of the distributable aggregate. |
| Generator format version | Version of generated carrier structure, independent of prompt wording and package identity. |
| Verified host range | Host versions exercised by retained conformance evidence. |
| Required capabilities | Capabilities whose absence blocks the named operation. |
| Optional enhancements | Host features that improve execution without changing core semantics. |
| Degraded behavior | Exact supported behavior when an optional capability is absent. |

Compatibility is asserted only for combinations present in the generated matrix and backed by retained evidence.

## 3. Migration sequence

1. Accept the portable-core architecture and catalog decisions.
2. Define machine-readable skill, authority, dependency, capability, and compatibility schemas.
3. Ratify the separate promotion governance standard before any candidate reusable component is admitted to Bedrock; until then, candidate mechanics remain product-owned.
4. Define reusable actor and bounded command/result schemas separately from product-owned workflow and execution contracts.
5. Classify existing clauses as portable invariant, actor contract, product orchestration, candidate reusable mechanic, Haffey profile, host adapter, contextual carrier, or defect.
6. Correct the skill clusters in the ratified dependency order, populating and verifying every skill's interaction-contract fields before its cluster gate, without changing public names unless the architecture is amended.
7. Split `design-review-loop`'s portable review semantics from product-owned lifecycle and runner machinery while preserving explicit-invocation compatibility.
8. Add Codex/OpenAI, Claude, and Cursor adapters with explicit capability gates and generated-or-checked carriers.
9. Run shared structural, routing, behavior, degraded-mode, permission, reference, and output fixtures across supported hosts; products separately prove their transitions and recovery.
10. Build a release candidate only after package governance is complete.
11. Perform cold acceptance and make an explicit consumer release decision.

No migration step authorizes a consumer release by itself.

## 4. Breaking-change treatment

The following require a portable-core major version and migration notes:

- removing or renaming a skill;
- changing the primary route for an established task class;
- breaking required inputs, outputs, evidence, refusal, or escalation behavior;
- changing normative authority or conflict precedence;
- making an optional capability required without a compatible degraded path;
- moving an established direct operation behind a required orchestration kernel without a compatible direct profile; or
- weakening or materially changing the safety floor.

The distributable package also takes a major version when it carries any portable-core major or independently breaks installation, explicit invocation, or the supported-host contract. An adapter-only incompatible change takes an adapter major and a package major when that adapter is part of the distribution's supported contract.

A host-only registration or enhancement change is versioned at the adapter boundary unless it changes portable semantics. A package release carries the compatible core and adapter identities; it does not collapse them into one version claim.

## 5. Prompt and generated-carrier treatment

Generated prompts and host carriers record the generator format version, source contract version, and source digest. Prompt wording can change without a core major version when routing, authority, interaction, evidence, and safety semantics remain compatible. A carrier-format break is versioned at the generator or affected adapter boundary.

Generated files are not independent authority. They are reproduced from or checked against their declared source, and drift blocks compatibility evidence.

## 6. Design-review and product-workflow transition

The `design-review-loop` name remains a compatibility anchor during Wave 2. Its internal monolith is separated without claiming that the capability is retired:

1. Bedrock retains the portable review, finding, decision-escalation, and assurance-profile contracts.
2. Each product owns its lifecycle meaning, actor roster, authority, transitions, and operational posture.
3. Product controllers own invocation, durable state, evidence, budgets, retries, resumability, and deterministic transitions for their workflows.
4. Existing product implementations are incubators and evidence sources; reusable candidates are extracted only after evidence and are not promoted wholesale.
5. Product orchestration and operator-interaction designs are not decided by Bedrock.

Direct review and multi-perspective review remain supported lower-assurance profiles. Existing consumers without a declared runner are not silently upgraded to runner-backed convergence, and they may not claim it. A future rename or split of the public skill identity requires routing and migration evidence under the governing ADR.

Prompt generations, repeated draws, calibration, replay, cost attribution, run dispositions, and cold instrument audits belong to the product operating surface unless a rule is independently established and promoted as a portable actor safety or evidence invariant. `agent-code` and `testing` govern implementation and evaluation discipline; they do not become runtime owners.

## 7. Current consumer impact

- No skill is removed, renamed, or merged in the proposed Wave 2 contract.
- Existing `design-review-loop` invocations remain valid while its portable actor contract and product execution bindings are separated.
- The Claude-format plugin is the implemented package distribution. The supported Codex desktop host ingests it natively; no separate Codex/OpenAI adapter is required or distributed.
- Products may consume Bedrock contracts, but none receives a Bedrock-assigned orchestration role.
- Codex desktop support is bounded by the installed [compatibility matrix](../../plugins/bedrock/governance/COMPATIBILITY.md); cloud Codex tasks and a separate Codex/OpenAI or Cursor adapter remain unsupported. Candidate cold acceptance remains a separate release gate.
- The existing package version is not retroactively treated as a core-contract or adapter version.
- The next package version is derived at landing; this record does not pre-claim it.
- Consumer rollout remains blocked pending cross-surface acceptance and an explicit release decision.

## 8. Change log

| Version | Date | Ticket | Change |
|---|---|---|---|
| 3.0.0 | 2026-09-29 | HEB-154 | Ratified agent-builder/core split, explicit Python dependency and evidence-v2 migration. |
| 2.0.0 | 2026-08-12 | HEB-126 | Accepted major migration repair for product-owned orchestration and evidence-driven promotion. |
| 1.0.0 | 2026-08-09 | HEB-111 | Accepted after direct audit; reconciled the landed safety baseline without changing the migration contract. |
| 0.1.0 | 2026-08-09 | HEB-111 | Initial migration, coverage, actor/recipe/kernel compatibility, rebind/package-major rules, and consumer impact. |

## HEB-154 consumer migration

Checked fleet-specialist requests now route primarily to agent-builder; direct
mechanism work remains agent-code. Install the shipped agent-core wheel into the
project environment, pin its Bedrock revision/digest and dependencies, and run
project checks on upgrades. No project uses plugin-cache imports. Core version
0.2.0 and EvidenceRecord v0.1 do not share the portable-core 3.0.0 or portable
execution evidence 2.0.0 identity. Migrate portable v1 records explicitly to
known/unknown usage with null unknown totals and separate reservation exposure;
absent responses have null hashes. The previous plugin and project dependency
pins provide rollback. Historical evidence is retained in the repository and
is not shipped with skills. HEB-161 composition and HEB-119 acceptance still gate
release; these migration notes confer neither acceptance nor additional live calls.

## HEB-184 bounded planning admission

HEB-184 ratifies this concrete addition within the existing manifest candidate.
Its admission reconciliation answers HEB-127's promotion questions without claiming
the general promotion standard is complete or making it a universal start blocker.
The originating HEX product's shared-release reconsumption and private-fork
reconciliation remain open HEB-184 completion gates in HEB-161's later rollout.
This bounded authorization qualifies step 3 for this admission only; it does not
change the product-owned orchestration boundary or promote an execution mechanic.

The accepted instruction and historical provenance retain their exact source
bytes. The skill-local PACKAGE_ADOPTION.json is current adoption authority.
Use planning explicitly for supervised advice only. Existing specialist, mutation
and lifecycle owners remain unchanged. HEB-161 must qualify discovery, usable
explicit invocation and identity on Codex, Claude Code and Claude.ai, as well as
live routing, before release. No personal-copy reconciliation occurs here.
