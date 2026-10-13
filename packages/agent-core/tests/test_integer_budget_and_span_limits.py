"""Regression controls for integer accounting and unique bounded source spans."""
import json

import pytest

from agent_core import Budget, BudgetExhausted, ParsePath, StructuredOutputError, parse_structured

SCHEMA = {"type": "object", "properties": {"answer": {"type": "string"}},
          "required": ["answer"], "additionalProperties": False}


@pytest.mark.parametrize("method", ["record_tokens", "record_model_attempt"])
@pytest.mark.parametrize("value", [0.75, 1.5, True, False, -1, float("nan"), float("inf"), -float("inf")])
def test_invalid_token_usage_refused_without_silent_undercount(method, value):
    budget = Budget(max_tokens=2)
    budget.record_tokens(1)
    with pytest.raises(ValueError):
        getattr(budget, method)(value)
    snapshot = budget.snapshot()
    assert snapshot.tokens_used == 1
    assert snapshot.spend_used == 0
    assert snapshot.model_attempts == (1 if method == "record_model_attempt" else 0)


@pytest.mark.parametrize("dimension", ["max_tokens", "max_model_attempts", "max_tool_iterations"])
@pytest.mark.parametrize("value", [0.75, 1.5, True, False, -1, float("nan"), float("inf"), -float("inf")])
def test_invalid_integer_budget_dimensions_refused(dimension, value):
    with pytest.raises(ValueError):
        Budget(**{dimension: value})


@pytest.mark.parametrize("method", ["record_tokens", "record_model_attempt"])
def test_integral_float_tokens_count_exactly_at_boundary(method):
    budget = Budget(max_tokens=2.0, max_model_attempts=3.0, max_tool_iterations=4.0)
    for dimension in ("max_tokens", "max_model_attempts", "max_tool_iterations"):
        assert type(getattr(budget, dimension)) is int
    getattr(budget, method)(0.0)
    getattr(budget, method)(1.0)
    assert budget.check("model").tokens_used == 1
    getattr(budget, method)(1)
    with pytest.raises(BudgetExhausted) as caught:
        budget.check("model")
    assert caught.value.dimension == "tokens"
    assert caught.value.snapshot.tokens_used == 2


def test_fractional_spend_and_wall_limits_remain_supported():
    budget = Budget(max_spend=0.75, max_wall_seconds=1.5)
    budget.record_spend(0.25)
    assert budget.snapshot().spend_used == 0.25
    assert budget.max_wall_seconds == 1.5


def fenced_occurrences(payloads):
    # Prefix prevents the separate whole/outer-fence fast path from carrying this test.
    return "prefix\n" + "\n".join("```json\n \t" + payload + " \t\n```" for payload in payloads)


@pytest.mark.parametrize("count,limit", [(33, 64), (33, 33), (64, 64), (1, 1)])
def test_fenced_unique_occurrences_accept_at_bound(count, limit):
    raw = fenced_occurrences([json.dumps({"answer": 7})] * (count - 1) + ['{"answer":"valid"}'])
    result = parse_structured(raw, SCHEMA, allow_salvage=True, best_effort=True, max_candidates=limit)
    assert result.data == {"answer": "valid"}
    assert result.parse_path == ParsePath.SALVAGE_FENCE
    assert result.diagnostics.candidate_count == count
    assert result.diagnostics.schema_valid_count == 1
    assert result.diagnostics.validation_failure_count == count - 1


def test_unique_bound_rejects_even_when_only_one_is_schema_valid():
    raw = fenced_occurrences(['{"answer":7}'] * 64 + ['{"answer":"valid"}'])
    with pytest.raises(StructuredOutputError) as caught:
        parse_structured(raw, SCHEMA, allow_salvage=True, best_effort=True, max_candidates=64)
    assert caught.value.diagnostics.reason == "candidate_limit"


@pytest.mark.parametrize("malformed", ["{bad}", "not json", ""])
def test_malformed_unique_occurrences_consume_bound_before_decoding(malformed):
    raw = fenced_occurrences([malformed, '{"answer":7}', '{"answer":"valid"}'])
    result = parse_structured(raw, SCHEMA, allow_salvage=True, best_effort=True, max_candidates=3)
    assert result.diagnostics.candidate_count == 2  # diagnostics count decoded occurrences
    assert result.diagnostics.validation_failure_count == 1
    assert result.parse_path == ParsePath.SALVAGE_FENCE
    with pytest.raises(StructuredOutputError) as caught:
        parse_structured(raw, SCHEMA, allow_salvage=True, best_effort=True, max_candidates=2)
    assert caught.value.diagnostics.reason == "candidate_limit"


def test_identical_text_in_distinct_spans_stays_ambiguous():
    raw = fenced_occurrences(['{"answer":"same"}', '{"answer":"same"}'])
    with pytest.raises(StructuredOutputError) as caught:
        parse_structured(raw, SCHEMA, allow_salvage=True, best_effort=True, max_candidates=2)
    assert caught.value.diagnostics.reason == "ambiguous"
    assert caught.value.diagnostics.candidate_count == caught.value.diagnostics.schema_valid_count == 2


def test_mixed_fence_and_balanced_paths_keep_source_occurrences():
    raw = 'prefix {"answer":7} ' + fenced_occurrences(['{bad}', '{"answer":"valid"}'])
    result = parse_structured(raw, SCHEMA, allow_salvage=True, best_effort=True, max_candidates=3)
    assert result.parse_path == ParsePath.SALVAGE_FENCE
    assert result.diagnostics.candidate_count == 2
    with pytest.raises(StructuredOutputError) as caught:
        parse_structured(raw, SCHEMA, allow_salvage=True, best_effort=True, max_candidates=2)
    assert caught.value.diagnostics.reason == "candidate_limit"
