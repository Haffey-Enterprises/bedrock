# Bedrock skill architecture and routing contract

**Status:** ACCEPTED
**Version:** 3.0.0
**Date:** 2026-09-29
**Governing principle:** [ADR-001](../adr/ADR-001-portable-core-and-surface-adapter-architecture.md)

This record is the catalog-level contract for the current Bedrock skills. It assigns one primary job to each skill, records the Wave 2 retain/merge/split/rename/remove decision, defines overlap precedence, and separates routable actor contracts from the workflows that compose them. The contract is self-contained; its finding identifiers trace to the [HEB-106 disposition ledger](https://linear.app/t-bone-haff-sofia/document/heb-106-finding-register-and-disposition-ledger-4f6f1f1f0e2d) for audit history, not interpretation.

## 1. Catalog decision

The existing skill identities are retained. HEB-154 adds agent-builder for checked fleet-specialist construction; HEB-184 adds planning for explicitly invoked, supervised advisory backlog assessment. The current candidate has fifteen skill identities. None is merged, renamed, or removed in this wave. The prior disposition set called for correction or modification, not retirement, and new routing evidence is required for the amended catalog. Content can move behind progressive-disclosure references without changing the routable identity.

A future identity change requires all of:

1. a task-boundary problem demonstrated by routing, context-cost, or completion evidence;
2. a candidate boundary with positive, negative, overlap, and cold-task fixtures;
3. compatibility and migration treatment for explicit invocations and links; and
4. an architecture amendment before implementation.

## 2. Skill inventory and decisions

| Skill | Primary job | Decision | Portable/profile treatment | Key finding trace |
|---|---|---|---|---|
| `agent-builder` | Build a checked fleet specialist from requirements through handoff. | Add; explicit bounded construction route. | Requires agent-code 2.0.0 and bundled Python agent-core 0.2.0; product orchestration remains external. | HEB-154 R1-R3, D1-D4 |
| `agent-code` | Author code whose central behavior is a large language model (LLM) call or bounded tool loop. | Retain; no rename. | Provider-neutral call, parse, budget, evidence, and tool-loop invariants in core; provider/transport and house Python choices are profiles. | AGT-004, AGT-011, AGT-002 |
| `app-delivery-pipeline` | Author application-artifact continuous integration and continuous delivery (CI/CD), release, deployment, and rollout verification. | Retain; no rename. | Trusted promotion and immutable-artifact invariants in core; branch topology, CI host, and cloud are profiles. | DLV-013, DLV-002, DLV-006 |
| `application-code` | Author conventional backend service and application behavior. | Retain; no rename. | Service safety and boundary invariants in core; FastAPI, SQLAlchemy, Python, and GCP are the Haffey service profile. | APP-002, APP-016 |
| `author-construct-spec` | Author an implementation-complete specification for one internal construct. | Retain as a distinct doctype owner. | Portable implementer-complete contract in core; Haffey actor mapping is a profile. Remove hidden sibling dependence through bundled authority or an explicit checked dependency. | ACS-002, ACS-003, ACS-004 |
| `author-decision-record` | Select, author, amend, and de-drift engineering decision records. | Retain as the decision-record owner. | Portable decision-information and lifecycle contract in core; ADR/DDR/SDD taxonomy and repository homes are the Haffey profile. | ADR-001, ADR-002, ADR-005 |
| `author-execution-relay` | Author a bounded prompt or handoff for an execution surface. | Retain; no rename. | Authorization, scope, mutation identity, and stop semantics in core; single-surface, separated-executor, and fully-gated modes are risk profiles. | REL-007, REL-008 |
| `author-standard` | Decide whether to create and then author a reusable standard. | Retain; no merge with decision records. | Authority, exception, proof, and lifecycle invariants in core; local artifact homes and rollout mechanics are profiles. | STD-002, STD-006, STD-007 |
| `code-review` | Review a finished change and produce evidence-backed findings and a merge verdict. | Retain; no merge with design review. | Review mechanics and result schema in core; domain authoring skills provide applicable overlays without mirrored doctrine. | REV-009, REV-011, PKG-029 |
| `debug` | Diagnose an observed failure through reproduction and hypothesis falsification. | Retain; no merge with testing. | Diagnostic method, containment, evidence, and closure in core; stack-specific probes are profiles. | DBG family |
| `design-review-loop` | Review a decision-record set through authority-cited findings, explicit aggregation, and honest decision escalation. | Retain as a compatibility route; supersede its monolithic internal contract. | Portable review and decision-escalation semantics remain in Bedrock. Products own lifecycle composition and execution. Only a declared runner-backed profile may claim mechanical convergence. | DRL-001, DRL-004–DRL-013 |
| `frontend-code` | Author browser-facing application behavior. | Retain one routable identity; split its body into a compact core and focused references, not new skills, until measurements justify another route. | Browser safety/accessibility invariants in core; React, Vite, styling, component-library, and prototype choices are profiles. | FRT-002, FRT-005, FRT-017 |
| `infrastructure-code` | Author infrastructure as code (IaC) and infrastructure plan/apply workflows. | Retain; no rename. | State, identity, plan/apply, recovery, and workload safety in core; Terraform, GCP, Kubernetes, and CI host are profiles. | INF-002, INF-004, INF family |
| `planning` | Assess a declared backlog against accepted intent, dependencies, sequence and evidence-loss risks. | Add unchanged accepted HEB-178 instruction under HEB-184. | Stateless supervised advice; explicit invocation; no mutation, durable stewardship or unattended guarantees. Current adoption authority is the skill-local PACKAGE_ADOPTION.json; historical provenance is unchanged. | HEB-178, HEB-184 |
| `testing` | Author new tests, test strategy, fixtures, and planned coverage. | Retain; no merge with debug. | Isolation, evidence, nondeterminism, and test-level contracts in core; pytest and service-stack details are profiles. | TST family, PKG-031, PKG-032 |

The finding scope for each row is its complete stable namespace in the disposition ledger, not only the architecture-driving identifiers shown in the final column: `AGT-001–012`, `DLV-001–013`, `APP-001–019`, `ACS-001–013`, `ADR-001–012`, `REL-001–012`, `STD-001–010`, `REV-001–012`, `DBG-001–010`, `DRL-001–013`, `FRT-001–019`, `INF-001–016`, and `TST-001–014`. Package-wide findings apply through the governing ADR and the authority and coverage boundaries below.

## 3. Routing precedence

Routing selects the requested operation before the subject domain. The primary skill owns the result; an allowed alternate may contribute domain context but does not take over the operation.

| Competing routes | Primary discriminator | Primary route | Allowed overlay or alternate |
|---|---|---|---|
| `author-decision-record` / `design-review-loop` | Author or amend a record versus review a record set to convergence. | Authoring → `author-decision-record`; convergence review → `design-review-loop`. | The review skill may cite the authoring contract; it does not rewrite records unless separately authorized. |
| `author-decision-record` / `author-construct-spec` | Select a decision doctype versus author an implementer-complete construct spec. | Doctype selection → `author-decision-record`; construct-spec authorship → `author-construct-spec`. | Selection may hand off to the construct owner. |
| `author-construct-spec` / `author-execution-relay` | Define what to build versus hand an approved design to an executor. | Specification → `author-construct-spec`; handoff prompt → `author-execution-relay`. | The relay consumes, but does not amend, the spec. |
| `author-standard` / `author-decision-record` | Govern future repeated work versus record one architecture/design decision. | Reusable rule → `author-standard`; bounded decision → `author-decision-record`. | Neither silently creates the other artifact. |
| `code-review` / domain authoring skill | Review a finished change versus author or conform the implementation. | Finished-change review → `code-review`. | Relevant domain skill supplies a review overlay. |
| `code-review` / `design-review-loop` | Review code versus review decision records. | Code/diff/PR → `code-review`; ADR/DDR/SDD set → `design-review-loop`. | None. |
| `debug` / `testing` | Diagnose an observed failure versus create planned test coverage. | Observed failure, including a flaky test → `debug`; new tests/strategy → `testing`. | Testing may add regression coverage after diagnosis. |
| `debug` / domain authoring skill | Explain an existing failure versus implement planned behavior. | Existing unexplained failure → `debug`; planned change → domain skill. | Domain skill may implement the verified repair. |
| `agent-builder` / `agent-code` | Checked fleet-specialist outcome versus mechanism implementation alone. | Fleet construction → `agent-builder`; LLM-call primitives → `agent-code`. | agent-code is an explicit versioned prerequisite for construction. Testing, diagnosis and review retain their owners. |
| `agent-code` / `application-code` | Whether an LLM call or agent loop is the central behavior. | Central model behavior → `agent-code`; conventional backend behavior → `application-code`. | Application conventions apply only where compatible. |
| `agent-code` / `testing` | Implement model behavior versus test it. | Test deliverable → `testing`. | `agent-code` supplies model-specific invariants. |
| `agent-code` / `author-decision-record` | Implement model behavior versus record an architecture choice about it. | Decision artifact → `author-decision-record`. | `agent-code` supplies domain constraints. |
| `infrastructure-code` / `app-delivery-pipeline` | Infrastructure desired state and plan/apply versus application-artifact build/deploy. | IaC or infrastructure plan/apply → `infrastructure-code`; application artifact delivery → `app-delivery-pipeline`. | A release workflow may invoke both as separately owned legs. |
| `frontend-code` / `application-code` | Browser-facing versus backend behavior. | Browser runtime → `frontend-code`; service/backend runtime → `application-code`. | Shared API contracts require explicit ownership. |
| `planning` / specialist or mutation owner | Advisory backlog assessment versus design, test authorship, finished review, executor handoff or record mutation. | Explicit supervised assessment → `planning`; other operations retain their existing owner or external handoff. | Product discovery, record maintenance and unattended planning have no planning route. No disposition grants writes or work start. |
| Direct skill / lifecycle workflow | One bounded operation versus an end-to-end artifact lifecycle spanning several operations. | Bounded operation → the owning skill; lifecycle outcome → a declared orchestration recipe when available. | The recipe invokes pinned actor contracts; it does not become their normative owner. |

If a request genuinely spans operations, it is decomposed into ordered outputs with one owner per output. If the discriminator is missing, the system asks for that discriminator or stops; it does not select by whichever description is broadest.

## 4. Actor contracts and product composition

The catalog distinguishes Bedrock contracts from product-owned composition and execution:

| Layer | Owns | Does not own |
|---|---|---|
| Bedrock actor contract | One bounded reasoning operation, its authority, inputs, outputs, evidence, refusal, and escalation behavior. | Durable workflow state, scheduling, or cross-workflow composition. |
| Product orchestration | Workflow meaning, policy, actor roster, authority, state transitions, operational posture, product-specific composition, and any runtime mechanism. | Bedrock actor-domain doctrine or operator authority. |
| Promoted reusable seam | A bounded contract, schema, primitive, template, or evidence convention admitted to Bedrock after product evidence. | A universal workflow model or the originating product's private assumptions. |

An actor is not necessarily a persistent agent or a routable skill. A product may bind Lead Application Architect (LAA), Solution Architect (SA), Enterprise Architect (EA), coherence, arbitration, authoring, validation, and landing as bounded invocations under its own policy. Bedrock supplies only the selected reusable contracts; the product owns the roster and lifecycle meaning.

Current product implementations are incubators and evidence sources. Their product-specific lifecycles and runtimes are not Bedrock contracts. Candidate mechanics may be extracted only after real-product evidence supports promotion; no universal orchestration kernel or DSL is presumed.

Products may use bounded, validated command/result seams between controllers and actors. Capability is separate from decision authority: invocation grants and tool permissions exist outside prompts and models. Authorized agents may delegate under product-enforced fanout, depth, budget, tool, data, and authority limits; delegation does not amplify authority.

## 5. Common interaction contract

Every skill must expose the following fields through the future registry and in human-readable guidance:

| Field | Required meaning |
|---|---|
| Task class | The operation and subject the skill owns. |
| Positive cues | Requests that should route to the skill. |
| Negative boundary | Nearest requests that must route elsewhere or nowhere. |
| Inputs | Required artifacts, authority, environment facts, and optional context. |
| Outputs | Result or artifact shape, including machine-readable evidence where applicable. |
| Authority | Decisions the skill may make and those reserved to the operator or another system. |
| Capabilities | Required and optional host, tool, model, network, or execution capabilities. |
| Failure behavior | Refusal, escalation, graceful degradation, and early-stop conditions. |
| Evidence | Proof required before claiming completion, convergence, safety, or enforcement. |
| Lifecycle | Owner, status, verified compatibility, successor, and retirement treatment. |

This record fixes the mandatory schema, owner boundary, and primary task for every skill. The correction tranche for each skill cluster must populate and verify that skill's exact field values before the cluster may pass its gate. Existing skill prose remains migration input, not an accepted interaction contract merely because it predates the registry.

## 6. Authority and coverage boundaries

- Skill bodies own task-local semantics; shared package schemas own mechanically identical vocabulary.
- Domain skills own domain rules; product actors and controllers point to them or load versioned contracts as overlays.
- Products own composition semantics and durable execution; their controllers may not invent Bedrock actor judgments or operator authority.
- Bedrock does not prescribe a universal recipe, orchestration kernel, control plane, or DSL.
- Adapter manifests own host registration and capability mapping, never portable engineering semantics.
- Project orientation files own repository-local operating context, never the plugin's skill roster, version, or duplicated doctrine.
- Tracker records own work status and deliberation history, never installed-consumer contract or rationale.
- Domains without a Bedrock owner follow the [product coverage map](coverage-map.md). Bedrock does not imply complete incident response, production operations, site reliability engineering, privacy, compliance, cost governance, or supply-chain coverage until an owner and contract exist.

## 7. Change log

| Version | Date | Ticket | Change |
|---|---|---|---|
| 3.0.0 | 2026-09-29 | HEB-154 | Ratified agent-builder/core split, explicit Python dependency and evidence-v2 migration. |
| 2.0.0 | 2026-08-12 | HEB-126 | Accepted major product-orchestration ownership correction and promotion boundary. |
| 1.0.0 | 2026-08-09 | HEB-111 | Accepted after direct audit; expanded cold-read terminology without changing the ratified catalog contract. |
| 0.1.0 | 2026-08-09 | HEB-111 | Initial inventory, disposition trace, coverage boundary, actor/workflow model, routing, and interaction contract. |
