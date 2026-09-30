# Routing quickstart

Bedrock routes by requested operation first, then subject domain. The selected
skill owns the output; a domain overlay does not take over another operation.

| Example request | Cue | Expected route | Expected output or boundary |
|---|---|---|---|
| “Use planning to assess this declared backlog against accepted intent and current rulings; return advisory gaps, dependencies and sequence.” | explicit supervised invocation | `planning` | Read [current adoption](../skills/planning/PACKAGE_ADOPTION.json) alongside the instruction and provenance; no mutation or work-start authority |
| “Run planning unattended and automatically reprioritize the backlog.” | outside accepted scope | no planning route | Requires separately owned lifecycle and mutation authority |
| “Build a checked requirements-readiness specialist for the fleet, with a runnable handoff.” | construction outcome | `agent-builder` | requirements, installed core, implementation, bounded verification and fleet interface |
| “Implement a bounded LLM tool loop with structured output and retry budgets.” | implicit | `agent-code` | model-call implementation and execution evidence |
| “Build the FastAPI endpoint and async persistence adapter.” | implicit | `application-code` | backend application behavior |
| “Define the Terraform plan/apply workflow in GitHub Actions.” | explicit domain | `infrastructure-code` | infrastructure desired-state and protected plan/apply workflow |
| “Define the workflow that builds, tests, and deploys our application image.” | implicit | `app-delivery-pipeline` | application-artifact delivery workflow |
| “Implement the browser settings panel in React.” | implicit | `frontend-code` | browser-facing behavior and selected frontend profile |
| “This deployment intermittently fails only in CI; diagnose it.” | implicit observed failure | `debug` | diagnosis, evidence, and bounded regression handoff |
| “Review this finished Terraform pull request before merge.” | review operation | `code-review` with infrastructure overlay | findings and merge verdict; no implementation without separate authorization |
| “Write planned browser accessibility and security coverage.” | testing operation | `testing` with frontend overlay | test strategy or tests, not frontend implementation |
| “Draft a customer billing PRD.” | negative | no Bedrock route | product requirements are outside the catalog |
| “Run the full decision-record lifecycle to mechanical convergence without a runner.” | unavailable capability | `design-review-loop` direct or multi-perspective profile, or stop | never claim runner-backed convergence without a declared product binding, versioned runner, and fresh gate evidence |

For installation, use the marketplace. Do not copy individual skill folders.
For explicit invocation, select the named skill and provide its required inputs.
If two routes remain plausible, provide the missing operation discriminator; the
host must not silently choose the broadest description.
