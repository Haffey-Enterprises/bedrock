from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts import run_routing_evals as runner


class RoutingSchemaTests(unittest.TestCase):
    """Only CLI transport and repository discovery are doubled; execution is real."""

    def run_response(self, fields):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for rel in ("tests/fixtures/routing.yaml", "validation/eval-policy.yaml"):
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("synthetic fixture")
            output = root / "report.json"
            case = dict(id="null-control", prompt="synthetic", kind="negative",
                        surface="portable-core", expected=None)
            policy = {"profiles": {"release": dict(runs_per_case=3,
                      minimum_overall_pass_rate=1.0, minimum_case_pass_rate=1.0,
                      excluded_selection_limit=0)}}
            calls = []
            def cli(argv, **kwargs):
                if argv[1] == "--version":
                    return Mock(returncode=0, stdout=runner.DEFAULT_CLI_VERSION, stderr="")
                calls.append(argv)
                body = dict(total_cost_usd=.01, modelUsage={runner.DEFAULT_RESOLVED_MODEL: {}},
                            **fields)
                return Mock(returncode=0, stdout=json.dumps(body), stderr="")
            args = ["runner", "--root", str(root), "--profile", "release",
                    "--output", str(output), "--max-total-budget-usd", "3"]
            with patch("sys.argv", args), patch.object(runner.shutil, "which", return_value="offline-cli"), patch.object(runner, "load_eval_policy", return_value=policy), patch.object(runner, "load_routing_cases", return_value=[case]), patch.object(runner, "validate_repository", return_value=([], {"skills": []})), patch.object(runner.subprocess, "run", side_effect=cli), patch.dict(os.environ, {"ANTHROPIC_API_KEY": "synthetic-offline-key"}), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                status = runner.main()
            report = json.loads(output.read_text())
            events = [json.loads(line) for line in output.with_suffix(".jsonl").read_text().splitlines()]
        return status, len(calls), report, events

    def assert_schema_failure(self, fields):
        status, calls, report, events = self.run_response(fields)
        self.assertEqual((2, 1), (status, calls))
        self.assertEqual("schema_failure", report["failure"]["classification"])
        self.assertEqual(0, report["completed_case_runs"])
        self.assertEqual(.01, report["total_cost_usd"])
        self.assertEqual("terminal_failure", events[-1]["event"])
        outcome = next(e["outcome"] for e in events if e["event"] == "attempt_finished")
        self.assertIsNone(outcome["passed"])
        self.assertEqual("schema_failure", outcome["classification"])

    def test_invalid_schema_stops_before_scoring_or_next_draw_in_both_formats(self):
        invalid = [{}, {"reason": "synthetic"}, {"skill": None},
                   {"skill": None, "reason": None},
                   {"skill": None, "reason": 1},
                   {"skill": False, "reason": "synthetic"},
                   {"skill": [], "reason": "synthetic"},
                   {"skill": {}, "reason": "synthetic"},
                   {"skill": None, "reason": "synthetic", "extra": True},
                   [], None, "synthetic", 0]
        for value in invalid:
            for field in ("structured_output", "result"):
                with self.subTest(value=value, field=field):
                    self.assert_schema_failure({field: value if field == "structured_output" else json.dumps(value)})

    def test_invalid_native_result_cannot_fall_back_to_valid_text(self):
        for value in ({}, [], None):
            with self.subTest(value=value):
                self.assert_schema_failure(dict(structured_output=value,
                    result=json.dumps(dict(skill=None, reason="synthetic"))))

    def test_explicit_null_and_string_controls_in_both_formats(self):
        for skill in (None, "debug"):
            value = dict(skill=skill, reason="synthetic")
            for field in ("structured_output", "result"):
                with self.subTest(skill=skill, field=field):
                    status, calls, report, events = self.run_response(
                        {field: value if field == "structured_output" else json.dumps(value)})
                    self.assertEqual((0 if skill is None else 1, 3), (status, calls))
                    self.assertEqual(3 if skill is None else 0, report["passed"])
                    self.assertEqual("terminal_evaluation", events[-1]["event"])

    def test_duplicate_keys_are_rejected_in_native_and_text_payloads(self):
        duplicates = [
            '{"structured_output":{"skill":"debug","skill":null,"reason":"synthetic"}}',
            '{"structured_output":{"skill":null,"reason":"one","reason":"two"}}',
            '{"structured_output":{},"structured_output":{"skill":null,"reason":"synthetic"}}',
            json.dumps({"result": '{"skill":"debug","skill":null,"reason":"synthetic"}'}),
        ]
        for raw in duplicates:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                runner._parse_result(raw)


if __name__ == "__main__":
    unittest.main()
