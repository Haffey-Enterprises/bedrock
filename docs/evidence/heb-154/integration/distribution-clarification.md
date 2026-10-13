# HEB-154 distribution clarification — 2026-09-29

Status: D1 ratified by Tad. D1-D4 and D6 are settled with the recorded conditions; D5 clarifies distribution scope and preserves the separate HEB-161 release gate. This record supersedes the corresponding initial proposals in integration-map.md.

## Tad's dispositions

- D1: separate Python library makes sense; determine how it participates in Bedrock installation and cascades to consumer projects.
- D2: the library license is part of Bedrock. Use the existing Bedrock MIT license and notice; no independent license disposition remains.
- D3: ratified as proposed (truthful unknown-usage representation).
- D4: ratified as proposed (routing split and independently versioned contracts).
- D5: only skills and shared Python components are distributed. Evidence is retained in the repository for history, outside the installed distribution. This clarifies payload scope; it does not by itself change HEB-161's release dependencies.
- D6: ratified conditional on the entire candidate being staged in its intended distribution form. Preserve the one PR-profile plus one release-profile routing allowance, USD 3 each / USD 6 aggregate, with no automatic repair reruns. No additional specialist-trial calls.

## Recommended D1 implementation

1. Keep agent-core source and tests authoritative at packages/agent-core/. Build one versioned wheel containing runtime implementation, typing data, package metadata and the Bedrock MIT notice. Preserve tests and historical trial proof outside the plugin.
2. Place the generated wheel and its installation metadata inside plugins/bedrock/skills/agent-builder/assets/python/. The current marketplace source is ./plugins/bedrock; packages/ alone is outside that delivery boundary. Keeping the wheel within the skill also gives skill-only packaging a self-contained resource to carry, subject to actual host acceptance.
3. Make project setup an explicit step of agent-builder: select the target project's Python environment, install the shipped core wheel and the qualified hash-pinned dependency closure, then exercise the imported library and verify its installed identity. Never satisfy the dependency by adding a mutable plugin-cache directory to sys.path.
4. Record the Bedrock revision, component version, wheel digest and resolved dependencies in the consuming project's dependency record. Rebuilding a project or its CI must be possible from the pinned Bedrock repository revision without the operator's plugin cache. The generated wheel is retained at that revision. Use existing project dependency tooling; avoid a new package service or updater.
5. A Bedrock update delivers the newer component; it does not silently mutate existing project environments. When project work requires an upgrade, agent-builder compares the required component identity, performs the explicit project dependency update and runs that project's relevant checks. Existing deployed projects remain on their pinned version until upgraded.
6. Test the staged payload itself: source-to-wheel content correspondence, wheel membership, dependency install, actual installed import/exercise, and rejection of a missing or wrong core. Include the wheel in existing accepted-versus-landed plugin byte equivalence. Cover separate source identity too. Evidence remains repository capture, not runtime payload.

This proposal covers HEB-154's agent-core. The existing packages/hex-linear library demonstrates a separate Python project in this repository but is not automatically added to Bedrock's payload by this task.

## Read scope and confidence

Current-main repository orientation, manifest, marketplace registration and root license were read whole. The saved integration map and original user kickoff were read whole again. The existing hex-linear README and package definition were read whole; no adoption decision was derived solely from their precedent. Official OpenAI skill-resource/package-hook sections and official Claude plugin path/dependency sections were read as focused sections, not whole sites. The pip repeatable-install page was read whole. A broad combined search response was truncated and therefore partial; recommendations rely on the subsequently fetched relevant official sections and the actual repository registration.

References:
- https://developers.openai.com/plugins/build/skills — supporting scripts, references and assets.
- https://developers.openai.com/plugins/build/plugins — package paths, hooks and execution-environment/trust limits.
- https://code.claude.com/docs/en/plugins-reference — plugin dependency and installed-root path contracts.
- https://pip.pypa.io/en/stable/topics/repeatable-installs/ — pinned versions, hashes and wheel installation bundles.

No new source implementation, package build, installation, live routing call, commit or PR is claimed by this clarification. Supported-host delivery and execution remain to be established by the integrated candidate's actual probes; documentation alone is not that proof.
