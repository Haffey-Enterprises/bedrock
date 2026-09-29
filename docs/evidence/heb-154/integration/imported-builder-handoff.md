# Agent Builder – Handoff Package

**Status**: Untested in a real agent. Core revised through review rounds C1–C7 and R1–R6; still no fresh proving-agent run. No fresh builder has yet used this skill to produce a running agent whose behavior was examined.
**Date**: 2026-09-28
**Authoring session**: Grok (remote sandbox) under explicit research boundary; skill-creator material was present in the environment but never opened or used as a template.

---

## 1. Ultimate goal (context)

Build a fleet of specialist agents that together form a complete software-development system covering planning, solution architecture, full-stack design, testing, data integration, social media posting, monitoring, security, standards/compliance, and related specialist tasks. A primary orchestrator will coordinate them. The skill exists to make construction of these agents (and any sub-agents) repeatable and standard.

All agents run in Python, locally or in a single cloud runtime. Discovery starts as static configuration; a service registry may come later. Evidence records land in PostgreSQL with session-level traceability. The environment is currently unregulated; no legal retention requirements apply at the start.

---

## 2. Decisions made (complete list)

### Definition & verification
- Agent = system that invokes a language model (optionally with tools) to pursue a goal under constraints and produces checkable outputs/actions.
- Verification always separates deterministic program behavior from model judgment / task completion. Both must be demonstrated. Never claim understanding or reliability beyond observed runs.

### Language & runtime
- Python for every agent.
- Prefer stdlib + the shared core package. Third-party packages only when justified and ratified.

### Process & operator interaction
- Requirements must be locked and explicitly ratified by Tad before architecture or implementation.
- Decision-bearing choices (architecture, tools, extensions, interface changes) require explicit ratification. Silence is not agreement.
- Address the operator as Tad.

### Substrate (agent-code lineage)
- Mandatory core + optional extensions model.
- The mandatory core is a **separately supplied** shared Python package. It is a prerequisite, not something developed or vendored inside an agent-build session.
- If the package is unavailable, the builder must stop and surface the missing dependency. Drift is intolerable; copy-paste or per-agent re-implementation is forbidden.
- Core contents (minimum):
  - Structured-output contract (parse → at-most-one salvage → strict schema → identity stamping from context → parse-path recording)
  - One aggregate execution budget
  - Basic tool-loop invariants (capability checks, result correlation, allow-list, deterministic ordering)
  - Evidence/invocation record emission with required provenance
  - Security boundary (untrusted model output, separation of instructions from retrieved/tool content, external auth for side-effects)
- Optional extensions (parallelism, circuit breakers, full MCP negotiation, richer telemetry, etc.) added only when requirements demand them and Tad ratifies.
- Shared-package development is a separately authorized task.

### Handoff package (every agent)
- Runnable entry point + configuration
- Ratified requirements statement
- Versioned fleet interface declaration
- Evidence/invocation records: execution metadata always retained; raw prompt/completion payloads only when the fleet data-classification policy explicitly permits. Exceptions to metadata retention require explicit ratification.
- Limitations & known gaps note
- Re-run instructions

### Fleet interface (required contract surface)
Language-agnostic first, then Python. Must include:
- Capability/tool surface (names, schemas, side-effect class, idempotency)
- Terminal dispositions
- Evidence record schema
- Input contract + version
- Budget/concurrency posture
- Version + compatibility range
Any change is a semantic change requiring ratification.
“How an orchestrator should invoke me” note is required when the agent will be called by the orchestrator or another specialist.

### Sub-agents
Ordinary specialists built with the same skill. Parent invokes them only through the published interface and records the child invocation in its own evidence trail.

### Orchestrator
Built with the same skill package. May ratify a tighter profile (stricter budgets, parallel-safety, richer evidence) as part of its own requirements. That tightening lives in the orchestrator design, not in the core skill.

### Evidence & retention
Execution metadata is always retained. Raw prompt/completion payloads are captured only when the fleet data-classification policy explicitly permits it. Records are written to PostgreSQL with traceability across orchestrated sessions. Exceptions to metadata retention require explicit ratification. Data-classification policy is fleet-wide.

### Discovery (v1)
Static configuration. All agents local or single cloud runtime.

### Scope boundary
Skill stops at a checked specialist (or the orchestrator). No production hardening, automated eval suites, or continuous monitoring unless explicitly ratified.

---

## 3. Rationale for the layered approach

- **Repeatability at fleet scale** requires both a consistent *process* (Agent Builder) and consistent *mechanism invariants* (shared core derived from agent-code). One without the other produces either chaos or paralysis.
- A single shared package is the only practical way to keep the substrate identical when drift is declared intolerable.
- Keeping the mandatory core small and moving orchestrator-only tightening into the orchestrator’s own design prevents ordinary specialists from carrying unnecessary weight.
- Treating sub-agents as ordinary specialists avoids a second construction path and keeps the interface contract uniform.
- Evidence records + limitations note + explicit judgment-vs-mechanism line are the defense against false confidence once the fleet looks “uniform.”

The early `agent-code` document supplied the high-value mechanism rules; Agent Builder supplies the builder process and the fleet-facing contracts. They are complementary layers, not alternatives.

---

## 4. Skill package contents

```
agent-builder/
├── SKILL.md              # the skill itself (authoritative process + defaults)
├── HANDOFF.md            # this document
├── shared/               # placeholder only; real agent-core supplied separately
│   └── placeholder only; real package supplied separately
└── reference/            # optional profiles / schema examples (empty until needed)
```

No other files are part of the skill package at this time.

---

## 5. Installation instructions (local)

1. Copy the entire `agent-builder/` directory into your skills location (or the equivalent path your host uses for skills).
2. Ensure the host can discover `SKILL.md` (title + description / triggers as needed by your runtime).
3. The `shared/` directory is a placeholder only. The real shared core package is supplied separately (parallel development). Point agents at the versioned package in your normal Python environment and record that version in every agent’s interface surface.
4. Do **not** install or publish the skill as “validated.” It remains untested until a fresh builder has used it end-to-end with the real core package available.

No automatic installation scripts are provided; this is a one-builder environment.

---

## 6. Proving plan (recommended first use)

**Prerequisite**: the shared core package must be available and its version recorded before the proving run begins. If it is missing, stop.

**Goal of the proving run**: confirm that a capable coding session can follow the skill and produce a checked specialist whose handoff package is usable by a future orchestrator.

**Suggested first agent** (keep it small):
- A pure reasoning or light-tool specialist (e.g., “standards/compliance checker” or “planning assistant”) that still exercises structured output, a budget, evidence emission, and a published interface.
- Explicitly **not** the orchestrator and not a multi-tool agent on the first run.

**Acceptance observations**:
- Requirements were locked and ratified before implementation.
- Agent depends on the separately supplied shared core rather than re-implementing it.
- Verification covered both program behavior and task behavior; limitations note is honest.
- Handoff contains the required pieces (entry point, requirements, interface declaration, original evidence records—metadata always, raw payloads only if policy permitted—and supplementary regeneration instructions, limitations note).
- Fleet interface is versioned and language-agnostic at the contract level.

**Stopping point**: after the handoff package is produced and you have reviewed it. Do not proceed to a second agent or to the orchestrator until the first proving run has been examined.

**Resources**: ordinary Python environment with the shared core package installed, access to one model provider, a PostgreSQL instance (or a temporary file-backed stand-in for evidence metadata if needed). No additional frameworks.

If a temporary file-backed stand-in is used for evidence, the proving run must explicitly state that PostgreSQL integration was not verified.

---

## 7. Known limitations of this authoring session

- The skill has never been used by a fresh builder.
- The shared core package is developed in a parallel session; this package only defines the required surface and the prerequisite rule.
- No concrete agent was built or executed.
- Provider-specific bindings are deliberately left out.
- PostgreSQL schema for evidence records is not yet defined; it must be ratified as a fleet-wide decision before the first production-like run.
- Prior references to unnamed findings 3–8 are historical narration, not an actionable defect inventory. Current F1–F3 and the ratified parser-policy amendment are tracked in the separate HEB-154 correction packet; test and live verdicts must be reported there.

---

## 8. Next actions for Tad

1. Use the frozen candidate skill directly in a fresh builder context; installation/rollout waits for acceptance.
2. Complete (or obtain) the shared core package from the parallel session and make it available in the Python environment.
3. Choose the first specialist and ratify its requirements under the skill.
4. Run the proving plan above only after the core is present.
5. Only after examining the resulting handoff package, decide whether the skill needs further revision based on identified findings or is ready for the next specialist.
```
