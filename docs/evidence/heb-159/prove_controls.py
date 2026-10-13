#!/usr/bin/env python3
"""Reproduce HEB-159 component controls; not RBT-124 adoption or release acceptance.

Run from a tracked-only snapshot, with --git-root naming its source repository.
The evidence specimen's local pins-block grammar is not a new relay schema.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.validate_authoring_contracts import (  # noqa: E402
    check_relay_shrink, evaluate_behavior_case, relay_anchors, sweep_relay,
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(argv: list[str], cwd: Path, stdin: str | None = None) -> dict:
    result = subprocess.run(argv, cwd=cwd, input=stdin, text=True, capture_output=True)
    return {"argv": argv, "cwd": str(cwd), "stdin": stdin, "exit": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--git-root", type=Path, required=True)
    args = parser.parse_args()
    evidence = Path(__file__).parent
    text = (evidence / "relay.md").read_text()
    lines = text.splitlines()
    start = lines.index("```text") + 2
    end = lines.index("```", start)  # inclusive last pin line, in one-based coordinates
    block = (start, end)
    checksum_row, object_row = lines[start - 1:end]
    checksum_pin, schema_relative = checksum_row.split()
    object_pin, object_kind = object_row.split()
    assert object_kind == "git-object"
    schema_bytes = (ROOT / schema_relative).read_bytes()
    checksum = ["sha256sum", "-c", "-"] if shutil.which("sha256sum") else ["shasum", "-a", "256", "-c", "-"]
    pin_valid = run(checksum, ROOT, checksum_row + "\n")
    planted_checksum = ("0" if checksum_pin[0] != "0" else "1") + checksum_pin[1:]
    pin_invalid = run(checksum, ROOT, f"{planted_checksum}  {schema_relative}\n")
    object_valid = run(["git", "cat-file", "-e", object_pin], args.git_root)
    object_invalid = run(["git", "cat-file", "-e", "0" * 40], args.git_root)
    object_bytes = subprocess.check_output(["git", "cat-file", "blob", object_pin], cwd=args.git_root)
    assert pin_valid["exit"] == 0 and pin_invalid["exit"] != 0
    assert object_valid["exit"] == 0 and object_invalid["exit"] != 0
    assert digest(schema_bytes) == checksum_pin and object_bytes == schema_bytes

    clean_issue = sweep_relay(text, pins_block=block)
    clean_receipt = sweep_relay(text, pins_block=block)
    planted_text = text + "\nInspect main.py:123; rev 3\n| Verify | ACCEPTED |\n"
    planted_hits = sweep_relay(planted_text, pins_block=block)
    assert clean_issue == clean_receipt == []
    assert [(hit["kind"], hit["text"]) for hit in planted_hits] == [
        ("path-line", "main.py:123"), ("revision", "rev 3"), ("contract-outcome", "ACCEPTED")]
    count_hits = sweep_relay("17 files")
    outside_pin_hits = sweep_relay(text + "\n" + checksum_pin, pins_block=block)
    assert count_hits and outside_pin_hits

    before = (evidence / "shrink-before.md").read_text()
    after = (evidence / "shrink-after.md").read_text()
    dispositions = json.loads((evidence / "shrink-dispositions.json").read_text())
    dropped = sorted(relay_anchors(before) - relay_anchors(after))
    retained = check_relay_shrink(before, before, {})
    unhandled = check_relay_shrink(before, after, {})
    handled = check_relay_shrink(before, after, dispositions)
    assert retained == handled == [] and dropped == ["F2"]
    assert unhandled == ["dropped anchor lacks disposition: F2"]

    reader = {"statement": "adjusted nothing", "changes": []}
    reader_result = evaluate_behavior_case({"kind": "relay-reader", "input": reader})
    silent_result = evaluate_behavior_case({"kind": "relay-reader", "input": {"changes": []}})
    assert reader_result == "accept" and silent_result == "stop-reader-silent"
    report = {
        "scope": "HEB-159 component proof on the retained read-only schema-verification relay; not the RBT-124/4G adoption consumer",
        "source_root": str(ROOT), "git_root": str(args.git_root.resolve()),
        "specimen_sha256": digest(text.encode()), "schema_subject": schema_relative,
        "pins_block": block,
        "pins": {"checksum_valid": pin_valid, "checksum_planted_mismatch": pin_invalid,
                 "object_valid": object_valid, "object_planted_mismatch": object_invalid,
                 "object_bytes_equal_schema": object_bytes == schema_bytes},
        "sweeps": {"author_time_dry_run": clean_issue, "executor_receipt": clean_receipt,
                   "planted_specimen_sha256": digest(planted_text.encode()),
                   "planted_specimen": planted_text, "planted_hits": planted_hits,
                   "numeric_count_control": count_hits, "outside_pin_control": outside_pin_hits},
        "dispositions": [
            {"candidate": checksum_pin, "disposition": "pin", "reason": "Verdict-bearing schema digest occurs in the checked pins block."},
            {"candidate": "17 files", "disposition": "derived-at-execution", "replacement": "Derive the file population at execution."},
            {"candidate": "main.py:123; rev 3; ACCEPTED in a stop cell", "disposition": "removed", "reason": "Planted carried values are absent from the issued relay."}],
        "shrink": {"before_sha256": digest(before.encode()), "after_sha256": digest(after.encode()),
                   "dropped": dropped, "retained_errors": retained, "undispositioned_errors": unhandled,
                   "dispositions": dispositions, "dispositioned_errors": handled},
        "reader": {"report": reader, "outcome": reader_result, "silent_control": silent_result},
        "limits": ["Pattern coverage is bounded: spelled-out counts, arbitrary member lists, extensionless path citations, short object IDs and prose outcomes may escape.",
                   "Pipe-row outcome tokens can be false-positive candidates, including legitimate stop-rule taxonomy; disposition is judgment.",
                   "Anchor sets cannot prove preservation of duplicate occurrences or anchor-less prose; clause and predecessor diff review remains required.",
                   "The reader fixture checks declared report shape and authorization flags; it does not independently classify an edit's semantics.",
                   "This detects a defect class, not all relay defects. RBT-124/4G adoption evidence is not substituted by this component specimen."]}
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
