"""Regression tests for HEB-116 agent/review contracts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import yaml

from scripts.validate_agent_review_contracts import (
    _balanced_json_candidates,
    _validate_agent,
    evaluate_runner_profile_case,
    validate_agent_review_contracts,
)


ROOT = Path(__file__).resolve().parents[1]


class AgentReviewContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name) / "bedrock"
        shutil.copytree(ROOT, self.root, ignore=shutil.ignore_patterns(".git", "__pycache__"))

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    @staticmethod
    def runner_case(
        *,
        product_binding_version: str = "release-2026-08-28",
        runner_version: str = "2.1.0-rc.1+build.7",
    ) -> dict[str, object]:
        invocation = "product-review run --profile convergence"
        subject = {
            "substrate_sha256": "a" * 64,
            "product_binding_id": "product-review-workflow",
            "product_binding_version": product_binding_version,
            "product_binding_sha256": "b" * 64,
            "product_binding_owner": "product-review-owner",
            "product_binding_authority": "product/review-workflow",
            "runner_id": "product-review-runner",
            "runner_version": runner_version,
            "runner_sha256": "c" * 64,
            "portable_core_version": "2.0.0",
            "review_schema_version": "1.0.0",
            "compatibility_manifest_sha256": "d" * 64,
            "invocation_sha256": hashlib.sha256(invocation.encode()).hexdigest(),
            "validator_profile": "convergence",
        }
        subject_sha256 = hashlib.sha256(
            json.dumps(subject, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return {
            "profile": "runner-backed",
            "product_binding_id": subject["product_binding_id"],
            "product_binding_version": subject["product_binding_version"],
            "product_binding_sha256": subject["product_binding_sha256"],
            "product_binding_owner": subject["product_binding_owner"],
            "product_binding_authority": subject["product_binding_authority"],
            "runner_id": subject["runner_id"],
            "runner_version": subject["runner_version"],
            "runner_sha256": subject["runner_sha256"],
            "portable_core_version": subject["portable_core_version"],
            "review_schema_version": subject["review_schema_version"],
            "compatibility_manifest_sha256": subject["compatibility_manifest_sha256"],
            "invocation": invocation,
            "validator_profile": subject["validator_profile"],
            "evidence": {
                "subject": subject,
                "required_actor_ids": ["laa", "sa", "ea", "cross-set"],
                "actor_results": [
                    {"id": actor_id, "outcome": "completed", "evidence_sha256": digest * 64}
                    for actor_id, digest in zip(
                        ("laa", "sa", "ea", "cross-set"),
                        ("1", "2", "3", "4"),
                        strict=True,
                    )
                ],
                "required_gate_ids": ["schema", "identity", "lifecycle", "convergence"],
                "gate_results": [
                    {"id": gate_id, "outcome": "passed", "evidence_sha256": digest * 64}
                    for gate_id, digest in zip(
                        ("schema", "identity", "lifecycle", "convergence"),
                        ("5", "6", "7", "8"),
                        strict=True,
                    )
                ],
                "ledger_sha256": "e" * 64,
                "evidence_manifest_sha256": "f" * 64,
                "verification": {
                    "method": "second-derivation",
                    "instrument": "verify_runner_evidence --profile convergence",
                    "subject_sha256": subject_sha256,
                    "result": "confirmed",
                },
            },
        }

    def test_repository_contracts_pass(self) -> None:
        self.assertEqual([], validate_agent_review_contracts(self.root))

    def test_missing_registry_fails_closed(self) -> None:
        (self.root / "validation/agent-review-contracts.yaml").unlink()
        self.assertTrue(any("registry is missing" in item for item in validate_agent_review_contracts(self.root)))

    def test_salvage_enumerates_ambiguity(self) -> None:
        self.assertEqual(2, len(_balanced_json_candidates('before {"a": 1} between {"b": 2} after')))

    def test_nested_object_is_one_candidate(self) -> None:
        self.assertEqual(1, len(_balanced_json_candidates('before {"a": {"b": 2}} after')))

    def test_low_confidence_resolvable_is_rejected(self) -> None:
        path = self.root / "tests/fixtures/agent-review-contracts/valid/arbitration.json"
        text = path.read_text(encoding="utf-8").replace('"confidence": "high"', '"confidence": "low"')
        path.write_text(text, encoding="utf-8")
        self.assertTrue(any("low-confidence resolvable" in item for item in validate_agent_review_contracts(self.root)))

    def test_forbidden_product_specific_profile_path_fails_closed(self) -> None:
        path = (
            self.root
            / "plugins/bedrock/skills/design-review-loop/reference/haffey-sofia-profile.md"
        )
        path.write_text("legacy product profile\n", encoding="utf-8")
        errors = validate_agent_review_contracts(self.root)
        self.assertTrue(any("forbidden path remains" in item for item in errors), errors)

    def test_runner_profile_case_expectations_are_enforced(self) -> None:
        path = self.root / "validation/agent-review-contracts.yaml"
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        payload["runner_profile_cases"][0]["expected"] = "stop-unavailable"
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        errors = validate_agent_review_contracts(self.root)
        self.assertTrue(any("runner profile case" in item for item in errors), errors)

    def test_runner_backed_claim_requires_replayable_binding_and_invocation(self) -> None:
        complete = self.runner_case()
        self.assertEqual("runner-backed-claim-permitted", evaluate_runner_profile_case(complete))
        for field in (
            "product_binding_id",
            "product_binding_version",
            "product_binding_sha256",
            "product_binding_owner",
            "product_binding_authority",
            "runner_id",
            "runner_version",
            "runner_sha256",
            "portable_core_version",
            "review_schema_version",
            "compatibility_manifest_sha256",
            "invocation",
            "validator_profile",
            "evidence",
        ):
            with self.subTest(field=field):
                incomplete = dict(complete)
                incomplete.pop(field)
                self.assertEqual("stop-unavailable", evaluate_runner_profile_case(incomplete))

    def test_runner_backed_claim_rejects_narration_only_evidence_boolean(self) -> None:
        legacy = {
            "profile": "runner-backed",
            "product_binding_id": "product-review-workflow",
            "product_binding_version": "1.0.0",
            "runner_id": "product-review-runner",
            "runner_version": "2.1.0",
            "schemas_compatible": True,
            "invocation": "product-review run --profile convergence",
            "fresh_gate_evidence": True,
        }
        self.assertEqual("stop-unavailable", evaluate_runner_profile_case(legacy))

    def test_product_binding_version_is_opaque_and_runner_accepts_full_semver(self) -> None:
        for binding_version in ("release-2026-08-28", "sha256:" + "a" * 64):
            for runner_version in ("2.1.0", "2.1.0-rc.1", "2.1.0+build.7"):
                with self.subTest(
                    binding_version=binding_version,
                    runner_version=runner_version,
                ):
                    self.assertEqual(
                        "runner-backed-claim-permitted",
                        evaluate_runner_profile_case(
                            self.runner_case(
                                product_binding_version=binding_version,
                                runner_version=runner_version,
                            )
                        ),
                    )

    def test_runner_rejects_malformed_semver(self) -> None:
        for runner_version in ("v2.1.0", "2.1", "02.1.0", "sha256:" + "a" * 64):
            with self.subTest(runner_version=runner_version):
                self.assertEqual(
                    "stop-unavailable",
                    evaluate_runner_profile_case(self.runner_case(runner_version=runner_version)),
                )

    def test_runner_accepts_subject_bound_falsification_control(self) -> None:
        case = self.runner_case()
        case["evidence"]["verification"].update(
            {"method": "falsification-control", "result": "refused"}
        )
        self.assertEqual("runner-backed-claim-permitted", evaluate_runner_profile_case(case))

    def test_runner_backed_claim_requires_complete_subject_bound_evidence(self) -> None:
        mutations = {
            "missing-actor": lambda case: case["evidence"]["actor_results"].pop(),
            "missing-gate": lambda case: case["evidence"]["gate_results"].pop(),
            "wrong-subject": lambda case: case["evidence"]["verification"].update(
                {"subject_sha256": "0" * 64}
            ),
            "wrong-invocation": lambda case: case.update({"invocation": "different invocation"}),
            "failed-discrimination": lambda case: case["evidence"]["verification"].update(
                {"result": "unavailable"}
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                case = self.runner_case()
                mutate(case)
                self.assertEqual("stop-unavailable", evaluate_runner_profile_case(case))


class AgentAccountingTests(unittest.TestCase):
    def fixture(self):
        return json.loads((ROOT / "tests/fixtures/agent-review-contracts/valid/agent-execution.json").read_text())

    def test_zero_model_attempts_cannot_succeed(self):
        value = self.fixture()
        value["attempts"] = []
        errors = []
        _validate_agent(value, Path("zero-model.json"), errors)
        self.assertTrue(any("success requires a model attempt" in e for e in errors), errors)

    def test_tool_dispatch_does_not_consume_model_attempt_limit(self):
        value = self.fixture()
        value["budget"].update(max_attempts=1, max_tool_iterations=1)
        value["attempts"].append({"attempt": 1, "kind": "tool", "tool_iteration": 1, "disposition": "succeeded"})
        errors = []
        _validate_agent(value, Path("model-and-tool.json"), errors)
        self.assertEqual([], errors)

    def test_unknown_usage_remains_a_truthful_failure(self):
        value=json.loads((ROOT/'tests/fixtures/agent-review-contracts/valid/agent-execution-unknown.json').read_text())
        errors=[]
        _validate_agent(value,Path('unknown.json'),errors)
        self.assertEqual([],errors)
        value['terminal_disposition']='succeeded'
        _validate_agent(value,Path('unknown-success.json'),errors)
        self.assertTrue(errors)

    def test_known_subtotal_cannot_disagree_with_reported_totals(self):
        value=self.fixture()
        value['usage']['known_subtotal']['input_tokens']+=1
        errors=[]
        _validate_agent(value,Path('false-subtotal.json'),errors)
        self.assertTrue(errors)


    def test_one_valid_salvage_candidate_among_several_is_accepted(self):
        value=self.fixture()
        value['parse'].update(path='salvaged',candidate_count=2,schema_valid_count=1)
        errors=[]
        _validate_agent(value,Path('unique-valid.json'),errors)
        self.assertEqual([],errors)
        value['parse']['schema_valid_count']=2
        _validate_agent(value,Path('ambiguous.json'),errors)
        self.assertTrue(any('one validated response' in error for error in errors))

    def test_valid_candidate_count_cannot_exceed_population(self):
        value=self.fixture()
        value['parse'].update(candidate_count=0,schema_valid_count=1)
        errors=[]
        _validate_agent(value,Path('impossible-count.json'),errors)
        self.assertTrue(any('invalid parsed candidate counts' in error for error in errors))


if __name__ == "__main__":
    unittest.main()
