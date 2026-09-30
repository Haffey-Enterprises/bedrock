"""Regression tests for the HEB-117 authoring and review contracts."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
import shutil
import tempfile
import unittest

import yaml

from scripts.validate_authoring_contracts import (
    check_relay_shrink, evaluate_behavior_case, relay_anchors, sweep_relay, validate_authoring_contracts,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class AuthoringContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name) / "bedrock"
        shutil.copytree(REPOSITORY_ROOT, self.root, ignore=shutil.ignore_patterns(".git", "__pycache__"))

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def assert_error(self, expected: str) -> None:
        self.assertTrue(any(expected in error for error in validate_authoring_contracts(self.root)))

    def test_repository_contracts_pass(self) -> None:
        self.assertEqual([], validate_authoring_contracts(self.root))

    def test_missing_registry_fails_closed(self) -> None:
        (self.root / "validation/authoring-contracts.yaml").unlink()
        self.assert_error("required authoring-contract registry is missing")

    def test_missing_interaction_field_fails(self) -> None:
        path = self.root / "validation/authoring-contracts.yaml"
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        del payload["skills"]["code-review"]["failure_behavior"]
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        self.assert_error("field mismatch")

    def test_high_assurance_relay_without_authorization_fails(self) -> None:
        path = self.root / "tests/fixtures/authoring-contracts/valid/relay.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        del payload["authorization"]
        path.write_text(json.dumps(payload), encoding="utf-8")
        self.assert_error("valid fixture or schema failed")

    def test_provisional_relation_without_owner_fails(self) -> None:
        path = self.root / "tests/fixtures/authoring-contracts/valid/relations.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        del payload["relations"][0]["owner"]
        path.write_text(json.dumps(payload), encoding="utf-8")
        self.assert_error("valid fixture or schema failed")

    def test_review_with_blocker_cannot_approve(self) -> None:
        valid = self.root / "tests/fixtures/authoring-contracts/valid/review.json"
        invalid = self.root / "tests/fixtures/authoring-contracts/invalid/review.json"
        valid.write_bytes(invalid.read_bytes())
        self.assert_error("approves with an unresolved blocking finding")

    def test_construct_template_size_is_bounded(self) -> None:
        path = self.root / "plugins/bedrock/skills/author-construct-spec/templates/construct-spec-template.md"
        path.write_text(path.read_text(encoding="utf-8") + "\n" * 181, encoding="utf-8")
        self.assert_error("must not exceed 180 lines")

    def test_behavior_fixture_cases_match_terminal_contracts(self) -> None:
        payload = yaml.safe_load(
            (self.root / "tests/fixtures/authoring-contracts/behavior.yaml").read_text(encoding="utf-8")
        )
        for case in payload["cases"]:
            with self.subTest(case=case["id"]):
                self.assertEqual(case["expected"], evaluate_behavior_case(case))

    def test_relay_instrument_contract_is_required(self) -> None:
        path = self.root / "plugins/bedrock/skills/author-execution-relay/SKILL.md"
        path.write_text(path.read_text(encoding="utf-8").replace("## Build the execution instrument", "## Missing"), encoding="utf-8")
        self.assert_error("execution-instrument contract is missing")

    def test_reviewer_charge_instrument_is_required(self) -> None:
        path = self.root / "plugins/bedrock/skills/design-review-loop/reference/reviewer-instrument.md"
        path.write_text(path.read_text(encoding="utf-8").replace("Falsification control", "Control"), encoding="utf-8")
        self.assert_error("review-charge instrument is missing")

    def test_required_instrument_reference_cannot_be_missing_or_weakened(self) -> None:
        path = self.root / "plugins/bedrock/skills/author-execution-relay/reference/execution-instrument.md"
        baseline = path.read_text(encoding="utf-8")
        path.unlink()
        self.assert_error("execution-instrument contract cannot be read")
        path.write_text(baseline.replace("outcome taxonomy verbatim", "outcomes"), encoding="utf-8")
        self.assert_error("execution-instrument contract is missing")
        path.write_text(baseline, encoding="utf-8")
        entrypoint = path.parent.parent / "SKILL.md"
        entrypoint.write_text(entrypoint.read_text().replace("whole and apply every requirement", "if convenient"))
        self.assert_error("missing its required read-whole pointer")

    def test_carried_value_contract_cannot_lose_a_rule(self) -> None:
        path = self.root / "plugins/bedrock/skills/author-execution-relay/SKILL.md"
        baseline = path.read_text(encoding="utf-8")
        for fragment in (
            "## Carry pins, not derivations",
            "Every pin appears once, in one pins block",
            "planted mismatch once per relay lineage",
            "A relay body carries no outcome and no revision narrative.",
            "Before issue, sweep the relay for carried values",
            "The executor repeats the sweep on receipt",
            "a value the patterns do not match can survive",
            "every dropped anchor is dispositioned before issue",
            "the predecessor retained, the hash reissued",
            "Loosening a prohibition, removing a stop, or changing what a gate verifies is the operator's.",
            "An executor who adjusts nothing says so",
        ):
            with self.subTest(fragment=fragment):
                path.write_text(baseline.replace(fragment, "[removed]"), encoding="utf-8")
                self.assert_error("carried-value contract is missing")
        path.write_text(baseline, encoding="utf-8")

    def test_template_sweep_and_stop_guidance_is_required(self) -> None:
        directory = self.root / "plugins/bedrock/skills/author-execution-relay/templates"
        for name, fragment in (
            ("high-assurance-relay.md", "one pins block, and a carried-value sweep at issue and at receipt with no hits"),
            ("small-relay.md", "**Pins block / sweep:** <every pin once; sweep at issue and at receipt: hits or none>"),
            ("standard-relay.md", "**Pins block / sweep:** <every pin once; sweep at issue and at receipt: hits or none>"),
            ("standard-relay.md", "A gate's cell states its stop rule, never its outcome."),
        ):
            with self.subTest(template=name, fragment=fragment):
                path = directory / name
                baseline = path.read_text(encoding="utf-8")
                path.write_text(baseline.replace(fragment, "[removed]"), encoding="utf-8")
                self.assert_error("carried-value template is missing")
                path.write_text(baseline, encoding="utf-8")


class RelayValueControlTests(unittest.TestCase):
    def test_issue_and_receipt_sweeps_detect_all_planted_forms(self) -> None:
        clean = "# Relay\nDerive the file population at execution.\n| Gate | Stop rule |\n| Verify | Stop on a pin mismatch. |\n"
        planted = clean + "Inspect main.py:123; rev 3\n| Verify | ACCEPTED |\n"
        expected = [
            {"line": 5, "column": 9, "kind": "path-line", "text": "main.py:123"},
            {"line": 5, "column": 22, "kind": "revision", "text": "rev 3"},
            {"line": 6, "column": 12, "kind": "contract-outcome", "text": "ACCEPTED"},
        ]
        for event in ("author-time dry-run", "executor receipt"):
            with self.subTest(event=event):
                self.assertEqual([], sweep_relay(clean))
                self.assertEqual(expected, sweep_relay(planted))

    def test_counts_are_candidates_including_verdict_bearing_counts(self) -> None:
        for text in ("17 files", "Tests: 17", "1,024 members", "rows=2"):
            with self.subTest(text=text):
                hits = sweep_relay(text)
                self.assertEqual(["population-count"], [hit["kind"] for hit in hits])
                self.assertEqual(text, hits[0]["text"])
        # The detector does not invent the judgment that a count is a pin.
        self.assertEqual("population-count", sweep_relay("17 files", pins_block=(1, 1))[0]["kind"])

    def test_pins_outside_block_and_duplicates_are_named(self) -> None:
        pin = "a" * 64
        self.assertEqual([], sweep_relay(pin, pins_block=(1, 1)))
        self.assertEqual("pin-outside-block", sweep_relay(pin)[0]["kind"])
        self.assertEqual("duplicate-pin", sweep_relay(pin + "\n" + pin, pins_block=(1, 2))[0]["kind"])
        with self.assertRaises(ValueError):
            sweep_relay(pin, pins_block=(1, 2))

    def test_pattern_edges_are_explicit_not_semantic_coverage(self) -> None:
        self.assertEqual([], sweep_relay("seventeen files; members are alpha and beta; inspect README:12"))
        self.assertEqual([], sweep_relay("Package 10.0.0; subject HEB-159; run sha256sum -c."))
        # Even a legitimate taxonomy token in a cell is a candidate to disposition.
        hits = sweep_relay("| Gate | Stop if status is FAILED. |")
        self.assertEqual(["contract-outcome"], [hit["kind"] for hit in hits])

    def test_shrink_retained_dropped_and_dispositioned_anchors(self) -> None:
        before = "Check `schema.json`, §2.1 and [gate](#verify); P1 supports F2."
        after = "Check `schema.json`, §2.1 and [gate](#verify); P1."
        self.assertEqual({"`schema.json`", "§2.1", "[gate](#verify)", "P1", "F2"}, relay_anchors(before))
        self.assertEqual([], check_relay_shrink(before, before, {}))
        self.assertEqual(["dropped anchor lacks disposition: F2"], check_relay_shrink(before, after, {}))
        self.assertEqual([], check_relay_shrink(before, after, {"F2": "Moved finding to the gate report; retained P1 rule."}))
        self.assertTrue(check_relay_shrink(before, after, {"F2": " "}))
        self.assertTrue(check_relay_shrink(before, after, {"F2": "Moved", "P1": "stale disposition"}))

    def test_anchor_backstop_does_not_claim_clause_semantics(self) -> None:
        self.assertEqual([], check_relay_shrink("Stop before publish.", "", {}))
        self.assertEqual([], check_relay_shrink("Check `x`. Stop on `x` mismatch.", "Check `x`.", {}))

    def test_reader_must_disclose_nothing_or_complete_tightening(self) -> None:
        def receipt(data):
            return evaluate_behavior_case({"kind": "relay-reader", "input": data})
        self.assertEqual("stop-reader-silent", receipt({}))
        self.assertEqual("stop-reader-silent", receipt({"changes": []}))
        self.assertEqual("accept", receipt({"statement": "adjusted nothing", "changes": []}))
        change = {"kind": "tightening", "before": "check the population", "after": "derive the tracked paths from the pinned checkout", "predecessor_retained": True, "hash_reissued": True}
        self.assertEqual("accept", receipt({"changes": [change]}))
        self.assertEqual("reject", receipt({"statement": "adjusted nothing", "changes": [change]}))
        for field in ("before", "after", "predecessor_retained", "hash_reissued"):
            with self.subTest(field=field):
                self.assertEqual("reject", receipt({"changes": [{**change, field: None}]}))
        for kind in ("loosen-prohibition", "remove-stop", "change-gate"):
            with self.subTest(kind=kind):
                self.assertEqual("stop-operator-reserved", receipt({"changes": [{**change, "kind": kind}]}))
                self.assertEqual("accept", receipt({"changes": [{**change, "kind": kind, "operator_authorized": True}]}))
        self.assertEqual("reject", receipt({"changes": [{**change, "kind": "unknown"}]}))

    def test_native_pin_checks_accept_valid_and_refuse_planted_mismatch(self) -> None:
        checksum = ["sha256sum", "-c", "-"] if shutil.which("sha256sum") else ["shasum", "-a", "256", "-c", "-"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subject = root / "subject.txt"
            subject.write_bytes(b"pinned subject\n")
            digest = hashlib.sha256(subject.read_bytes()).hexdigest()
            valid = subprocess.run(checksum, input=f"{digest}  subject.txt\n", text=True, capture_output=True, cwd=root)
            planted = ("0" if digest[0] != "0" else "1") + digest[1:]
            invalid = subprocess.run(checksum, input=f"{planted}  subject.txt\n", text=True, capture_output=True, cwd=root)
            self.assertEqual(0, valid.returncode, valid.stderr)
            self.assertNotEqual(0, invalid.returncode)
            self.assertIn("subject.txt", invalid.stdout)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            object_id = subprocess.check_output(["git", "hash-object", "-w", "subject.txt"], cwd=root, text=True).strip()
            self.assertEqual(0, subprocess.run(["git", "cat-file", "-e", object_id], cwd=root).returncode)
            self.assertNotEqual(0, subprocess.run(["git", "cat-file", "-e", "0" * 40], cwd=root, capture_output=True).returncode)


if __name__ == "__main__":
    unittest.main()
