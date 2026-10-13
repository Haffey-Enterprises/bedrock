"""File-controlled config: strict keys, finite limits, identity."""

import json
from pathlib import Path

import pytest

from agent_core.config import CoreConfig, config_to_dict, load_config
from agent_core.evidence import InvocationContext, emit_evidence
from agent_core.structured import stamp_identity
from agent_core.types import TerminalDisposition


def test_load_config_defaults(tmp_path: Path):
    p = tmp_path / "cfg.json"
    p.write_text("{}")
    cfg = load_config(p)
    assert cfg.allow_salvage is False
    assert cfg.max_model_attempts == 8
    assert cfg.max_spend == 1.0
    b = cfg.make_budget()
    assert b.max_tokens == 128_000


def test_load_config_overrides(tmp_path: Path):
    p = tmp_path / "cfg.json"
    p.write_text(
        json.dumps(
            {
                "allow_salvage": False,
                "budget": {"max_model_attempts": 3, "max_spend": 0.25},
                "identity_keys": ["agent_id", "project_id"],
            }
        )
    )
    cfg = load_config(p)
    assert cfg.allow_salvage is False
    assert cfg.max_model_attempts == 3
    assert cfg.max_spend == 0.25
    assert cfg.identity_keys == ("agent_id", "project_id")


def test_rejects_nan_spend(tmp_path: Path):
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps({"budget": {"max_spend": float("nan")}}))
    # JSON may serialize nan as NaN which is non-standard; write literal
    p.write_text('{"budget": {"max_spend": NaN}}')
    with pytest.raises((ValueError, json.JSONDecodeError)):
        load_config(p)


def test_rejects_unknown_keys(tmp_path: Path):
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps({"budget": {"max_spned": 1.0}}))
    with pytest.raises(ValueError, match="unknown"):
        load_config(p)
    p.write_text('{"nope": true}')
    with pytest.raises(ValueError, match="unknown"):
        load_config(p)


def test_rejects_non_object_budget(tmp_path: Path):
    p = tmp_path / "cfg.json"
    p.write_text('{"budget": false}')
    with pytest.raises(ValueError, match="object"):
        load_config(p)


def test_identity_includes_project_and_run():
    ctx = InvocationContext(
        agent_id="a1",
        session_id="s1",
        invocation_id="i1",
        parent_invocation_id="p0",
        run_id="run-9",
        project_id="proj-x",
    )
    m = ctx.identity_map()
    assert m["run_id"] == "run-9"
    assert m["project_id"] == "proj-x"
    stamped = stamp_identity({"answer": 1, "project_id": "forged"}, m)
    assert stamped["project_id"] == "proj-x"
    assert "forged" not in str(stamped.values())
    rec = emit_evidence(ctx, TerminalDisposition.SUCCESS)
    d = rec.to_dict()
    assert d["project_id"] == "proj-x"
    assert d["run_id"] == "run-9"


def test_config_roundtrip():
    cfg = CoreConfig(allow_salvage=False, max_spend=2.5)
    d = config_to_dict(cfg)
    assert d["allow_salvage"] is False
    assert d["budget"]["max_spend"] == 2.5
