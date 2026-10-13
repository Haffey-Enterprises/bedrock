import dataclasses
import pytest
from agent_core import parse_structured, StructuredOutputError, ParsePath

S = {"type": "object", "properties": {"answer": {"type": "string"}},
     "required": ["answer"], "additionalProperties": False}

@pytest.mark.parametrize("raw", ['{"answer":"ok"}', ' \n {"answer":"ok"} \n'])
@pytest.mark.parametrize("salvage", [False, True])
def test_whole_precedes_salvage(raw, salvage):
    r = parse_structured(raw, S, allow_salvage=salvage, best_effort=salvage)
    assert r.parse_path == ParsePath.DIRECT
    assert r.diagnostics.candidate_count == r.diagnostics.schema_valid_count == 1

@pytest.mark.parametrize("raw", ['prefix {"answer":"ok"}', '```json\n{"answer":"ok"}\n```'])
def test_whole_default_rejects_wrapping(raw):
    with pytest.raises(StructuredOutputError) as e:
        parse_structured(raw, S)
    assert e.value.diagnostics.reason == "no_json"

def test_one_outer_fence_and_normalized_span():
    r = parse_structured('  ```json\n  {"answer":"ok"}  \n```  ', S, allow_salvage=True)
    assert r.parse_path == ParsePath.SALVAGE_FENCE
    assert r.diagnostics.candidate_count == 1
    with pytest.raises(StructuredOutputError):
        parse_structured('prefix ```json\n{"answer":"ok"}\n```', S, allow_salvage=True)

@pytest.mark.parametrize("raw,reason", [
    ('no json', 'no_json'), ('{"answer":3}', 'schema_invalid'),
    ('{"answer":"a","answer":"b"}', 'duplicate_key'),
    ('{"answer":NaN}', 'non_finite'), ('[]', 'schema_invalid')])
def test_typed_safe_diagnostics(raw, reason):
    with pytest.raises(StructuredOutputError) as e:
        parse_structured(raw, S)
    assert e.value.diagnostics.reason == reason
    assert "answer" not in str(dataclasses.asdict(e.value.diagnostics))

def test_mixed_and_ambiguous_best_effort():
    r = parse_structured('{"answer":7} then {"answer":"ok"}', S,
                         allow_salvage=True, best_effort=True)
    assert (r.diagnostics.candidate_count, r.diagnostics.schema_valid_count,
            r.diagnostics.validation_failure_count) == (2, 1, 1)
    with pytest.raises(StructuredOutputError) as e:
        parse_structured('{"answer":"same"} then {"answer":"same"}', S,
                         allow_salvage=True, best_effort=True)
    assert e.value.diagnostics.reason == "ambiguous"
    assert e.value.diagnostics.schema_valid_count == 2

def test_does_not_extract_from_schema_invalid_whole():
    with pytest.raises(StructuredOutputError) as e:
        parse_structured('{"nested":{"answer":"ok"}}', S,
                         allow_salvage=True, best_effort=True)
    assert e.value.diagnostics.candidate_count == 1
    assert e.value.diagnostics.reason == "schema_invalid"

def test_resource_limits_and_controls():
    raw = '{"answer":"ok"}'
    assert parse_structured(raw, S, max_input_bytes=len(raw)).data["answer"] == "ok"
    for text, kwargs, reason in [(raw, {"max_input_bytes":len(raw)-1}, "byte_limit"),
        ('['*1000 + ']'*1000, {}, "depth_limit"),
        ('{} {}', {"allow_salvage":True,"best_effort":True,"max_candidates":1}, "candidate_limit")]:
        with pytest.raises(StructuredOutputError) as e:
            parse_structured(text, S, **kwargs)
        assert e.value.diagnostics.reason == reason
    assert parse_structured('{"answer":"[{}]"}', S, max_depth=1).data["answer"] == "[{}]"


@pytest.mark.parametrize("prefix", ["", 'prefix " '])
def test_prose_quote_cannot_hide_candidate_depth(prefix):
    nested = '{"a":' * 9 + '{}' + '}' * 9
    with pytest.raises(StructuredOutputError) as e:
        parse_structured(prefix + nested, {"type":"object"}, max_depth=2,
                         allow_salvage=True, best_effort=True)
    assert e.value.diagnostics.reason == "depth_limit"
    shallow = parse_structured(prefix + '{"answer":"ok"}', S, max_depth=2,
                               allow_salvage=True, best_effort=True)
    assert shallow.data["answer"] == "ok"
