from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

import yaml

from scripts.validate_plugin import (
    EXPECTED_SKILLS,
    run_host_manifest_validator,
    validate_repository,
)


class ValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self._write_valid_repository()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _write_valid_repository(self) -> None:
        plugin = self.root / "plugins" / "bedrock"
        (plugin / ".claude-plugin").mkdir(parents=True)
        (self.root / ".claude-plugin").mkdir()
        (self.root / "tests" / "fixtures").mkdir(parents=True)
        (self.root / "validation").mkdir()
        (self.root / "docs" / "evidence" / "heb-109").mkdir(parents=True)
        description = "Author the named work. Use for the matching task. Do not use for unrelated work."
        for name in EXPECTED_SKILLS:
            skill_dir = plugin / "skills" / name
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                f'---\nname: {name}\ndescription: "{description}"\n---\n\n# {name}\n',
                encoding="utf-8",
            )
        plugin_description = "Bedrock test plugin"
        (plugin / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": "bedrock", "description": plugin_description, "version": "1.0.0"}),
            encoding="utf-8",
        )
        (self.root / ".claude-plugin" / "marketplace.json").write_text(
            json.dumps(
                {
                    "plugins": [
                        {
                            "name": "bedrock",
                            "description": plugin_description,
                            "source": "./plugins/bedrock",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        cases = []
        for name in EXPECTED_SKILLS:
            cases.extend(
                [
                    {
                        "id": f"{name}-positive",
                        "kind": "positive",
                        "cue": "implicit" if name == "agent-code" else "direct",
                        "surface": "portable-core",
                        "prompt": f"Use {name}",
                        "expected": name,
                        "excluded": [],
                    },
                    {
                        "id": f"{name}-negative",
                        "kind": "negative",
                        "cue": "adversarial" if name == "agent-code" else "direct",
                        "surface": "portable-core",
                        "prompt": f"Do not use {name}",
                        "expected": None,
                        "excluded": [name],
                    },
                ]
            )
        (self.root / "tests" / "fixtures" / "routing.yaml").write_text(
            yaml.safe_dump({"schema_version": 2, "cases": cases}, sort_keys=False),
            encoding="utf-8",
        )
        (self.root / "validation" / "eval-policy.yaml").write_text(
            yaml.safe_dump(
                {
                    "schema_version": 1,
                    "profiles": {
                        "pr": {
                            "runs_per_case": 1,
                            "minimum_overall_pass_rate": 1.0,
                            "minimum_case_pass_rate": 1.0,
                            "excluded_selection_limit": 0,
                        },
                        "release": {
                            "runs_per_case": 3,
                            "minimum_overall_pass_rate": 0.95,
                            "minimum_case_pass_rate": 0.66,
                            "excluded_selection_limit": 0,
                        },
                    },
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (self.root / "validation" / "package-contract.yaml").write_text(
            yaml.safe_dump(
                {
                    "schema_version": 1,
                    "external_dependencies": [],
                    "private_path_examples": [],
                    "snapshots": [],
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (self.root / "validation" / "executable-samples.yaml").write_text(
            yaml.safe_dump({"schema_version": 1, "samples": []}, sort_keys=False),
            encoding="utf-8",
        )
        (self.root / "docs" / "evidence" / "heb-109" / "baseline.md").write_text(
            "# Baseline\n", encoding="utf-8"
        )
        (self.root / "docs" / "evidence" / "heb-109" / "manifest.yaml").write_text(
            yaml.safe_dump(
                {
                    "schema_version": 1,
                    "claims": [
                        {
                            "id": "baseline",
                            "status": "verified",
                            "command": "python scripts/validate_plugin.py",
                            "evidence": ["docs/evidence/heb-109/baseline.md"],
                        }
                    ],
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

    def assert_has_error(self, needle: str) -> None:
        errors, _ = validate_repository(
            self.root,
            run_host_cli=False,
            run_safety_checks=False,
            require_authoring_contracts=False,
            require_package_governance=False,
        )
        self.assertTrue(any(needle in error for error in errors), errors)

    def test_valid_fixture_passes(self) -> None:
        errors, report = validate_repository(
            self.root,
            run_host_cli=False,
            run_safety_checks=False,
            require_authoring_contracts=False,
            require_package_governance=False,
        )
        self.assertEqual([], errors)
        self.assertEqual(14, report["skill_count"])

    def test_rejects_malformed_frontmatter(self) -> None:
        path = self.root / "plugins" / "bedrock" / "skills" / "agent-code" / "SKILL.md"
        path.write_text("---\nname: agent-code\ndescription: bad: yaml\n---\n", encoding="utf-8")
        self.assert_has_error("invalid YAML frontmatter")

    def test_rejects_overlong_description(self) -> None:
        path = self.root / "plugins" / "bedrock" / "skills" / "agent-code" / "SKILL.md"
        path.write_text(
            f'---\nname: agent-code\ndescription: "Use this. Do not use that. {"x" * 1024}"\n---\n',
            encoding="utf-8",
        )
        self.assert_has_error("exceeds 1024")

    def test_rejects_duplicate_name(self) -> None:
        path = self.root / "plugins" / "bedrock" / "skills" / "testing" / "SKILL.md"
        path.write_text(
            '---\nname: agent-code\ndescription: "Use this. Do not use that."\n---\n',
            encoding="utf-8",
        )
        self.assert_has_error("duplicate skill name")

    def test_rejects_manifest_description_drift(self) -> None:
        path = self.root / ".claude-plugin" / "marketplace.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["plugins"][0]["description"] = "drifted"
        path.write_text(json.dumps(payload), encoding="utf-8")
        self.assert_has_error("description must equal plugin.json description")

    def test_rejects_duplicate_json_key_before_value_collapse(self) -> None:
        path = self.root / "plugins/bedrock/.claude-plugin/plugin.json"
        path.write_text(
            '{"name":"bedrock","name":"other","description":"Bedrock test plugin","version":"1.0.0"}',
            encoding="utf-8",
        )
        self.assert_has_error("duplicate JSON key")

    def test_rejects_missing_negative_route(self) -> None:
        path = self.root / "tests" / "fixtures" / "routing.yaml"
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        payload["cases"] = [case for case in payload["cases"] if case["id"] != "testing-negative"]
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        self.assert_has_error("missing negative routing case excluding testing")

    def test_rejects_missing_application_test_debug_registry(self) -> None:
        errors, _ = validate_repository(
            self.root,
            run_host_cli=False,
            run_safety_checks=False,
            require_authoring_contracts=True,
            require_package_governance=False,
        )
        self.assertTrue(
            any("application/test/debug contract registry is missing" in error for error in errors),
            errors,
        )

    def test_rejects_non_mapping_route(self) -> None:
        path = self.root / "tests" / "fixtures" / "routing.yaml"
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        payload["cases"].append("not-a-case")
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        self.assert_has_error("case must be a mapping")

    def test_rejects_unknown_overlap_alternate(self) -> None:
        path = self.root / "tests" / "fixtures" / "routing.yaml"
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        payload["cases"].append(
            {
                "id": "bad-overlap",
                "kind": "overlap",
                "cue": "direct",
                "surface": "portable-core",
                "prompt": "Ambiguous task",
                "expected": "testing",
                "allowed_alternates": ["missing-skill"],
                "excluded": [],
            }
        )
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        self.assert_has_error("allowed_alternates must contain only known skill names")

    def test_rejects_missing_relative_markdown_target(self) -> None:
        path = self.root / "plugins/bedrock/skills/agent-code/SKILL.md"
        path.write_text(path.read_text(encoding="utf-8") + "\n[missing](reference/nope.md)\n", encoding="utf-8")
        self.assert_has_error("relative link target does not exist")

    def test_rejects_missing_markdown_anchor(self) -> None:
        path = self.root / "plugins/bedrock/skills/agent-code/SKILL.md"
        path.write_text(path.read_text(encoding="utf-8") + "\n[missing](#not-a-heading)\n", encoding="utf-8")
        self.assert_has_error("markdown anchor does not exist")

    def test_rejects_cross_skill_relative_link(self) -> None:
        path = self.root / "plugins/bedrock/skills/agent-code/SKILL.md"
        path.write_text(path.read_text(encoding="utf-8") + "\n[cross-skill](../testing/SKILL.md)\n", encoding="utf-8")
        self.assert_has_error("relative link escapes its skill package")

    def test_rejects_private_absolute_path(self) -> None:
        path = self.root / "plugins/bedrock/skills/agent-code/SKILL.md"
        path.write_text(path.read_text(encoding="utf-8") + "\nUse /Users/example/private/tool.\n", encoding="utf-8")
        self.assert_has_error("private absolute path")

    def test_rejects_tilde_home_path(self) -> None:
        path = self.root / "plugins/bedrock/skills/agent-code/SKILL.md"
        path.write_text(path.read_text(encoding="utf-8") + "\nUse ~/private/tool.\n", encoding="utf-8")
        self.assert_has_error("private absolute path")

    def test_rejects_undeclared_external_dependency(self) -> None:
        path = self.root / "plugins/bedrock/skills/agent-code/SKILL.md"
        path.write_text(path.read_text(encoding="utf-8") + "\nRun $PRIVATE_ROOT/tool.\n", encoding="utf-8")
        self.assert_has_error("undeclared external dependency $PRIVATE_ROOT")

    def test_rejects_stale_snapshot_declaration(self) -> None:
        contract = self.root / "validation/package-contract.yaml"
        contract.write_text(
            yaml.safe_dump(
                {
                    "schema_version": 1,
                    "external_dependencies": [],
                    "private_path_examples": [],
                    "snapshots": [
                        {
                            "path": "plugins/bedrock/skills/agent-code/SKILL.md",
                            "source_marker": "canonical/source.md",
                            "currency_marker": "verify against it fresh",
                        }
                    ],
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        self.assert_has_error("snapshot source marker is missing")

    def test_rejects_uninventoried_code_fence(self) -> None:
        path = self.root / "plugins/bedrock/skills/agent-code/SKILL.md"
        path.write_text(path.read_text(encoding="utf-8") + "\n```python\nprint('x')\n```\n", encoding="utf-8")
        self.assert_has_error("code sample is absent from executable-samples.yaml")

    def test_rejects_fixture_backed_sample_without_command(self) -> None:
        path = self.root / "plugins/bedrock/skills/agent-code/SKILL.md"
        path.write_text(path.read_text(encoding="utf-8") + "\n```python\nprint('x')\n```\n", encoding="utf-8")
        inventory = self.root / "validation/executable-samples.yaml"
        inventory.write_text(
            yaml.safe_dump(
                {
                    "schema_version": 1,
                    "samples": [
                        {
                            "path": "plugins/bedrock/skills/agent-code/SKILL.md",
                            "language": "python",
                            "count": 1,
                            "classification": "fixture-backed",
                            "evidence": ["plugins/bedrock/skills/agent-code/SKILL.md"],
                        }
                    ],
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        self.assert_has_error("fixture-backed samples require a reproducible command")

    def test_rejects_missing_evidence_file(self) -> None:
        manifest = self.root / "docs/evidence/heb-109/manifest.yaml"
        payload = yaml.safe_load(manifest.read_text(encoding="utf-8"))
        payload["claims"][0]["evidence"] = ["docs/evidence/heb-109/missing.md"]
        manifest.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        self.assert_has_error("evidence path does not exist")

    def test_rejects_evidence_path_outside_repository(self) -> None:
        manifest = self.root / "docs/evidence/heb-109/manifest.yaml"
        payload = yaml.safe_load(manifest.read_text(encoding="utf-8"))
        payload["claims"][0]["evidence"] = ["/etc/hosts"]
        manifest.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        self.assert_has_error("evidence path must be repository-relative")

    def test_rejects_invalid_eval_threshold(self) -> None:
        policy = self.root / "validation/eval-policy.yaml"
        payload = yaml.safe_load(policy.read_text(encoding="utf-8"))
        payload["profiles"]["release"]["minimum_overall_pass_rate"] = 1.1
        policy.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        self.assert_has_error("minimum_overall_pass_rate must be between 0 and 1")

    def test_rejects_invalid_retained_routing_report(self) -> None:
        report = self.root / "docs/evidence/heb-109/routing-results.json"
        report.write_text("{}\n", encoding="utf-8")
        self.assert_has_error("routing report schema_version must be 2")

    def test_rejects_duplicate_yaml_key_before_value_collapse(self) -> None:
        policy = self.root / "validation/eval-policy.yaml"
        policy.write_text(
            policy.read_text(encoding="utf-8") + "\nschema_version: 1\n",
            encoding="utf-8",
        )
        self.assert_has_error("duplicate YAML key")

    def test_seeded_defect_manifest_names_existing_tests(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        payload = yaml.safe_load(
            (repository_root / "tests/fixtures/package-defects/manifest.yaml").read_text(encoding="utf-8")
        )
        declared = {row["test"] for row in payload["defects"]}
        available = {name for name in dir(type(self)) if name.startswith("test_")}
        self.assertEqual(set(), declared - available)
@unittest.skipUnless(shutil.which("claude"), "Claude Code CLI is not installed")
class StrictHostValidatorIntegrationTests(unittest.TestCase):
    def test_seeded_invalid_manifest_fails_strict_host_validation(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            fixture_root = Path(temporary)
            destination = fixture_root / "plugins" / "bedrock"
            destination.parent.mkdir(parents=True)
            shutil.copytree(repository_root / "plugins" / "bedrock", destination)
            manifest = destination / ".claude-plugin" / "plugin.json"
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["unexpected_field"] = True
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            errors: list[str] = []
            run_host_manifest_validator(fixture_root, errors)
            self.assertTrue(errors, "seeded invalid plugin manifest unexpectedly passed strict host validation")


if __name__ == "__main__":
    unittest.main()
