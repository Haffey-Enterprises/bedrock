## Problem

`recall` has the only current fail-closed data-hygiene pre-commit gate (`recall/hooks/pre-commit`, 57 lines, active through repository-local `core.hooksPath = hooks`). Freshly re-derived on the operator's machine 2026-09-08 ET: every other inspected local repository is ungated.

* `vault` is the live exposure: it receives close-harvest writes and has no pre-commit gate.
* `HEX`, `IRIS`, `LILY`, `SOFIA-Reboot`, `ops`, and `bedrock` have no effective `core.hooksPath` and no active pre-commit hook.
* `SOFIA` and its linked `SOFIA-rbt-124` worktree share one common Git directory. They have no pre-commit hook, but that common directory does contain active Git LFS hooks for `post-checkout`, `post-commit`, `post-merge`, and `pre-push`.
* `bedrock` currently has a main checkout plus four linked Codex worktrees. One common-Git-directory installation covers all five.

The current hook is local-only and its README names the bootstrap gap: a fresh clone remains ungated until the operator installs the control.

## Ratified direction

The governing design and rollout sequence are ratified at implementation-detail level. This design leg is complete. Implementation and proving have not begun; they proceed as part of Bedrock 10.0.0, with <issue id="13fe57b3-a339-4a1d-afb0-39184c315d9c" href="https://linear.app/t-bone-haff-sofia/issue/HEB-151/prevent-unaccepted-bedrock-release-candidates-from-propagating-through">HEB-151</issue> first.

### D1 — Bedrock-owned source; machine-local runtime; preserve repository-native hooks

Bedrock is the canonical authority for the portable control implementation, its tests, deployment manager, and future-project setup contract. The package surface is:

```text
plugins/bedrock/scripts/data-hygiene/
├── README.md
├── manager.py
├── pre-commit
└── dispatcher.sh.tmpl

tests/
└── test_data_hygiene.py
```

The earlier `plugins/bedrock/hooks/data-hygiene/` placement is superseded: the plugin format reserves `hooks/` for Claude lifecycle-hook configuration, while `scripts/` is the utility-script surface. No new skill is created because this is deterministic enforcement rather than model judgment.

Neither `recall`, `ops`, nor any product repository owns a policy copy. The private pattern file remains outside every repository on the operator's machine. This is an explicit single-operator/single-machine constraint: <issue id="f787418b-3469-495e-a497-3b1ad94b2d2e" href="https://linear.app/t-bone-haff-sofia/issue/HEB-155/extend-the-fail-closed-data-hygiene-pre-commit-gate-to-every-writable">HEB-155</issue> does not build team-scale or multi-machine distribution.

#### Accepted-release deployment boundary

Only an accepted Bedrock release may deploy the implementation. The single Bedrock-shipped `manager.py` accepts an explicit Bedrock source repository, release tag, operator-selected runtime root, and private pattern-file path. Deployment:

* refuses working-tree source bytes and extracts `pre-commit` from the immutable tag;
* requires an annotated tag whose version agrees with the package manifest;
* requires the tag to have a published, non-draft GitHub release;
* records the peeled source commit, package version, source path, source digest, and deployed digest; and
* treats <issue id="f085be99-5c44-4b47-905f-f3c8889e6c01" href="https://linear.app/t-bone-haff-sofia/issue/HEB-119/wp7-acceptance-cold-verification-and-staged-release-decision">HEB-119</issue> cold acceptance and the explicit release `proceed` as lifecycle governance evidence rather than claiming to infer those decisions from Git metadata.

The network and Bedrock checkout are deployment-time dependencies only. Ordinary commits do not depend on the Bedrock source checkout, its branch or working tree, a plugin cache path, the network, `recall`, or `ops`.

#### Machine-local runtime

The runtime layout is:

```text
<operator-selected-root>/data-hygiene/
├── current -> versions/<runtime-sha256>
├── pattern-file.path
└── versions/
    └── <runtime-sha256>/
        ├── pre-commit
        └── receipt.json
```

The version identity is the deployed hook's SHA-256. `pattern-file.path` contains only the absolute path to the private file, never its contents or digest. The selected payload is regular, readable, executable, non-writable during ordinary operation, contained beneath the managed version root, and digest-identical to its version identity.

Deployment stages and proves a candidate version before atomically replacing `current`. Retained accepted versions are not pruned automatically. Rollback verifies a retained version and atomically repoints `current`. Editing the private file in place requires no Bedrock release; a missing, unreadable, invalid, or empty file intentionally stops commits.

#### Manager contract

One executable provides these bounded subcommands:

```text
manager.py deploy-runtime
manager.py configure-pattern
manager.py audit-runtime
manager.py install-repo
manager.py audit-repo
manager.py rollback-runtime
```

Each mutating command operates on one explicit target. The manager derives the target's Git-resolved common directory, effective hook path, and complete current worktree population. It refuses a non-default `core.hooksPath`, refuses to overwrite an unmanaged existing `pre-commit`, and treats an exact managed dispatcher as an idempotent result. Every non-pre-commit hook remains untouched.

`audit-runtime` proves the selected runtime and receipt without requiring Bedrock to be present. When an explicit source repository is supplied, it additionally compares the receipt to the accepted source commit for rollout evidence. No removal command, registry, background service, or automatic cleanup mechanism is introduced.

#### Repository dispatcher contract

Each repository receives one small managed `pre-commit` dispatcher in its common Git hook directory. It contains only its managed identity and the absolute machine-runtime root—no matcher, pattern, or term data.

On each invocation the dispatcher:

1. requires `current` to be a relative link with the expected content-addressed form;
2. resolves the selected directory once and proves containment beneath the managed `versions` directory;
3. requires the payload to be a regular, readable, executable, non-writable file;
4. recomputes its SHA-256 and compares it with the version-directory identity;
5. executes that already-resolved payload; and
6. refuses with neutral diagnostics on any failure.

The commit path does not parse `receipt.json`; provenance comparison belongs to manager audit. Consumer `core.hooksPath` is not redirected. Existing repository-native hooks remain in place and continue to run. A linked-worktree claim is accepted only after the common Git directory and complete current worktree population are derived.

#### Future-project setup contract

The consumer project template carries a model-neutral README checkpoint: after repository initialization and before the first commit, run the manager's install and audit operations. The existing model instruction carrier adds only the corresponding readiness invariant: a project is not represented as commit-ready until that audit succeeds.

The template contains no copied hook, private file, private path, pattern digest, or policy implementation. Template creation makes the obligation visible but does not claim the resulting repository is gated.

#### Compatibility and minimum-machinery boundary

The initial supported host is the current macOS operator workstation. Ordinary enforcement may depend on Git, `/bin/bash`, `shasum`, and standard system utilities. Management may additionally depend on Python 3.11; GitHub access is required only for release deployment verification. A second operator or machine is a redesign trigger.

This implementation rides the bundled Bedrock 10.0.0 major. <issue id="d2e330ea-0c71-4b0a-9005-0d397e018e61" href="https://linear.app/t-bone-haff-sofia/issue/HEB-161/bedrock-1000-bundled-major-acceptance-and-rollout-ledger">HEB-161</issue> owns the composed candidate, cold-acceptance decision, tag, and GitHub release.

Implementation is bounded to one manager executable with subcommands, one portable hook, one dispatcher template, one README, one test module, one machine-local runtime root, and one dispatcher per common Git directory. It must not introduce a daemon, registry, framework, new skill, consumer manifest, copied policy carrier, or network dependency on the ordinary commit path. If the implementation cannot stay within this boundary or needs persistent state beyond the declared runtime layout, D1 must be reopened before proceeding.

### D2 — Rollout population and unit

One rollout unit is one Git common directory. Linked worktrees are evidence subjects, not additional installations; one dispatcher in the common hook directory covers every worktree that resolves there.

Gate these nine locally cloned, active repositories:

1. `recall`
2. `vault`
3. `HEX`
4. `SOFIA`, only after the <issue id="f9daf87a-e143-472a-9f33-a075cee13634" href="https://linear.app/t-bone-haff-sofia/issue/RBT-124/build-the-sofia-document-review-workbench-the-capability-itself-not">RBT-124</issue> hold clears
5. `bedrock`
6. `IRIS`
7. `LILY`
8. `SOFIA-Reboot`
9. `ops`

Worktree names and counts are not durable rollout design. At installation and audit time, the manager derives the complete current worktree population without a result cap and proves that every worktree resolves to the same common Git directory and dispatcher. `SOFIA-rbt-124-verify` is a detached parallel-session worktree, not a repository or separate rollout unit, and creates no separate D2 work. No SOFIA derivation or operation occurs until <issue id="f9daf87a-e143-472a-9f33-a075cee13634" href="https://linear.app/t-bone-haff-sofia/issue/RBT-124/build-the-sofia-document-review-workbench-the-capability-itself-not">RBT-124</issue> is Done.

`IRIS-OLD` and the organization `.github` repository are active but not locally cloned. Do not clone them solely for <issue id="f787418b-3469-495e-a497-3b1ad94b2d2e" href="https://linear.app/t-bone-haff-sofia/issue/HEB-155/extend-the-fail-closed-data-hygiene-pre-commit-gate-to-every-writable">HEB-155</issue>. If either is cloned for future work, manager installation and audit must precede the first local commit; archival remains a separate repository-lifecycle decision.

`HE-Bedrock`, `JARVIS`, `SOFIA-legacy`, and `First-Bot` are historical-only local repositories. They receive no <issue id="f787418b-3469-495e-a497-3b1ad94b2d2e" href="https://linear.app/t-bone-haff-sofia/issue/HEB-155/extend-the-fail-closed-data-hygiene-pre-commit-gate-to-every-writable">HEB-155</issue> gate, audit, quarantine, or other action. No future local work is expected, and their eventual purge is outside this ticket. If that premise changes, D2 must be reopened before local work resumes.

<issue id="f787418b-3469-495e-a497-3b1ad94b2d2e" href="https://linear.app/t-bone-haff-sofia/issue/HEB-155/extend-the-fail-closed-data-hygiene-pre-commit-gate-to-every-writable">HEB-155</issue> holds the population dispositions and execution receipts hold the derived observations. No workstation rollout registry or discovery service is introduced.

### D3 — Local workstation boundary

<issue id="f787418b-3469-495e-a497-3b1ad94b2d2e" href="https://linear.app/t-bone-haff-sofia/issue/HEB-155/extend-the-fail-closed-data-hygiene-pre-commit-gate-to-every-writable">HEB-155</issue> is an audited workstation `pre-commit` control. It governs staged content only when the current operator workstation invokes the managed dispatcher through `git commit`; it is not a guarantee over every way a commit can enter history.

| Operation | D3 disposition |
| -- | -- |
| Normal `git commit` | Covered |
| `git commit --amend` | Covered |
| Conflict resolution followed by `git commit` | Covered |
| GUI or IDE delegating to normal Git commit hooks | Covered only when the client honors those hooks |
| `git commit --no-verify` | Explicit bypass |
| Automatic merge commit | Not contractually covered |
| Patch import, cherry-pick, or rebase replay | Not contractually covered |
| Commit plumbing such as `commit-tree` | Not covered |
| GitHub UI or API commit | Not covered |
| Commit on another machine | Not covered |
| Fresh clone before installation | Not covered |

This boundary follows Git's hook contract: `pre-commit` is invoked by `git commit` and can be bypassed with `--no-verify`; automatic merge and patch-application operations have different hook surfaces, and replay behavior is not a dependable `pre-commit` contract. The design was checked against the current operator host's Apple Git 2.50.1 and the current official Git hook documentation; implementation evidence must record the then-current host version.

#### Meaning of fail-closed

`Fail-closed` applies after the dispatcher is invoked. An invalid or inaccessible runtime, invalid or inaccessible private pattern file, matcher failure, staged-path enumeration failure, staged-blob read failure, or detected match refuses the commit.

A missing or non-executable dispatcher, a later `core.hooksPath` redirection, or a commit-producing operation that does not invoke `pre-commit` cannot be refused by this hook. Those are accepted boundary conditions or audit-detectable installation/configuration drift, not runtime clean results.

#### Accepted bypasses and non-goals

<issue id="f787418b-3469-495e-a497-3b1ad94b2d2e" href="https://linear.app/t-bone-haff-sofia/issue/HEB-155/extend-the-fail-closed-data-hygiene-pre-commit-gate-to-every-writable">HEB-155</issue> accepts `--no-verify`, dispatcher deletion or executable-bit removal, later hook-path redirection, non-`pre-commit` commit-producing commands, remote commits, and commits on other machines. The operator is trusted; this control prevents accidental introduction rather than resisting an adversarial committer.

Do not add Git wrappers, aliases, telemetry, a background watcher, global hook redirection, merge/apply/push hooks, branch protection, a pre-receive control, CI secret distribution, or a remote scanner to compensate. CI enforcement remains outside this ticket. The existing pipeline search found no wiring to this mechanism; that establishes no pipeline use of this mechanism, not the absence of every possible equivalent check.

Reopen the threat model only for a second operator or workstation, routine GitHub UI/API commits, an observed bypass causing exposure, or a requirement for repository-wide or server-side guarantees. Do not create a speculative follow-up ticket before a trigger occurs.

#### Drift and bootstrap audit

Manager audit derives the effective `core.hooksPath` across Git configuration scopes, the Git-resolved hook path, exact dispatcher bytes and executable mode, selected runtime identity, and complete common-directory worktree population.

Required audit triggers are initial rollout, a new clone before its first local commit, explicit runtime deployment or rollback, a known Git configuration or hook-directory change, and the final <issue id="f787418b-3469-495e-a497-3b1ad94b2d2e" href="https://linear.app/t-bone-haff-sofia/issue/HEB-155/extend-the-fail-closed-data-hygiene-pre-commit-gate-to-every-writable">HEB-155</issue> estate audit. A new linked worktree requires no installation because it shares the common hook directory. No periodic monitoring is introduced.

#### D3 acceptance evidence

Use disposable repositories to prove both the protected and unprotected sides of the boundary:

* a normal safe commit invokes the control and succeeds;
* a runtime-derived harmless canary is refused;
* `--no-verify` succeeds only in the disposable fixture, proving the accepted bypass is understood rather than accidentally omitted;
* redirected `core.hooksPath` causes manager audit to fail;
* a fresh clone without installation causes manager audit to fail; and
* no bypass fixture or canary is persisted in a product repository.

Evidence language says `local pre-commit gate installed and audited`. It must not claim `all commits protected`, `repository guaranteed clean`, or an equivalent broader guarantee.

### D4 — Canonical-hook hardening

The portable runtime remains one Bash 3.2 hook. It is not rewritten in Python and gains no helper executable. It follows the Bedrock Bash application profile; tests use the repository-native Python `unittest` and subprocess stack rather than adding pytest.

#### Pattern-file contract

Pattern-file precedence is:

1. `DATA_HYGIENE_PATTERN_FILE`
2. existing `RECALL_HYGIENE_TERMS` compatibility fallback
3. the machine runtime's `pattern-file.path`

If either environment variable is present but empty, the hook refuses rather than falling through. The selected source must be a readable regular file.

Normalization treats the file as one fixed string per line: remove a trailing CR, trim leading and trailing spaces or tabs, ignore empty lines, ignore lines whose first non-whitespace character is `#`, preserve inline `#`, reject NUL-containing input, permit duplicate patterns, and refuse if no patterns remain. Matching uses deterministic fixed-byte comparison with ASCII case-insensitivity under `LC_ALL=C`; non-ASCII bytes match exactly except for identical bytes.

No private path or pattern is hardcoded, logged, placed in evidence, or copied into Bedrock.

#### Runtime self-controls

Every invocation runs two controls after normalization:

* positive: stream the first normalized pattern through the complete matcher and require a match;
* negative: run the matcher against zero-byte input and require the documented no-match status.

The positive input exists only in the process pipeline. It is never written as a committed fixture or evidence artifact. Any unexpected matcher status refuses as an operational failure.

#### Staged population and blob reads

Enumerate staged paths once with NUL delimiters and exclude only deleted entries. This covers additions, copies, modifications, renames, and type changes regardless of rename-detection configuration. Materialize the enumeration into the private temporary workspace and prove its command status before scanning; process substitution is prohibited because it can hide enumeration failure.

For every enumerated path:

* require the staged index object to resolve to a blob;
* stream that staged blob with `git cat-file`;
* capture the Git, matcher, and redaction-stage statuses independently;
* refuse if any stage fails;
* scan symlink targets as blob content; and
* refuse an unsupported non-blob entry, such as a changed gitlink, rather than silently skipping it.

Deleted paths require no scan because their content is leaving the proposed tree.

#### Matching, reporting, and exit meanings

Use the host's BSD-compatible `grep` in fixed-string, case-insensitive, line-number, treat-binary-as-text mode. Matched line content flows directly into a redaction stage that retains only the line number; it is never written to a report file. The durable temporary report contains locations only.

Text and binary blobs use the same matcher, and binary hits must still produce line numbers. Normal pathnames render as `path:line`; pathnames containing control characters use Bash's escaped representation so one location remains one output line. Continue scanning after a hit to return the complete location population. Never print the pattern, matching line, or blob content. A clean result reports only the number of staged blobs scanned.

Exit meanings are:

* `0`: both controls passed and no match was found;
* `1`: protected data was detected; and
* `2`: configuration, dependency, self-control, enumeration, blob-read, matcher, or redaction failure.

Git blocks on both nonzero statuses.

#### Shell and temporary-state behavior

The hook uses `#!/usr/bin/env bash`, declares Bash 3.2 as its minimum, and uses `set -uo pipefail`. Omitting `-e` is deliberate because matcher status `1` is expected; every external status is classified explicitly.

It sets `umask 077`, creates one `mktemp -d` workspace, installs one cleanup trap, quotes paths, uses NUL-delimited traversal, avoids `eval`, sends neutral diagnostics to stderr, and sends clean confirmation to stdout.

D3 trusts the workstation and PATH. Tests inject command failures through temporary PATH shims; production code receives no test-only fault switch.

#### D4 test and evidence matrix

One isolated `unittest` module uses disposable Git repositories and subprocesses. A meaningful-red run is required before implementation. The finished suite covers:

* missing, non-regular, unreadable, empty, and comments-only inputs;
* CRLF, whitespace trimming, full-line comments, inline `#`, duplicates, and literal regex characters;
* primary variable, compatibility fallback, machine pointer, and empty-variable refusal;
* positive and negative self-controls;
* safe and matching text, including case variants;
* binary content containing NUL bytes;
* spaces, colons, leading dashes, and control characters in paths;
* addition, copy, modification, rename, type change, symlink, and deletion;
* unsupported non-blob staged entries;
* matcher, enumeration, blob-read, and redaction-stage faults;
* an empty staged population;
* exact exit classifications;
* captured output proving the pattern and matching line are absent; and
* actual `git commit` integration for safe and refusing cases.

These tests block Bedrock package acceptance. No arbitrary line-coverage percentage, network, randomized fuzzing, mutation framework, or parallel test machinery is added; the explicit branch-and-fault matrix is the gate.

#### Explicit content boundary

The matcher scans staged blob contents, including symlink targets. It does not scan commit messages, pathname text itself, content inside a referenced submodule commit, existing unstaged or untracked files, or unmodified historical blobs. Those exclusions follow the ratified D3 pre-commit/staged-content boundary; expanding them requires a new design disposition.

### D5 — 10.0.0 integration, then repository rollout

1. Run <issue id="13fe57b3-a339-4a1d-afb0-39184c315d9c" href="https://linear.app/t-bone-haff-sofia/issue/HEB-151/prevent-unaccepted-bedrock-release-candidates-from-propagating-through">HEB-151</issue> first while its live refresh-test condition still exists. No new merge or candidate acceptance precedes that experiment.
2. Implement and prove the Bedrock-owned hook, manager, tests, and template contract as one component of Bedrock 10.0.0. Feed the package evidence into <issue id="d2e330ea-0c71-4b0a-9005-0d397e018e61" href="https://linear.app/t-bone-haff-sofia/issue/HEB-161/bedrock-1000-bundled-major-acceptance-and-rollout-ledger">HEB-161</issue>; do not run a separate plugin release for <issue id="f787418b-3469-495e-a497-3b1ad94b2d2e" href="https://linear.app/t-bone-haff-sofia/issue/HEB-155/extend-the-fail-closed-data-hygiene-pre-commit-gate-to-every-writable">HEB-155</issue>.
3. After <issue id="d2e330ea-0c71-4b0a-9005-0d397e018e61" href="https://linear.app/t-bone-haff-sofia/issue/HEB-161/bedrock-1000-bundled-major-acceptance-and-rollout-ledger">HEB-161</issue> records cold acceptance and an explicit release `proceed`, deploy the accepted machine-local runtime. Prove `bedrock` first, then migrate `recall` and gate `vault`, `HEX`, and the remaining active local repositories individually.
4. Do not touch SOFIA for <issue id="f787418b-3469-495e-a497-3b1ad94b2d2e" href="https://linear.app/t-bone-haff-sofia/issue/HEB-155/extend-the-fail-closed-data-hygiene-pre-commit-gate-to-every-writable">HEB-155</issue> until <issue id="f9daf87a-e143-472a-9f33-a075cee13634" href="https://linear.app/t-bone-haff-sofia/issue/RBT-124/build-the-sofia-document-review-workbench-the-capability-itself-not">RBT-124</issue> is Done. After that state is freshly verified, baseline and gate SOFIA, then complete the final estate audit.

Per-repository installation receipts remain required. Bundling removes only the separate plugin release; it does not collapse package acceptance into workstation or repository rollout.

## Acceptance evidence

### Bedrock source and machine-runtime receipt

* The portable source, tests, manager, and template setup contract belong to one accepted Bedrock package identity.
* The machine-local runtime receipt binds the accepted package version, source commit, source path and digest, and deployed digest.
* The selected content-addressed runtime is contained within the managed root, executable, non-writable during ordinary operation, and digest-identical to its version identity.
* Atomic selection and explicit rollback to a retained accepted version are proven.
* No private term value enters Bedrock, a deployed receipt, dispatcher, test fixture, commit message, evidence record, or tracker record.
* Full positive and negative runtime self-controls pass.
* Missing, unreadable, and empty pattern inputs each refuse.
* Matcher, enumeration, and blob-read faults each refuse rather than read clean.
* Safe staged content passes; a runtime-derived positive refuses.
* Renamed and type-changed staged paths are included.
* Output contains locations only and no matched data.
* The manager refuses an unmanaged existing pre-commit hook and preserves every non-pre-commit hook.

### Per-repository rollout receipt

For every gated common Git directory, record:

* repository identity, common Git directory, and complete current worktree population;
* baseline effective `core.hooksPath`, existing hook inventory, index state, and worktree state;
* managed dispatcher identity, selected runtime identity, and accepted Bedrock source identity;
* preservation of every pre-existing hook;
* a safe execution that passes both runtime self-controls;
* an observed refusal using a harmless per-run canary, with `path:line` output only and no protected term introduced or persisted;
* final index and worktree state equal to baseline.

For SOFIA specifically, the receipt must additionally prove:

* <issue id="f9daf87a-e143-472a-9f33-a075cee13634" href="https://linear.app/t-bone-haff-sofia/issue/RBT-124/build-the-sofia-document-review-workbench-the-capability-itself-not">RBT-124</issue> was freshly fetched in the Done state before the first <issue id="f787418b-3469-495e-a497-3b1ad94b2d2e" href="https://linear.app/t-bone-haff-sofia/issue/HEB-155/extend-the-fail-closed-data-hygiene-pre-commit-gate-to-every-writable">HEB-155</issue> touch;
* the four Git LFS hooks remain byte-identical and executable;
* both the main checkout and linked worktree resolve the same managed dispatcher;
* the pinned wall re-derives unchanged at 3,962 tracked / 0 differing by content / 12 untracked.

### Final estate audit

The final audit must derive, without a result cap:

* the complete current repository population for the Haffey Enterprises organization and the operator-owned GitHub account;
* archived historical-only/pending-purge, active-but-not-cloned, locally gated, and unresolved dispositions separately;
* all local Git repositories under the declared machine root and all linked worktrees;
* selected-runtime containment/readability/executability/digest, exact dispatcher identity, accepted Bedrock source identity, and self-control behavior for every gated common Git directory.

Every negative audit result requires a known-positive control. Instrument silence is not evidence of absence.

## Accepted costs and residual risks

* The operator accepts delaying repository rollout until the 10.0.0 bundle is implemented and accepted, relying on the current authoring/load safeguards during the interim. This is accepted exposure, not evidence that any ungated repository is protected.
* The private term list and selected runtime are machine-local dependencies. If either is missing, unreadable, invalid, or empty, commits stop in every gated repository. That blast radius is intentional.
* The design deliberately does not solve team-scale or multi-machine distribution; the review trigger is a second operator or machine.
* Bedrock owns the source and release lifecycle, but ordinary commits do not depend on a Bedrock checkout, branch, working tree, plugin cache, or network.
* New clones require explicit installation and verification; package or template availability alone does not configure Git.
* `HE-Bedrock`, `JARVIS`, `SOFIA-legacy`, and `First-Bot` intentionally remain ungated because they are historical-only, will receive no local work, and are expected to be purged later outside <issue id="f787418b-3469-495e-a497-3b1ad94b2d2e" href="https://linear.app/t-bone-haff-sofia/issue/HEB-155/extend-the-fail-closed-data-hygiene-pre-commit-gate-to-every-writable">HEB-155</issue>.
* `--no-verify`, dispatcher deletion or mode change, later hook-path redirection, non-`pre-commit` commit-producing commands, remote commits, and other-machine commits bypass the local hook. D3 owns that accepted boundary and manager audit detects only the installation/configuration drift it can observe.
* The control is preventative at local commit time, not a remote repository guarantee.
* The matcher covers staged blob contents only. Commit messages, pathname text, referenced submodule content, unstaged or untracked files, and unmodified history remain outside D4.

## Provenance

Fresh derivation on 2026-09-08 ET covered:

* <issue id="f787418b-3469-495e-a497-3b1ad94b2d2e" href="https://linear.app/t-bone-haff-sofia/issue/HEB-155/extend-the-fail-closed-data-hygiene-pre-commit-gate-to-every-writable">HEB-155</issue> and its relations read in full; the complete comment population was empty;
* `recall/hooks/pre-commit` and `recall/hooks/README.md` read in full;
* effective hook configuration and active hook files for 14 Git roots directly under the declared `~/Documents/GitHub` inventory surface;
* linked worktrees for every locally cloned, non-archived rollout repository;
* complete current GitHub repository populations for the Haffey Enterprises organization and the authenticated operator-owned account;
* exact-mechanism search across local `.github/workflows`, with a known-positive search control;
* SOFIA's four existing hooks read in full and its <issue id="f9daf87a-e143-472a-9f33-a075cee13634" href="https://linear.app/t-bone-haff-sofia/issue/RBT-124/build-the-sofia-document-review-workbench-the-capability-itself-not">RBT-124</issue> wall re-derived.
* Bedrock repository orientation, `author-standard`, and the normative package lifecycle read in full; the operator ratified Bedrock as source authority, a machine-local generated runtime carrier, and repository-local activation dispatchers.

Repositories elsewhere on the machine were not part of the local-root derivation and are not implied clean.

Related execution constraint: <issue id="f9daf87a-e143-472a-9f33-a075cee13634" href="https://linear.app/t-bone-haff-sofia/issue/RBT-124/build-the-sofia-document-review-workbench-the-capability-itself-not">RBT-124</issue>.
