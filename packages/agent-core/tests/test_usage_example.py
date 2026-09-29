from pathlib import Path
import pytest
import agent_core

@pytest.mark.parametrize("fault", ["none", "transport", "accounting"])
def test_documented_example_counts_one_physical_attempt(tmp_path, monkeypatch, fault):
    usage = Path(__file__).parents[1] / "USAGE.md"
    code = usage.read_text().split("```python\n", 1)[1].split("```", 1)[0]
    cfg = tmp_path / "config.json"
    cfg.write_text("{}")
    code = code.replace('"/path/to/agent_config.json"', repr(str(cfg)))
    if fault == "transport":
        raw_line = next(line.strip() for line in code.splitlines() if line.strip().startswith("raw ="))
        code = code.replace(raw_line,
                            'raise RuntimeError("simulated transport")')
    if fault == "accounting":
        code = code.replace('actual_tokens, actual_spend = 100, 0.001',
                            'actual_tokens, actual_spend = 100, float("nan")')
    records = []
    original = agent_core.emit_evidence
    def capture(*args, **kwargs):
        rec = original(*args, **kwargs)
        records.append(rec.to_dict())
        return rec
    monkeypatch.setattr(agent_core, "emit_evidence", capture)
    if fault == "none":
        exec(code, {})
    else:
        with pytest.raises((RuntimeError, ValueError)):
            exec(code, {})
    assert len(records) == 1
    assert records[0]["model_attempts"] == 1
    if fault != "none":
        assert records[0]["payload"]["usage_status"] == "unknown"
        assert records[0]["disposition"] == "provider_error"
