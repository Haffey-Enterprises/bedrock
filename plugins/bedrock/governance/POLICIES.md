# Security, support, and deprecation policies

## Security reporting

Do not file public issues containing secrets, exploit details, private consumer
content, or active credentials. Report a suspected Bedrock package
vulnerability through [GitHub private vulnerability reporting](https://github.com/Haffey-Enterprises/bedrock/security/advisories/new).
On GitHub, open Security → Advisories → Report a vulnerability. Include the
affected manifest identity, installation surface, reproduction, impact, and
whether active exploitation is suspected.
The package owner acknowledges receipt when available, preserves the report as
sensitive evidence, and publishes remediation guidance only after affected
consumers have a safe path. This is a reporting channel, not a service-level
guarantee or incident-response contract.

The package safety floor cannot be waived by a profile. A material safety defect
pauses the affected candidate or rollout until repaired with regression evidence
or explicitly withdrawn from the supported contract.

## Support

Supported behavior is limited to the compatibility matrix, package lifecycle,
and product coverage map. Requests should include manifest identity, host
identity, installation source, reproduction steps, and validation output.
Best-effort support carries no response-time guarantee. Consumers own their
runtime credentials, repository permissions, production operations, and any
external orchestration capabilities.

A declared minimum host version defines the supported compatibility floor.
Exact host versions in lifecycle rows and retained evidence identify the
executions that produced that evidence; they do not replace the minimum-version
contract or imply that only one exact host version is supported.

## Deprecation and retirement

Deprecation is a versioned lifecycle state in `registry.yaml`, never a prose-only
warning. A deprecated skill or capability names its owner, successor, migration
path, compatibility window, last verified host, and removal trigger. Removal,
rename, split, merge, routing-owner change, or loss of a supported host is a
major package change and requires explicit migration evidence.

Retirement requires every affected registry row to name a successor or an
explicit no-successor rationale. Published tags are immutable. A deprecated
artifact remains supported for its declared window or is withdrawn through the
security rollback path with the reason preserved.
