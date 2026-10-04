from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import test_validate_plugin as fixtures
from scripts import run_routing_evals as runner
from scripts import validate_plugin as validator

MODEL = "claude-haiku-4-5-20251001"
CLI = "2.1.226 (Claude Code)"


class ComposedEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ValidatorTests()
        self.fixture.setUp()
        self.root = self.fixture.root
        self.options = dict(run_host_cli=False, run_safety_checks=False,
                            require_authoring_contracts=False, require_package_governance=False)

    def tearDown(self):
        self.fixture.tearDown()

    def current_report(self):
        errors, inventory = validator.validate_repository(
            self.root, validate_retained_evidence=False, **self.options)
        self.assertEqual([], errors)
        cases = validator.load_routing_cases(self.root, [])
        policy = validator.load_eval_policy(self.root, [])["profiles"]["release"]
        results = [dict(case=c["id"], kind=c["kind"], cue=c["cue"], surface=c["surface"],
                        run=n, expected=c["expected"], selected=c["expected"],
                        selected_excluded=False, passed=True, cost_usd=0.0, models=[MODEL],
                        detail="synthetic route", usage_status="known", usage_reason=None)
                   for c in cases for n in range(1, 4)]
        report = runner.build_report(
            model=MODEL, profile="release", policy=policy, runs=3,
            max_budget_usd=.06, timeout_seconds=120, cli_version=CLI,
            fixture_digest=hashlib.sha256((self.root / "tests/fixtures/routing.yaml").read_bytes()).hexdigest(),
            catalog_digest=hashlib.sha256(json.dumps(inventory["skills"], sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            policy_digest=hashlib.sha256((self.root / "validation/eval-policy.yaml").read_bytes()).hexdigest(),
            results=results, planned_case_ids=[c["id"] for c in cases], max_total_budget_usd=3.0)
        self.retain_custody(report)
        return report

    def retain_custody(self, report):
        """Synthetic independent baseline and journal, never a live observation."""
        adapter = self.root / "scripts/run_routing_evals.py"
        adapter.parent.mkdir(exist_ok=True)
        adapter.write_text("synthetic adapter source")
        fields = ("generated_at", "profile", "suite_scope", "planned_case_ids", "runs_per_case",
                  "requested_model", "claude_cli_version", "identity", "thresholds",
                  "max_budget_usd_per_case_run", "max_total_budget_usd", "timeout_seconds_per_case_run")
        events = [dict(event="preregistration", schema_version=1, expected_model=MODEL,
                       **{k: report[k] for k in fields})]
        events[0]["planned_case_ids"] = list(dict.fromkeys(row["case"] for row in report["results"]))
        for row in report["results"]:
            events.append(dict(event="attempt_started", case=row["case"], run=row["run"],
                               budget_usd=.06, prompt_sha256="a" * 64))
            events.append(dict(event="attempt_finished", **{k: row[k] for k in
                ("case", "run", "expected", "kind", "cue", "surface")},
                outcome=dict(classification="route_result", **{k: row[k] for k in
                ("passed", "selected", "detail", "cost_usd", "models", "usage_status", "usage_reason")})))
        events.append(dict(event="terminal_evaluation", evaluation=report["evaluation"],
                           total=report["total"], total_cost_usd=report["total_cost_usd"]))
        journal = self.root / "composed.jsonl"
        journal.write_text("".join(json.dumps(e) + "\n" for e in events))
        baseline = dict(schema_version=1, execution_source_commit="1" * 40,
            adapter="claude-code", claude_cli_version=CLI, requested_model=MODEL,
            resolved_models=[MODEL], max_budget_usd_per_case_run=.06,
            max_total_budget_usd=3.0, timeout_seconds_per_case_run=120,
            adapter_sha256=hashlib.sha256(adapter.read_bytes()).hexdigest(),
            journal_sha256=hashlib.sha256(journal.read_bytes()).hexdigest())
        (self.root / "validation/routing-baseline.json").write_text(json.dumps(baseline))

    def test_selected_report_passes_without_rewriting_historical_report(self):
        historical = self.root / "docs/evidence/heb-109/routing-results.json"
        historical.write_text("{}")
        report = self.root / "composed.json"
        report.write_text(json.dumps(self.current_report()))
        errors, _ = validator.validate_repository(self.root, routing_evidence=report, **self.options)
        self.assertEqual([], errors)
        self.assertEqual("{}", historical.read_text())
        report.unlink()
        errors, _ = validator.validate_repository(self.root, routing_evidence=report, **self.options)
        self.assertTrue(any("routing evidence is missing" in e for e in errors), errors)

    def test_missing_default_report_fails_closed(self):
        errors, _ = validator.validate_repository(self.root, **self.options)
        self.assertTrue(any("routing evidence is missing" in e for e in errors), errors)

    def test_selected_stale_report_is_not_accepted(self):
        report = self.root / "composed.json"
        payload = self.current_report()
        payload["identity"]["catalog_sha256"] = "0" * 64
        report.write_text(json.dumps(payload))
        errors, _ = validator.validate_repository(self.root, routing_evidence=report, **self.options)
        self.assertTrue(any("identity drift" in e for e in errors), errors)

    def test_selected_report_with_policy_permitted_miss_is_accepted(self):
        payload = self.current_report()
        payload["results"][0]["selected"] = "not-a-skill"
        payload["results"][0]["passed"] = False
        payload["passed"] -= 1
        payload["evaluation"] = runner.evaluate_thresholds(payload["results"], payload["thresholds"])
        payload["evaluation"].update(suite_complete=True, retained_evidence_eligible=True)
        payload["evaluation"]["gates"]["budget"] = True
        self.retain_custody(payload)
        report = self.root / "composed.json"
        report.write_text(json.dumps(payload))
        errors, _ = validator.validate_repository(self.root, routing_evidence=report, **self.options)
        self.assertEqual([], errors)

    def test_selected_report_cannot_override_recomputed_policy_gates(self):
        cases = validator.load_routing_cases(self.root, [])
        excluded_case = next(c for c in cases if c.get("excluded"))
        for gate in ("overall", "per-case", "excluded"):
            with self.subTest(gate=gate):
                payload = self.current_report()
                rows = payload["results"]
                if gate == "overall":
                    changed = rows
                elif gate == "per-case":
                    changed = rows[:2]
                else:
                    changed = [next(r for r in rows if r["case"] == excluded_case["id"])]
                for row in changed:
                    row["selected"] = excluded_case["excluded"][0] if gate == "excluded" else "not-a-skill"
                    row["passed"] = False
                    row["selected_excluded"] = gate == "excluded"
                payload["passed"] -= len(changed)
                payload["evaluation"]["excluded_selections"] = int(gate == "excluded")
                # Keep the original green aggregate flags: row evidence must win.
                report = self.root / "composed.json"
                report.write_text(json.dumps(payload))
                errors, _ = validator.validate_repository(self.root, routing_evidence=report, **self.options)
                self.assertTrue(any("recomputed routing outcomes fail" in e for e in errors), errors)

    def test_cli_selection_is_forwarded_and_cannot_be_skipped(self):
        args = ["validator", "--root", str(self.root), "--routing-evidence", "composed.json"]
        with patch("sys.argv", args), patch.object(validator, "validate_repository", return_value=([], {"skill_count": 15})) as check, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, validator.main())
        self.assertEqual(self.root.resolve() / "composed.json", check.call_args.kwargs["routing_evidence"])
        with patch("sys.argv", args + ["--component"]), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                validator.main()


class RoutingCustodyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for rel in ("tests/fixtures/routing.yaml", "validation/eval-policy.yaml"):
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("offline fixture")
        self.output = self.root / "evidence/report.json"
        self.cases = [dict(id=x, prompt="synthetic", kind="positive", surface="portable-core", expected="debug") for x in ("a", "b", "c")]
        self.policy = {"profiles": {"pr": {"runs_per_case": 1, "minimum_overall_pass_rate": 1.0, "minimum_case_pass_rate": 1.0, "excluded_selection_limit": 0}}}

    def tearDown(self):
        self.temp.cleanup()

    def run_offline(self, outcomes=None, cli=CLI, extra=(), observer=None):
        outcomes = iter(outcomes or [runner.InvocationResult.route(True, "debug", "retained detail", .01, [MODEL])] * 3)
        def invoke(*args):
            if observer:
                observer()
            return next(outcomes)
        args = ["runner", "--root", str(self.root), "--profile", "pr", "--output", str(self.output), *extra]
        with patch("sys.argv", args), patch.object(runner.shutil, "which", return_value="offline-only-cli"), patch.object(runner, "load_eval_policy", return_value=self.policy), patch.object(runner, "load_routing_cases", return_value=self.cases), patch.object(runner, "validate_repository", return_value=([], {"skills": []})), patch.object(runner.subprocess, "run", return_value=Mock(returncode=0, stdout=cli, stderr="")), patch.object(runner, "run_case", side_effect=invoke) as call, patch.dict(os.environ, {"ANTHROPIC_API_KEY": "synthetic-offline-key"}), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            status = runner.main()
        return status, call.call_count

    def events(self):
        return [json.loads(line) for line in self.output.with_suffix(".jsonl").read_text().splitlines()]

    def test_terminal_failure_retains_all_earlier_draw_fields(self):
        status, calls = self.run_offline([
            runner.InvocationResult.route(True, "debug", "first detail", .012, [MODEL]),
            runner.InvocationResult.failure("transport_failure")])
        self.assertEqual((2, 2), (status, calls))
        events = self.events()
        draws = [e for e in events if e["event"] == "attempt_finished"]
        self.assertEqual(2, len(draws))
        self.assertEqual("first detail", draws[0]["outcome"]["detail"])
        self.assertEqual(.012, draws[0]["outcome"]["cost_usd"])
        self.assertEqual([MODEL], draws[0]["outcome"]["models"])
        self.assertEqual("transport_failure", draws[1]["outcome"]["classification"])
        self.assertEqual("failed", json.loads(self.output.read_text())["status"])

    def test_unknown_usage_keeps_prior_spend_and_stops_with_truthful_journal(self):
        status, calls = self.run_offline([
            runner.InvocationResult.route(True, "debug", "known", .012, [MODEL]),
            runner.InvocationResult.route(True, "debug", "unknown", None, [MODEL])])
        self.assertEqual((2, 2), (status, calls))
        report = json.loads(self.output.read_text())
        self.assertIsNone(report["total_cost_usd"])
        self.assertEqual(.012, report["known_cost_subtotal_usd"])
        self.assertEqual("unknown", report["usage_status"])
        self.assertEqual("usage_unknown", report["failure"]["classification"])
        draws = [e for e in self.events() if e["event"] == "attempt_finished"]
        self.assertEqual(2, len(draws))
        self.assertIsNone(draws[-1]["outcome"]["cost_usd"])
        self.assertIsNone(draws[-1]["outcome"]["passed"])
        self.assertEqual("unknown", draws[-1]["outcome"]["usage_status"])
        self.assertEqual("debug", draws[-1]["outcome"]["selected"])
        self.assertEqual("unknown", draws[-1]["outcome"]["detail"])
        self.assertEqual(runner.FAILURE_DIAGNOSTICS["usage_unknown"],
                         draws[-1]["outcome"]["diagnostic"])
        self.assertEqual(runner.FAILURE_DIAGNOSTICS["usage_unknown"],
                         report["failure"]["diagnostic"])
        self.assertEqual("terminal_failure", self.events()[-1]["event"])

    def test_each_result_is_on_disk_before_next_invocation(self):
        observed = []
        def observe():
            observed.append(sum(e["event"] == "attempt_finished" for e in self.events()))
        status, calls = self.run_offline(observer=observe)
        self.assertEqual((0, 3), (status, calls))
        self.assertEqual([0, 1, 2], observed)
        self.assertTrue(json.loads(self.output.read_text())["evaluation"]["passed"])

    def test_report_update_preserves_another_invocations_temporary_named_report(self):
        prior = self.output.with_suffix(".json.tmp")
        prior.parent.mkdir()
        prior.write_text("independent prior evidence")
        status, calls = self.run_offline()
        self.assertEqual((0, 3), (status, calls))
        self.assertEqual("independent prior evidence", prior.read_text())
        self.assertEqual([], list(self.output.parent.glob(".report.json.*.tmp")))

    def test_existing_report_is_never_overwritten(self):
        self.output.parent.mkdir()
        self.output.write_text("prior evidence")
        status, calls = self.run_offline()
        self.assertEqual((2, 0), (status, calls))
        self.assertEqual("prior evidence", self.output.read_text())

    def test_existing_journal_is_never_overwritten(self):
        journal = self.output.with_suffix(".jsonl")
        journal.parent.mkdir()
        journal.write_text("prior journal")
        status, calls = self.run_offline()
        self.assertEqual((2, 0), (status, calls))
        self.assertEqual("prior journal", journal.read_text())

    def test_cli_drift_stops_before_model_call(self):
        status, calls = self.run_offline(cli="2.1.284 (Claude Code)")
        self.assertEqual((2, 0), (status, calls))

    def test_resolved_model_drift_or_missing_identity_stops_next_call(self):
        for models in (["unexpected-model"], []):
            with self.subTest(models=models):
                self.output = self.root / ("drift-" + str(len(models)) + ".json")
                status, calls = self.run_offline([runner.InvocationResult.route(True, "debug", "route", .01, models)])
                self.assertEqual((2, 1), (status, calls))
                self.assertEqual("identity_mismatch", json.loads(self.output.read_text())["failure"]["classification"])
                self.assertEqual(models, [e for e in self.events() if e["event"] == "attempt_finished"][0]["outcome"]["models"])

    def test_journal_sync_failure_prevents_dispatch(self):
        with patch.object(runner.os, "fsync", side_effect=OSError("offline disk fault")):
            status, calls = self.run_offline()
        self.assertEqual((2, 0), (status, calls))

    def test_result_sync_failure_stops_before_another_draw(self):
        original = runner.append_event
        def fail_on_result(path, event):
            if event["event"] == "attempt_finished":
                raise OSError("offline result storage fault")
            return original(path, event)
        with patch.object(runner, "append_event", side_effect=fail_on_result):
            status, calls = self.run_offline()
        self.assertEqual((2, 1), (status, calls))
        self.assertEqual("attempt_started", self.events()[-1]["event"])
        self.assertEqual("incomplete", json.loads(self.output.read_text())["status"])

    def test_report_and_journal_paths_cannot_collide(self):
        self.output = self.root / "colliding.jsonl"
        status, calls = self.run_offline()
        self.assertEqual((2, 0), (status, calls))


if __name__ == "__main__":
    unittest.main()
