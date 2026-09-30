# Bedrock product coverage map

**Status:** ACCEPTED
**Version:** 2.0.0
**Date:** 2026-08-12
**Governing principle:** [ADR-001](../adr/ADR-001-portable-core-and-surface-adapter-architecture.md)

This map states what Bedrock owns, where it supplies only local invariants, and where a consumer must provide another capability. An uncovered domain is an explicit product boundary; it is never covered by selecting the nearest broad skill.

## 1. Coverage states

| State | Meaning |
|---|---|
| Owned | A Bedrock skill owns the operation and its portable contract. |
| Local invariant | Domain skills carry secure or reliable implementation rules, but Bedrock has no cross-cutting assurance owner for the domain. |
| External handoff | Bedrock does not own the operation; a consumer must supply and declare another capability. |
| Deferred gap | The future owner or contract remains deliberately unresolved with a named revisit trigger. |

## 2. Owned engineering operations

The [skill inventory and routing contract](skill-architecture.md) is authoritative for the fifteen skill identities, their primary jobs, and overlap precedence. Together they own:

- large language model (LLM)-centered, backend, frontend, infrastructure, and delivery implementation;
- explicitly invoked, stateless supervised backlog assessment, with current adoption in planning/PACKAGE_ADOPTION.json;
- planned testing and observed-failure diagnosis;
- finished-change and design-record review;
- decision-record, construct-spec, execution-relay, and reusable-standard authoring; and
- the task-local evidence, escalation, refusal, and safety obligations declared by those contracts.

Durable multi-actor workflow execution is not supplied by adding planning or agent-builder. It is product-owned orchestration. Bedrock may later own selected reusable seams that pass evidence-driven promotion, but it does not presume a universal runtime.

## 3. Cross-cutting domains and handoffs

| Domain | Current state | Bedrock responsibility | Required handoff or gap behavior |
|---|---|---|---|
| Application security | Local invariant | Domain skills retain secure-by-default implementation, testing, review, credential, identity, and dependency rules within their tasks. | Cross-cutting assurance, threat modeling, and residual-risk acceptance require another declared capability. |
| Agent and inter-agent security | Local invariant + deferred gap | `agent-code` owns task-local model, tool, identity, budget, and untrusted-input safety. | Cross-agent trust, delegation, communication, and supply-chain assurance remain unresolved; do not imply a system-wide security owner. |
| Privacy and compliance | Local invariant + deferred gap | Applicable skills retain data-minimization, sensitive-content, evidence, and auditability obligations within their tasks. | Control mapping, regulatory scope, retention, waivers, and accountable compliance sign-off require another declared capability. |
| Incident response | External handoff | Bedrock may help diagnose a bounded failure but does not own incident command, severity, communications, or post-incident governance. | Route to the consumer's incident-response capability; refuse to represent `debug` as incident command. |
| Production operations and site reliability engineering | External handoff | Infrastructure, application, and delivery skills own implementation-time operability obligations only. | On-call, service-level objectives, error budgets, capacity operations, and production change control require consumer-owned operations. |
| Database delivery and migration operations | Local invariant + external handoff | Application, infrastructure, testing, and delivery skills own their local portions of schema safety, state, verification, and deployment. | No Bedrock skill owns an end-to-end database migration programme; the consumer must declare coordination and rollback ownership. |
| Cost governance | Local invariant + external handoff | Applicable skills own bounded cost visibility, budgets, and evidence for the task they perform. | Portfolio budgets, allocation policy, forecasting, and financial approval require consumer-owned governance. |
| Dependency and artifact supply chain | Local invariant + external handoff | Domain and delivery skills own task-local pinning, provenance, scanning hooks, and immutable artifact expectations. | Estate-wide inventory, advisory response, exception ownership, and supplier governance require another capability. |
| Bedrock package lifecycle | Owned product process; enforcement pending | The manifest remains the package version authority; compatibility, migration, release evidence, and rollback are governed by the package lifecycle. | Release remains blocked until the planned package-governance and cold-acceptance gates are implemented and passed. |

## 4. Security and compliance specialization trigger

[HEB-120](https://linear.app/t-bone-haff-sofia/issue/HEB-120/explore-bedrock-securitycompliance-ownership-for-sofia-agents) holds historical work on the proposed Aegis security and Themis governance/compliance roles. They are candidate product actors, not current Bedrock or cross-product runtime authorities.

Until that decision is ratified:

- domain skills keep their local safety invariants;
- cross-cutting assurance remains an explicit deferred gap or external handoff;
- no adapter or product controller may silently assign blocking authority to Aegis or Themis; and
- the Bedrock recovery and acceptance sequence does not depend on resolving their future design.

The trigger fires when a product designs a real multi-agent authority and evidence contract, when a concrete Bedrock boundary cannot otherwise be resolved safely, or by explicit operator election.

## 5. Routing and compatibility consequences

- Unsupported cross-cutting work fails or hands off with the missing capability and affected operation named.
- A consumer may add an external owner through a versioned adapter or workflow binding, but that owner does not become Bedrock authority.
- Adding a new Bedrock-owned domain requires a routable contract, overlap evidence, lifecycle ownership, compatibility treatment, and an architecture amendment.
- Removing a declared handoff by assigning new blocking authority is a contract change, not an implementation detail.

## 6. Change log

| Version | Date | Ticket | Change |
|---|---|---|---|
| 2.0.0 | 2026-08-12 | HEB-126 | Accepted major correction: durable multi-actor execution is product-owned rather than a Bedrock runtime capability. |
| 1.0.0 | 2026-08-09 | HEB-111 | Accepted after direct audit; expanded cold-read terminology without changing the ratified coverage boundary. |
| 0.1.0 | 2026-08-09 | HEB-111 | Initial owned-operation, local-invariant, external-handoff, and deferred-gap coverage map. |
