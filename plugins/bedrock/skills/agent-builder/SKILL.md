---
name: agent-builder
description: "Build checked fleet specialist agents from requirements through implementation, bounded verification and handoff, using the shared Python core and published interfaces. Use for a requested running fleet specialist, including a single structured-output model call. Do not use for mechanism-only LLM-call work (agent-code), observed failures (debug), ordinary services (application-code), tests alone (testing), finished-diff review, or deployment."
---

# Agent Builder

## When to use
Use this skill when Tad supplies (or asks you to help clarify) functional requirements for a software agent that will join the fleet and wants a running implementation whose intended behavior has been checked, plus a usable handoff that includes evidence records and a published fleet interface.

**Routing on outcome:**
- One-shot structured-output agents (single model call, no tool loop) are in scope when requirements call for them.
- Model + tool-loop agents are the common case.
- Pure prompt engineering, static wrappers with no control loop *and* no structured-output contract, production deployment pipelines, and multi-agent coordination frameworks are out of scope.
- Specialist tasks (documents, spreadsheets, media, etc.) belong to their existing skills; call them rather than re-implementing.

## Prerequisite: shared core package
Every fleet agent built under this skill **must** depend on `agent-core` and follow sibling **agent-code**. Read [installation](reference/installation.md) and [dependencies](reference/dependencies.json) before implementation.

The Bedrock plugin supplies the core wheel; this skill installs and verifies it in the selected project virtual environment. Pin the Bedrock revision, wheel digest and dependencies for reproducible project/CI builds. Plugin updates deliver newer components; project upgrades are explicit and tested.

Stop if the core, sibling contract or execution capability is unavailable. Do not re-implement or vendor core mechanisms. Record `agent_core.CORE_VERSION` in fleet interfaces and evidence.

## Core commitments
- Prefer the smallest coherent design that meets the stated function.
- Depend on the shared core; optional extensions only when requirements demand them and Tad ratifies.
- Distinguish checks of program behavior (tools, control flow, contracts) from evaluation of model judgment and task completion.
- Surface decision-bearing choices to Tad and obtain explicit ratification before locking them in. Silence is not agreement.
- Stop at a checked, hand-off-ready agent.

## Ratified defaults
- **Agent**: a system that invokes a language model (once or repeatedly), optionally with tools, under explicit constraints, producing checkable outputs/actions.
- **Verification**: separate (a) deterministic program behavior from (b) model judgment / task completion. Demonstrate both.
- **Language**: Python. Prefer stdlib + agent-core. Third-party packages only when justified and ratified (`jsonschema` is already required by agent-core).
- **Handoff**: runnable entry point + limitations note + evidence records + published fleet interface.
- **Scope**: single specialist (or minimal multi-step). Sub-agents are ordinary specialists via published interfaces. Orchestrator is built with this skill and may ratify a tighter profile.
- **Evidence**: core-owned `EvidenceRecord` (v0.1). Execution metadata always retained. Raw prompt/completion payloads only when fleet data-classification policy explicitly permits. Adapters map records into PostgreSQL.
- **Discovery (v1)**: static configuration.

## Process

### 1. Lock requirements
Produce a short requirements statement covering goal, inputs/outputs, tools, constraints, success criteria, and whether the agent is standalone or will invoke/be invoked as a sub-agent.

**Bounded verification (required before runs):** agree with Tad on (a) verification cases, (b) expected outcomes, (c) run/spend limit, (d) stopping and acceptance rule. Ordinary regression tests against the core and agent interfaces are permitted inside that bound.

Do not proceed until Tad explicitly ratifies the statement.

### 2. Choose minimal architecture
Recommend the simplest structure: single model call with structured output, or model + tools in a loop, or explicit multi-step only if required. Obtain ratification for decision-bearing choices.

### 3. Specify interfaces (fleet contract surface)
Define, language-agnostic first, then Python:
- Capability/tool surface: names, JSON schemas, side-effect class, idempotency
- Terminal dispositions (from agent-core)
- Evidence record shape (agent-core `EvidenceRecord` + any agent-specific payload keys under policy)
- **Task-result schema** (the agent’s **return envelope** to the caller—typically post-stamp and post-disposition, not raw model JSON alone) and concrete **invocation / return / error convention** for orchestrator callers
- Input contract (payload, version, validation)
- Budget and concurrency posture
- Version and compatibility range
- “How an orchestrator should invoke me” note when applicable

Any change is a semantic change requiring ratification.

### 4. Implement
- Depend on agent-core. Do not re-implement or vendor the core.
- Isolate provider-specific code behind thin adapters.
- Prefer stdlib. Additional third-party deps must be justified and ratified.
- Sub-agents: invoke only through published interfaces; record child invocation in parent evidence; when children are supported, pass bounded authority/budget and account for child consumption (standalone-only first trial may defer this).

### 5. Run and observe
Execute under controlled conditions within the pre-agreed verification bound.

### 6. Verify
Demonstrate program behavior and task behavior separately. Report failures, partial successes, and variance honestly. Do not claim understanding beyond observed runs.

### 7. Handoff
Deliver: runnable entry point + config; ratified requirements; versioned fleet interface; evidence records (metadata always; raw payloads only if policy permitted) with regeneration instructions as a supplement, never a replacement for original execution metadata; limitations note; re-run instructions.

Stop. Do not expand into production hardening, eval platforms, or monitoring unless Tad ratifies new scope.

## Budget enforcement
`agent-core` admits on **past** consumption. The **provider adapter** must apply prospective per-call limits from remaining allowance and must not declare success after reconciled usage exhausts the agreed shared ceiling (including equality) unless an explicit overshoot was ratified before the run. Configuring `max_spend` alone does not bound a one-call agent.

## Mandatory core substrate
Mechanism rules for LLM calls originate in the portable **agent-code** skill; **agent-core** is the fleet’s shared Python binding of a ratified subset of those rules.

Plugin-delivered package. See Prerequisite. Optional extensions only when ratified. Package version recorded in every agent’s interface and evidence.

## Sub-agents
Ordinary specialists. Parent invokes through published interface and records the child in its evidence trail.

## Orchestrator
Built with this skill. May ratify a tighter profile in its own requirements; tightening does not live in this core skill.

## Supporting material
- `assets/python/` — generated core wheel, component identity and dependency lock.
- `reference/` — installation, dependency contract and optional profiles.

## Boundaries
- Prompt refinement alone is not this skill.
- Infrastructure, CI, deployment, monitoring are ordinary engineering.
- Existing specialist skills cover their domains; call them.
- Data-classification and retention are fleet-wide.
