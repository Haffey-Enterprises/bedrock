# Local data-hygiene gate

This utility implements HEB-155 D1–D5 for one trusted operator on the current
macOS workstation. It scans staged blob contents when Git invokes `pre-commit`.
It is package content only: installing Bedrock does not deploy a runtime or
configure any repository. Bedrock 10.0.0 remains a candidate until HEB-161 records
cold acceptance and explicit release `proceed` under the package lifecycle.

## Dependencies and deployment

Ordinary commits use Bash 3.2+, Git, `shasum`, and standard macOS utilities
(`awk`, `grep`, `sed`, `tr`, `cmp`, `mktemp`, `dirname`, `readlink`, `cat`, `rm`).
Management additionally requires Python 3.11+; `gh` and GitHub access are required
only for `deploy-runtime`. PATH and the operator are trusted. A second operator
or machine requires design review; no cross-platform support is claimed.

After acceptance and release, invoke the packaged executable with explicit
absolute paths. These are placeholders, not workstation defaults:

```sh
python3 "$MANAGER" deploy-runtime --source-repo "$BEDROCK_SOURCE" \
  --github-repo "$GITHUB_REPOSITORY" --tag "$ACCEPTED_TAG" \
  --runtime-root "$RUNTIME_ROOT" --pattern-file "$PATTERN_FILE"
python3 "$MANAGER" audit-runtime --runtime-root "$RUNTIME_ROOT" \
  --source-repo "$BEDROCK_SOURCE"
```

The manager verifies an annotated tag, its peeled commit, the tagged manifest's
version and repository, and a published non-draft GitHub release whose remote tag
identity matches. It extracts only the tagged hook blob; working-tree edits are
irrelevant. Cold acceptance and explicit proceed are external lifecycle evidence;
the manager cannot infer those decisions from Git or the release object.

The operator-selected root contains only this managed runtime:

```text
data-hygiene/
  current -> versions/<hook-sha256>
  pattern-file.path
  versions/<hook-sha256>/
    pre-commit
    receipt.json
```

The receipt binds the release, tag object, peeled source commit, package version,
source path, source SHA-256 and deployed SHA-256. The pointer contains only the
absolute pattern-file path; neither private contents nor a pattern digest enter
a receipt. A verified candidate is staged before `current` is atomically replaced.
Payload and receipt are non-writable during ordinary operation. Retained versions
are never automatically pruned. If the same hook digest already exists with a
different release receipt, deployment refuses rather than changing provenance.

```sh
python3 "$MANAGER" configure-pattern --runtime-root "$RUNTIME_ROOT" \
  --pattern-file "$PATTERN_FILE"
python3 "$MANAGER" audit-runtime --runtime-root "$RUNTIME_ROOT"
python3 "$MANAGER" rollback-runtime --runtime-root "$RUNTIME_ROOT" \
  --digest "$RETAINED_HOOK_SHA256"
```

Offline audit verifies the selected bytes and receipt; optional `--source-repo`
also verifies their tagged source identity. Rollback verifies a retained version
and atomically selects it. Audit affected repositories after deployment or
rollback. A failed selection leaves the prior link; a staged retained version or
updated pattern pointer may remain if deployment fails after staging. Inspect
with audit before retrying. Pattern-file edits need no package release.

## Repository installation and audit

After `git init` or clone, before the first local commit:

```sh
python3 "$MANAGER" install-repo --runtime-root "$RUNTIME_ROOT" --repo "$REPOSITORY"
python3 "$MANAGER" audit-repo --runtime-root "$RUNTIME_ROOT" --repo "$REPOSITORY"
```

One explicit repository target yields its common Git directory and complete
current worktree population. All must resolve the default common hook directory.
A configured `core.hooksPath` is allowed only when Git resolves it to that same
default directory; a redirection is refused. An unmanaged pre-commit is never overwritten; exact managed bytes and
mode are idempotent. All other hooks remain untouched. Audit checks dispatcher
bytes and mode, runtime identity, pattern-pointer accessibility, and every current
worktree's effective configuration. It does not scan historical repository data.

A linked worktree shares the dispatcher and needs no separate installation.
Re-audit on a new clone, initial rollout, runtime deployment/rollback, known Git
configuration or hook-directory changes, and the final HEB-155 estate audit.
No registry, watcher, background service or automatic cleanup is installed.

A successful repository result means **local pre-commit gate installed and
audited**. It is not a guarantee over every commit. Normal commit, amend and
conflict resolution followed by commit invoke the gate; GUI clients are covered
only when they honor Git hooks. `--no-verify`, dispatcher deletion/mode removal,
hook-path redirection, automatic merges, replay, plumbing, GitHub commits and
other machines are outside the enforcement guarantee. Audit detects observable
installation/configuration drift. Reopen D3 on a second operator/workstation,
routine remote commits, an exposure caused by bypass, or a server-wide requirement.

## Staged-content contract

Pattern precedence is `DATA_HYGIENE_PATTERN_FILE`, `RECALL_HYGIENE_TERMS`, then
the machine pointer. Either environment variable present but empty refuses.
The selected file must be readable and regular. Normalize each line by removing
a trailing CR and trimming spaces/tabs; skip blank lines and full-line comments,
preserve inline `#`, permit duplicates and reject NUL or an empty normalized set.
Fixed strings match with ASCII case-insensitivity under `LC_ALL=C`; other bytes
are exact. Private configuration remains outside every repository.

Each invocation streams a positive first-pattern control and a zero-byte negative
control, proves one NUL-delimited staged enumeration, and reads every nondeleted
staged blob independently of the working tree. Renames and type changes are
included; symlink targets are content; changed gitlinks refuse. Binary and text
use the same matcher. Only line numbers reach temporary reports; all matching
locations are returned, with control characters in paths escaped by Bash.

Exit 0 means both controls passed and all enumerated blobs were clean; stdout
contains only the scanned count. Exit 1 reports matching `path:line` locations.
Exit 2 means operational/configuration failure with neutral stderr diagnostics.
The private temporary directory is removed on exit. No matched line or pattern
is printed. Commit messages, pathname text, submodule history, unstaged/untracked
files and unchanged historical blobs are excluded.

## Package proof and later rollout

`tests/test_data_hygiene.py` uses unittest and subprocesses with invented patterns,
disposable repositories, command faults and closed offline release fixtures.
Package governance requires the four-file surface and template checkpoint;
isolated installation checks exact package bytes and executable modes. These
checks do not install this control into any real repository.

HEB-161 owns bundled qualification, acceptance and release. Only afterward may
HEB-155 deploy the accepted runtime and perform separately receipted repository
rollout and final estate audit. SOFIA remains held until RBT-124 is freshly Done.
