#!/usr/bin/env python3
"""Validate Bedrock package lifecycle and release-governance contracts."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError
import yaml

if __package__:
    from .sync_package_identity import (
        carrier_paths,
        carrier_population_errors,
        expected_carrier_bytes,
        expected_carrier_payload,
    )
else:
    from sync_package_identity import (
        carrier_paths,
        carrier_population_errors,
        expected_carrier_bytes,
        expected_carrier_payload,
    )


EXPECTED_SKILLS = {
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
    "testing",
}
REPOSITORY = "https://github.com/T-Bone-Haff/bedrock"
REQUIRED_FILES = (
    "LICENSE",
    "SECURITY.md",
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    "docs/repository-orientation.md",
    "plugins/bedrock/LICENSE",
    "plugins/bedrock/CHANGELOG.md",
    "plugins/bedrock/governance/README.md",
    "plugins/bedrock/governance/COMPATIBILITY.md",
    "plugins/bedrock/governance/POLICIES.md",
    "plugins/bedrock/governance/THREAT-MODEL.md",
    "plugins/bedrock/governance/QUICKSTART.md",
    "plugins/bedrock/governance/REBINDING.md",
    "plugins/bedrock/governance/registry.yaml",
    "plugins/bedrock/governance/vocabulary.yaml",
    "plugins/bedrock/governance/authority-inventory.yaml",
    "plugins/bedrock/governance/release-evidence.schema.json",
    "plugins/bedrock/governance/release-evidence.template.yaml",
    "plugins/bedrock/governance/rollout-ledger.schema.json",
    "plugins/bedrock/governance/rollout-ledger.template.yaml",
    "docs/evidence/heb-118/baseline.md",
    "docs/evidence/heb-118/manifest.yaml",
    "docs/evidence/heb-118/context-budget.json",
)
EXPECTED_CODEX_ADAPTER = (
    "# AGENTS.md — bedrock\n\n"
    "Read `docs/repository-orientation.md` from disk before acting in this repository; "
    "it is the single host-neutral repository-orientation authority. This file contains "
    "no repository guidance of its own.\n"
)
SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
MINIMUM_SEMVER = re.compile(r"^>=([0-9]+\.[0-9]+\.[0-9]+)$")
VERIFIED_CLAUDE_CODE_HOST = re.compile(r"^claude-code-([0-9]+\.[0-9]+\.[0-9]+)$")
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
FINAL_RELEASE_GATES = {
    "deterministic",
    "strict-host",
    "isolated-install",
    "routing",
    "review",
    "migration",
    "cold-acceptance",
    "github-release",
}
PACKAGE_IDENTITY_CARRIER = "plugins/bedrock/skills/{skill}/PACKAGE_IDENTITY.json"
PORTABLE_CORE_AUTHORITY = "docs/adr/ADR-001-portable-core-and-surface-adapter-architecture.md"
PRODUCTION_MARKETPLACE_SOURCE = "./plugins/bedrock"
PRESERVED_DISTRIBUTION_PATHS = (
    ".claude-plugin/marketplace.json",
    "plugins/bedrock",
    "packages/agent-core",
)
ADR_VERSION = re.compile(r"^\| \*\*Version\*\* \| ([0-9]+\.[0-9]+\.[0-9]+) \|$", re.MULTILINE)
ADR_STATUS = re.compile(r"^\| \*\*Status\*\* \| ACCEPTED\b", re.MULTILINE)


def _error(errors: list[str], location: Path | str, message: str) -> None:
    errors.append(f"{location}: {message}")


def _load_json(path: Path, errors: list[str]) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _error(errors, path, f"invalid JSON: {exc}")
        return None
    if not isinstance(value, dict):
        _error(errors, path, "top level must be an object")
        return None
    return value


def _load_yaml(path: Path, errors: list[str]) -> dict[str, Any] | None:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        _error(errors, path, f"invalid YAML: {exc}")
        return None
    if not isinstance(value, dict):
        _error(errors, path, "top level must be a mapping")
        return None
    return value


def _frontmatter_description(path: Path) -> str | None:
    match = re.search(r'^description: "(.*)"$', path.read_text(encoding="utf-8"), re.MULTILINE)
    return match.group(1) if match else None


def _semver_tuple(value: str) -> tuple[int, int, int]:
    return tuple(int(part) for part in value.split("."))


def _accepted_portable_core_version(root: Path, errors: list[str]) -> str | None:
    path = root / PORTABLE_CORE_AUTHORITY
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        _error(errors, path, f"cannot read portable-core authority: {exc}")
        return None
    version = ADR_VERSION.search(text)
    if version is None or ADR_STATUS.search(text) is None:
        _error(errors, path, "portable-core authority must be ACCEPTED with a SemVer version")
        return None
    return version.group(1)


def _validate_metadata(root: Path, errors: list[str]) -> str | None:
    plugin_path = root / "plugins/bedrock/.claude-plugin/plugin.json"
    marketplace_path = root / ".claude-plugin/marketplace.json"
    plugin = _load_json(plugin_path, errors)
    marketplace = _load_json(marketplace_path, errors)
    if plugin is None or marketplace is None:
        return None

    version = plugin.get("version")
    if not isinstance(version, str) or not SEMVER.fullmatch(version):
        _error(errors, plugin_path, "version must be a SemVer core string")
        version = None
    expected = {
        "repository": REPOSITORY,
        "homepage": REPOSITORY,
        "license": "MIT",
    }
    for field, value in expected.items():
        if plugin.get(field) != value:
            _error(errors, plugin_path, f"{field} must equal {value!r}")
    keywords = plugin.get("keywords")
    if not isinstance(keywords, list) or not {"engineering", "skills", "governance"}.issubset(keywords):
        _error(errors, plugin_path, "keywords must include engineering, skills, and governance")

    entries = marketplace.get("plugins")
    matches = [row for row in entries if isinstance(row, dict) and row.get("name") == "bedrock"] if isinstance(entries, list) else []
    if len(matches) != 1:
        _error(errors, marketplace_path, "must contain exactly one bedrock plugin entry")
        return version
    entry = matches[0]
    if entry.get("source") != PRODUCTION_MARKETPLACE_SOURCE:
        _error(errors, marketplace_path, "marketplace source must match the accepted distribution boundary")
    for field in ("description", "author", "repository", "homepage", "license", "keywords"):
        if entry.get(field) != plugin.get(field):
            _error(errors, marketplace_path, f"bedrock {field} must equal plugin.json {field}")
    if "version" in entry:
        _error(errors, marketplace_path, "marketplace must not duplicate the manifest version authority")
    return version


def _validate_registry(root: Path, errors: list[str]) -> dict[str, Any] | None:
    path = root / "plugins/bedrock/governance/registry.yaml"
    registry = _load_yaml(path, errors)
    if registry is None:
        return None
    if registry.get("schema_version") != 1:
        _error(errors, path, "schema_version must be 1")
    if registry.get("version_authority") != "plugins/bedrock/.claude-plugin/plugin.json#/version":
        _error(errors, path, "manifest must be the sole package version authority")
    if not isinstance(registry.get("release_state_source"), str) or not registry["release_state_source"].strip():
        _error(errors, path, "release state must be derived from external tag and evidence authority")
    distribution = registry.get("distribution")
    if not isinstance(distribution, dict):
        _error(errors, path, "distribution boundary must be declared")
    else:
        if distribution.get("marketplace_branch") != "main":
            _error(errors, path, "production marketplace branch must be main")
        if distribution.get("marketplace_source") != PRODUCTION_MARKETPLACE_SOURCE:
            _error(errors, path, "registry marketplace source must match the accepted distribution boundary")
        if distribution.get("acceptance_order") != "before-marketplace-branch-merge":
            _error(errors, path, "cold acceptance must precede merge to the marketplace branch")
        if distribution.get("permitted_landing_methods") != ["merge_commit"]:
            _error(errors, path, "landing method must require merge_commit only")
        if distribution.get("preserved_paths") != list(PRESERVED_DISTRIBUTION_PATHS):
            _error(errors, path, "distribution parity paths must cover the marketplace and installed package")
        if not isinstance(distribution.get("candidate_isolation"), str) or not distribution["candidate_isolation"].strip():
            _error(errors, path, "candidate isolation rule is required")
    contracts = registry.get("contracts")
    if not isinstance(contracts, dict) or any(
        not isinstance(contracts.get(key), str) or not SEMVER.fullmatch(contracts[key])
        for key in ("portable_core", "claude_adapter", "prompt_generation_format")
    ):
        _error(errors, path, "all independent contract identities must be SemVer strings")
    portable_core_version = _accepted_portable_core_version(root, errors)
    if (
        portable_core_version is not None
        and isinstance(contracts, dict)
        and contracts.get("portable_core") != portable_core_version
    ):
        _error(errors, path, "portable_core must match the accepted ADR-001 version")

    capabilities = registry.get("capabilities")
    claude_code_rows = [
        row
        for row in capabilities or []
        if isinstance(row, dict) and row.get("id") == "claude-code-plugin-host"
    ] if isinstance(capabilities, list) else []
    claude_code_minimum: str | None = None
    if len(claude_code_rows) != 1:
        _error(errors, path, "registry must declare exactly one Claude Code capability")
    else:
        capability = claude_code_rows[0]
        minimum_match = (
            MINIMUM_SEMVER.fullmatch(capability.get("version", ""))
            if isinstance(capability.get("version"), str)
            else None
        )
        if capability.get("version_semantics") != "minimum-supported" or minimum_match is None:
            _error(errors, path, "Claude Code capability must declare a minimum-supported SemVer floor")
        else:
            claude_code_minimum = minimum_match.group(1)

    skills = registry.get("skills")
    if not isinstance(skills, list):
        _error(errors, path, "skills must be a list")
        skills = []
    names = [row.get("name") for row in skills if isinstance(row, dict)]
    if set(names) != EXPECTED_SKILLS or len(names) != len(EXPECTED_SKILLS):
        _error(errors, path, f"skill lifecycle inventory mismatch: {sorted(names)}")
    for index, row in enumerate(skills):
        location = f"{path}:skills[{index}]"
        if not isinstance(row, dict):
            _error(errors, location, "skill lifecycle row must be a mapping")
            continue
        for field in ("owner", "reviewer", "status", "contract_version", "layer", "last_verified", "verified_hosts"):
            if row.get(field) in (None, "", []):
                _error(errors, location, f"{field} is required")
        if row.get("status") not in {"active", "deprecated", "retired"}:
            _error(errors, location, "status must be active, deprecated, or retired")
        if row.get("status") != "active" and not row.get("migration"):
            _error(errors, location, "non-active skill requires migration treatment")
        if row.get("status") == "retired" and not (row.get("successor") or row.get("migration")):
            _error(errors, location, "retired skill requires a successor or explicit migration rationale")
        verified = row.get("last_verified")
        if not isinstance(verified, (date, str)):
            _error(errors, location, "last_verified must be a date")
        verified_hosts = row.get("verified_hosts")
        if isinstance(verified_hosts, list) and claude_code_minimum is not None:
            claude_code_hosts = [
                host
                for host in verified_hosts
                if isinstance(host, str) and host.startswith("claude-code")
            ]
            matches = [VERIFIED_CLAUDE_CODE_HOST.fullmatch(host) for host in claude_code_hosts]
            if not claude_code_hosts or any(match is None for match in matches):
                _error(errors, location, "verified Claude Code hosts must use exact SemVer identities")
            for match in matches:
                if match and _semver_tuple(match.group(1)) < _semver_tuple(claude_code_minimum):
                    _error(errors, location, "verified Claude Code host is below the supported minimum")

    for key in ("authorities", "precedence", "capabilities", "consumer_surfaces", "release_gates", "sources"):
        if not isinstance(registry.get(key), list) or not registry[key]:
            _error(errors, path, f"{key} must be a non-empty list")
    sources = registry.get("sources", [])
    adr_sources = [
        row for row in sources
        if isinstance(row, dict) and row.get("id") == "adr-001"
    ] if isinstance(sources, list) else []
    expected_adr_source = {
        "id": "adr-001",
        "type": "ratified-architecture",
        "location": PORTABLE_CORE_AUTHORITY,
        "authority_version": portable_core_version,
        "status": "accepted",
        "applicability": "package architecture and versioning",
    }
    if len(adr_sources) != 1 or adr_sources[0] != expected_adr_source:
        _error(errors, path, "ADR-001 source must identify the accepted portable-core authority")
    package_authorities = [
        row for row in registry.get("authorities", [])
        if isinstance(row, dict) and row.get("id") == "package-version"
    ]
    if (
        len(package_authorities) != 1
        or package_authorities[0].get("owner") != "plugins/bedrock/.claude-plugin/plugin.json#/version"
        or package_authorities[0].get("carriers") != [PACKAGE_IDENTITY_CARRIER]
    ):
        _error(errors, path, "package-version authority must declare the generated skill identity carrier exactly once")
    capability_ids = [row.get("id") for row in registry.get("capabilities", []) if isinstance(row, dict)]
    if len(capability_ids) != len(set(capability_ids)):
        _error(errors, path, "capability identifiers must be unique")
    for index, row in enumerate(registry.get("capabilities", [])):
        if not isinstance(row, dict) or any(not row.get(field) for field in ("id", "required_for", "version", "detection", "unavailable_behavior")):
            _error(errors, f"{path}:capabilities[{index}]", "capability declaration is incomplete")
    surfaces = {row.get("id") for row in registry.get("consumer_surfaces", []) if isinstance(row, dict)}
    if surfaces != {"claude-ai", "claude-code", "codex"}:
        _error(errors, path, "consumer surface enumeration must contain claude-ai, claude-code, and codex exactly")
    prompt = registry.get("prompt_generation")
    if not isinstance(prompt, dict) or len(prompt.get("required_provenance", [])) < 3:
        _error(errors, path, "prompt generations require format, source, and digest provenance")
    return registry


def _validate_package_identity_carriers(root: Path, errors: list[str]) -> None:
    errors.extend(carrier_population_errors(root))
    try:
        expected_payload = expected_carrier_payload(root)
        expected_bytes = expected_carrier_bytes(root)
    except (OSError, json.JSONDecodeError, yaml.YAMLError, KeyError, TypeError) as exc:
        _error(errors, "package identity", f"cannot derive package identity carrier: {exc}")
        return
    observed_bytes: list[bytes] = []
    paths = carrier_paths(root)
    if {path.parent.name for path in paths} != EXPECTED_SKILLS or len(paths) != len(EXPECTED_SKILLS):
        _error(errors, "package identity", "carrier population must match the 14-skill inventory")
    for path in paths:
        if not path.is_file():
            _error(errors, path, "package identity carrier is missing")
            continue
        raw = path.read_bytes()
        observed_bytes.append(raw)
        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            _error(errors, path, f"package identity carrier is not valid JSON: {exc}")
            continue
        if payload != expected_payload or raw != expected_bytes:
            _error(errors, path, "package identity carrier does not match the manifest authority")
    if len(set(observed_bytes)) > 1:
        _error(errors, "package identity", "package identity carriers must be byte-identical")


def _validate_budgets(root: Path, registry: dict[str, Any] | None, errors: list[str]) -> None:
    if registry is None or not isinstance(registry.get("budgets"), dict):
        return
    budgets = registry["budgets"]
    maximum = budgets.get("description_max_characters")
    aggregate_maximum = budgets.get("catalog_description_max_characters")
    word_maximum = budgets.get("skill_entrypoint_max_words")
    descriptions: list[tuple[Path, str]] = []
    observed_rows: list[dict[str, Any]] = []
    for path in sorted((root / "plugins/bedrock/skills").glob("*/SKILL.md")):
        description = _frontmatter_description(path)
        if description is None:
            _error(errors, path, "cannot measure missing quoted description")
            continue
        descriptions.append((path, description))
        if not isinstance(maximum, int) or len(description) > maximum:
            _error(errors, path, f"description exceeds package budget {maximum}")
        words = len(re.findall(r"\b[\w'-]+\b", path.read_text(encoding="utf-8")))
        observed_rows.append(
            {
                "name": path.parent.name,
                "description_characters": len(description),
                "entrypoint_words": words,
            }
        )
        if not isinstance(word_maximum, int) or words > word_maximum:
            _error(errors, path, f"entrypoint word count {words} exceeds package budget {word_maximum}")
    aggregate = sum(len(description) for _, description in descriptions)
    if not isinstance(aggregate_maximum, int) or aggregate > aggregate_maximum:
        _error(errors, "skill catalog", f"description total {aggregate} exceeds package budget {aggregate_maximum}")
    context_path = root / "docs/evidence/heb-118/context-budget.json"
    context = _load_json(context_path, errors)
    if context is None:
        return
    measurement = context.get("measurement")
    if not isinstance(measurement, dict):
        _error(errors, context_path, "measurement must be an object")
        return
    if measurement.get("catalog_description_characters") != aggregate:
        _error(errors, context_path, "catalog description measurement is stale")
    if measurement.get("skill_entrypoint_words") != sum(row["entrypoint_words"] for row in observed_rows):
        _error(errors, context_path, "skill entrypoint word measurement is stale")
    if context.get("skills") != observed_rows:
        _error(errors, context_path, "per-skill context measurements are stale")
    if not isinstance(measurement.get("projected_always_on_tokens"), int) or measurement["projected_always_on_tokens"] <= 0:
        _error(errors, context_path, "host projected token measurement is required")
    routing_path = root / "docs/evidence/heb-109/routing-results.json"
    routing = _load_json(routing_path, errors)
    if routing:
        excluded = routing.get("evaluation", {}).get("excluded_selections")
        expected = f"{routing.get('passed')}/{routing.get('total')} with {excluded} excluded selections"
        if measurement.get("routing_population") != expected:
            _error(errors, context_path, "routing population measurement is stale")


def _validate_documents(
    root: Path,
    version: str | None,
    registry: dict[str, Any] | None,
    errors: list[str],
) -> None:
    for relative in REQUIRED_FILES:
        path = root / relative
        if not path.is_file() or not path.read_text(encoding="utf-8").strip():
            _error(errors, path, "required package-governance file is missing or empty")
    root_license = root / "LICENSE"
    package_license = root / "plugins/bedrock/LICENSE"
    if root_license.is_file() and package_license.is_file() and root_license.read_bytes() != package_license.read_bytes():
        _error(errors, package_license, "installed-package license must match repository license exactly")

    markers = {
        "plugins/bedrock/governance/README.md": (
            "## Semantic-version decisions",
            "## Rollback",
            "HEB-119",
            "accepted package content only",
            "Squash and rebase merges are prohibited",
        ),
        "plugins/bedrock/governance/COMPATIBILITY.md": ("Claude Code", "Claude.ai", "unsupported"),
        "plugins/bedrock/governance/POLICIES.md": ("## Security reporting", "## Support", "## Deprecation and retirement"),
        "plugins/bedrock/governance/THREAT-MODEL.md": ("Malicious skill content", "Poisoned or drifting references", "Marketplace or source compromise", "External product-runner drift"),
        "plugins/bedrock/governance/REBINDING.md": ("## Preserved invariants", "## Changed axes and assumptions", "## Replacement authority and responsibility", "## Migration and compatibility", "## Exceptions, degradation, and refusal", "## Proving evidence"),
    }
    for relative, required in markers.items():
        path = root / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for marker in required:
            if marker not in text:
                _error(errors, path, f"required lifecycle marker is missing: {marker}")

    quickstart = root / "plugins/bedrock/governance/QUICKSTART.md"
    if quickstart.is_file():
        rows = [line for line in quickstart.read_text(encoding="utf-8").splitlines() if line.startswith("| “")]
        if len(rows) < 5 or not any("no Bedrock route" in row for row in rows):
            _error(errors, quickstart, "quickstart requires at least five tasks and one non-trigger example")

    changelog = root / "plugins/bedrock/CHANGELOG.md"
    if version and changelog.is_file() and version not in changelog.read_text(encoding="utf-8"):
        _error(errors, changelog, "must identify the current manifest candidate without becoming version authority")
    compatibility = root / "plugins/bedrock/governance/COMPATIBILITY.md"
    portable_core = registry.get("contracts", {}).get("portable_core") if registry else None
    if (
        isinstance(portable_core, str)
        and compatibility.is_file()
        and f"portable skill core has contract version `{portable_core}`"
        not in compatibility.read_text(encoding="utf-8")
    ):
        _error(errors, compatibility, "portable-core identity must match the registry")
    claude_code_capabilities = [
        row
        for row in registry.get("capabilities", [])
        if isinstance(row, dict) and row.get("id") == "claude-code-plugin-host"
    ] if registry else []
    if len(claude_code_capabilities) == 1:
        minimum = claude_code_capabilities[0].get("version")
        compatibility_text = compatibility.read_text(encoding="utf-8") if compatibility.is_file() else ""
        if not isinstance(minimum, str) or f"| Claude Code | {minimum} |" not in compatibility_text:
            _error(errors, compatibility, "minimum supported Claude Code version must match the registry")
        minimum_match = MINIMUM_SEMVER.fullmatch(minimum) if isinstance(minimum, str) else None
        workflow = root / ".github/workflows/plugin-validation.yml"
        workflow_text = workflow.read_text(encoding="utf-8") if workflow.is_file() else ""
        pins = re.findall(r"@anthropic-ai/claude-code@([0-9]+\.[0-9]+\.[0-9]+)", workflow_text)
        if minimum_match is None or len(pins) != 2 or any(pin != minimum_match.group(1) for pin in pins):
            _error(errors, workflow, "Claude Code CI pins must exercise the supported minimum")
    orientation = root / "CLAUDE.md"
    if orientation.is_file():
        text = orientation.read_text(encoding="utf-8")
        if "docs/repository-orientation.md" not in text:
            _error(errors, orientation, "host carrier must point to the tracked orientation authority")
        if "plugins/bedrock/.claude-plugin/plugin.json" not in text:
            _error(errors, orientation, "tracked orientation must name the actual manifest authority")
        if "root `AGENTS.md` is the tracked Codex adapter" not in text:
            _error(errors, orientation, "Claude carrier must classify root AGENTS.md as the tracked Codex adapter")
        if "HEB-119 cold acceptance binds to the frozen reviewed" not in text or "commit before merge" not in text:
            _error(errors, orientation, "Claude carrier must preserve the pre-merge acceptance boundary")

    readme = root / "README.md"
    if readme.is_file():
        text = readme.read_text(encoding="utf-8")
        if "cold acceptance runs against the" not in text or "before that commit lands" not in text:
            _error(errors, readme, "README release guidance must preserve the pre-merge acceptance boundary")

    codex_adapter = root / "AGENTS.md"
    if codex_adapter.is_file() and codex_adapter.read_text(encoding="utf-8") != EXPECTED_CODEX_ADAPTER:
        _error(errors, codex_adapter, "Codex adapter must be the exact content-free authority pointer")

    canonical_orientation = root / "docs/repository-orientation.md"
    if canonical_orientation.is_file():
        text = canonical_orientation.read_text(encoding="utf-8")
        if "root `AGENTS.md` is the Codex adapter" not in text:
            _error(errors, canonical_orientation, "canonical orientation must classify root AGENTS.md as the Codex adapter")
        if (
            "production marketplace resolves `main`" not in text
            or "package content only" not in text
            or "cold acceptance against that commit before merge" not in text
        ):
            _error(errors, canonical_orientation, "canonical orientation must require acceptance before marketplace-branch merge")

    markdown_files = [root / relative for relative in REQUIRED_FILES if relative.endswith(".md")]
    for path in markdown_files:
        if not path.is_file():
            continue
        for target in MARKDOWN_LINK.findall(path.read_text(encoding="utf-8")):
            target = target.strip().strip("<>")
            if not target or target.startswith(("https://", "http://", "mailto:")):
                continue
            local = target.split("#", 1)[0]
            if not local:
                continue
            candidate = (path.parent / local).resolve()
            if not candidate.is_relative_to(root.resolve()) or not candidate.exists():
                _error(errors, path, f"package-governance link target does not exist: {target}")


def _validate_schemas(root: Path, errors: list[str]) -> None:
    governance = root / "plugins/bedrock/governance"
    for name in ("release-evidence", "rollout-ledger"):
        schema_path = governance / f"{name}.schema.json"
        schema = _load_json(schema_path, errors)
        if schema is None:
            continue
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as exc:
            _error(errors, schema_path, f"invalid schema: {exc.message}")
        template_path = governance / f"{name}.template.yaml"
        template = _load_yaml(template_path, errors)
        if template is not None and template.get("schema_version") != 1:
            _error(errors, template_path, "schema_version must be 1")
        if name == "release-evidence" and template is not None:
            gate_ids = [row.get("id") for row in template.get("gates", []) if isinstance(row, dict)]
            if set(gate_ids) != FINAL_RELEASE_GATES or len(gate_ids) != len(FINAL_RELEASE_GATES):
                _error(errors, template_path, "template must enumerate every final release gate exactly once")
            expected_landing = {
                "marketplace_branch": "main",
                "commit": None,
                "method": None,
                "merged_at": None,
                "evidence": None,
            }
            if template.get("landing") != expected_landing:
                _error(errors, template_path, "release template must carry a pending marketplace landing record")


def _nested_enum(schema: dict[str, Any], *path: str) -> list[str] | None:
    value: Any = schema
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value if isinstance(value, list) else None


def _validate_vocabulary_and_authority(root: Path, errors: list[str]) -> None:
    governance = root / "plugins/bedrock/governance"
    vocabulary_path = governance / "vocabulary.yaml"
    vocabulary = _load_yaml(vocabulary_path, errors)
    release_schema = _load_json(governance / "release-evidence.schema.json", errors)
    rollout_schema = _load_json(governance / "rollout-ledger.schema.json", errors)
    if vocabulary and release_schema and rollout_schema:
        comparisons = (
            ("gate_status", _nested_enum(release_schema, "properties", "gates", "items", "properties", "status", "enum")),
            ("migration_classification", _nested_enum(release_schema, "properties", "migration", "properties", "classification", "enum")),
            ("release_decision", _nested_enum(release_schema, "properties", "decision", "properties", "status", "enum")),
            ("rollout_status", _nested_enum(rollout_schema, "properties", "status", "enum")),
            ("surface_status", _nested_enum(rollout_schema, "properties", "surfaces", "items", "properties", "status", "enum")),
        )
        for key, schema_values in comparisons:
            if vocabulary.get(key) != schema_values:
                _error(errors, vocabulary_path, f"{key} must match the governing schema enum exactly")

    inventory_path = governance / "authority-inventory.yaml"
    inventory = _load_yaml(inventory_path, errors)
    if inventory is None:
        return
    concepts = inventory.get("concepts")
    if not isinstance(concepts, list) or not concepts:
        _error(errors, inventory_path, "concepts must be a non-empty list")
        return
    names: list[str] = []
    allowed = {"authority", "generated-carrier", "contextual-restatement"}
    for index, concept in enumerate(concepts):
        location = f"{inventory_path}:concepts[{index}]"
        if not isinstance(concept, dict) or not concept.get("concept") or not concept.get("authority"):
            _error(errors, location, "concept requires a name and authority")
            continue
        names.append(concept["concept"])
        repetitions = concept.get("repetitions")
        if not isinstance(repetitions, list) or not repetitions:
            _error(errors, location, "concept requires classified repetitions")
            continue
        for row in repetitions:
            if not isinstance(row, dict) or row.get("classification") not in allowed or not row.get("drift_control"):
                _error(errors, location, "every repetition requires an allowed classification and drift control")
    if len(names) != len(set(names)):
        _error(errors, inventory_path, "concept names must be unique")


def _validate_heb118_evidence(root: Path, errors: list[str]) -> None:
    path = root / "docs/evidence/heb-118/manifest.yaml"
    payload = _load_yaml(path, errors)
    if payload is None:
        return
    if payload.get("schema_version") != 1 or payload.get("ticket") != "HEB-118":
        _error(errors, path, "must identify HEB-118 schema version 1")
    rows = payload.get("finding_reconciliation")
    if not isinstance(rows, list):
        _error(errors, path, "finding_reconciliation must be a list")
        return
    ids = [row.get("id") for row in rows if isinstance(row, dict)]
    expected = {f"PKG-{number:03d}" for number in range(1, 40)}
    if set(ids) != expected or len(ids) != len(expected):
        _error(errors, path, "finding reconciliation must contain PKG-001 through PKG-039 exactly once")
    residual = {
        *(f"PKG-{number:03d}" for number in range(4, 13)),
        *(f"PKG-{number:03d}" for number in range(17, 24)),
        "PKG-026",
        "PKG-028",
        "PKG-033",
        "PKG-039",
    }
    implemented = {
        row.get("id")
        for row in rows
        if isinstance(row, dict) and row.get("status") == "heb-118-implemented"
    }
    if implemented != residual:
        _error(errors, path, f"HEB-118 residual finding set drifted: {sorted(implemented)}")
    for index, row in enumerate(rows):
        location = f"{path}:finding_reconciliation[{index}]"
        if not isinstance(row, dict) or row.get("status") not in {"upstream-verified", "heb-118-implemented"}:
            _error(errors, location, "finding row must have an implemented or upstream-verified status")
            continue
        if not row.get("owner"):
            _error(errors, location, "finding row requires an owner")
        evidence = row.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            _error(errors, location, "finding row requires retained evidence")
            continue
        for item in evidence:
            candidate = root / item if isinstance(item, str) else root / "__invalid__"
            if not candidate.exists() or not candidate.resolve().is_relative_to(root.resolve()):
                _error(errors, location, f"evidence path does not exist in the repository: {item!r}")
    claims = payload.get("claims")
    if not isinstance(claims, list) or not claims:
        _error(errors, path, "claims must be a non-empty list")
    else:
        for index, claim in enumerate(claims):
            location = f"{path}:claims[{index}]"
            if not isinstance(claim, dict) or not all(claim.get(key) for key in ("id", "status", "command", "evidence")):
                _error(errors, location, "claim requires id, status, command, and evidence")
                continue
            for item in claim["evidence"]:
                if not (root / item).exists():
                    _error(errors, location, f"claim evidence does not exist: {item}")


def _git_result(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _validate_release(
    root: Path,
    version: str | None,
    registry: dict[str, Any] | None,
    evidence_path: Path | None,
    rollout_path: Path | None,
    errors: list[str],
) -> None:
    if version is None or registry is None:
        return
    if evidence_path is None:
        _error(errors, "release gate", "release mode requires --release-evidence")
    if rollout_path is None:
        _error(errors, "release gate", "release mode requires --rollout-ledger")
    if evidence_path is None or rollout_path is None:
        return
    tag = f"v{version}"
    evidence = _load_yaml(evidence_path, errors)
    rollout = _load_yaml(rollout_path, errors)
    schemas = {
        evidence_path: (evidence, root / "plugins/bedrock/governance/release-evidence.schema.json"),
        rollout_path: (rollout, root / "plugins/bedrock/governance/rollout-ledger.schema.json"),
    }
    for path, (payload, schema_path) in schemas.items():
        if payload is None:
            continue
        schema = _load_json(schema_path, errors)
        if schema is None:
            continue
        try:
            Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER).validate(payload)
        except ValidationError as exc:
            _error(errors, path, f"schema violation: {exc.message}")
    if evidence:
        if evidence.get("manifest_version") != version:
            _error(errors, evidence_path, "manifest_version must match the manifest")
        manifest_digest = hashlib.sha256(
            (root / "plugins/bedrock/.claude-plugin/plugin.json").read_bytes()
        ).hexdigest()
        if evidence.get("manifest_sha256") != manifest_digest:
            _error(errors, evidence_path, "manifest_sha256 must match the packaged manifest")
        findings = evidence.get("findings", {})
        if findings.get("assigned") != findings.get("closed"):
            _error(errors, evidence_path, "all assigned findings must be closed")
        decision = evidence.get("decision")
        if not isinstance(decision, dict):
            _error(errors, evidence_path, "release requires a valid decision record")
            decision = {}
        if decision.get("status") != "proceed":
            _error(errors, evidence_path, "release requires a proceed decision")
        blocked = {"failed", "unavailable"}
        if any(row.get("status") in blocked for row in evidence.get("gates", []) if isinstance(row, dict)):
            _error(errors, evidence_path, "release has a failed or unavailable gate")
        raw_gates = [row for row in evidence.get("gates", []) if isinstance(row, dict)]
        gate_rows = {row.get("id"): row for row in raw_gates}
        if (
            set(gate_rows) != FINAL_RELEASE_GATES
            or len(raw_gates) != len(FINAL_RELEASE_GATES)
            or any(row.get("status") != "passed" for row in gate_rows.values())
        ):
            _error(errors, evidence_path, "release requires every named final gate to pass exactly once")
        source_commit = evidence.get("source_commit")
        landing = evidence.get("landing", {})
        marketplace_branch = landing.get("marketplace_branch") if isinstance(landing, dict) else None
        landing_commit = landing.get("commit") if isinstance(landing, dict) else None
        landing_method = landing.get("method") if isinstance(landing, dict) else None
        merged_at_value = landing.get("merged_at") if isinstance(landing, dict) else None
        decision_at = _parse_timestamp(decision.get("recorded_at"))
        merged_at = _parse_timestamp(merged_at_value)
        if (
            not isinstance(landing_commit, str)
            or not isinstance(landing_method, str)
            or not isinstance(merged_at_value, str)
            or not merged_at_value.strip()
            or not isinstance(landing.get("evidence"), str)
            or not landing["evidence"].strip()
        ):
            _error(errors, evidence_path, "release requires a complete landing record")
        elif landing_method != "merge_commit":
            _error(errors, evidence_path, "release permits merge_commit landing only")
        elif decision_at is None or merged_at is None:
            _error(
                errors,
                evidence_path,
                "decision and landing timestamps must be valid timezone-aware date-times",
            )
        elif decision_at >= merged_at:
            _error(errors, evidence_path, "cold-acceptance proceed decision must precede landing")
        elif not isinstance(source_commit, str):
            _error(errors, evidence_path, "release requires an accepted source commit")
        else:
            landing_object = _git_result(root, "cat-file", "-e", f"{landing_commit}^{{commit}}")
            if landing_object.returncode != 0:
                _error(errors, evidence_path, "landing commit must resolve to a commit object")
            elif marketplace_branch == "main":
                marketplace_ref = f"refs/heads/{marketplace_branch}"
                branch = _git_result(root, "show-ref", "--verify", "--quiet", marketplace_ref)
                if branch.returncode != 0:
                    _error(errors, evidence_path, f"marketplace branch ref {marketplace_ref} must exist locally")
                else:
                    reachable = _git_result(
                        root,
                        "merge-base",
                        "--is-ancestor",
                        landing_commit,
                        marketplace_ref,
                    )
                    if reachable.returncode != 0:
                        _error(
                            errors,
                            evidence_path,
                            f"landing commit must be reachable from marketplace branch {marketplace_branch}",
                        )
                    first_parent = _git_result(root, "rev-list", "--first-parent", marketplace_ref)
                    if first_parent.returncode != 0:
                        _error(
                            errors,
                            evidence_path,
                            f"marketplace branch {marketplace_branch} first-parent history must be readable",
                        )
                    else:
                        first_parent_shas = set(first_parent.stdout.splitlines())
                        if landing_commit not in first_parent_shas:
                            _error(
                                errors,
                                evidence_path,
                                "merge landing commit must be on the marketplace branch first-parent history",
                            )
                parents = _git_result(root, "rev-list", "--parents", "-n", "1", landing_commit)
                parent_shas = parents.stdout.strip().split()[1:] if parents.returncode == 0 else []
                if len(parent_shas) < 2 or parent_shas[1] != source_commit:
                    _error(
                        errors,
                        evidence_path,
                        "merge landing must preserve the accepted source commit as its second parent",
                    )
                parity = _git_result(
                    root,
                    "diff",
                    "--quiet",
                    source_commit,
                    landing_commit,
                    "--",
                    *PRESERVED_DISTRIBUTION_PATHS,
                )
                if parity.returncode != 0:
                    _error(errors, evidence_path, "landing changed marketplace or installed package bytes after acceptance")
        result = _git_result(root, "rev-list", "-n", "1", tag)
        if result.returncode != 0 or result.stdout.strip() != source_commit:
            _error(errors, "release gate", f"immutable tag {tag} must resolve to the evidence source commit")
        tag_type = _git_result(root, "cat-file", "-t", tag)
        if tag_type.returncode != 0 or tag_type.stdout.strip() != "tag":
            _error(errors, "release gate", f"{tag} must be an annotated tag")
    if rollout:
        if rollout.get("manifest_version") != version or rollout.get("release_tag") != tag:
            _error(errors, rollout_path, "rollout identity must match the manifest and tag")
        if rollout.get("status") != "complete":
            _error(errors, rollout_path, "rollout ledger must be complete")
        if evidence and rollout.get("source_commit") != evidence.get("source_commit"):
            _error(errors, rollout_path, "rollout and release evidence source commits must match")
        surface_ids = [row.get("id") for row in rollout.get("surfaces", []) if isinstance(row, dict)]
        if Counter(surface_ids) != Counter({"claude-ai": 1, "claude-code": 1, "codex": 1}):
            _error(errors, rollout_path, "rollout must enumerate claude-ai, claude-code, and codex exactly once")
        for row in rollout.get("surfaces", []):
            if not isinstance(row, dict):
                continue
            if row.get("status") == "waived":
                if not row.get("waiver"):
                    _error(errors, rollout_path, "waived surface requires a waiver rationale")
            elif row.get("status") != "verified":
                _error(errors, rollout_path, "every unwaived surface must be verified")


def validate_package_governance(
    root: Path,
    *,
    release: bool = False,
    release_evidence: Path | None = None,
    rollout_ledger: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    version = _validate_metadata(root, errors)
    registry = _validate_registry(root, errors)
    _validate_package_identity_carriers(root, errors)
    _validate_budgets(root, registry, errors)
    _validate_documents(root, version, registry, errors)
    _validate_schemas(root, errors)
    _validate_vocabulary_and_authority(root, errors)
    _validate_heb118_evidence(root, errors)
    if release:
        _validate_release(root, version, registry, release_evidence, rollout_ledger, errors)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--release", action="store_true", help="Require post-acceptance tag, evidence, and rollout proof")
    parser.add_argument("--release-evidence", type=Path, help="Schema-valid operator release-evidence export")
    parser.add_argument("--rollout-ledger", type=Path, help="Schema-valid completed rollout-ledger export")
    args = parser.parse_args()
    root = args.root.resolve()
    evidence = (
        (root / args.release_evidence).resolve()
        if args.release_evidence and not args.release_evidence.is_absolute()
        else args.release_evidence
    )
    rollout = (
        (root / args.rollout_ledger).resolve()
        if args.rollout_ledger and not args.rollout_ledger.is_absolute()
        else args.rollout_ledger
    )
    errors = validate_package_governance(
        root,
        release=args.release,
        release_evidence=evidence,
        rollout_ledger=rollout,
    )
    if errors:
        print("FAIL: package governance")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS: package lifecycle, metadata, compatibility, policy, registry, and evidence contracts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
