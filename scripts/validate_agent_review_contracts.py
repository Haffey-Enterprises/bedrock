#!/usr/bin/env python3
"""Deterministically validate the HEB-116 portable agent/review contracts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError


SHA256 = re.compile(r"^[0-9a-f]{64}$")
SEMVER = re.compile(
    r"""
    ^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)
    (?:-
        (?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)
        (?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*
    )?
    (?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?
    $
    """,
    re.VERBOSE,
)


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA256.fullmatch(value))


def _unique_string_list(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(_nonempty_string(item) for item in value)
        and len(value) == len(set(value))
    )


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _complete_outcomes(
    required_ids: Any,
    results: Any,
    *,
    required_outcome: str,
) -> bool:
    if not _unique_string_list(required_ids) or not isinstance(results, list):
        return False
    result_ids: list[str] = []
    for result in results:
        if (
            not isinstance(result, dict)
            or not _nonempty_string(result.get("id"))
            or result.get("outcome") != required_outcome
            or not _sha256(result.get("evidence_sha256"))
        ):
            return False
        result_ids.append(result["id"])
    return len(result_ids) == len(set(result_ids)) and set(result_ids) == set(required_ids)


def _balanced_json_candidates(text: str) -> list[Any]:
    """Return non-overlapping balanced object/array spans; never choose the first."""
    candidates: list[Any] = []
    start = 0
    while start < len(text):
        while start < len(text) and text[start] not in "[{":
            start += 1
        if start >= len(text):
            break
        stack: list[str] = []
        quoted = escaped = False
        completed = False
        for end in range(start, len(text)):
            char = text[end]
            if quoted:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
                continue
            if char == '"':
                quoted = True
            elif char in "[{":
                stack.append(char)
            elif char in "]}":
                if not stack or (stack[-1], char) not in {("[", "]"), ("{", "}")}:
                    break
                stack.pop()
                if not stack:
                    try:
                        candidates.append(json.loads(text[start : end + 1]))
                    except json.JSONDecodeError:
                        pass
                    start = end + 1
                    completed = True
                    break
        if not completed:
            start += 1
    return candidates


def _load_json(path: Path, errors: list[str]) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: invalid JSON: {exc}")
        return None
    if not isinstance(value, dict):
        errors.append(f"{path}: top level must be an object")
        return None
    return value


def _validate_agent(value: dict[str, Any], path: Path, errors: list[str]) -> None:
    # Schema validation is separate; this semantic check must also survive malformed input.
    budget, attempts, parse, usage = (value.get(k) for k in ("budget", "attempts", "parse", "usage"))
    if not isinstance(budget, dict) or not isinstance(attempts, list) or not isinstance(parse, dict) or not isinstance(usage, dict):
        errors.append(f"{path}: invalid agent execution structure")
        return
    models = [a for a in attempts if isinstance(a, dict) and a.get("kind") == "model"]
    tools = [a for a in attempts if isinstance(a, dict) and a.get("kind") == "tool"]
    for kind, rows in (("model", models), ("tool", tools)):
        if [a.get("attempt") for a in rows] != list(range(1, len(rows) + 1)):
            errors.append(f"{path}: {kind} physical attempt sequence is invalid")
    maximum = budget.get("max_attempts")
    if type(maximum) is int and len(models) > maximum:
        errors.append(f"{path}: aggregate model attempt budget exceeded")
    iterations = [a.get("tool_iteration") for a in tools]
    maximum = budget.get("max_tool_iterations")
    if any(type(i) is not int or i < 1 for i in iterations):
        errors.append(f"{path}: invalid tool iteration")
    elif type(maximum) is int and iterations and max(iterations) > maximum:
        errors.append(f"{path}: tool iteration budget exceeded")
    measures = ("input_tokens", "output_tokens", "spend_micros")
    subtotal, reserved = usage.get("known_subtotal", {}), usage.get("reserved_exposure", {})
    if not isinstance(subtotal, dict) or not isinstance(reserved, dict):
        errors.append(f"{path}: invalid usage accounting")
        return
    if usage.get("status") == "unknown":
        if any(usage.get(k) is not None for k in measures):
            errors.append(f"{path}: unknown usage cannot have numeric totals")
        if not _nonempty_string(usage.get("unknown_reason")):
            errors.append(f"{path}: unknown usage requires a reason")
        if value.get("terminal_disposition") == "succeeded":
            errors.append(f"{path}: unknown usage cannot succeed")
    elif usage.get("status") == "known":
        if any(usage.get(k) != subtotal.get(k) or reserved.get(k) != 0 for k in measures):
            errors.append(f"{path}: known usage must equal subtotal with no outstanding reservation")
    else:
        errors.append(f"{path}: usage status is required")
    if parse.get("response_status") == "absent":
        if parse.get("response_sha256") is not None or parse.get("path") != "failed" or parse.get("candidate_count") != 0 or parse.get("schema_valid_count") != 0:
            errors.append(f"{path}: absent response must have no hash or parsed candidate")
    elif parse.get("response_status") != "present" or not _sha256(parse.get("response_sha256")):
        errors.append(f"{path}: invalid response provenance")
    candidates, valid = parse.get("candidate_count"), parse.get("schema_valid_count")
    if type(candidates) is not int or type(valid) is not int or not 0 <= valid <= candidates:
        errors.append(f"{path}: invalid parsed candidate counts")
    if parse.get("path") in {"native", "whole"} and candidates != 1:
        errors.append(f"{path}: whole/native parse requires one candidate")
    if value.get("terminal_disposition") == "succeeded":
        if not models:
            errors.append(f"{path}: success requires a model attempt")
        if parse.get("path") not in {"native", "whole", "salvaged"} or parse.get("schema_valid_count") != 1 or parse.get("response_status") != "present":
            errors.append(f"{path}: success requires one validated response")
        for key in measures:
            total, limit = usage.get(key), budget.get("max_" + key)
            if type(total) is int and type(limit) is int and total >= limit:
                errors.append(f"{path}: success cannot exhaust the {key} ceiling")


def _validate_review(value: dict[str, Any], path: Path, errors: list[str]) -> None:
    kind = value.get("kind")
    if kind == "reviewer_result":
        if not isinstance(value.get("findings"), list) or not isinstance(value.get("survived_attacks"), list):
            errors.append(f"{path}: reviewer arrays are required")
    elif kind == "arbitration_result":
        if value.get("classification") == "resolvable" and value.get("confidence") == "low":
            errors.append(f"{path}: low-confidence resolvable is invalid")
        if value.get("classification") == "resolvable" and not value.get("authority_locus"):
            errors.append(f"{path}: resolvable arbitration requires authority_locus")
        for field in ("finding_id", "input_sha256"):
            if not SHA256.fullmatch(str(value.get(field, ""))):
                errors.append(f"{path}: invalid {field}")
    else:
        errors.append(f"{path}: unknown design-review result kind")


def evaluate_runner_profile_case(case: dict[str, Any]) -> str:
    profile = case.get("profile")
    if profile == "direct":
        return "direct-review-complete"
    if profile == "multi-perspective":
        return "multi-perspective-review-complete"
    if profile != "runner-backed":
        return "stop-unavailable"
    string_fields = (
        "product_binding_id",
        "product_binding_version",
        "product_binding_owner",
        "product_binding_authority",
        "runner_id",
        "invocation",
        "validator_profile",
    )
    digest_fields = (
        "product_binding_sha256",
        "runner_sha256",
        "compatibility_manifest_sha256",
    )
    if (
        not all(_nonempty_string(case.get(field)) for field in string_fields)
        or not all(_sha256(case.get(field)) for field in digest_fields)
        or not _nonempty_string(case.get("runner_version"))
        or not SEMVER.fullmatch(case["runner_version"])
        or not _nonempty_string(case.get("portable_core_version"))
        or not SEMVER.fullmatch(case["portable_core_version"])
        or not _nonempty_string(case.get("review_schema_version"))
        or not SEMVER.fullmatch(case["review_schema_version"])
    ):
        return "stop-unavailable"

    invocation_sha256 = hashlib.sha256(case["invocation"].encode()).hexdigest()
    expected_subject = {
        "substrate_sha256": None,
        "product_binding_id": case["product_binding_id"],
        "product_binding_version": case["product_binding_version"],
        "product_binding_sha256": case["product_binding_sha256"],
        "product_binding_owner": case["product_binding_owner"],
        "product_binding_authority": case["product_binding_authority"],
        "runner_id": case["runner_id"],
        "runner_version": case["runner_version"],
        "runner_sha256": case["runner_sha256"],
        "portable_core_version": case["portable_core_version"],
        "review_schema_version": case["review_schema_version"],
        "compatibility_manifest_sha256": case["compatibility_manifest_sha256"],
        "invocation_sha256": invocation_sha256,
        "validator_profile": case["validator_profile"],
    }
    evidence = case.get("evidence")
    if not isinstance(evidence, dict) or not isinstance(evidence.get("subject"), dict):
        return "stop-unavailable"
    subject = evidence["subject"]
    expected_subject["substrate_sha256"] = subject.get("substrate_sha256")
    if not _sha256(expected_subject["substrate_sha256"]) or subject != expected_subject:
        return "stop-unavailable"
    if not _complete_outcomes(
        evidence.get("required_actor_ids"),
        evidence.get("actor_results"),
        required_outcome="completed",
    ) or not _complete_outcomes(
        evidence.get("required_gate_ids"),
        evidence.get("gate_results"),
        required_outcome="passed",
    ):
        return "stop-unavailable"
    if not _sha256(evidence.get("ledger_sha256")) or not _sha256(
        evidence.get("evidence_manifest_sha256")
    ):
        return "stop-unavailable"

    verification = evidence.get("verification")
    if not isinstance(verification, dict) or not _nonempty_string(
        verification.get("instrument")
    ):
        return "stop-unavailable"
    method = verification.get("method")
    required_result = {
        "second-derivation": "confirmed",
        "falsification-control": "refused",
    }.get(method)
    if (
        required_result is None
        or verification.get("result") != required_result
        or verification.get("subject_sha256") != _canonical_sha256(subject)
    ):
        return "stop-unavailable"
    return "runner-backed-claim-permitted"


def validate_agent_review_contracts(root: Path, *, required: bool = True) -> list[str]:
    errors: list[str] = []
    registry_path = root / "validation/agent-review-contracts.yaml"
    if not registry_path.is_file():
        return [f"{registry_path}: required agent-review contract registry is missing"] if required else []
    try:
        registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return [f"{registry_path}: invalid registry: {exc}"]
    for relative in registry.get("schemas", {}).values():
        schema = _load_json(root / relative, errors)
        if schema is not None and schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            errors.append(f"{relative}: schema must declare draft 2020-12")
        if schema is not None:
            try:
                Draft202012Validator.check_schema(schema)
            except SchemaError as exc:
                errors.append(f"{relative}: invalid JSON Schema: {exc.message}")
    schema_documents = {
        name: _load_json(root / relative, errors)
        for name, relative in registry.get("schemas", {}).items()
    }
    for relative in registry.get("fixtures", {}).get("valid", []):
        path = root / relative
        value = _load_json(path, errors)
        if value is None:
            continue
        if "actor_id" in value:
            _validate_agent(value, path, errors)
            schema = schema_documents.get("agent_execution")
        else:
            _validate_review(value, path, errors)
            schema = schema_documents.get("design_review_result")
        if schema is not None:
            failures = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda item: list(item.path))
            if failures:
                errors.append(f"{path}: valid fixture or schema failed: {failures[0].message}")
    invalid_rows = registry.get("fixtures", {}).get("invalid", [])
    for row in invalid_rows:
        path = root / row["path"]
        if row["expected"] == "ambiguous salvage":
            if len(_balanced_json_candidates(path.read_text(encoding="utf-8"))) < 2:
                errors.append(f"{path}: ambiguous salvage fixture did not produce multiple candidates")
        else:
            value = _load_json(path, errors)
            fixture_errors: list[str] = []
            if value is not None:
                if "actor_id" in value:
                    _validate_agent(value, path, fixture_errors)
                    schema = schema_documents.get("agent_execution")
                    if schema is not None:
                        fixture_errors.extend(e.message for e in Draft202012Validator(schema).iter_errors(value))
                else:
                    _validate_review(value, path, fixture_errors)
            if not any(row["expected"] in error for error in fixture_errors):
                errors.append(f"{path}: invalid fixture was accepted")
    for relative, markers in registry.get("required_contract_markers", {}).items():
        text = (root / relative).read_text(encoding="utf-8")
        for marker in markers:
            if marker not in text:
                errors.append(f"{relative}: missing required contract marker {marker!r}")
    corpus = "\n".join(path.read_text(encoding="utf-8") for directory in (root / "plugins/bedrock/skills/agent-code", root / "plugins/bedrock/skills/design-review-loop") for path in directory.rglob("*.md"))
    for marker in registry.get("forbidden_markers", []):
        if marker in corpus:
            errors.append(f"agent/review contract: forbidden marker remains {marker!r}")
    for relative in registry.get("forbidden_paths", []):
        if (root / relative).exists():
            errors.append(f"agent/review contract: forbidden path remains {relative!r}")
    runner_cases = registry.get("runner_profile_cases")
    if not isinstance(runner_cases, list) or not runner_cases:
        errors.append("agent/review contract: runner_profile_cases must be a non-empty list")
    else:
        case_ids = [case.get("id") for case in runner_cases if isinstance(case, dict)]
        if len(case_ids) != len(runner_cases) or len(case_ids) != len(set(case_ids)):
            errors.append("agent/review contract: runner profile case ids must be unique")
        for index, case in enumerate(runner_cases):
            if not isinstance(case, dict) or not isinstance(case.get("input"), dict):
                errors.append(f"agent/review contract: runner profile case[{index}] is invalid")
                continue
            actual = evaluate_runner_profile_case(case["input"])
            if actual != case.get("expected"):
                errors.append(
                    f"agent/review contract: runner profile case {case.get('id')!r} "
                    f"expected {case.get('expected')!r}, got {actual!r}"
                )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    errors = validate_agent_review_contracts(args.root.resolve())
    if errors:
        print(f"FAIL: {len(errors)} agent/review contract error(s)", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("PASS: agent/review contracts and fixtures validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
