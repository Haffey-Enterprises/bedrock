# Compatibility and support matrix

Support is bounded by the declared requirements below. Retained evidence must
exercise each minimum and record the exact identity of every execution.

| Surface | Support requirement | Distribution and reload behavior | Evidence | Status |
|---|---|---|---|---|
| Claude Code | >=2.1.226 | Refresh/update marketplace, update plugin, then start a new session. | strict validation and isolated install/reload at the minimum version in required CI | supported |
| Claude.ai / Cowork | Hosted service observed 2026-08-27 | Marketplace changes take effect in the next new session; the host exposes skill-local supporting files but not the package-root manifest. | v8.3.0 fresh-session and full-client-restart probes proved 13 skills and current content while package version remained unavailable; HEB-140's retained v8.4.0 final release evidence and rollout ledger record release acceptance and successful two-surface verification through the generated skill-local carrier | supported |
| Codex (ChatGPT desktop) | `codex-cli >= 0.153.4`; observed floor, with no CI pin for the minimum | Land the versioned change in the configured Git source; `codex plugin marketplace upgrade bedrock`; start a new task. Full application restart is not required. ChatGPT desktop only; `chatgpt.com/codex` cloud tasks are not covered. | [HEB-149 closure](https://linear.app/t-bone-haff-sofia/issue/HEB-149): installation, discovery, inventory and package identity. No strict plugin-manifest validator exists on this host, and no Codex routing result is claimed. | supported; the below-floor ChatGPT Classic.app was removed and the surviving installed package verified from a fresh desktop task; see [HEB-153 cleanup evidence](https://linear.app/t-bone-haff-sofia/issue/HEB-153). This host cleanup does not establish candidate installation or release acceptance |
| Codex/OpenAI adapter | None | No package-distributed adapter is required for the supported desktop host's native ingestion of the Claude-format package; none is distributed. | none for a separate adapter | unsupported as a separate adapter |
| Cursor adapter | None | No adapter is distributed. | none | unsupported |
| External product runner-backed review | No package binding | Requires a product-owned workflow binding and versioned runner with compatible schemas, exact invocation, and fresh gate evidence. | none in this package | unavailable; direct and multi-perspective profiles remain supported |

The portable skill core has contract version `3.0.0`; the distributed Claude
adapter contract has version `1.1.0`. These are compatibility identities, not
the package version. The manifest remains the package-version authority.

Portable-core 2.0 moves workflow meaning, actor rosters, authority assignments,
state transitions, retries, budgets, durable execution, and operational posture
to the consuming product. The former product-specific runner reference is
replaced by a generic external binding contract. Direct and multi-perspective
review require no runner. Consumers of the former bundled reference path must
select the generic binding and supply their own declared runner evidence; no
existing product implementation is promoted or mapped automatically.

Support covers installation, discovery, deterministic package validation, and
the declared skill contracts on verified rows. It does not promise incident
response, production operations, regulatory compliance, or cross-agent
security assurance; see the product coverage map and threat model.

The Claude Code capability is a minimum-version contract. Exact versions in
skill `verified_hosts` rows, CI logs, and retained reports identify individual
executions; they neither narrow nor expand the supported minimum. Required CI
pins the minimum so the oldest supported host remains exercised.

A host below the declared minimum, an observed incompatibility at or above the
minimum, a manifest-schema change, a routing-adapter change, or a generated
carrier format change invalidates the corresponding evidence until it is
reconciled and rerun. A host upgrade at or above the minimum does not by itself
invalidate support. Unsupported surfaces fail closed: name the missing adapter
or capability and do not claim compatibility by similarity.

## HEB-154 breaking migration

The candidate adds agent-builder 1.0.0 as primary owner for checked fleet
specialists; agent-code 2.0.0 remains the mechanism authority. Existing explicit
agent-code calls remain valid for LLM-call implementation. Agent-builder checks
its agent-code sibling identity and installs bundled agent-core 0.2.1 into the
consumer project environment before implementation. Python >=3.10 and compatible
pinned third-party wheels are required for that operation; absence stops it.
Plugin loading alone does not prove Python execution support.

Portable evidence 1.0.0 consumers must migrate to 2.0.0: unknown totals become
null with explicit status/reason, known subtotal and reserved exposure remain
separate, and absent responses have no invented hash. Count model attempts and
physical tool dispatches independently. The core-owned EvidenceRecord v0.1 is
unchanged and still requires adapter mapping. No automatic v1 reinterpretation
or mixed-version evidence pooling is supported.

Bedrock 10.0.0 remains a candidate pending composed release acceptance. Rollback
retains the prior accepted plugin and the project's prior dependency lock;
plugin rollback does not mutate deployed project environments. New wheel and
host claims require the corresponding installation evidence. The historical
one-provider trial does not prove other providers, side-effect reconciliation,
PostgreSQL, parallel execution, or fleet orchestration.

## HEB-184 planning addition

Planning is accepted for stateless, explicitly invoked, supervised advisory backlog
assessment. Read [current adoption](../skills/planning/PACKAGE_ADOPTION.json) with
the unchanged instruction and historical provenance. No mutation, priority change,
work start, release, deployment or coordination-state authority follows. The
Codex invocation policy disables implicit invocation where the host honors that
metadata; it does not prove Claude host selection enforcement. Supervision and
explicit selection remain required.

Isolated package installation is not usable cold consumer invocation. HEB-161
owns composed live routing, discovery, explicit invocation and source identity
checks on Codex, Claude Code and Claude.ai before release. HEB-184 remains open
through later HEX shared-version reconsumption and reconciliation of private
copies. One retained backlog case and selected controls, followed by applications
to that same broad backlog, do not establish general reliability. C1 coverage,
C2 read-depth/history, A1 unsupported dependencies and A2 unavailable historical
loading evidence remain limitations in the current adoption record.

## Local data-hygiene utility

The [utility](../scripts/data-hygiene/README.md) initially supports the current single-operator macOS workstation: Bash 3.2+, Git, shasum and standard macOS utilities for commits; Python 3.11+ for management; gh and GitHub only during release deployment verification. Runtime and dispatcher installation are explicit after accepted release. A second machine/operator requires redesign. No Linux, Windows, team distribution, or Python 3.11 floor execution is inferred from current-host package proof.
