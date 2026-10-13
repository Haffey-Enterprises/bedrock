"""Independent admission of retained routing execution and custody evidence.

The repository-owned baseline is a reviewed declaration, not producer output.
It binds one historical execution; changing it does not authorize a live run.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any


def _cost(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        value = float(value)
    except (OverflowError, ValueError):
        return None
    return value if math.isfinite(value) and value >= 0 else None


def _object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('duplicate key')
        value[key] = item
    return value


def _json(raw):
    def invalid(_):
        raise ValueError('non-finite number')
    return json.loads(raw, object_pairs_hook=_object, parse_constant=invalid)


def validate_execution(root: Path, report_path: Path, report: dict[str, Any],
                       policy: dict[str, Any], errors: list[str]) -> None:
    """Check baseline, every usage/model row, reconciled budget, and journal."""
    def fail(message):
        errors.append(f'{report_path}: {message}')

    baseline_path = root / 'validation/routing-baseline.json'
    try:
        baseline = _json(baseline_path.read_text())
    except (OSError, ValueError, UnicodeError):
        fail('qualification baseline missing or invalid')
        return
    if not isinstance(baseline, dict) or type(baseline.get('schema_version')) is not int or baseline['schema_version'] != 1:
        fail('qualification baseline must use schema_version 1')
        return
    for field, length in (('execution_source_commit', 40), ('adapter_sha256', 64), ('journal_sha256', 64)):
        if not isinstance(baseline.get(field), str) or not re.fullmatch('[0-9a-f]{' + str(length) + '}', baseline[field]):
            fail(f'qualification baseline {field} missing or invalid')
            return
    for field in ('adapter', 'claude_cli_version', 'requested_model'):
        if not isinstance(baseline.get(field), str) or not baseline[field].strip():
            fail(f'qualification baseline execution identity {field} missing')
            return
    models = baseline.get('resolved_models')
    if not isinstance(models, list) or len(models) != 1 or not isinstance(models[0], str) or not models[0].strip():
        fail('qualification baseline requires one resolved model')
        return
    per_call = _cost(baseline.get('max_budget_usd_per_case_run'))
    total_limit = _cost(baseline.get('max_total_budget_usd'))
    timeout = baseline.get('timeout_seconds_per_case_run')
    if per_call is None or per_call <= 0 or total_limit is None or total_limit <= 0 or type(timeout) is not int or timeout <= 0:
        fail('qualification baseline budget ceilings missing or invalid')
        return
    try:
        adapter_digest = hashlib.sha256((root / 'scripts/run_routing_evals.py').read_bytes()).hexdigest()
    except OSError:
        adapter_digest = None
    if adapter_digest != baseline['adapter_sha256']:
        fail('adapter source differs from qualification baseline; fresh qualification required')
    for field in ('adapter', 'claude_cli_version', 'requested_model', 'resolved_models'):
        if report.get(field) != baseline[field]:
            fail(f'execution identity {field} differs from qualification baseline')
    for field in ('max_budget_usd_per_case_run', 'max_total_budget_usd', 'timeout_seconds_per_case_run'):
        if type(report.get(field)) not in (int, float) or report.get(field) != baseline[field]:
            fail(f'budget declaration {field} differs from qualification baseline')
    if report.get('thresholds') != policy or type(report.get('runs_per_case')) is not int or report['runs_per_case'] != policy.get('runs_per_case'):
        fail('execution thresholds or repetition count differ from release policy')
    rows = report.get('results')
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        fail('execution rows must be a list of mappings')
        return
    known_costs = []
    for index, row in enumerate(rows):
        cost = _cost(row.get('cost_usd'))
        if cost is None or row.get('usage_status') != 'known' or 'usage_reason' not in row or row['usage_reason'] is not None:
            fail(f'row usage missing, invalid or unknown at {index}')
        if row.get('models') != models:
            fail(f'row model differs from qualification baseline at {index}')
        if cost is not None:
            if cost >= per_call:
                fail(f'per-attempt budget exhausted at {index}')
            known_costs.append(cost)
        if type(row.get('run')) is not int:
            fail(f'row run identity invalid at {index}')
    try:
        total = round(math.fsum(known_costs), 8)
    except OverflowError:
        total = float("inf")
    if not math.isfinite(total) or total >= total_limit:
        fail('aggregate budget exhausted')
    if len(known_costs) != len(rows) or _cost(report.get('total_cost_usd')) != total:
        fail('budget total does not reconcile with known row usage')
    evaluation = report.get('evaluation')
    gates = evaluation.get('gates') if isinstance(evaluation, dict) else None
    if report.get('budget_exhausted') is not False or not isinstance(gates, dict) or gates.get('budget') is not True:
        fail('budget gate missing or failed')

    journal_path = report_path.with_suffix('.jsonl')
    try:
        raw = journal_path.read_bytes()
        events = [_json(line) for line in raw.splitlines()]
    except (OSError, ValueError, UnicodeError):
        fail('journal missing or invalid')
        return
    if hashlib.sha256(raw).hexdigest() != baseline['journal_sha256']:
        fail('journal digest differs from qualification baseline')
    if len(events) != 2 + 2 * len(rows) or any(not isinstance(e, dict) for e in events):
        fail('journal event population does not match complete report')
        return
    registration, terminal = events[0], events[-1]
    if registration.get('event') != 'preregistration' or registration.get('schema_version') != 1 or registration.get('expected_model') != models[0]:
        fail('journal preregistration execution identity invalid')
    for field in ('generated_at', 'profile', 'suite_scope', 'runs_per_case', 'requested_model',
                  'claude_cli_version', 'identity', 'thresholds', 'max_budget_usd_per_case_run',
                  'max_total_budget_usd', 'timeout_seconds_per_case_run'):
        if field not in registration or registration[field] != report.get(field):
            fail(f'journal preregistration {field} differs from report')
    planned = registration.get('planned_case_ids')
    if not isinstance(planned, list) or any(not isinstance(c, str) for c in planned) or sorted(planned) != report.get('planned_case_ids'):
        fail('journal planned cases differ from report')
        return
    expected_order = [(case, run) for case in planned for run in range(1, policy['runs_per_case'] + 1)]
    if [(row.get('case'), row.get('run')) for row in rows] != expected_order:
        fail('journal/report draw sequence differs from preregistration')
    spent = 0.0
    for index, row in enumerate(rows):
        started, finished = events[1 + 2 * index:3 + 2 * index]
        if started.get('event') != 'attempt_started' or finished.get('event') != 'attempt_finished':
            fail(f'journal attempt order invalid at {index}')
        if type(started.get('run')) is not int or type(finished.get('run')) is not int:
            fail(f'journal run identity invalid at {index}')
        for field in ('case', 'run'):
            if started.get(field) != row.get(field) or finished.get(field) != row.get(field):
                fail(f'journal attempt identity {field} differs at {index}')
        for field in ('expected', 'kind', 'cue', 'surface'):
            if field not in finished or finished[field] != row.get(field):
                fail(f'journal attempt {field} differs at {index}')
        bound = _cost(started.get('budget_usd'))
        if bound is None or bound <= 0 or bound != min(per_call, total_limit - spent):
            fail(f'journal prospective attempt budget differs at {index}')
        prompt = started.get('prompt_sha256')
        if not isinstance(prompt, str) or not re.fullmatch('[0-9a-f]{64}', prompt):
            fail(f'journal prompt identity missing at {index}')
        outcome = finished.get('outcome')
        if not isinstance(outcome, dict) or outcome.get('classification') != 'route_result':
            fail(f'journal outcome is not a successful returned route at {index}')
            continue
        if _cost(outcome.get('cost_usd')) is None or type(outcome.get('passed')) is not bool or not isinstance(outcome.get('detail'), str):
            fail(f'journal returned draw types invalid at {index}')
        for field in ('selected', 'passed', 'detail', 'cost_usd', 'models', 'usage_status', 'usage_reason'):
            if field not in outcome or field not in row or outcome[field] != row[field]:
                fail(f'journal returned draw {field} differs at {index}')
        cost = _cost(row.get('cost_usd'))
        if cost is not None:
            if bound is not None and cost >= bound:
                fail(f'journal reconciled attempt budget exhausted at {index}')
            spent += cost
    if terminal.get('event') != 'terminal_evaluation':
        fail('journal lacks terminal evaluation')
    for field in ('evaluation', 'total', 'total_cost_usd'):
        if field not in terminal or terminal[field] != report.get(field):
            fail(f'journal terminal {field} differs from report')
