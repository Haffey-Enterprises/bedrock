# CLAUDE.md — {{PROJECT}}

Repo-root orientation for Claude (auto-loaded by Claude Code). This file is **context, not conventions** — what this project is, its stack, and where things live. The engineering conventions are not here: they live in the `bedrock:` skills — installed as a plugin, auto-discovered, and triggered by task, not vendored into this repo. Keep this file lean; prune as it grows.

## What this is

{{One paragraph: what {{PROJECT}} does and the core differentiating behavior that makes it distinct. Point to the defining ADR for the authoritative statement rather than narrating the full design here. Until that ADR exists, this is a stub.}}

## Stack

- **Language / runtime:** {{Python 3.11+}}
- **Framework:** {{FastAPI}}
- **Cloud / host:** {{GCP / GitHub}}
- **Data:** {{async SQLAlchemy + Postgres / Neo4j / ...}}

A materially different choice on any axis is a **rebind**, not a substitution — re-derive the conventions for that stack and capture it as an ADR (see the `application-code` skill). The `bedrock:` skills assume the stack above.

## Branch model

{{feature/* → develop → main, via PRs; never commit directly to develop or main. Confirm the current branch before any git operation. Rebind to your project's flow if different.}}

## Services

{{Inventory — name | purpose | status. Fill as services land; stub until then.}}

| Service | Purpose | Status |
|---|---|---|
| {{name}} | {{purpose}} | {{status}} |

## Project-specific rules

{{Only rules with no other home — repeatedly-invoked, project-specific content that can't live in a skill or an ADR. Most conventions live in the skills; leave this empty until something genuinely earns a place here. Premature codification is an anti-pattern. Under-govern until it hurts: prefer the lightest artifact that captures the value, and let structure follow content.}}

## Commit readiness

The project is not commit-ready until the README's data-hygiene installation and
`audit-repo` checkpoint succeeds after Git initialization and before the first
commit. The template does not install a hook or carry private configuration.
