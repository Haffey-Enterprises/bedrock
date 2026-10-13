# Protected infrastructure plan/apply pipeline

Terraform and infrastructure plan/apply remain owned by `infrastructure-code` even when the jobs live in GitHub Actions.

## Verification and plan

On a pull request, use unprivileged deterministic gates first: format, init from lock, validate, lint, policy/security scan, and tests. A cloud-backed speculative plan uses short-lived read/plan identity and must not inherit apply authority.

A saved plan is sensitive executable intent. Encrypt it in transit and at rest, restrict readers, set a short expiry, and retain its digest and custody events. Redact the human-readable summary separately; redaction does not make the binary plan public.

## Apply binding

Before apply, produce and verify `infrastructure-apply-manifest.schema.json`. It binds:

- source commit, configuration-tree digest, dependency-lock digest, Terraform/profile version;
- environment, project/account, workspace/state target, state lineage and serial;
- plan digest, creation and expiry, producer identity, custody, policy results;
- approved actor/authority and expected workload/artifact digests.

Apply only the exact unexpired plan when all bound identities still match. A new commit, configuration/lock change, state advance, ownership change, expired plan, or missing approval invalidates it and requires a new plan.

## GitHub Actions Haffey profile

Use least-privilege job permissions, SHA-pinned third-party actions, GitHub Environment protection for mutation, and GCP Workload Identity Federation with audience/attribute conditions. Separate plan and apply identities. Never export a long-lived service-account key.

```yaml
uses: hashicorp/setup-terraform@dfe3c3f87815947d99a8997f908cb6525fc44e9e # v4.0.1 (Node 24)
```

Use concurrency keyed by state target. Read-only verification may cancel stale runs; mutation must queue or fail closed and uses `cancel-in-progress: false`. Retain run, environment approval, OIDC subject, plan/apply manifest, policy output, Terraform result, and recovery/escalation evidence.

## Drift and failure

Run scheduled read-only drift detection with explicit alert ownership. Do not auto-apply drift repair. On partial apply, preserve logs and state identity, stop competing mutation, assess provider/API outcome, and follow the recovery contract before retrying. A rerun is not recovery evidence.

Application image and static-site delivery remain separate `app-delivery-pipeline` workflows with disjoint authority.
