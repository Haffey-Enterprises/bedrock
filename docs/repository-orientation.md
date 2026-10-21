# Bedrock repository orientation

This is the tracked, host-neutral repository orientation authority. Host-loaded
files may carry a concise contextual view but must not redefine package version,
skill semantics, release gates, or engineering doctrine.

## Repository identity and layout

`Haffey-Enterprises/bedrock` contains the distributable Bedrock Claude plugin and the
consumer project template. It is not the private HE-Bedrock governance corpus.

- `plugins/bedrock/` is the installed package.
- `plugins/bedrock/.claude-plugin/plugin.json#/version` is the sole current
  package-version authority.
- `plugins/bedrock/skills/` contains the fifteen portable skill contracts and
  their bundled profiles, references, schemas, and templates.
- `packages/agent-core/` owns shared Python source and tests; its generated wheel
  ships inside `agent-builder/assets/python/`. Execution evidence stays in the repository.
- `plugins/bedrock/governance/` contains the installed package lifecycle,
  compatibility, policy, threat-model, quickstart, registry, and evidence
  contracts.
- `.claude-plugin/marketplace.json` registers the package and carries checked
  metadata; it does not carry an independent version.
- `validation/`, `tests/`, and `scripts/` implement the deterministic and
  evaluation gates.
- `docs/evidence/` retains repository-visible evidence. Tracker records are
  operational history, not installed authority.

## Change and release path

The production marketplace resolves `main`, so that branch carries accepted
package content only. Changes use an isolated feature branch and pull request.
Skill-content changes and their manifest bump form one candidate transaction on
that branch. After review, freeze the exact candidate commit and run HEB-119
cold acceptance against that commit before merge. A failed or changed candidate
returns to implementation and requires fresh review and acceptance.

After an explicit `proceed`, land the accepted commit by a merge commit on
`main`'s first-parent history whose second parent is the accepted source commit.
Fast-forward, squash, and rebase are not release landing methods.
Before tag or release, prove that `.claude-plugin/marketplace.json` and
`plugins/bedrock/` are byte-identical between the accepted commit and the
landing commit. Then create the matching immutable tag at the accepted commit,
publish the GitHub release, and execute consumer-surface rollout. This ordering
preserves the one-transaction manifest rule while preventing an unaccepted
candidate from reaching the production marketplace branch.

The package's own skill contracts are the engineering standards for work in
this repository. This orientation does not mirror them.

## Host carriers and local context

Tracked `CLAUDE.md` is the Claude Code carrier for this orientation. Tracked
root `AGENTS.md` is the Codex adapter: it points to this file and carries no
repository guidance of its own. Host carriers must not become second
hand-maintained orientation authorities.
