# bedrock

**Haffey Enterprises engineering skills** — by T-Bone-Haff

Self-contained Claude skills distilled from the HE-Bedrock governance corpus. They carry the *content* — the engineering standard, the doctype templates, the testing and review disciplines — with none of the private self-governance machinery. Dependencies are explicit: agent-builder requires agent-code and the bundled Python core. A skill's own depth lives in its bundled `reference/` and `templates/` files (some skills are a single SKILL.md). Portable actor contracts name optional host profiles without embedding a private runner, tracker, path, or authority corpus.

## What's in the kit

The kit spans the authoring-through-review lifecycle on the house stacks — service, infrastructure, agent, frontend, and pipeline work alike. Skills are discoverable by task; planning is accepted only for explicit supervised invocation; the live roster is the plugin's [`skills/`](plugins/bedrock/skills) folder, every skill carries its own description, and the plugin manifest carries the current summary. This README deliberately restates neither.

## Shared libraries

[Agent core](packages/agent-core/README.md) is authored separately and distributed
as a wheel with agent-builder. That skill installs it into a selected project
virtual environment and records the exact Bedrock revision, wheel hash and
qualified dependencies. Bedrock updates deliver components; consuming projects
upgrade explicitly with their own checks. Tests and execution evidence remain
in the repository, outside the plugin distribution.

[Linear API client](packages/hex-linear/README.md) is a standalone Python library
for direct issue and comment operations. Install it separately from the skills
plugin; it takes caller-supplied credentials and has no assistant-app dependency.
Its import name remains `hex_linear` for compatibility with the originating
consumer. [Extraction and verification](docs/evidence/heb-164/linear-adapter/README.md).

## Stack binding

Bindings are declared per skill, not kit-wide. The service-side skills assume **Python 3.11+ / FastAPI / async SQLAlchemy / GCP / GitHub**; the frontend skill binds **TypeScript / React / Vite** with plain CSS on design tokens; the pipeline skill binds **GitHub Actions + GCP** on the house branch model; reasoning-protocol skills like `debug` and `author-standard` are stack-agnostic. `agent-code` and `design-review-loop` expose provider/runner-neutral cores plus explicit optional profiles. A profile binds the portable contract without becoming its authority.

## Install — Claude Code

Add the marketplace and install the plugin:

```
/plugin marketplace add T-Bone-Haff/bedrock
/plugin install bedrock@bedrock
```

For local development of the kit itself, point the marketplace at a clone instead: `/plugin marketplace add /path/to/bedrock`. Do **not** copy skill folders out of the repo by hand — a copied skill is an unsynced snapshot with no update path and no staleness signal; it will silently rot the moment the next release lands.

## Install — Claude.ai / Cowork

Install through the plugin marketplace: Settings → Customize → Plugins → Add marketplace from repository (`T-Bone-Haff/bedrock`) → install **bedrock**. The skills load account-wide from the plugin. Do not upload skills as individual ZIPs — hand-uploaded copies are unsynced snapshots that compete with the plugin's skills for routing.

## Staying current

Distribution behavior differs by surface. Claude.ai/Cowork loads a pushed
marketplace version in the next new session. Claude Code requires marketplace
refresh/update, plugin update, and a new session. Neither path requires copying
the skill corpus into consumer repositories.

The production marketplace resolves `main`, so cold acceptance runs against the
frozen reviewed feature-branch commit before that commit lands. Only an explicit
proceed decision permits a merge commit on `main`'s first-parent history whose
second parent is the accepted source commit.
A release completes only after post-landing package-byte parity, an immutable
tag and GitHub release at the accepted commit, and verification of every
enumerated consumer surface. The operational rollout ledger may live in the
HE-Bedrock tracker, but it conforms to the installed schema and cannot replace
the package's load-bearing lifecycle rules. See the
[package lifecycle](plugins/bedrock/governance/README.md),
[compatibility matrix](plugins/bedrock/governance/COMPATIBILITY.md), and
[security/support policies](plugins/bedrock/governance/POLICIES.md).

Any snapshot a consumer keeps anyway — a vendored authority file or pinned copy
— must verify currency at time-of-use against the current release, not against
the baseline it was copied from.

On hosts that expose only skill-local files, each skill's generated
`PACKAGE_IDENTITY.json` provides that verification surface. It repeats the
manifest identity and digest without becoming a second version authority.

## Quickstart and profile rebinding

The [routing quickstart](plugins/bedrock/governance/QUICKSTART.md) gives explicit,
implicit, overlap, and non-trigger examples. The
[worked rebind specimen](plugins/bedrock/governance/REBINDING.md) demonstrates
how a non-house stack preserves portable invariants without silently becoming a
supported profile.

## Maintenance

Edit the relevant skill's authored files directly — the SKILL.md and any bundled
`reference/` or `templates/` files; single source of truth per skill. Do not
hand-edit `PACKAGE_IDENTITY.json`: after a manifest or Claude-adapter identity
change, regenerate all 15 copies with
`python3 scripts/sync_package_identity.py --write`. Releases follow the push
discipline in the `author-standard` skill.

### Validation

Install the pinned validation dependency, then run the deterministic and host checks:

```sh
python3 -m pip install -r validation/requirements.txt
python3 -m unittest discover -s tests -v
python3 scripts/sync_package_identity.py --check
python3 scripts/validate_plugin.py
python3 scripts/validate_package_governance.py
bash scripts/smoke_clean_install.sh
```

For component preparation before composed routing acceptance, `validate_plugin.py --component` runs deterministic and strict-host checks without treating prior routing evidence as current. Its success is not release acceptance; the default validator still requires current retained routing evidence. Select composed evidence explicitly with `--routing-evidence docs/evidence/heb-161/routing-results.json` (relative to `--root`), preserving the historical HEB-109 report. A missing selected or default report fails closed; explicit evidence selection cannot be combined with `--component`.

`validate_plugin.py` deterministically enforces the 15-skill inventory, strict YAML frontmatter, the 1,024-character description limit, explicit positive and negative routing boundaries, unique names, plugin/marketplace coherence, package lifecycle and policy contracts, relative-link and private-path safety, declared external-root dependencies and snapshot currency markers, complete code-sample accounting, evidence-manifest integrity, and routing-fixture coverage. It separately runs `claude plugin validate --strict` against the plugin manifest; that host check does not claim recursive skill-frontmatter coverage.

`validate_package_governance.py` separately exposes the package gate for seeded
tests and release automation. Its default mode validates a candidate. Its
`--release` mode additionally requires paths to operator-supplied, schema-valid
release evidence and a completed consumer-surface rollout ledger, and proves
the acceptance decision preceded landing, the accepted commit survived landing,
the distributed paths retained byte parity, and the tag and rollout identities
agree. It is a final release-closure check, not the pre-merge HEB-119 candidate
gate itself.

`sync_package_identity.py --check` proves the 15 skill-local identity carriers
are byte-identical, canonical generations of the manifest and registry
authorities. The package-governance validator enforces the same contract.

Shared routing prompts live in `tests/fixtures/routing.yaml` and are surface-neutral. They cover direct, implicit, adversarial, negative, and overlap decisions. The Claude Code adapter presents the exact validated name/description catalog to each isolated model session, so the regression measures the metadata routing contract rather than unaided name association, and retains machine-readable results:

```sh
python3 scripts/run_routing_evals.py \
  --profile release \
  --expected-cli-version "2.1.226 (Claude Code)" \
  --model claude-haiku-4-5-20251001 \
  --expected-model claude-haiku-4-5-20251001 \
  --max-total-budget-usd 3.00 \
  --output /path/to/fresh-evidence/report.json
```

The live adapter requires `ANTHROPIC_API_KEY` and incurs model usage. Its
`claude --bare --print` execution path intentionally does not read Claude
subscription/OAuth or keychain authentication, so `claude auth status` is not
an adapter preflight. The harness first checks for the API-key credential source;
the first real case invocation then validates that credential and the exact
adapter execution path without adding a separate model call. Any authentication,
API-access, transport, or model failure aborts the remaining matrix immediately
and writes sanitized failure evidence instead of counting the failure as a
routing miss. Pull requests use the preregistered `pr` profile: every case runs
once and every draw must pass. Authenticated retained evidence uses the `release`
profile: three independent draws per case, at least a 95% aggregate pass rate, at
least two of three passing draws for every case, and zero excluded-route
selections. The machine-readable report records fixture, catalog, and policy
SHA-256 digests; results with different identities are not pooled. Each model
call is capped at $0.04 and 120 seconds. Deterministic validation and the isolated
install/reload smoke test do not require model inference. Branch protection must
require `Plugin validation / live-routing`.

Each invocation requires a fresh `--output` report and a distinct sibling `.jsonl`
journal. Existing files are refused before any model call. The journal retains
preregistration, a start record before each invocation, every returned draw
(including detail, reported cost and resolved models), and terminal disposition.
Each journal append is flushed and synced before dispatch can continue; a custody
failure stops execution without retry. A start without a finish records an
interrupted attempt whose outcome and charges remain unknown. A terminal failure
may replace the summary report, but never the journal or prior invocation's files.
This is local filesystem custody, not a claim of off-machine backup or provider
internal retry accounting.

The CLI must match `--expected-cli-version` before any model call. Every successful
response must name exactly `--expected-model`; missing or different identity is
retained and stops the matrix before another draw. Defaults are the workflow's
pinned Claude Code version and resolved model shown above. Changing these values
requires a new preregistration; it does not reuse a previous evaluation baseline.
Retained admission additionally reads the reviewed `validation/routing-baseline.json`:
it declares the execution source commit, adapter source digest, exact CLI/model
identities, budget ceilings and journal digest. The selected report's sibling
`.jsonl` must reconcile preregistration, every ordered start/finish pair and the
terminal evaluation. Known row costs must reconcile with the total and remain
strictly below the per-attempt and aggregate ceilings. Producer green flags are
not sufficient. An adapter source change makes the old baseline ineligible;
retain its original report/journal as historical evidence and qualify a new
baseline under separately authorized execution. Do not rewrite historical draws
or automatically update a baseline to make validation pass. This custody check
binds the declared local execution; it is not independent provider billing proof.

CI retains both files under `heb-161-routing-results`; the composed release report
is separately selected by the deterministic gate. A PR-profile observation does
not replace a release-profile report, and an unavailable composed report remains
a failed gate. No live run or additional spend is authorized by these commands.

Using `--case` creates an explicitly targeted report. It can prove that selected cases passed, but the report is marked ineligible as retained full-suite release evidence.

`validation/executable-samples.yaml` accounts for every language-tagged skill example. `fixture-backed` entries name executable evidence; `illustrative` and `deferred` entries name the correction ticket that owns stronger proof. `docs/evidence/heb-109/manifest.yaml` ties validation claims to reproducible commands, retained evidence, and explicit deferrals.

The package also ships the [local data-hygiene utility](plugins/bedrock/scripts/data-hygiene/README.md). Package availability does not deploy its machine runtime or install repository dispatchers; HEB-161 acceptance and release precede HEB-155 rollout.
