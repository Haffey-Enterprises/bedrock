#!/usr/bin/env python3
"""Deterministic Bedrock plugin validation for HEB-108 / minimum HEB-109."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any
from urllib.parse import unquote

import yaml
from yaml.constructor import ConstructorError
from yaml.resolver import BaseResolver

if __package__:
    from scripts.validate_agent_review_contracts import validate_agent_review_contracts
    from scripts.validate_application_test_debug_contracts import validate_application_test_debug_contracts
    from scripts.validate_authoring_contracts import validate_authoring_contracts
    from scripts.validate_frontend_contracts import validate_frontend_contracts
    from scripts.validate_infrastructure_delivery_contracts import validate_infrastructure_delivery_contracts
    from scripts.validate_package_governance import validate_package_governance
    from scripts.validate_safety import validate_safety_contracts
else:  # Direct execution: python scripts/validate_plugin.py
    from validate_agent_review_contracts import validate_agent_review_contracts
    from validate_application_test_debug_contracts import validate_application_test_debug_contracts
    from validate_authoring_contracts import validate_authoring_contracts
    from validate_frontend_contracts import validate_frontend_contracts
    from validate_infrastructure_delivery_contracts import validate_infrastructure_delivery_contracts
    from validate_package_governance import validate_package_governance
    from validate_safety import validate_safety_contracts


EXPECTED_SKILLS = (
    "agent-builder",
    "agent-code",
    "app-delivery-pipeline",
    "application-code",
    "author-construct-spec",
    "author-decision-record",
    "author-execution-relay",
    "author-standard",
    "code-review",
    "debug",
    "design-review-loop",
    "frontend-code",
    "infrastructure-code",
    "planning",
    "testing",
)
NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DESCRIPTION_LIMIT = 1024
ROUTING_SCHEMA_VERSION = 2
ROUTING_CUES = {"direct", "implicit", "adversarial"}
SAMPLE_CLASSIFICATIONS = {"fixture-backed", "syntax-checked", "illustrative", "deferred"}
MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
PRIVATE_PATH_PATTERN = re.compile(r"(?:/Users/|/home/|/root/|/tmp/|~/|file://|[A-Za-z]:\\\\Users\\\\)")
EXTERNAL_ROOT_PATTERN = re.compile(r"\$([A-Z][A-Z0-9_]*_ROOT)/")
CODE_FENCE_PATTERN = re.compile(r"^```([A-Za-z0-9_+-]+)\s*$", re.MULTILINE)


class UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate keys before they collapse."""


def _construct_unique_mapping(
    loader: UniqueKeyLoader,
    node: yaml.nodes.MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "unhashable YAML key",
                key_node.start_mark,
            ) from exc
        if duplicate:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"duplicate YAML key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping)


def _error(errors: list[str], location: Path | str, message: str) -> None:
    errors.append(f"{location}: {message}")


def parse_frontmatter(path: Path, errors: list[str]) -> dict[str, Any] | None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        _error(errors, path, f"cannot read file: {exc}")
        return None

    if not lines or lines[0] != "---":
        _error(errors, path, "must begin with a YAML frontmatter delimiter")
        return None
    try:
        end = lines.index("---", 1)
    except ValueError:
        _error(errors, path, "missing closing YAML frontmatter delimiter")
        return None

    try:
        metadata = yaml.load("\n".join(lines[1:end]), Loader=UniqueKeyLoader)
    except yaml.YAMLError as exc:
        _error(errors, path, f"invalid YAML frontmatter: {exc}")
        return None
    if not isinstance(metadata, dict):
        _error(errors, path, "frontmatter must be a mapping")
        return None
    return metadata


def validate_skills(root: Path, errors: list[str]) -> dict[str, dict[str, Any]]:
    skills_dir = root / "plugins" / "bedrock" / "skills"
    if not skills_dir.is_dir():
        _error(errors, skills_dir, "skills directory is missing")
        return {}

    skill_dirs = sorted(path.name for path in skills_dir.iterdir() if path.is_dir())
    if tuple(skill_dirs) != EXPECTED_SKILLS:
        missing = sorted(set(EXPECTED_SKILLS) - set(skill_dirs))
        extra = sorted(set(skill_dirs) - set(EXPECTED_SKILLS))
        _error(errors, skills_dir, f"skill inventory mismatch; missing={missing}, extra={extra}")

    inventory: dict[str, dict[str, Any]] = {}
    seen_names: dict[str, Path] = {}
    for directory_name in skill_dirs:
        skill_path = skills_dir / directory_name / "SKILL.md"
        if not skill_path.is_file():
            _error(errors, skill_path, "required skill entrypoint is missing")
            continue
        metadata = parse_frontmatter(skill_path, errors)
        if metadata is None:
            continue

        extra_keys = sorted(set(metadata) - {"name", "description"})
        if extra_keys:
            _error(errors, skill_path, f"unsupported frontmatter keys: {extra_keys}")

        name = metadata.get("name")
        description = metadata.get("description")
        if not isinstance(name, str) or not NAME_PATTERN.fullmatch(name):
            _error(errors, skill_path, "name must be a non-empty kebab-case string")
            continue
        if name != directory_name:
            _error(errors, skill_path, f"name {name!r} must match directory {directory_name!r}")
        if name in seen_names:
            _error(errors, skill_path, f"duplicate skill name; first declared at {seen_names[name]}")
        else:
            seen_names[name] = skill_path

        if not isinstance(description, str) or not description.strip():
            _error(errors, skill_path, "description must be a non-empty string")
            continue
        if len(description) > DESCRIPTION_LIMIT:
            _error(
                errors,
                skill_path,
                f"description length {len(description)} exceeds {DESCRIPTION_LIMIT}",
            )
        if "Use " not in description:
            _error(errors, skill_path, "description must contain an explicit positive 'Use ...' routing cue")
        if "Do not use" not in description:
            _error(errors, skill_path, "description must contain an explicit negative 'Do not use ...' boundary")

        inventory[name] = {
            "path": str(skill_path.relative_to(root)),
            "description": description,
            "description_length": len(description),
        }
    return inventory


def _load_json(path: Path, errors: list[str]) -> dict[str, Any] | None:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"duplicate JSON key {key!r}")
            value[key] = item
        return value

    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        _error(errors, path, f"invalid JSON: {exc}")
        return None
    if not isinstance(value, dict):
        _error(errors, path, "top level must be an object")
        return None
    return value


def _load_yaml_mapping(path: Path, errors: list[str]) -> dict[str, Any] | None:
    try:
        value = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
    except (OSError, yaml.YAMLError) as exc:
        _error(errors, path, f"invalid YAML: {exc}")
        return None
    if not isinstance(value, dict):
        _error(errors, path, "top level must be a mapping")
        return None
    return value


def _skill_markdown_files(root: Path) -> list[Path]:
    skills_dir = root / "plugins" / "bedrock" / "skills"
    return sorted(path for path in skills_dir.rglob("*.md") if path.is_file()) if skills_dir.is_dir() else []


def _resolve_repository_path(root: Path, value: str) -> Path | None:
    relative = Path(value)
    if relative.is_absolute():
        return None
    candidate = (root / relative).resolve()
    return candidate if candidate.is_relative_to(root.resolve()) else None


def _markdown_anchors(path: Path) -> set[str]:
    anchors: set[str] = set()
    counts: Counter[str] = Counter()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
        if not match:
            continue
        heading = re.sub(r"<[^>]+>", "", match.group(1)).replace("`", "").strip().lower()
        slug = re.sub(r"[^\w\- ]", "", heading, flags=re.UNICODE).replace(" ", "-")
        suffix = counts[slug]
        counts[slug] += 1
        anchors.add(slug if suffix == 0 else f"{slug}-{suffix}")
    return anchors


def validate_package_contract(root: Path, errors: list[str]) -> None:
    """Validate bundled links, private paths, external roots, and snapshots."""
    contract_path = root / "validation" / "package-contract.yaml"
    contract = _load_yaml_mapping(contract_path, errors)
    if contract is None:
        return
    if contract.get("schema_version") != 1:
        _error(errors, contract_path, "schema_version must be 1")

    dependency_rows = contract.get("external_dependencies")
    if not isinstance(dependency_rows, list):
        _error(errors, contract_path, "external_dependencies must be a list")
        dependency_rows = []
    declared_dependencies: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(dependency_rows):
        location = f"{contract_path}:external_dependencies[{index}]"
        if not isinstance(row, dict) or not isinstance(row.get("variable"), str):
            _error(errors, location, "dependency must declare a variable")
            continue
        variable = row["variable"]
        if variable in declared_dependencies:
            _error(errors, location, f"duplicate external dependency ${variable}")
        declared_dependencies[variable] = row
        if not isinstance(row.get("purpose"), str) or not row["purpose"].strip():
            _error(errors, location, "dependency must declare its purpose")
        if not isinstance(row.get("unavailable_behavior"), str) or not row["unavailable_behavior"].strip():
            _error(errors, location, "dependency must declare unavailable_behavior")
        paths = row.get("paths")
        if not isinstance(paths, list) or not paths or any(not isinstance(item, str) for item in paths):
            _error(errors, location, "dependency paths must be a non-empty string list")

    private_examples = contract.get("private_path_examples", [])
    if not isinstance(private_examples, list):
        _error(errors, contract_path, "private_path_examples must be a list")
        private_examples = []
    allowed_private_markers: dict[str, list[str]] = {}
    for index, row in enumerate(private_examples):
        location = f"{contract_path}:private_path_examples[{index}]"
        if not isinstance(row, dict) or not all(
            isinstance(row.get(field), str) and row[field].strip() for field in ("path", "marker", "rationale")
        ):
            _error(errors, location, "private-path example must declare path, marker, and rationale")
            continue
        allowed_private_markers.setdefault(row["path"], []).append(row["marker"])

    observed_dependencies: dict[str, set[str]] = {}
    skills_dir = root / "plugins" / "bedrock" / "skills"
    for path in _skill_markdown_files(root):
        text = path.read_text(encoding="utf-8")
        relative = str(path.relative_to(root))
        skill_name = path.relative_to(skills_dir).parts[0]
        skill_root = (skills_dir / skill_name).resolve()
        for target in MARKDOWN_LINK_PATTERN.findall(text):
            target = target.strip().strip("<>")
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            local_target, separator, anchor = target.partition("#")
            target_path = path if not local_target else (path.parent / unquote(local_target)).resolve()
            if local_target and not target_path.exists():
                _error(errors, path, f"relative link target does not exist: {target}")
                continue
            if local_target and not target_path.is_relative_to(skill_root):
                _error(errors, path, f"relative link escapes its skill package: {target}")
                continue
            if (
                separator
                and anchor
                and target_path.is_file()
                and unquote(anchor) not in _markdown_anchors(target_path)
            ):
                _error(errors, path, f"markdown anchor does not exist: {target}")
        private_scan = text
        for marker in allowed_private_markers.get(relative, []):
            if marker not in private_scan:
                _error(errors, contract_path, f"declared private-path example is missing: {marker!r}")
            private_scan = private_scan.replace(marker, "")
        if PRIVATE_PATH_PATTERN.search(private_scan):
            _error(errors, path, "private absolute path is not portable")
        for variable in EXTERNAL_ROOT_PATTERN.findall(text):
            observed_dependencies.setdefault(variable, set()).add(relative)

    for variable, paths in observed_dependencies.items():
        declaration = declared_dependencies.get(variable)
        if declaration is None:
            _error(errors, contract_path, f"undeclared external dependency ${variable}")
            continue
        declared_paths = set(declaration.get("paths", []))
        if paths != declared_paths:
            _error(
                errors,
                contract_path,
                f"external dependency ${variable} path drift; "
                f"observed={sorted(paths)}, declared={sorted(declared_paths)}",
            )
    for variable in sorted(set(declared_dependencies) - set(observed_dependencies)):
        _error(errors, contract_path, f"declared external dependency ${variable} is unused")

    snapshots = contract.get("snapshots")
    if not isinstance(snapshots, list):
        _error(errors, contract_path, "snapshots must be a list")
        return
    for index, row in enumerate(snapshots):
        location = f"{contract_path}:snapshots[{index}]"
        if not isinstance(row, dict):
            _error(errors, location, "snapshot must be a mapping")
            continue
        relative = row.get("path")
        source_marker = row.get("source_marker")
        currency_marker = row.get("currency_marker")
        if not all(isinstance(value, str) and value for value in (relative, source_marker, currency_marker)):
            _error(errors, location, "snapshot must declare path, source_marker, and currency_marker")
            continue
        snapshot_path = _resolve_repository_path(root, relative)
        if snapshot_path is None:
            _error(errors, location, "snapshot path must be repository-relative")
            continue
        if not snapshot_path.is_file():
            _error(errors, location, "snapshot path does not exist")
            continue
        text = snapshot_path.read_text(encoding="utf-8")
        if source_marker not in text:
            _error(errors, snapshot_path, "snapshot source marker is missing")
        if currency_marker not in text:
            _error(errors, snapshot_path, "snapshot currency marker is missing")


def validate_sample_inventory(root: Path, errors: list[str]) -> dict[str, int]:
    """Account for every language-tagged sample and its proof disposition."""
    inventory_path = root / "validation" / "executable-samples.yaml"
    payload = _load_yaml_mapping(inventory_path, errors)
    if payload is None:
        return {}
    if payload.get("schema_version") != 1:
        _error(errors, inventory_path, "schema_version must be 1")
    rows = payload.get("samples")
    if not isinstance(rows, list):
        _error(errors, inventory_path, "samples must be a list")
        rows = []

    observed: Counter[tuple[str, str]] = Counter()
    for path in _skill_markdown_files(root):
        relative = str(path.relative_to(root))
        for language in CODE_FENCE_PATTERN.findall(path.read_text(encoding="utf-8")):
            observed[(relative, language.lower())] += 1

    declared: dict[tuple[str, str], int] = {}
    for index, row in enumerate(rows):
        location = f"{inventory_path}:samples[{index}]"
        if not isinstance(row, dict):
            _error(errors, location, "sample entry must be a mapping")
            continue
        path = row.get("path")
        language = row.get("language")
        count = row.get("count")
        classification = row.get("classification")
        if not isinstance(path, str) or not isinstance(language, str) or not isinstance(count, int) or count < 1:
            _error(errors, location, "sample entry requires path, language, and positive count")
            continue
        key = (path, language.lower())
        if key in declared:
            _error(errors, location, f"duplicate sample inventory entry for {path} ({language})")
        declared[key] = count
        if classification not in SAMPLE_CLASSIFICATIONS:
            _error(errors, location, f"classification must be one of {sorted(SAMPLE_CLASSIFICATIONS)}")
        if classification in {"illustrative", "deferred"}:
            if not isinstance(row.get("owner"), str) or not row["owner"].strip():
                _error(errors, location, f"{classification} samples require an owner")
        if classification in {"fixture-backed", "syntax-checked"}:
            evidence = row.get("evidence")
            if not isinstance(evidence, list) or not evidence:
                _error(errors, location, f"{classification} samples require evidence paths")
            else:
                for evidence_path in evidence:
                    resolved = (
                        _resolve_repository_path(root, evidence_path)
                        if isinstance(evidence_path, str)
                        else None
                    )
                    if resolved is None:
                        _error(
                            errors,
                            location,
                            f"sample evidence path must be repository-relative: {evidence_path!r}",
                        )
                    elif not resolved.exists():
                        _error(errors, location, f"sample evidence path does not exist: {evidence_path!r}")
            if not isinstance(row.get("command"), str) or not row["command"].strip():
                _error(errors, location, f"{classification} samples require a reproducible command")

    for key, count in observed.items():
        if key not in declared:
            _error(errors, Path(key[0]), "code sample is absent from executable-samples.yaml")
        elif declared[key] != count:
            _error(
                errors,
                Path(key[0]),
                f"code sample count drift for {key[1]}; observed={count}, declared={declared[key]}",
            )
    for key in sorted(set(declared) - set(observed)):
        _error(errors, inventory_path, f"inventoried code sample is missing from package: {key[0]} ({key[1]})")
    return dict(Counter(str(row.get("classification")) for row in rows if isinstance(row, dict)))


def validate_evidence_manifest(root: Path, errors: list[str]) -> None:
    """Validate claim status, reproduction commands, and retained paths."""
    manifest_path = root / "docs" / "evidence" / "heb-109" / "manifest.yaml"
    payload = _load_yaml_mapping(manifest_path, errors)
    if payload is None:
        return
    if payload.get("schema_version") != 1:
        _error(errors, manifest_path, "schema_version must be 1")
    claims = payload.get("claims")
    if not isinstance(claims, list) or not claims:
        _error(errors, manifest_path, "claims must be a non-empty list")
        return
    ids: set[str] = set()
    for index, claim in enumerate(claims):
        location = f"{manifest_path}:claims[{index}]"
        if not isinstance(claim, dict):
            _error(errors, location, "claim must be a mapping")
            continue
        claim_id = claim.get("id")
        if not isinstance(claim_id, str) or not claim_id or claim_id in ids:
            _error(errors, location, "claim id must be non-empty and unique")
        else:
            ids.add(claim_id)
        status = claim.get("status")
        if status not in {"verified", "baseline-failure", "deferred"}:
            _error(errors, location, "status must be verified, baseline-failure, or deferred")
        if not isinstance(claim.get("command"), str) or not claim["command"].strip():
            _error(errors, location, "claim must declare a reproducible command")
        evidence = claim.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            _error(errors, location, "claim must declare evidence paths")
        else:
            for evidence_path in evidence:
                resolved = _resolve_repository_path(root, evidence_path) if isinstance(evidence_path, str) else None
                if resolved is None:
                    _error(errors, location, f"evidence path must be repository-relative: {evidence_path!r}")
                elif not resolved.exists():
                    _error(errors, location, f"evidence path does not exist: {evidence_path!r}")
        if status == "deferred" and (not isinstance(claim.get("owner"), str) or not claim["owner"].strip()):
            _error(errors, location, "deferred claim must name its owner")


def load_eval_policy(root: Path, errors: list[str]) -> dict[str, Any]:
    """Load and validate the preregistered routing evaluation policy."""
    policy_path = root / "validation" / "eval-policy.yaml"
    payload = _load_yaml_mapping(policy_path, errors)
    if payload is None:
        return {}
    if payload.get("schema_version") != 1:
        _error(errors, policy_path, "schema_version must be 1")
    profiles = payload.get("profiles")
    if not isinstance(profiles, dict):
        _error(errors, policy_path, "profiles must be a mapping")
        return {}
    for name in ("pr", "release"):
        profile = profiles.get(name)
        location = f"{policy_path}:profiles.{name}"
        if not isinstance(profile, dict):
            _error(errors, location, "required profile is missing")
            continue
        runs = profile.get("runs_per_case")
        if not isinstance(runs, int) or runs < 1:
            _error(errors, location, "runs_per_case must be a positive integer")
        for field in ("minimum_overall_pass_rate", "minimum_case_pass_rate"):
            value = profile.get(field)
            if not isinstance(value, (int, float)) or not 0 <= value <= 1:
                _error(errors, location, f"{field} must be between 0 and 1")
        limit = profile.get("excluded_selection_limit")
        if not isinstance(limit, int) or limit < 0:
            _error(errors, location, "excluded_selection_limit must be a non-negative integer")
    return payload


def validate_routing_evidence(
    root: Path,
    cases: list[dict[str, Any]],
    inventory_report: dict[str, Any],
    policy_document: dict[str, Any],
    errors: list[str],
) -> None:
    """Validate retained routing evidence against current inputs and outcomes."""
    report_path = root / "docs" / "evidence" / "heb-109" / "routing-results.json"
    if not report_path.exists():
        return
    report = _load_json(report_path, errors)
    if report is None:
        return
    if report.get("schema_version") != 2:
        _error(errors, report_path, "routing report schema_version must be 2")
        return
    if report.get("profile") != "release" or report.get("suite_scope") != "full":
        _error(errors, report_path, "retained routing report must be a full release-profile suite")

    identity = report.get("identity")
    if not isinstance(identity, dict):
        _error(errors, report_path, "routing report identity must be a mapping")
        return
    expected_identity = {
        "fixture_sha256": hashlib.sha256((root / "tests/fixtures/routing.yaml").read_bytes()).hexdigest(),
        "catalog_sha256": hashlib.sha256(
            json.dumps(inventory_report["skills"], sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "policy_sha256": hashlib.sha256((root / "validation/eval-policy.yaml").read_bytes()).hexdigest(),
    }
    if identity != expected_identity:
        _error(
            errors,
            report_path,
            f"routing report identity drift; observed={identity}, expected={expected_identity}",
        )

    release_policy = policy_document.get("profiles", {}).get("release", {})
    runs = release_policy.get("runs_per_case")
    case_by_id = {str(case["id"]): case for case in cases if isinstance(case.get("id"), str)}
    expected_case_ids = sorted(case_by_id)
    if report.get("planned_case_ids") != expected_case_ids:
        _error(errors, report_path, "routing report planned cases drift from the current fixture")
    if report.get("completed_case_ids") != expected_case_ids:
        _error(errors, report_path, "routing report is not complete for the current fixture")

    results = report.get("results")
    if not isinstance(results, list):
        _error(errors, report_path, "routing report results must be a list")
        return
    grouped_runs: dict[str, set[int]] = {case_id: set() for case_id in expected_case_ids}
    recomputed_passes = 0
    recomputed_excluded = 0
    for index, result in enumerate(results):
        location = f"{report_path}:results[{index}]"
        if not isinstance(result, dict):
            _error(errors, location, "routing result must be a mapping")
            continue
        case_id = result.get("case")
        case = case_by_id.get(str(case_id))
        if case is None:
            _error(errors, location, f"routing result references unknown case {case_id!r}")
            continue
        run_number = result.get("run")
        if not isinstance(run_number, int):
            _error(errors, location, "routing result run must be an integer")
        else:
            grouped_runs[str(case_id)].add(run_number)
        for field, expected in (
            ("kind", case.get("kind")),
            ("cue", case.get("cue", "direct")),
            ("surface", case.get("surface")),
            ("expected", case.get("expected")),
        ):
            if result.get(field) != expected:
                _error(errors, location, f"routing result {field} drift")
        selected = result.get("selected")
        excluded = selected in case.get("excluded", [])
        allowed = selected == case.get("expected") or (
            case.get("kind") == "overlap" and selected in case.get("allowed_alternates", [])
        )
        passed = allowed and not excluded
        recomputed_passes += int(passed)
        recomputed_excluded += int(excluded)
        if result.get("selected_excluded") is not excluded or result.get("passed") is not passed:
            _error(errors, location, "routing result disposition does not match the current fixture")

    expected_runs = set(range(1, runs + 1)) if isinstance(runs, int) else set()
    for case_id, observed_runs in grouped_runs.items():
        if observed_runs != expected_runs:
            _error(
                errors,
                report_path,
                f"routing report run coverage drift for {case_id}; "
                f"observed={sorted(observed_runs)}, expected={sorted(expected_runs)}",
            )
    expected_total = len(expected_case_ids) * len(expected_runs)
    if len(results) != expected_total or report.get("total") != expected_total:
        _error(errors, report_path, "routing report total does not match case and repetition coverage")
    if report.get("passed") != recomputed_passes:
        _error(errors, report_path, "routing report pass total does not match recomputed outcomes")
    evaluation = report.get("evaluation")
    if not isinstance(evaluation, dict):
        _error(errors, report_path, "routing report evaluation must be a mapping")
    elif not (
        evaluation.get("passed") is True
        and evaluation.get("suite_complete") is True
        and evaluation.get("retained_evidence_eligible") is True
        and evaluation.get("excluded_selections") == recomputed_excluded
    ):
        _error(errors, report_path, "routing report is not eligible retained evidence")


def validate_manifests(root: Path, errors: list[str]) -> None:
    plugin_path = root / "plugins" / "bedrock" / ".claude-plugin" / "plugin.json"
    marketplace_path = root / ".claude-plugin" / "marketplace.json"
    plugin = _load_json(plugin_path, errors)
    marketplace = _load_json(marketplace_path, errors)
    if plugin is None or marketplace is None:
        return

    if plugin.get("name") != "bedrock":
        _error(errors, plugin_path, "plugin name must be 'bedrock'")
    version = plugin.get("version")
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        _error(errors, plugin_path, "version must be a SemVer core string")

    entries = marketplace.get("plugins")
    if not isinstance(entries, list):
        _error(errors, marketplace_path, "plugins must be a list")
        return
    matching = [entry for entry in entries if isinstance(entry, dict) and entry.get("name") == "bedrock"]
    if len(matching) != 1:
        _error(errors, marketplace_path, f"expected exactly one bedrock entry, found {len(matching)}")
        return
    entry = matching[0]
    if entry.get("description") != plugin.get("description"):
        _error(errors, marketplace_path, "bedrock description must equal plugin.json description verbatim")
    source = entry.get("source")
    if not isinstance(source, str):
        _error(errors, marketplace_path, "bedrock source must be a string")
    elif (root / source).resolve() != (root / "plugins" / "bedrock").resolve():
        _error(errors, marketplace_path, "bedrock source must resolve to ./plugins/bedrock")


def load_routing_cases(root: Path, errors: list[str]) -> list[dict[str, Any]]:
    path = root / "tests" / "fixtures" / "routing.yaml"
    try:
        payload = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
    except (OSError, yaml.YAMLError) as exc:
        _error(errors, path, f"cannot load routing fixtures: {exc}")
        return []
    if not isinstance(payload, dict) or payload.get("schema_version") != ROUTING_SCHEMA_VERSION:
        _error(errors, path, f"schema_version must be {ROUTING_SCHEMA_VERSION}")
        return []
    cases = payload.get("cases")
    if not isinstance(cases, list):
        _error(errors, path, "cases must be a list")
        return []
    valid_cases: list[dict[str, Any]] = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            _error(errors, f"{path}:case[{index}]", "case must be a mapping")
            continue
        valid_cases.append(case)
    return valid_cases


def validate_routing(
    root: Path,
    skill_inventory: dict[str, dict[str, Any]],
    errors: list[str],
) -> list[dict[str, Any]]:
    path = root / "tests" / "fixtures" / "routing.yaml"
    cases = load_routing_cases(root, errors)
    known = set(skill_inventory)
    positive: set[str] = set()
    negative: set[str] = set()
    cues: set[str] = set()
    ids: set[str] = set()

    for index, case in enumerate(cases):
        location = f"{path}:case[{index}]"
        case_id = case.get("id")
        kind = case.get("kind")
        cue = case.get("cue", "direct")
        prompt = case.get("prompt")
        expected = case.get("expected")
        excluded = case.get("excluded", [])
        alternates = case.get("allowed_alternates", [])
        if not isinstance(case_id, str) or not case_id:
            _error(errors, location, "id must be a non-empty string")
        elif case_id in ids:
            _error(errors, location, f"duplicate case id {case_id!r}")
        else:
            ids.add(case_id)
        if kind not in {"positive", "negative", "overlap"}:
            _error(errors, location, "kind must be positive, negative, or overlap")
        if cue not in ROUTING_CUES:
            _error(errors, location, f"cue must be one of {sorted(ROUTING_CUES)}")
        else:
            cues.add(cue)
        if case.get("surface") != "portable-core":
            _error(errors, location, "surface must be 'portable-core'; adapters execute shared cases")
        if not isinstance(prompt, str) or not prompt.strip():
            _error(errors, location, "prompt must be a non-empty string")
        if expected is not None and expected not in known:
            _error(errors, location, f"unknown expected skill {expected!r}")
        if not isinstance(excluded, list) or any(item not in known for item in excluded):
            _error(errors, location, "excluded must contain only known skill names")
            excluded = []
        if not isinstance(alternates, list) or any(item not in known for item in alternates):
            _error(errors, location, "allowed_alternates must contain only known skill names")
            alternates = []
        if kind != "overlap" and alternates:
            _error(errors, location, "allowed_alternates is valid only for overlap cases")
        if expected in excluded:
            _error(errors, location, "expected skill cannot also be excluded")
        if set(alternates) & set(excluded):
            _error(errors, location, "allowed_alternates and excluded must be disjoint")
        if kind == "positive" and expected in known:
            positive.add(expected)
        negative.update(excluded)

    for skill in sorted(known):
        if skill not in positive:
            _error(errors, path, f"missing positive routing case for {skill}")
        if skill not in negative:
            _error(errors, path, f"missing negative routing case excluding {skill}")
    for cue in sorted(ROUTING_CUES - cues):
        _error(errors, path, f"missing routing cue class {cue!r}")
    return cases


def run_host_manifest_validator(root: Path, errors: list[str]) -> None:
    executable = shutil.which("claude")
    if executable is None:
        _error(errors, "claude", "Claude Code CLI is required for strict plugin-manifest validation")
        return
    environment = os.environ.copy()
    environment.pop("CLAUDECODE", None)
    result = subprocess.run(
        [executable, "plugin", "validate", "--strict", str(root / "plugins" / "bedrock")],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stdout + result.stderr).strip()
        _error(
            errors,
            "claude plugin validate --strict (plugin manifest)",
            detail or f"exited {result.returncode}",
        )


def validate_repository(
    root: Path,
    *,
    run_host_cli: bool = True,
    run_safety_checks: bool = True,
    validate_retained_evidence: bool = True,
    require_authoring_contracts: bool = True,
    require_package_governance: bool = True,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    inventory = validate_skills(root, errors)
    validate_manifests(root, errors)
    validate_package_contract(root, errors)
    if require_package_governance:
        errors.extend(validate_package_governance(root))
    cases = validate_routing(root, inventory, errors)
    sample_summary = validate_sample_inventory(root, errors)
    validate_evidence_manifest(root, errors)
    policy_document = load_eval_policy(root, errors)
    if run_safety_checks:
        errors.extend(validate_safety_contracts(root))
    errors.extend(validate_authoring_contracts(root, required=require_authoring_contracts))
    errors.extend(validate_agent_review_contracts(root, required=require_authoring_contracts))
    errors.extend(
        validate_application_test_debug_contracts(root, required=require_authoring_contracts)
    )
    errors.extend(
        validate_infrastructure_delivery_contracts(root, required=require_authoring_contracts)
    )
    errors.extend(validate_frontend_contracts(root, required=require_authoring_contracts))
    if run_host_cli:
        run_host_manifest_validator(root, errors)

    for name, record in inventory.items():
        record["positive_cases"] = [case.get("id") for case in cases if case.get("expected") == name]
        record["negative_cases"] = [case.get("id") for case in cases if name in case.get("excluded", [])]
        record["overlap_cases"] = [
            case.get("id")
            for case in cases
            if case.get("kind") == "overlap"
            and (case.get("expected") == name or name in case.get("allowed_alternates", []))
        ]
    report = {
        "schema_version": 1,
        "skill_count": len(inventory),
        "description_limit": DESCRIPTION_LIMIT,
        "routing_schema_version": ROUTING_SCHEMA_VERSION,
        "sample_classifications": sample_summary,
        "skills": [inventory[name] | {"name": name} for name in sorted(inventory)],
    }
    if validate_retained_evidence and policy_document:
        validate_routing_evidence(root, cases, report, policy_document, errors)
    return errors, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--skip-host-cli", action="store_true", help="Skip Claude CLI plugin-manifest validation (tests only).")
    parser.add_argument("--component", action="store_true", help="Component checks only: retain historical routing evidence without claiming current routing acceptance. Default still verifies current retained evidence.")
    parser.add_argument("--inventory", type=Path, help="Write the derived metadata/routing inventory as JSON.")
    args = parser.parse_args()

    root = args.root.resolve()
    errors, report = validate_repository(root, run_host_cli=not args.skip_host_cli, validate_retained_evidence=not args.component)
    if args.inventory:
        args.inventory.parent.mkdir(parents=True, exist_ok=True)
        args.inventory.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if errors:
        print(f"FAIL: {len(errors)} validation error(s)", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    message = f"PASS: {report['skill_count']}/{len(EXPECTED_SKILLS)} skills passed deterministic validation"
    if not args.skip_host_cli:
        message += "; plugin manifest passed strict host validation"
    if args.component:
        message += "; COMPONENT ONLY: current routing and release acceptance remain unverified"
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
