"""Admission mutations are synthetic; they never call a provider."""
from copy import deepcopy
import hashlib
import json
import unittest

import test_composed_routing as composed
from scripts import validate_plugin as validator


class RoutingAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = composed.ComposedEvidenceTests()
        self.fixture.setUp()
        self.root = self.fixture.root
        self.payload = self.fixture.current_report()
        self.report = self.root / 'composed.json'
        self.cases = validator.load_routing_cases(self.root, [])
        self.policy = validator.load_eval_policy(self.root, [])
        _, self.inventory = validator.validate_repository(
            self.root, validate_retained_evidence=False, **self.fixture.options)

    def tearDown(self):
        self.fixture.tearDown()

    def errors(self, payload=None):
        self.report.write_text(json.dumps(self.payload if payload is None else payload))
        errors = []
        validator.validate_routing_evidence(self.root, self.cases, self.inventory,
                                            self.policy, errors, self.report)
        return errors

    def test_complete_baseline_and_journal_control(self):
        self.assertEqual([], self.errors())

    def test_each_execution_identity_is_required_and_bound(self):
        for field in ('adapter', 'claude_cli_version', 'requested_model', 'resolved_models'):
            for operation in ('missing', 'different'):
                with self.subTest(field=field, operation=operation):
                    report = deepcopy(self.payload)
                    if operation == 'missing':
                        del report[field]
                    else:
                        report[field] = ['other'] if field == 'resolved_models' else 'other'
                    self.assertTrue(any('execution identity' in e for e in self.errors(report)))
        for models in (None, [], ['other'], [self.payload['requested_model'], 'other']):
            with self.subTest(models=models):
                report = deepcopy(self.payload)
                report['results'][0]['models'] = models
                self.assertTrue(any('row model' in e for e in self.errors(report)))

    def test_each_unknown_invalid_or_missing_usage_is_rejected(self):
        for value in (None, False, '0', -1, float('nan'), float('inf')):
            with self.subTest(cost=value):
                report = deepcopy(self.payload)
                report['results'][0]['cost_usd'] = value
                self.assertTrue(any('row usage' in e for e in self.errors(report)))
        for field, value in (('usage_status', 'unknown'), ('usage_reason', 'missing'),
                             ('cost_usd', None), ('usage_status', None)):
            with self.subTest(field=field):
                report = deepcopy(self.payload)
                if value is None:
                    del report['results'][0][field]
                else:
                    report['results'][0][field] = value
                self.assertTrue(any('row usage' in e for e in self.errors(report)))

    def test_budget_claims_are_recomputed_and_bound(self):
        for field, value in (('total_cost_usd', None), ('total_cost_usd', True),
                             ('total_cost_usd', .01), ('budget_exhausted', True),
                             ('max_total_budget_usd', None), ('max_total_budget_usd', 300),
                             ('max_budget_usd_per_case_run', None), ('timeout_seconds_per_case_run', None)):
            with self.subTest(field=field, value=value):
                report = deepcopy(self.payload); report[field] = value
                self.assertTrue(any('budget' in e for e in self.errors(report)))
        report = deepcopy(self.payload); report['evaluation']['gates']['budget'] = False
        self.assertTrue(any('budget' in e for e in self.errors(report)))
        report = deepcopy(self.payload); report['results'][0]['cost_usd'] = .061
        report['total_cost_usd'] = .061
        self.assertTrue(any('per-attempt budget' in e for e in self.errors(report)))
        report = deepcopy(self.payload)
        for row in report['results']: row['cost_usd'] = .06
        report['total_cost_usd'] = round(.06 * len(report['results']), 8)
        self.assertTrue(any('aggregate budget' in e for e in self.errors(report)))

    def test_missing_or_changed_baseline_and_adapter_fail_closed(self):
        baseline = self.root / 'validation/routing-baseline.json'
        raw = baseline.read_bytes(); baseline.unlink()
        self.assertTrue(any('qualification baseline' in e for e in self.errors()))
        baseline.write_bytes(raw)
        (self.root / 'scripts/run_routing_evals.py').write_text('changed adapter')
        self.assertTrue(any('adapter source' in e for e in self.errors()))

    def test_journal_custody_and_individual_draws_are_required(self):
        journal = self.root / 'composed.jsonl'; raw = journal.read_bytes()
        journal.unlink()
        self.assertTrue(any('journal' in e for e in self.errors()))
        journal.write_bytes(raw + b'{}\n')
        self.assertTrue(any('journal digest' in e for e in self.errors()))
        # Rebind the synthetic digest so semantic checks, not a hash alone,
        # must reject mismatched/missing/reordered/duplicate events.
        original = [json.loads(line) for line in raw.splitlines()]
        for mutation in ('detail', 'cost', 'model', 'missing-finish', 'duplicate', 'order',
                         'preregistration', 'terminal', 'attempt-budget'):
            with self.subTest(mutation=mutation):
                events = deepcopy(original)
                if mutation in ('detail', 'cost', 'model'):
                    field, value = {'detail': ('detail', 'changed'), 'cost': ('cost_usd', .01),
                                    'model': ('models', ['other'])}[mutation]
                    events[2]['outcome'][field] = value
                elif mutation == 'missing-finish': events.pop(2)
                elif mutation == 'duplicate': events[3:5] = deepcopy(events[1:3])
                elif mutation == 'order': events[1], events[2] = events[2], events[1]
                elif mutation == 'preregistration': events[0]['expected_model'] = 'other'
                elif mutation == 'terminal': events[-1]['total_cost_usd'] = 1
                elif mutation == 'attempt-budget': events[1]['budget_usd'] = 0
                journal.write_text(''.join(json.dumps(e) + '\n' for e in events))
                baseline = self.root / 'validation/routing-baseline.json'
                value = json.loads(baseline.read_text())
                value['journal_sha256'] = hashlib.sha256(journal.read_bytes()).hexdigest()
                baseline.write_text(json.dumps(value))
                self.assertTrue(any('journal' in e for e in self.errors()), self.errors())


if __name__ == '__main__':
    unittest.main()
