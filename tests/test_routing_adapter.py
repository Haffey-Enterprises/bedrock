from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.run_routing_evals import (
    DEFAULT_MAX_BUDGET_USD,
    InvocationResult,
    MatrixFailure,
    _build_parser,
    _classify_invocation_failure,
    _extract_usage,
    _parse_result,
    build_failure_report,
    build_report,
    build_routing_prompt,
    check_authentication,
    execute_case_matrix,
    evaluate_thresholds,
    run_case,
)


class RoutingAdapterResultTests(unittest.TestCase):
    def test_planning_fixture_boundaries_and_adapter_discrimination(self) -> None:
        from scripts.validate_plugin import load_routing_cases, validate_skills, validate_routing
        root = Path(__file__).resolve().parents[1]
        errors = []
        inventory = validate_skills(root, errors)
        cases = validate_routing(root, inventory, errors)
        self.assertEqual([], errors)
        planning = [case for case in cases if case["id"].startswith("planning-")]
        required = {"explicit-assessment", "sequence-overlap", "product-discovery",
                    "record-mutation", "executor-handoff", "specialist-design",
                    "unattended", "tests", "finished-review"}
        self.assertEqual(required, {case.get("planning_boundary") for case in planning})
        self.assertEqual(len(required), len(planning))
        for case in planning:
            with self.subTest(case=case["id"]):
                catalog = [dict(row, name=name) for name, row in inventory.items()]
                prompt = build_routing_prompt(case, catalog)
                self.assertTrue(prompt.endswith(case["prompt"]))
                self.assertIn(inventory["planning"]["description"], prompt)
                for selected, passed in ((case["expected"], True),
                                         ("planning" if "planning" in case["excluded"] else None, False)):
                    envelope = unittest.mock.Mock(returncode=0, stderr="", stdout=json.dumps({
                        "structured_output": {"skill": selected, "reason": "deterministic envelope control"},
                        "total_cost_usd": 0.0}))
                    with patch("scripts.run_routing_evals.subprocess.run", return_value=envelope) as invoke:
                        result = run_case("offline-cli", root, case, catalog, "offline", 0.01, 10)
                    self.assertIs(result.passed, passed)
                    self.assertEqual(subprocess.DEVNULL, invoke.call_args.kwargs["stdin"])

    def test_default_call_budget_matches_documented_contract(self) -> None:
        readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
        normalized_readme = " ".join(readme.split())
        documented_contract = (
            f"Each model call is capped at ${DEFAULT_MAX_BUDGET_USD:.2f} and 120 seconds."
        )

        self.assertEqual(0.04, DEFAULT_MAX_BUDGET_USD)
        self.assertEqual(DEFAULT_MAX_BUDGET_USD, _build_parser().parse_args([]).max_budget_usd)
        self.assertEqual(1, normalized_readme.count(documented_contract))

    def test_api_key_authentication_satisfies_bare_adapter_contract(self) -> None:
        self.assertIsNone(check_authentication({"ANTHROPIC_API_KEY": "test-secret"}))

    def test_subscription_status_does_not_satisfy_bare_adapter_contract(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertIn("ANTHROPIC_API_KEY", check_authentication())

    def test_successful_auth_status_cannot_mask_not_logged_in_invocation(self) -> None:
        completed = unittest.mock.Mock(
            returncode=1,
            stdout=json.dumps({"subtype": "error", "result": "Not logged in"}),
            stderr="",
        )
        with patch(
            "scripts.run_routing_evals.subprocess.run", return_value=completed
        ) as run:
            result = run_case(
                "/usr/local/bin/claude",
                unittest.mock.Mock(),
                {"prompt": "route", "expected": "debug", "kind": "direct"},
                [],
                "haiku",
                0.03,
                120,
            )
            command = run.call_args.args[0]

        self.assertEqual("authentication_failure", result.classification)
        self.assertIsNone(result.passed)
        self.assertEqual(["--bare", "--print"], command[1:3])
        self.assertNotIn("auth", command)

    def test_routing_subprocess_excludes_inherited_launcher_input(self) -> None:
        """The CLI may reread a consumed regular fd or accept a pipe as user input."""
        root = Path(__file__).resolve().parents[1]
        prompt = build_routing_prompt({"prompt": "Diagnose a flaky test."}, [])
        launcher_text = "UNRELATED_LAUNCHER_INPUT_CANARY"
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            executable = directory / "capture-cli"
            capture = directory / "capture.py"
            capture.write_text(
                "import json, os, sys\n"
                "try:\n    os.lseek(0, 0, os.SEEK_SET)\n"
                "except OSError:\n    pass\n"
                "received = {'stdin': sys.stdin.read(), 'prompt': sys.argv[-1]}\n"
                "print(json.dumps({'total_cost_usd': 0.0, 'structured_output': {'skill': 'debug', "
                "'reason': json.dumps(received)}}))\n",
                encoding="utf-8",
            )
            executable.write_text(
                "#!/bin/sh\nexec " + shlex.quote(sys.executable) + " "
                + shlex.quote(str(capture)) + ' "$@"\n', encoding="utf-8",
            )
            executable.chmod(0o700)
            runner = (
                "import json, sys; from pathlib import Path; "
                "from scripts.run_routing_evals import run_case; "
                "result = run_case(sys.argv[1], Path(sys.argv[2]), "
                "{'prompt': 'Diagnose a flaky test.', 'expected': 'debug'}, "
                "[], 'offline', 0.01, 10); "
                "print(json.dumps({'classification': result.classification, "
                "'detail': result.detail}))"
            )
            for mode in ("pipe", "consumed_regular_file"):
                with self.subTest(mode=mode), tempfile.TemporaryFile(mode="w+") as inherited:
                    inherited.write(launcher_text)
                    inherited.flush()  # Keep fd at EOF, as after Python reads a heredoc.
                    stdin_args = {"input": launcher_text} if mode == "pipe" else {"stdin": inherited}
                    control = subprocess.run(
                        [str(executable), prompt], capture_output=True, text=True,
                        check=True, timeout=10, **stdin_args,
                    )
                    received_control = json.loads(json.loads(control.stdout)["structured_output"]["reason"])
                    self.assertEqual(launcher_text, received_control["stdin"])
                    inherited.seek(0, os.SEEK_END)
                    result = subprocess.run(
                        [sys.executable, "-c", runner, str(executable), str(directory)],
                        cwd=root, capture_output=True, text=True, check=True, timeout=15,
                        **stdin_args,
                    )
                    envelope = json.loads(result.stdout)
                    self.assertEqual("route_result", envelope["classification"])
                    received = json.loads(envelope["detail"])
                    self.assertEqual(prompt, received["prompt"])
                    self.assertEqual("", received["stdin"])

    def test_typed_authentication_failure_after_evaluation_begins_fails_fast(self) -> None:
        calls: list[str] = []

        def invoke(case: dict[str, object], _run: int, _budget: float) -> InvocationResult:
            calls.append(str(case["id"]))
            if case["id"] == "b":
                return InvocationResult.failure("authentication_failure")
            return InvocationResult.route(True, "debug", "correct", 0.0, [])

        execution = execute_case_matrix(
            [
                {"id": "a", "kind": "direct", "surface": "shared", "expected": "debug"},
                {"id": "b", "kind": "direct", "surface": "shared", "expected": "debug"},
                {"id": "c", "kind": "direct", "surface": "shared", "expected": "debug"},
            ],
            runs=2,
            max_budget_usd=0.03,
            max_total_budget_usd=None,
            invoke=invoke,
        )

        self.assertEqual(["a", "a", "b"], calls)
        self.assertEqual("authentication_failure", execution.failure.classification)
        self.assertEqual(2, len(execution.results))

    def test_transport_failure_is_not_a_route_miss(self) -> None:
        classification = _classify_invocation_failure("", "connection reset by peer", 1)
        self.assertEqual("transport_failure", classification)

    def test_api_access_failure_is_not_a_route_miss(self) -> None:
        classification = _classify_invocation_failure(
            json.dumps({"type": "permission_error", "message": "forbidden"}), "", 1
        )
        self.assertEqual("api_access_failure", classification)

    def test_typed_model_failure_is_not_a_route_miss(self) -> None:
        completed = unittest.mock.Mock(
            returncode=0,
            stdout=json.dumps({"subtype": "error_max_budget_usd", "total_cost_usd": 0.03}),
            stderr="",
        )
        with patch("scripts.run_routing_evals.subprocess.run", return_value=completed):
            result = run_case(
                "/usr/local/bin/claude",
                unittest.mock.Mock(),
                {"prompt": "route", "expected": "debug", "kind": "direct"},
                [],
                "haiku",
                0.03,
                120,
            )

        self.assertEqual("model_failure", result.classification)
        self.assertIsNone(result.passed)

    def test_genuine_wrong_route_remains_an_evaluation_miss(self) -> None:
        completed = unittest.mock.Mock(
            returncode=0,
            stdout=json.dumps(
                {
                    "structured_output": {"skill": "testing", "reason": "valid but wrong"},
                    "total_cost_usd": 0.01,
                }
            ),
            stderr="",
        )
        with patch("scripts.run_routing_evals.subprocess.run", return_value=completed):
            result = run_case(
                "/usr/local/bin/claude",
                unittest.mock.Mock(),
                {"prompt": "route", "expected": "debug", "kind": "direct"},
                [],
                "haiku",
                0.03,
                120,
            )

        self.assertEqual("route_result", result.classification)
        self.assertFalse(result.passed)
        self.assertEqual("testing", result.selected)

    def test_failure_diagnostic_does_not_retain_secret_output(self) -> None:
        secret = "sk-ant-secret-material"
        completed = unittest.mock.Mock(
            returncode=1,
            stdout=json.dumps({"subtype": "authentication_error", "message": secret}),
            stderr=f"invalid x-api-key {secret}",
        )
        with patch("scripts.run_routing_evals.subprocess.run", return_value=completed):
            result = run_case(
                "/usr/local/bin/claude",
                unittest.mock.Mock(),
                {"prompt": secret, "expected": "debug", "kind": "direct"},
                [],
                "haiku",
                0.03,
                120,
            )

        failure = MatrixFailure(
            case="case-a",
            run=1,
            classification=result.classification,
            diagnostic=result.detail,
            cost_usd=result.cost_usd,
            models=result.models,
        )
        retained = json.dumps(
            build_failure_report(
                model="haiku",
                profile="pr",
                cli_version="2.1.226",
                fixture_digest="fixture",
                catalog_digest="catalog",
                policy_digest="policy",
                generated_at="2026-08-11T00:00:00+00:00",
                completed_case_runs=0,
                failure=failure,
            )
        )
        self.assertNotIn(secret, retained)
        self.assertEqual("authentication_failure", result.classification)

    def test_reads_structured_output(self) -> None:
        payload = {"structured_output": {"skill": "debug", "reason": "failure diagnosis"}}
        self.assertEqual(payload["structured_output"], _parse_result(json.dumps(payload)))

    def test_reads_json_result_fallback(self) -> None:
        result = {"skill": None, "reason": "no matching skill"}
        self.assertEqual(result, _parse_result(json.dumps({"result": json.dumps(result)})))

    def test_rejects_non_object_envelope(self) -> None:
        with self.assertRaisesRegex(ValueError, "envelope must be an object"):
            _parse_result("[]")

    def test_recovers_billed_usage_from_typed_error_envelope(self) -> None:
        payload = json.dumps(
            {
                "subtype": "error_max_budget_usd",
                "total_cost_usd": 0.033976,
                "modelUsage": {"resolved-model": {"costUSD": 0.033976}},
            }
        )
        self.assertEqual((0.033976, ["resolved-model"]), _extract_usage(payload))

    def test_unstructured_failure_has_no_claimed_usage(self) -> None:
        self.assertEqual((None, []), _extract_usage("transport failed"))

    def test_malformed_failure_usage_cannot_mask_terminal_classification(self) -> None:
        payload = json.dumps(
            {"subtype": "authentication_error", "total_cost_usd": "not-a-number"}
        )
        self.assertEqual((None, []), _extract_usage(payload))
        self.assertEqual("authentication_failure", _classify_invocation_failure(payload, "", 1))

    def test_prompt_embeds_authoritative_catalog_and_request(self) -> None:
        prompt = build_routing_prompt(
            {"prompt": "Diagnose a flaky test."},
            [
                {"name": "testing", "description": "New tests only. Do not use for flakes."},
                {"name": "debug", "description": "Use for an existing flaky test."},
            ],
        )

        self.assertIn("- debug: Use for an existing flaky test.", prompt)
        self.assertIn("- testing: New tests only. Do not use for flakes.", prompt)
        self.assertIn("do not infer ownership from a skill name alone", prompt)
        self.assertIn("not binding authority", prompt)
        self.assertIn("select that skill rather than returning null", prompt)
        self.assertTrue(prompt.endswith("Diagnose a flaky test."))

    def test_thresholds_require_aggregate_case_and_exclusion_gates(self) -> None:
        policy = {
            "minimum_overall_pass_rate": 0.75,
            "minimum_case_pass_rate": 0.5,
            "excluded_selection_limit": 0,
        }
        results = [
            {"case": "a", "passed": True, "selected_excluded": False},
            {"case": "a", "passed": False, "selected_excluded": False},
            {"case": "b", "passed": True, "selected_excluded": False},
            {"case": "b", "passed": True, "selected_excluded": False},
        ]
        evaluation = evaluate_thresholds(results, policy)
        self.assertTrue(evaluation["passed"])
        results[-1]["selected_excluded"] = True
        self.assertFalse(evaluate_thresholds(results, policy)["passed"])

    def test_report_carries_reproducibility_identity_and_evaluation(self) -> None:
        results = [
            {
                "case": "a",
                "passed": True,
                "selected_excluded": False,
                "cost_usd": 0.01,
                "models": ["resolved-model"],
            }
        ]
        report = build_report(
            model="haiku",
            profile="pr",
            policy={
                "minimum_overall_pass_rate": 1.0,
                "minimum_case_pass_rate": 1.0,
                "excluded_selection_limit": 0,
            },
            runs=1,
            max_budget_usd=0.03,
            timeout_seconds=120,
            cli_version="1.2.3",
            fixture_digest="fixture-sha",
            catalog_digest="catalog-sha",
            policy_digest="policy-sha",
            results=results,
            max_total_budget_usd=3.0,
        )
        self.assertEqual(2, report["schema_version"])
        self.assertEqual("fixture-sha", report["identity"]["fixture_sha256"])
        self.assertEqual(3.0, report["max_total_budget_usd"])
        self.assertFalse(report["budget_exhausted"])
        self.assertTrue(report["evaluation"]["passed"])
        self.assertTrue(report["evaluation"]["retained_evidence_eligible"])

    def test_targeted_report_cannot_claim_retained_release_evidence(self) -> None:
        results = [
            {
                "case": "a",
                "passed": True,
                "selected_excluded": False,
                "cost_usd": 0.0,
                "models": [],
            }
        ]
        report = build_report(
            model="haiku",
            profile="release",
            policy={
                "minimum_overall_pass_rate": 1.0,
                "minimum_case_pass_rate": 1.0,
                "excluded_selection_limit": 0,
            },
            runs=1,
            max_budget_usd=0.03,
            timeout_seconds=120,
            cli_version="1.2.3",
            fixture_digest="fixture-sha",
            catalog_digest="catalog-sha",
            policy_digest="policy-sha",
            results=results,
            suite_scope="targeted",
            planned_case_ids=["a"],
        )
        self.assertTrue(report["evaluation"]["passed"])
        self.assertFalse(report["evaluation"]["retained_evidence_eligible"])

    def test_report_fails_when_aggregate_budget_is_exceeded(self) -> None:
        results = [
            {
                "case": "a",
                "passed": True,
                "selected_excluded": False,
                "cost_usd": 0.031,
                "models": ["resolved-model"],
            }
        ]
        report = build_report(
            model="haiku",
            profile="release",
            policy={
                "minimum_overall_pass_rate": 1.0,
                "minimum_case_pass_rate": 1.0,
                "excluded_selection_limit": 0,
            },
            runs=1,
            max_budget_usd=0.03,
            timeout_seconds=120,
            cli_version="1.2.3",
            fixture_digest="fixture-sha",
            catalog_digest="catalog-sha",
            policy_digest="policy-sha",
            results=results,
            max_total_budget_usd=0.03,
        )
        self.assertFalse(report["evaluation"]["gates"]["budget"])
        self.assertFalse(report["evaluation"]["passed"])
        self.assertFalse(report["evaluation"]["retained_evidence_eligible"])


if __name__ == "__main__":
    unittest.main()
