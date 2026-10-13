# High-assurance execution relay

Attach a relay document conforming to `reference/relay.schema.json` and evidence that the execution boundary validates it.

The schema carries transaction identity and controls; the authored relay also carries this instrument contract:

- consumer configuration, parser, schema, wrapper, or gate read whole and pinned;
- its accepted grammar and outcome taxonomy carried verbatim;
- an exact author-time dry-run proving the command, actor, checkout, inputs, and output are jointly satisfiable;
- touch allowlist derived bidirectionally from ratified edit-locus rows;
- one pins block, and a carried-value sweep at issue and at receipt with no hits; and
- custody evidence separated from production reachability evidence.

| Property or premise | Claim subject | Verdict-bearing inputs/pins | Population derivation / expected-state oracle | Structural instrument / discrimination control | Outcomes / unavailable | Report field |
|---|---|---|---|---|---|---|
| <property> | <repository; checkout or working directory; inputs; population> | <pins> | <execution-time command/API/parser; canonicalization; pinned baseline or rule deriving the expected set; or n/a when no comparison> | <independent instrument; differently-shaped derivation or falsification control> | <subject mismatch or state mismatch: stop; arithmetic or transcription defect: report and proceed; unavailable or ambiguous: stop> | <field> |

A typed count or member list is never the population oracle. If retained as a cross-check, generate it from the declared derivation. Verify the claim subject, then compare the execution-time derived population with the mechanically expected population before consulting any prose summary.

## Required controls

- authenticated, scoped, fresh, revocable, replay-resistant authorization;
- canonical mutation manifest and repository base identity;
- executable allowlist enforcement;
- separated authority, instructions, untrusted data, and evidence;
- explicit operator gates, halt on a subject mismatch, derived-state mismatch, or failed discrimination, and report-and-proceed behavior for an arithmetic or transcription defect when the named subject and derived observed and expected populations match mechanically; and
- independent durable-form verification with unavailable behavior and premise dispositions of `confirmed`, `falsified`, or `unavailable`.

If any required control is unavailable, stop or deliberately select a lower profile without claiming high-assurance enforcement.
