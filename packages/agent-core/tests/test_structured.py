"""Critical behaviours: uniqueness salvage, schema rejection, identity stripping."""

import pytest

from agent_core.structured import (
    ParsePath,
    StructuredOutputError,
    parse_structured,
    stamp_identity,
)


SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["answer"],
    "additionalProperties": False,
}


def test_direct_parse():
    raw = '{"answer": "yes", "confidence": 0.9}'
    result = parse_structured(raw, SCHEMA)
    assert result.parse_path == ParsePath.DIRECT
    assert result.data["answer"] == "yes"


def test_salvage_fence_unique():
    raw = 'Here is the result:\n```json\n{"answer": "fenced"}\n```\nThanks.'
    result = parse_structured(raw, SCHEMA, allow_salvage=True, best_effort=True)
    assert result.parse_path == ParsePath.SALVAGE_FENCE
    assert result.data["answer"] == "fenced"


def test_salvage_first_object_unique():
    raw = 'Sure, I think {"answer": "object"} is correct.'
    result = parse_structured(raw, SCHEMA, allow_salvage=True, best_effort=True)
    assert result.parse_path == ParsePath.SALVAGE_FIRST_OBJECT
    assert result.data["answer"] == "object"


def test_ambiguity_two_objects_rejected():
    raw = '{"answer": "one"} and also {"answer": "two"}'
    with pytest.raises(StructuredOutputError) as ei:
        parse_structured(raw, SCHEMA, allow_salvage=True, best_effort=True)
    assert "ambiguous" in str(ei.value).lower() or "uniqueness" in str(ei.value).lower()
    assert ei.value.parse_path == ParsePath.FAILED


def test_fence_plus_outside_both_valid_rejected():
    raw = '```json\n{"answer": "fence"}\n```\nand outside {"answer": "out"}'
    with pytest.raises(StructuredOutputError) as ei:
        parse_structured(raw, SCHEMA, allow_salvage=True, best_effort=True)
    assert ei.value.parse_path == ParsePath.FAILED


def test_salvage_disabled_fails():
    raw = '```json\n{"answer": "x"}\n```'
    with pytest.raises(StructuredOutputError) as ei:
        parse_structured(raw, SCHEMA, allow_salvage=False)
    assert ei.value.parse_path == ParsePath.FAILED


def test_schema_rejects_extra_and_missing():
    with pytest.raises(StructuredOutputError):
        parse_structured('{"answer": "a", "extra": 1}', SCHEMA)
    with pytest.raises(StructuredOutputError):
        parse_structured('{"confidence": 0.5}', SCHEMA)


def test_bool_not_integer():
    schema = {"type": "object", "properties": {"n": {"type": "integer"}}, "required": ["n"]}
    with pytest.raises(StructuredOutputError):
        parse_structured('{"n": true}', schema)


def test_required_without_properties():
    schema = {"type": "object", "required": ["x"]}
    with pytest.raises(StructuredOutputError):
        parse_structured("{}", schema)


def test_additional_properties_false_without_properties_list():
    # With only additionalProperties: false and no properties, extra keys fail
    schema = {"type": "object", "additionalProperties": False}
    with pytest.raises(StructuredOutputError):
        parse_structured('{"a": 1}', schema)
    # empty object is fine
    result = parse_structured("{}", schema)
    assert result.data == {}


def test_identity_strips_model_claims():
    data = {
        "answer": "ok",
        "agent_id": "model-lied",
        "session_id": "fake",
        "project_id": "forged-project",
        "run_id": "forged-run",
    }
    ctx = {"agent_id": "real-agent", "session_id": "sess-1", "invocation_id": "inv-9"}
    stamped = stamp_identity(data, ctx)
    assert stamped["agent_id"] == "real-agent"
    assert stamped["session_id"] == "sess-1"
    assert stamped["invocation_id"] == "inv-9"
    assert "project_id" not in stamped  # model value stripped; context had none
    assert "run_id" not in stamped
    assert stamped["answer"] == "ok"


def test_unparseable_raises():
    with pytest.raises(StructuredOutputError) as ei:
        parse_structured("not json at all", SCHEMA)
    assert ei.value.parse_path == ParsePath.FAILED


def test_invalid_schema_rejected():
    with pytest.raises(StructuredOutputError):
        parse_structured('{"a": 1}', {"type": "not-a-real-type"})


def test_two_identical_separate_objects_ambiguous():
    raw = '{"answer": "same"} then {"answer": "same"}'
    with pytest.raises(StructuredOutputError) as ei:
        parse_structured(raw, SCHEMA, allow_salvage=True, best_effort=True)
    assert ei.value.parse_path == ParsePath.FAILED


def test_same_span_fence_and_object_not_ambiguous():
    # Single fence whose body is the only object — one span may be seen two ways
    raw = '```json\n{"answer": "only"}\n```'
    result = parse_structured(raw, SCHEMA, allow_salvage=True, best_effort=True)
    assert result.data["answer"] == "only"
    assert result.parse_path in (ParsePath.SALVAGE_FENCE, ParsePath.SALVAGE_FIRST_OBJECT, ParsePath.DIRECT)


@pytest.mark.parametrize("context,expected", [({}, {"answer": "ok"}),
    ({"actor_id": "trusted"}, {"answer": "ok", "actor_id": "trusted"})])
def test_configured_identity_never_comes_from_model(tmp_path, context, expected):
    import json
    from agent_core.config import load_config
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"identity_keys": ["actor_id"]}))
    config = load_config(path)
    original = {"answer": "ok", "actor_id": "forged", "agent_id": "forged"}
    assert stamp_identity(original, context, identity_keys=config.identity_keys) == expected
    assert original["actor_id"] == "forged"


def test_unresolved_reference_is_typed_and_content_safe():
    schema = {"$ref": "#/$defs/private_schema_marker"}
    with pytest.raises(StructuredOutputError) as caught:
        parse_structured('{}', schema)
    assert caught.value.diagnostics.reason == "invalid_schema_reference"
    assert "private_schema_marker" not in str(caught.value)
    import traceback
    assert "private_schema_marker" not in "".join(traceback.format_exception(caught.value))
    assert parse_structured('{}', {"$defs": {"ok": {"type": "object"}},
                                  "$ref": "#/$defs/ok"}).data == {}
