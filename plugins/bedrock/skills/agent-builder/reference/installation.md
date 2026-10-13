# Install the shared core into a project

Bedrock distributes agent-core as a wheel in this skill's `assets/python/`.
Source and tests remain in the Bedrock repository at `packages/agent-core/`.
Historical execution evidence remains repository-only. The library uses Bedrock's MIT license.

Use the selected project's virtual environment. From this skill directory, run
`python scripts/install_core.py --python PROJECT_VENV_PYTHON --bedrock-revision ACCEPTED_FULL_COMMIT --record PROJECT_DEPENDENCY_RECORD`.
The script refuses a global interpreter, verifies bundled hashes, installs the
qualified dependency closure, checks dependency compatibility, and exercises the
actual isolated import. An existing record is not overwritten: review the upgrade,
write a new record, run project checks, then replace the old dependency pin as part
of that project change. Never add the plugin cache to the runtime import path.

For repeatable CI, fetch the pinned Bedrock repository commit, verify the recorded
wheel and dependency-lock hashes, and invoke its same installer. Do not resolve a
moving branch or an unqualified package-index name. Pin the resolved full commit
at handoff. The component manifest binds the wheel to source files; it does not
self-authenticate an untrusted repository revision.

`--check` verifies an existing installation without installing. Failure is a stop:
do not hand off an agent as runnable when dependency or import checks fail.
Installation may need network access for pinned third-party wheels; the Bedrock
core wheel itself ships with the skill. Python >=3.10 is the declared language
floor. Availability of compatible third-party wheels and execution permissions
must be demonstrated in the selected environment; a loaded Markdown skill alone
is not evidence of executable readiness.

Provider SDKs are project-owned dependencies, outside the shared core. The
Anthropic trial is one exercised adapter, not a provider-neutral certification.
Installing or upgrading Bedrock does not change an existing project's environment.
