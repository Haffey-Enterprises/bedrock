# Bedrock package threat model

## Assets and trust boundaries

Assets are the normative skill contracts, manifest identity, routing catalog,
evidence, installed package bytes, consumer credentials, and operator release
authority. Trust boundaries exist at source review, marketplace packaging,
host installation/cache, external references, model input/output, optional
runner integrations, CI credentials, and consumer repositories.

Prompt text is advisory. GitHub protection, CI, schemas, host validation,
credential separation, and operator release decisions are mechanical only where
the named system actually enforces them.

## Threat and control register

| Threat | Attack or failure | Controls and evidence | Residual risk and owner |
|---|---|---|---|
| Malicious skill content | A change exfiltrates data, weakens authority, or instructs unsafe mutation. | reviewed feature-branch diff; package safety validator; private-path and dependency checks; direct evidence-cited review; cold acceptance | model interpretation can still be surprising; package owner and consumer retain review authority |
| Poisoned or drifting references | External or copied material silently changes or becomes unavailable. | no load-bearing external dependency in the core; bundled relative resources; source/digest requirements for generated carriers and snapshots; currency checks | public authorities can change after access; standards owner must reverify on trigger |
| Marketplace or source compromise | Consumers receive bytes that do not match the accepted candidate. | manifest repository/license provenance; immutable source commit; annotated release tag after acceptance; GitHub release identity; rollout verification on every surface | hosting-account compromise remains possible; package owner pauses rollout and restores the last accepted identity |
| External product-runner drift | A product-owned runner or workflow binding changes while the skill still claims convergence. | runner-backed claims require binding and runner identities, immutable versions, compatible schemas, exact invocation, and fresh gate evidence; absent capability degrades honestly or stops | product execution evidence remains outside this package; the product runner owner supplies and retains it |
| Untrusted pull-request code with credentials | CI executes attacker-controlled code with cloud authority. | read-only default permissions; SHA-pinned actions; credential-free PR builds; trusted post-merge promotion | host/platform compromise remains external; repository owner controls protection and secrets |
| Sensitive-content capture | Raw model, debug, or evidence bodies retain secrets or private data. | package capture minimization, redaction, bounded evidence, and private security reporting | human-entered sensitive content may evade detection; evidence owner reviews before retention |
| Secret materialization in state | Infrastructure examples place secret values in Terraform state. | runtime-only secret path and state inspection fixtures | provider behavior can change; infrastructure owner reruns pinned integration evidence |
| Token/cookie misuse | Audience, delegation, CSRF, or browser-session guidance is applied incompletely. | package safety floor and domain contract fixtures | application context determines final control sufficiency; application security owner remains external |
| Dependency supply chain | A pinned tool or fixture dependency is compromised or stale. | immutable GitHub Action SHAs, lockfiles, audits, provenance expectations, and compatibility triggers | estate-wide advisory response is outside Bedrock; consumer owns supplier governance |

## Acceptance and review

Every release candidate rechecks this table against changed surfaces and records
new threats, invalidated controls, and residual-risk disposition in the release
evidence. A critical unowned threat blocks the candidate; bounded external gaps
are named rather than assigned to the nearest skill. HEB-119 performs the
independent cold audit and owns the final release decision.

## Local staged-content hygiene

The [data-hygiene control](../scripts/data-hygiene/README.md) trusts the operator, workstation and PATH. Fail-closed applies after dispatcher invocation. Deletion, executable-mode removal, hooksPath redirection, --no-verify, non-pre-commit operations and remote/other-machine commits are accepted boundaries. Manager audit detects observable installation drift; it is no remote cleanliness guarantee. No wrappers, background monitoring, CI private data, or server enforcement compensate for these boundaries. Reopen on another operator/workstation, routine remote commits, bypass exposure, or a repository-wide/server-side requirement.
