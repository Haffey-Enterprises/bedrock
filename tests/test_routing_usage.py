from __future__ import annotations

import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock, patch

from scripts import run_routing_evals as runner


class RoutingUsageTests(unittest.TestCase):
    case = dict(id="usage-control", prompt="synthetic", kind="positive",
                surface="portable-core", expected="debug")

    def outcome(self, value=0.01, *, missing=False, returncode=0):
        envelope = dict(structured_output=dict(skill="debug", reason="synthetic"),
                        modelUsage={runner.DEFAULT_RESOLVED_MODEL: {}})
        if not missing:
            envelope["total_cost_usd"] = value
        with patch.object(runner.subprocess, "run", return_value=Mock(
                returncode=returncode, stdout=json.dumps(envelope), stderr="")):
            return runner.run_case("offline-cli", Path("."), self.case, [],
                                   runner.DEFAULT_RESOLVED_MODEL, .06, 1)

    def test_unknown_usage_stops_actual_adapter_matrix_and_stays_unknown(self):
        cases = [("missing", None, True), ("null", None, False),
                 ("text", "invalid", False), ("numeric-text", "0.01", False),
                 ("boolean", False, False), ("negative", -1, False),
                 ("nan", float("nan"), False), ("infinity", float("inf"), False)]
        for label, value, missing in cases:
            with self.subTest(label=label):
                calls = []
                def invoke(*args):
                    calls.append(args)
                    return self.outcome(value, missing=missing)
                execution = runner.execute_case_matrix(
                    [self.case], runs=2, max_budget_usd=.06,
                    max_total_budget_usd=.05, invoke=invoke)
                self.assertEqual(1, len(calls))
                self.assertEqual([], execution.results)
                self.assertEqual("usage_unknown", execution.failure.classification)
                self.assertIsNone(execution.failure.cost_usd)
                report = runner.build_failure_report(
                    model=runner.DEFAULT_RESOLVED_MODEL, profile="release",
                    cli_version=runner.DEFAULT_CLI_VERSION, fixture_digest="fixture",
                    catalog_digest="catalog", policy_digest="policy", generated_at="synthetic",
                    completed_case_runs=0, failure=execution.failure)
                self.assertIsNone(report["failure"]["cost_usd"])
                self.assertEqual("unknown", report["failure"]["usage_status"])
                draw = self.outcome(value, missing=missing).as_evidence()
                self.assertEqual("debug", draw["selected"])
                self.assertEqual("synthetic", draw["detail"])
                self.assertIsNone(draw["passed"])
                self.assertEqual(runner.FAILURE_DIAGNOSTICS["usage_unknown"], draw["diagnostic"])

    def test_known_zero_and_known_spend_discriminate(self):
        for cost, expected_calls, exhausted in [(0.0, 2, False), (.05, 1, True)]:
            with self.subTest(cost=cost):
                calls = []
                def invoke(*args):
                    calls.append(args)
                    return self.outcome(cost)
                execution = runner.execute_case_matrix(
                    [self.case], runs=2, max_budget_usd=.06,
                    max_total_budget_usd=.05, invoke=invoke)
                self.assertEqual(expected_calls, len(calls))
                self.assertEqual(exhausted, execution.budget_exhausted)
                self.assertIsNone(execution.failure)
                self.assertTrue(all(row["cost_usd"] == cost for row in execution.results))

    def test_matrix_refuses_unknown_cost_from_another_binding(self):
        calls = []
        def invoke(*args):
            calls.append(args)
            return runner.InvocationResult("route_result", True, "debug", "synthetic", None, [])
        execution = runner.execute_case_matrix(
            [self.case], runs=2, max_budget_usd=.06,
            max_total_budget_usd=3, invoke=invoke)
        self.assertEqual(1, len(calls))
        self.assertEqual("usage_unknown", execution.failure.classification)
        self.assertIsNone(execution.failure.cost_usd)

    def test_timeout_and_error_without_usage_do_not_claim_zero(self):
        with patch.object(runner.subprocess, "run",
                          side_effect=subprocess.TimeoutExpired("offline", 1)):
            result = runner.run_case("offline", Path("."), self.case, [], "offline", .06, 1)
        self.assertEqual("transport_failure", result.classification)
        self.assertIsNone(result.cost_usd)
        self.assertIsNone(self.outcome(missing=True, returncode=1).cost_usd)

    def test_error_usage_can_be_recovered_from_stderr(self):
        response = Mock(returncode=1, stdout="",
                        stderr=json.dumps(dict(subtype="authentication_error",
                                               total_cost_usd=.012,
                                               modelUsage={runner.DEFAULT_RESOLVED_MODEL: {}})))
        with patch.object(runner.subprocess, "run", return_value=response):
            result = runner.run_case("offline", Path("."), self.case, [], "offline", .06, 1)
        self.assertEqual("authentication_failure", result.classification)
        self.assertEqual(.012, result.cost_usd)
