# Independent integration review

Reviewer: isolated Codex sub-agent, clean context; no live model evaluation calls.
Read whole: orientation, review contract/checklist, selected overlays, core runtime,
build/installer, CI, portable schema/validator, builder dependencies and offline
fixture. Changed architecture/routing/governance hunks were read completely.
Historical trial archive and every evidence artifact were excluded. An aggregate
diff truncation was recovered by narrower reads.

Two initially blocking defects were repaired and independently rechecked:

1. CI referred to nonexistent requirements.lock. It now consumes the actual
   requirements-lock.txt. The first finding was a concrete path-population check.
2. Success required candidate_count == 1, incorrectly rejecting legitimate salvage
   with two decoded candidates and one schema-valid candidate. Added required
   schema_valid_count, bounded by candidate_count, and use it for success.
   Independent installed-core/schema/semantic controls: whole 1/1 accepted;
   Prefix {"ok":false} then {"ok":true} under strict {ok:true}, explicit best effort
   salvage, 2/1 accepted; alleged success with 2/2 rejected.

Reviewer observations: wheel rebuild SHA
fdeba49630b213a12d437bdd6836585f39d96eeea619d8efe7fd8cfed368cfa0
and full asset equality passed. Isolated installed import/source/dependencies and
pip check passed on Python 3.14.6. Initial combined scoped tests: 78 tests and
31 subtests; after repair affected agent-review tests: 19 tests and 29 subtests.
Separate offline specialist fixture: 91 passed, synthetic/mock SDK transport only.
These populations overlap author tests and must not be added as unique coverage.
No unresolved code finding remains. The structured verdict remains pause because
CI/routing and composed-package cold acceptance were outside this review.

## Routing input repair review

Independent reviewer read both changed files whole, eight diagnostic JSON files,
three completed red/green logs and CLI package identity. Narrowed reads recovered
a truncated aggregate. Current adapter suite: 22 passed. In a temporary copy,
removing only DEVNULL caused both expected contamination failures. No findings;
narrow repair approved. Review did not replay the actual CLI capture, inspect
host settings, or independently reconcile original live-run billing. The broader
release verdict remains pause. See routing-repair-review.json and routing-diagnosis.json.

## CI fixture lock repair review

Independent reviewer approved unchanged-version hash completion. Every one of
20 pinned versions, 368 wheel hashes, six shared-core dependency hash sets and
20 downloaded Linux wheels was mechanically checked against prior source and
fresh exact-version PyPI metadata. All 28 active Python3.13 dependency edges
were checked. Human reads covered normalized populations, complete repair logs
and diagnosis; full CI log was mechanically loaded, with human review of the
relevant failure/install lines. Fresh local installation,91 offline tests, pip
check and wrong-hash refusal were retained author proofs, not reviewer reruns.
No findings. Native CI remains pending. No provider call or repository edit by
the reviewer. See ci-lock-review.json and ci-lock-diagnosis.json.
