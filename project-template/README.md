# {{PROJECT}}

{{One-line description.}}

## Engineering conventions

This project follows the **bedrock** engineering skills — installed as a plugin in Claude (account + Claude Code), auto-discovered, and triggered by task. The conventions are not vendored into this repo — they're ambient.

Stack assumption: Python 3.11+ / FastAPI / async SQLAlchemy / GCP / GitHub. A materially different stack is a rebind, captured as an ADR (see `CLAUDE.md`).

## Layout

- `CLAUDE.md` — repo-root orientation (what this project is, its stack, where things live)
- `docs/adr/` — Architecture Decision Records (platform principles)
- `docs/ddr/` — Design Decision Records (specific design rulings)
- `docs/sdd/` — Service Design Documents (per-service designs)
- `docs/reviews/` — review-of-record artifacts

Service code, tests, and scaffolding are generated under the `application-code` and `testing` skills.

## Starting from this template

1. Copy this `project-template/` to a new repo directory and rename it.
2. Initialize Git. Before the first commit, complete the data-hygiene checkpoint below.
3. Fill in `CLAUDE.md` (replace every `{{PLACEHOLDER}}`).
4. Author the defining ADR (`author-decision-record` skill).
5. Scaffold the first service (`application-code` skill).

## Before the first commit

Use the accepted Bedrock package's `scripts/data-hygiene/manager.py` and the
operator's already deployed runtime. Supply explicit paths:

```sh
python3 "$MANAGER" install-repo --runtime-root "$RUNTIME_ROOT" --repo "$REPOSITORY"
python3 "$MANAGER" audit-repo --runtime-root "$RUNTIME_ROOT" --repo "$REPOSITORY"
```

Complete installation and audit after repository initialization and before the
first commit. A copied template alone does not configure Git. Resolve a refused
audit before representing the project as commit-ready; the package utility README
owns the control and its local-workstation limits.
