from __future__ import annotations

import json
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml

from scripts.sync_package_identity import synchronize
from scripts.validate_package_governance import validate_package_governance
from scripts.validate_plugin import validate_repository


class PackageGovernanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        source = Path(__file__).resolve().parents[1]
        shutil.copytree(
            source,
            self.root,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", "__pycache__", "node_modules"),
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def assert_has_error(self, needle: str) -> None:
        errors = validate_package_governance(self.root)
        self.assertTrue(any(needle in error for error in errors), errors)

    def write_package_identity_carriers(self) -> list[Path]:
        manifest_path = self.root / "plugins/bedrock/.claude-plugin/plugin.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        registry = yaml.safe_load(
            (self.root / "plugins/bedrock/governance/registry.yaml").read_text(encoding="utf-8")
        )
        payload = {
            "schema_version": 1,
            "classification": "generated-carrier",
            "package": manifest["name"],
            "manifest_version": manifest["version"],
            "version_authority": ".claude-plugin/plugin.json#/version",
            "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "generator": {
                "id": "scripts/sync_package_identity.py",
                "version": "1.0.0",
            },
            "contracts": {
                "claude_adapter": registry["contracts"]["claude_adapter"],
            },
        }
        encoded = json.dumps(payload, indent=2) + "\n"
        paths = sorted((self.root / "plugins/bedrock/skills").glob("*/SKILL.md"))
        carrier_paths = [path.with_name("PACKAGE_IDENTITY.json") for path in paths]
        for path in carrier_paths:
            path.write_text(encoded, encoding="utf-8")
        return carrier_paths

    def test_planning_has_accepted_explicit_adoption_and_source_identity(self) -> None:
        skill = self.root / "plugins/bedrock/skills/planning"
        self.assertTrue((skill / "SKILL.md").is_file(), "accepted planning entrypoint is absent")
        adoption = json.loads((skill / "PACKAGE_ADOPTION.json").read_text())
        self.assertEqual("accepted-supervised-advisory", adoption["status"])
        self.assertEqual("explicit", adoption["invocation"])
        self.assertEqual("pending-HEB-161", adoption["release_qualification"])
        self.assertEqual("open-after-shared-release", adoption["hex_reconsumption"])
        self.assertIn("adoption remains pending", (skill / "reference/provenance.md").read_text())
        self.assertEqual([], validate_package_governance(self.root))

    def test_planning_adoption_and_exact_source_fail_closed(self) -> None:
        skill = self.root / "plugins/bedrock/skills/planning"
        for name in ("SKILL.md", "reference/provenance.md"):
            with self.subTest(source=name):
                path = skill / name
                original = path.read_bytes()
                path.write_bytes(original + b"\nchanged\n")
                self.assert_has_error("accepted planning source digest mismatch")
                path.write_bytes(original)
        path = skill / "PACKAGE_ADOPTION.json"
        original = path.read_bytes()
        payload = json.loads(original)
        for key, bad in (("status", "proposed"), ("invocation", "implicit"),
                         ("release_qualification", "accepted"), ("hex_reconsumption", "complete")):
            with self.subTest(field=key):
                changed = dict(payload, **{key: bad})
                path.write_text(json.dumps(changed))
                self.assert_has_error("planning adoption authority drift")
        path.write_bytes(original)
        path.unlink()
        self.assert_has_error("planning adoption authority is unavailable")

    def test_planning_invocation_policy_cannot_be_omitted_or_implicit(self) -> None:
        policy = self.root / "plugins/bedrock/skills/planning/agents/openai.yaml"
        original = policy.read_bytes()
        for value in ("true", "0", "null", "\"false\""):
            with self.subTest(value=value):
                policy.write_text(f"policy:\n  allow_implicit_invocation: {value}\n")
                self.assert_has_error("planning requires explicit invocation policy")
        policy.unlink()
        self.assert_has_error("planning requires explicit invocation policy")
        policy.write_bytes(original)
        self.assertEqual([], validate_package_governance(self.root))

    def test_planning_authorities_reject_duplicate_keys_before_collapse(self) -> None:
        skill = self.root / "plugins/bedrock/skills/planning"
        policy = skill / "agents/openai.yaml"
        original_policy = policy.read_bytes()
        for text in ("policy:\n  allow_implicit_invocation: true\n  allow_implicit_invocation: false\n",
                     "policy: {allow_implicit_invocation: true}\npolicy: {allow_implicit_invocation: false}\n",
                     "policy: {<<: {allow_implicit_invocation: true}, allow_implicit_invocation: false}\n"):
            with self.subTest(policy=text):
                policy.write_text(text)
                self.assert_has_error("duplicate YAML key")
        policy.write_bytes(original_policy)
        adoption = skill / "PACKAGE_ADOPTION.json"
        original_adoption = adoption.read_bytes()
        adoption.write_text(original_adoption.decode().replace('{', '{"invocation":"implicit",', 1))
        self.assert_has_error("duplicate JSON key")
        adoption.write_bytes(original_adoption)
        self.assertEqual([], validate_package_governance(self.root))

    def test_data_hygiene_surface_and_template_defects_refuse(self) -> None:
        surface = self.root / "plugins/bedrock/scripts/data-hygiene"
        self.assertEqual([], validate_package_governance(self.root))
        hook = surface / "pre-commit"
        original, mode = hook.read_bytes(), hook.stat().st_mode
        for defect in ("missing", "empty", "mode", "symlink", "extra"):
            with self.subTest(defect=defect):
                if defect == "missing": hook.unlink()
                elif defect == "empty": hook.write_bytes(b"")
                elif defect == "mode": hook.chmod(0o644)
                elif defect == "symlink":
                    hook.unlink(); hook.symlink_to(surface / "manager.py")
                else: (surface / "unexpected").write_text("fixture")
                self.assert_has_error("data-hygiene")
                if hook.is_symlink(): hook.unlink()
                hook.write_bytes(original); hook.chmod(mode)
                (surface / "unexpected").unlink(missing_ok=True)
        for relative in ("project-template/README.md", "project-template/CLAUDE.md"):
            path = self.root / relative
            old = path.read_text()
            path.write_text(old.replace("audit-repo", "removed-checkpoint"))
            self.assert_has_error("data-hygiene")
            path.write_text(old)
        self.assertEqual([], validate_package_governance(self.root))

    def test_main_validator_consumes_data_hygiene_gate(self) -> None:
        (self.root / "plugins/bedrock/scripts/data-hygiene/pre-commit").chmod(0o644)
        errors, _ = validate_repository(self.root, validate_retained_evidence=False,
                                        run_host_cli=False)
        self.assertTrue(any("data-hygiene" in error for error in errors), errors)

    def test_repository_package_governance_passes(self) -> None:
        self.assertEqual([], validate_package_governance(self.root))

    def test_rejects_manifest_metadata_drift(self) -> None:
        path = self.root / "plugins/bedrock/.claude-plugin/plugin.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["license"] = "UNKNOWN"
        path.write_text(json.dumps(payload), encoding="utf-8")
        self.assert_has_error("license must equal 'MIT'")

    def test_rejects_marketplace_authority_drift(self) -> None:
        path = self.root / ".claude-plugin/marketplace.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["plugins"][0]["version"] = "99.0.0"
        path.write_text(json.dumps(payload), encoding="utf-8")
        self.assert_has_error("must not duplicate the manifest version authority")

    def test_rejects_marketplace_source_boundary_drift(self) -> None:
        path = self.root / ".claude-plugin/marketplace.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["plugins"][0]["source"] = {
            "source": "git-subdir",
            "url": "https://github.com/Haffey-Enterprises/bedrock.git",
            "path": "plugins/bedrock",
            "ref": "candidate",
        }
        path.write_text(json.dumps(payload), encoding="utf-8")
        self.assert_has_error("marketplace source must match the accepted distribution boundary")

    def test_rejects_license_carrier_drift(self) -> None:
        path = self.root / "plugins/bedrock/LICENSE"
        path.write_text(path.read_text(encoding="utf-8") + "\ndrift\n", encoding="utf-8")
        self.assert_has_error("license must match repository license exactly")

    def test_rejects_orphaned_skill_lifecycle(self) -> None:
        path = self.root / "plugins/bedrock/governance/registry.yaml"
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        payload["skills"][0]["owner"] = ""
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        self.assert_has_error("owner is required")

    def test_rejects_retired_skill_without_migration(self) -> None:
        path = self.root / "plugins/bedrock/governance/registry.yaml"
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        payload["skills"][0]["status"] = "retired"
        payload["skills"][0]["migration"] = None
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        self.assert_has_error("non-active skill requires migration treatment")

    def test_rejects_incomplete_consumer_enumeration(self) -> None:
        path = self.root / "plugins/bedrock/governance/registry.yaml"
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        payload["consumer_surfaces"] = payload["consumer_surfaces"][:1]
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        self.assert_has_error("must contain claude-ai, claude-code, and codex exactly")

    def test_consumer_surface_set_is_exact(self) -> None:
        path = self.root / "plugins/bedrock/governance/registry.yaml"
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        expected = {"claude-ai", "claude-code", "codex"}
        self.assertEqual(expected, {row["id"] for row in payload["consumer_surfaces"]})
        self.assertEqual([], validate_package_governance(self.root))
        original = path.read_bytes()
        valid_rows = payload["consumer_surfaces"]
        cases = {
            **{f"missing-{name}": [row for row in valid_rows if row["id"] != name]
               for name in expected},
            "stale-two-surface": [row for row in valid_rows if row["id"] != "codex"],
            "unknown": valid_rows + [{"id": "unknown-host"}],
        }
        for label, rows in cases.items():
            with self.subTest(case=label):
                payload["consumer_surfaces"] = rows
                path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
                self.assert_has_error("must contain claude-ai, claude-code, and codex exactly")
        path.write_bytes(original)
        self.assertEqual([], validate_package_governance(self.root))

    def test_rollout_schema_and_template_declare_three_surfaces(self) -> None:
        governance = self.root / "plugins/bedrock/governance"
        schema = json.loads((governance / "rollout-ledger.schema.json").read_text())
        template = yaml.safe_load((governance / "rollout-ledger.template.yaml").read_text())
        expected = ["claude-ai", "claude-code", "codex"]
        self.assertEqual(expected, schema["properties"]["surfaces"]["items"]["properties"]["id"]["enum"])
        self.assertCountEqual(expected, [row["id"] for row in template["surfaces"]])
        for row in template["surfaces"]:
            self.assertEqual("pending", row["status"])
            self.assertIsNone(row["evidence"])
            self.assertEqual("MANIFEST_VERSION and 15 skills", row["expected_identity"])

    def test_rejects_non_merge_commit_landing_method(self) -> None:
        path = self.root / "plugins/bedrock/governance/registry.yaml"
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        payload["distribution"]["permitted_landing_methods"].append("fast_forward")
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        self.assert_has_error("landing method must require merge_commit only")

    def test_rejects_portable_core_version_drift_from_accepted_adr(self) -> None:
        path = self.root / "plugins/bedrock/governance/registry.yaml"
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        payload["contracts"]["portable_core"] = "9.9.9"
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        self.assert_has_error("portable_core must match the accepted ADR-001 version")

    def test_rejects_portable_core_authority_provenance_drift(self) -> None:
        path = self.root / "plugins/bedrock/governance/registry.yaml"
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        source = next(row for row in payload["sources"] if row["id"] == "adr-001")
        source["type"] = "contextual-restatement"
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        self.assert_has_error("ADR-001 source must identify the accepted portable-core authority")

    def test_rejects_compatibility_portable_core_version_drift(self) -> None:
        path = self.root / "plugins/bedrock/governance/COMPATIBILITY.md"
        registry = yaml.safe_load(
            (self.root / "plugins/bedrock/governance/registry.yaml").read_text(encoding="utf-8")
        )
        portable_core = registry["contracts"]["portable_core"]
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                f"portable skill core has contract version `{portable_core}`",
                "portable skill core has contract version `9.9.9`",
            ),
            encoding="utf-8",
        )
        self.assert_has_error("portable-core identity must match the registry")

    def test_rejects_claude_code_minimum_version_semantics_drift(self) -> None:
        path = self.root / "plugins/bedrock/governance/registry.yaml"
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        capability = next(
            row for row in payload["capabilities"] if row["id"] == "claude-code-plugin-host"
        )
        capability.pop("version_semantics", None)
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        self.assert_has_error("Claude Code capability must declare a minimum-supported SemVer floor")

    def test_rejects_compatibility_minimum_host_drift(self) -> None:
        path = self.root / "plugins/bedrock/governance/COMPATIBILITY.md"
        text, replacements = re.subn(
            r"^\| Claude Code \| [^|]+ \|",
            "| Claude Code | >=9.9.9 |",
            path.read_text(encoding="utf-8"),
            count=1,
            flags=re.MULTILINE,
        )
        self.assertEqual(1, replacements)
        path.write_text(text, encoding="utf-8")
        self.assert_has_error("minimum supported Claude Code version must match the registry")

    def test_rejects_verified_host_below_minimum(self) -> None:
        path = self.root / "plugins/bedrock/governance/registry.yaml"
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        payload["skills"][0]["verified_hosts"] = ["claude-code-2.1.225"]
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        self.assert_has_error("verified Claude Code host is below the supported minimum")

    def test_rejects_nonexact_verified_host_identity(self) -> None:
        path = self.root / "plugins/bedrock/governance/registry.yaml"
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        payload["skills"][0]["verified_hosts"] = ["claude-code>=2.1.226"]
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        self.assert_has_error("verified Claude Code hosts must use exact SemVer identities")

    def test_rejects_ci_host_floor_drift(self) -> None:
        path = self.root / ".github/workflows/plugin-validation.yml"
        original = path.read_text(encoding="utf-8")
        changed = original.replace(
            "@anthropic-ai/claude-code@2.1.226",
            "@anthropic-ai/claude-code@2.1.247",
        )
        self.assertNotEqual(original, changed)
        path.write_text(changed, encoding="utf-8")
        self.assert_has_error("Claude Code CI pins must exercise the supported minimum")

    def test_rejects_vocabulary_schema_drift(self) -> None:
        path = self.root / "plugins/bedrock/governance/vocabulary.yaml"
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        payload["gate_status"] = ["passed", "failed"]
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        self.assert_has_error("gate_status must match the governing schema enum exactly")

    def test_rejects_release_template_without_pending_landing(self) -> None:
        path = self.root / "plugins/bedrock/governance/release-evidence.template.yaml"
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        payload.pop("landing")
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        self.assert_has_error("release template must carry a pending marketplace landing record")

    def test_rejects_uncontrolled_duplicate_authority(self) -> None:
        path = self.root / "plugins/bedrock/governance/authority-inventory.yaml"
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        payload["concepts"][0]["repetitions"][0]["classification"] = "defect"
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        self.assert_has_error("every repetition requires an allowed classification and drift control")

    def test_rejects_stale_context_measurement(self) -> None:
        path = self.root / "docs/evidence/heb-118/context-budget.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["measurement"]["catalog_description_characters"] = 1
        path.write_text(json.dumps(payload), encoding="utf-8")
        self.assert_has_error("catalog description measurement is stale")

    def test_rejects_missing_package_finding(self) -> None:
        path = self.root / "docs/evidence/heb-118/manifest.yaml"
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        payload["finding_reconciliation"] = payload["finding_reconciliation"][:-1]
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        self.assert_has_error("must contain PKG-001 through PKG-039 exactly once")

    def test_rejects_missing_governance_link(self) -> None:
        path = self.root / "plugins/bedrock/governance/QUICKSTART.md"
        path.write_text(path.read_text(encoding="utf-8") + "\n[missing](missing.md)\n", encoding="utf-8")
        self.assert_has_error("package-governance link target does not exist")

    def test_rejects_missing_codex_adapter(self) -> None:
        (self.root / "AGENTS.md").unlink()
        self.assert_has_error("required package-governance file is missing or empty")

    def test_rejects_codex_adapter_drift(self) -> None:
        path = self.root / "AGENTS.md"
        path.write_text(
            path.read_text(encoding="utf-8") + "\n## Mirrored repository guidance\n",
            encoding="utf-8",
        )
        self.assert_has_error("Codex adapter must be the exact content-free authority pointer")

    def test_rejects_claude_carrier_codex_adapter_classification_drift(self) -> None:
        path = self.root / "CLAUDE.md"
        original = path.read_text(encoding="utf-8")
        changed = original.replace("tracked Codex adapter", "local Codex context", 1)
        self.assertNotEqual(original, changed)
        path.write_text(changed, encoding="utf-8")
        self.assert_has_error("Claude carrier must classify root AGENTS.md as the tracked Codex adapter")

    def test_rejects_canonical_orientation_codex_adapter_classification_drift(self) -> None:
        path = self.root / "docs/repository-orientation.md"
        original = path.read_text(encoding="utf-8")
        changed = original.replace("root `AGENTS.md` is the Codex adapter", "root `AGENTS.md` is local context", 1)
        self.assertNotEqual(original, changed)
        path.write_text(changed, encoding="utf-8")
        self.assert_has_error("canonical orientation must classify root AGENTS.md as the Codex adapter")

    def test_rejects_canonical_orientation_acceptance_order_drift(self) -> None:
        path = self.root / "docs/repository-orientation.md"
        original = path.read_text(encoding="utf-8")
        changed = original.replace(
            "cold acceptance against that commit before merge",
            "cold acceptance against that commit after merge",
            1,
        )
        self.assertNotEqual(original, changed)
        path.write_text(changed, encoding="utf-8")
        self.assert_has_error("canonical orientation must require acceptance before marketplace-branch merge")

    def test_rejects_missing_package_identity_carrier(self) -> None:
        carrier_paths = self.write_package_identity_carriers()
        carrier_paths[0].unlink()
        self.assert_has_error("package identity carrier is missing")

    def test_rejects_malformed_package_identity_carrier(self) -> None:
        carrier_paths = self.write_package_identity_carriers()
        carrier_paths[0].write_text("{not-json}\n", encoding="utf-8")
        self.assert_has_error("package identity carrier is not valid JSON")

    def test_rejects_stale_package_identity_version(self) -> None:
        carrier_paths = self.write_package_identity_carriers()
        payload = json.loads(carrier_paths[0].read_text(encoding="utf-8"))
        payload["manifest_version"] = "0.0.0"
        carrier_paths[0].write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("package identity carrier does not match the manifest authority")

    def test_rejects_stale_package_identity_digest(self) -> None:
        carrier_paths = self.write_package_identity_carriers()
        payload = json.loads(carrier_paths[0].read_text(encoding="utf-8"))
        payload["manifest_sha256"] = "0" * 64
        carrier_paths[0].write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("package identity carrier does not match the manifest authority")

    def test_rejects_divergent_package_identity_copy(self) -> None:
        carrier_paths = self.write_package_identity_carriers()
        carrier_paths[0].write_text(
            carrier_paths[0].read_text(encoding="utf-8").replace("  \"package\"", "    \"package\""),
            encoding="utf-8",
        )
        self.assert_has_error("package identity carriers must be byte-identical")

    def test_rejects_package_identity_contract_drift(self) -> None:
        mutations = {
            "package": "not-bedrock",
            "version_authority": "wrong#/version",
            "generator.id": "wrong-generator",
            "generator.version": "9.9.9",
            "contracts.claude_adapter": "9.9.9",
        }
        for field, replacement in mutations.items():
            with self.subTest(field=field):
                carrier_paths = self.write_package_identity_carriers()
                payload = json.loads(carrier_paths[0].read_text(encoding="utf-8"))
                target = payload
                parts = field.split(".")
                for part in parts[:-1]:
                    target = target[part]
                target[parts[-1]] = replacement
                carrier_paths[0].write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
                self.assert_has_error("package identity carrier does not match the manifest authority")

    def test_rejects_package_identity_extra_field(self) -> None:
        carrier_paths = self.write_package_identity_carriers()
        payload = json.loads(carrier_paths[0].read_text(encoding="utf-8"))
        payload["unexpected"] = True
        carrier_paths[0].write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("package identity carrier does not match the manifest authority")

    def test_rejects_nested_noncanonical_package_identity_carrier(self) -> None:
        carrier_paths = self.write_package_identity_carriers()
        extra = self.root / "plugins/bedrock/skills/agent-code/reference/PACKAGE_IDENTITY.json"
        extra.write_bytes(carrier_paths[0].read_bytes())
        expected = f"{extra}: package identity carrier is unexpected"

        self.assertIn(expected, synchronize(self.root, write=False))
        self.assertIn(expected, validate_package_governance(self.root))
        plugin_errors, _ = validate_repository(
            self.root,
            run_host_cli=False,
            run_safety_checks=False,
            validate_retained_evidence=False,
            require_authoring_contracts=False,
        )
        self.assertIn(expected, plugin_errors)

    def test_cli_entrypoints_report_same_unexpected_package_identity_carrier(self) -> None:
        carrier_paths = self.write_package_identity_carriers()
        extra = self.root / "plugins/bedrock/skills/stale/PACKAGE_IDENTITY.json"
        extra.parent.mkdir(parents=True)
        extra.write_bytes(carrier_paths[0].read_bytes())
        expected = f"{extra}: package identity carrier is unexpected"

        commands = (
            [sys.executable, "scripts/sync_package_identity.py", "--root", str(self.root), "--check"],
            [sys.executable, "scripts/validate_package_governance.py", "--root", str(self.root)],
        )
        for command in commands:
            with self.subTest(command=command[1]):
                result = subprocess.run(
                    command,
                    cwd=self.root,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(1, result.returncode, result.stdout + result.stderr)
                self.assertIn(expected, result.stdout)

    def test_rejects_every_package_identity_carrier_in_stale_skill_directories(self) -> None:
        carrier_paths = self.write_package_identity_carriers()
        extras = [
            self.root / "plugins/bedrock/skills/retired-one/PACKAGE_IDENTITY.json",
            self.root / "plugins/bedrock/skills/retired-two/nested/PACKAGE_IDENTITY.json",
        ]
        for extra in extras:
            extra.parent.mkdir(parents=True, exist_ok=True)
            extra.write_bytes(carrier_paths[0].read_bytes())

        sync_errors = synchronize(self.root, write=False)
        governance_errors = validate_package_governance(self.root)
        for extra in extras:
            expected = f"{extra}: package identity carrier is unexpected"
            self.assertIn(expected, sync_errors)
            self.assertIn(expected, governance_errors)

    def test_write_refuses_unexpected_package_identity_carrier_before_mutation(self) -> None:
        carrier_paths = self.write_package_identity_carriers()
        stale = carrier_paths[0]
        stale.write_text("stale\n", encoding="utf-8")
        extra = self.root / "plugins/bedrock/skills/stale/PACKAGE_IDENTITY.json"
        extra.parent.mkdir(parents=True)
        extra.write_bytes(carrier_paths[1].read_bytes())

        errors = synchronize(self.root, write=True)

        self.assertIn(f"{extra}: package identity carrier is unexpected", errors)
        self.assertEqual("stale\n", stale.read_text(encoding="utf-8"))
        self.assertTrue(extra.is_file())

    def test_release_mode_fails_closed_before_acceptance(self) -> None:
        errors = validate_package_governance(self.root, release=True)
        self.assertTrue(any("requires --release-evidence" in error for error in errors), errors)

    def write_release_fixture(
        self,
        *,
        decision_at: str = "2026-08-11T21:00:00Z",
        merged_at: str = "2026-08-11T21:05:00Z",
        landing_drift: bool = False,
        landing_scenario: str = "merge_main",
    ) -> tuple[Path, Path]:
        manifest_path = self.root / "plugins/bedrock/.claude-plugin/plugin.json"
        manifest_version = json.loads(manifest_path.read_text(encoding="utf-8"))["version"]
        release_tag = f"v{manifest_version}"
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Bedrock Test"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "maintenance.auto", "false"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "gc.auto", "0"], cwd=self.root, check=True)
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "base"], cwd=self.root, check=True)
        subprocess.run(["git", "switch", "-qc", "candidate"], cwd=self.root, check=True)
        (self.root / "candidate-marker.txt").write_text("accepted candidate\n", encoding="utf-8")
        subprocess.run(["git", "add", "candidate-marker.txt"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "candidate"], cwd=self.root, check=True)
        source_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.root, check=True, capture_output=True, text=True
        ).stdout.strip()
        subprocess.run(["git", "switch", "-q", "main"], cwd=self.root, check=True)
        if landing_drift:
            drift_path = self.root / "plugins/bedrock/governance/README.md"
            drift_path.write_text(drift_path.read_text(encoding="utf-8") + "\nlanding drift\n", encoding="utf-8")
            subprocess.run(["git", "add", str(drift_path)], cwd=self.root, check=True)
            subprocess.run(["git", "commit", "-qm", "change package during landing"], cwd=self.root, check=True)
        if landing_scenario == "merge_main":
            subprocess.run(
                ["git", "merge", "--no-ff", "-m", "land accepted candidate", "candidate"],
                cwd=self.root,
                check=True,
            )
            landing_method = "merge_commit"
            landing_commit = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=self.root, check=True, capture_output=True, text=True
            ).stdout.strip()
        elif landing_scenario == "merge_off_main":
            subprocess.run(["git", "switch", "-qc", "landing-side"], cwd=self.root, check=True)
            subprocess.run(
                ["git", "merge", "--no-ff", "-m", "land accepted candidate off main", "candidate"],
                cwd=self.root,
                check=True,
            )
            landing_method = "merge_commit"
            landing_commit = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=self.root, check=True, capture_output=True, text=True
            ).stdout.strip()
        elif landing_scenario == "fast_forward":
            subprocess.run(["git", "merge", "--ff-only", "candidate"], cwd=self.root, check=True)
            landing_method = "fast_forward"
            landing_commit = source_commit
        elif landing_scenario == "merge_main_mislabeled_fast_forward":
            subprocess.run(
                ["git", "merge", "--no-ff", "-m", "land accepted candidate", "candidate"],
                cwd=self.root,
                check=True,
            )
            landing_method = "fast_forward"
            landing_commit = source_commit
        elif landing_scenario == "folded_side_branch_mislabeled_fast_forward":
            subprocess.run(["git", "switch", "-qc", "landing-side"], cwd=self.root, check=True)
            subprocess.run(
                ["git", "merge", "--no-ff", "-m", "land accepted candidate off main", "candidate"],
                cwd=self.root,
                check=True,
            )
            subprocess.run(["git", "switch", "-q", "main"], cwd=self.root, check=True)
            drift_path = self.root / "plugins/bedrock/governance/README.md"
            drift_path.write_text(drift_path.read_text(encoding="utf-8") + "\nlanding drift\n", encoding="utf-8")
            subprocess.run(["git", "add", str(drift_path)], cwd=self.root, check=True)
            subprocess.run(["git", "commit", "-qm", "change package before folding side branch"], cwd=self.root, check=True)
            subprocess.run(
                ["git", "merge", "--no-ff", "-m", "fold landing side branch into main", "landing-side"],
                cwd=self.root,
                check=True,
            )
            landing_method = "fast_forward"
            landing_commit = source_commit
        elif landing_scenario == "swapped_parent_merge_mislabeled_fast_forward":
            subprocess.run(["git", "switch", "-q", "candidate"], cwd=self.root, check=True)
            subprocess.run(
                ["git", "merge", "--no-ff", "-m", "merge advanced main into candidate", "main"],
                cwd=self.root,
                check=True,
            )
            subprocess.run(["git", "switch", "-q", "main"], cwd=self.root, check=True)
            subprocess.run(["git", "merge", "--ff-only", "candidate"], cwd=self.root, check=True)
            landing_method = "fast_forward"
            landing_commit = source_commit
        elif landing_scenario == "merge_source_as_third_parent":
            subprocess.run(["git", "switch", "-qc", "alternate"], cwd=self.root, check=True)
            (self.root / "alternate-marker.txt").write_text("alternate candidate\n", encoding="utf-8")
            subprocess.run(["git", "add", "alternate-marker.txt"], cwd=self.root, check=True)
            subprocess.run(["git", "commit", "-qm", "alternate candidate"], cwd=self.root, check=True)
            subprocess.run(["git", "switch", "-q", "main"], cwd=self.root, check=True)
            subprocess.run(
                ["git", "merge", "--no-ff", "-m", "land octopus", "alternate", "candidate"],
                cwd=self.root,
                check=True,
            )
            landing_method = "merge_commit"
            landing_commit = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=self.root, check=True, capture_output=True, text=True
            ).stdout.strip()
        elif landing_scenario == "rebased_false_fast_forward":
            (self.root / "main-marker.txt").write_text("main advanced\n", encoding="utf-8")
            subprocess.run(["git", "add", "main-marker.txt"], cwd=self.root, check=True)
            subprocess.run(["git", "commit", "-qm", "advance main"], cwd=self.root, check=True)
            subprocess.run(["git", "switch", "-q", "candidate"], cwd=self.root, check=True)
            subprocess.run(["git", "rebase", "main"], cwd=self.root, check=True)
            subprocess.run(["git", "switch", "-q", "main"], cwd=self.root, check=True)
            subprocess.run(["git", "merge", "--ff-only", "candidate"], cwd=self.root, check=True)
            landing_method = "fast_forward"
            landing_commit = source_commit
        else:
            self.fail(f"unsupported landing scenario: {landing_scenario}")
        subprocess.run(
            ["git", "tag", "-am", "release", release_tag, source_commit],
            cwd=self.root,
            check=True,
        )
        manifest_digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        gate_ids = (
            "deterministic",
            "strict-host",
            "isolated-install",
            "routing",
            "review",
            "migration",
            "cold-acceptance",
            "github-release",
        )
        evidence = {
            "schema_version": 1,
            "manifest_version": manifest_version,
            "source_commit": source_commit,
            "manifest_sha256": manifest_digest,
            "findings": {"assigned": 39, "closed": 39, "evidence": ["HEB-118"]},
            "changed_surfaces": ["package-governance"],
            "migration": {"classification": "compatible", "rationale": "Additive", "notes": None},
            "gates": [{"id": gate_id, "status": "passed", "evidence": gate_id} for gate_id in gate_ids],
            "limitations": [],
            "decision": {
                "status": "proceed",
                "authority": "operator",
                "recorded_at": decision_at,
            },
            "landing": {
                "marketplace_branch": "main",
                "commit": landing_commit,
                "method": landing_method,
                "merged_at": merged_at,
                "evidence": "https://github.com/Haffey-Enterprises/bedrock/pull/1",
            },
        }
        rollout = {
            "schema_version": 1,
            "manifest_version": manifest_version,
            "release_tag": release_tag,
            "source_commit": source_commit,
            "surfaces": [
                {
                    "id": surface,
                    "expected_action": "verify",
                    "expected_identity": f"{manifest_version} and 15 skills",
                    "status": "verified",
                    "evidence": surface,
                    "owner": "operator",
                    "waiver": None,
                }
                for surface in ("claude-ai", "claude-code", "codex")
            ],
            "rollback": {"triggered": False, "last_accepted_tag": None, "evidence": None},
            "status": "complete",
        }
        evidence_path = self.root / "release-evidence.yaml"
        rollout_path = self.root / "rollout-ledger.yaml"
        evidence_path.write_text(yaml.safe_dump(evidence, sort_keys=False), encoding="utf-8")
        rollout_path.write_text(yaml.safe_dump(rollout, sort_keys=False), encoding="utf-8")
        return evidence_path, rollout_path

    def test_release_mode_accepts_external_evidence_after_immutable_tag(self) -> None:
        evidence_path, rollout_path = self.write_release_fixture()
        self.assertEqual(
            [],
            validate_package_governance(
                self.root,
                release=True,
                release_evidence=evidence_path,
                rollout_ledger=rollout_path,
            ),
        )

    def test_rollout_rejects_inexact_surface_populations(self) -> None:
        evidence_path, rollout_path = self.write_release_fixture()
        def validate() -> list[str]:
            return validate_package_governance(
                self.root, release=True, release_evidence=evidence_path,
                rollout_ledger=rollout_path,
            )
        self.assertEqual([], validate())
        original = rollout_path.read_bytes()
        rollout = yaml.safe_load(original)
        rows = rollout["surfaces"]
        expected = {"claude-ai", "claude-code", "codex"}
        self.assertEqual(expected, {row["id"] for row in rows})
        cases = {
            **{f"missing-{name}": [row for row in rows if row["id"] != name]
               for name in expected},
            **{f"duplicate-{name}": rows + [next(row for row in rows if row["id"] == name)]
               for name in expected},
            "unknown": rows + [dict(rows[0], id="unknown-host")],
            "stale-two-surface": [row for row in rows if row["id"] != "codex"],
            "duplicate-replaces-missing": [rows[0], rows[1], rows[1]],
            "unknown-replaces-codex": [dict(row, id="unknown-host") if row["id"] == "codex" else row for row in rows],
        }
        for label, population in cases.items():
            with self.subTest(case=label):
                rollout["surfaces"] = population
                rollout_path.write_text(yaml.safe_dump(rollout, sort_keys=False), encoding="utf-8")
                errors = validate()
                self.assertTrue(any(
                    "rollout must enumerate claude-ai, claude-code, and codex exactly once" in error
                    for error in errors
                ), errors)
        rollout_path.write_bytes(original)
        self.assertEqual([], validate())

    def test_release_mode_rejects_landing_before_acceptance(self) -> None:
        evidence_path, rollout_path = self.write_release_fixture(
            decision_at="2026-08-11T21:10:00Z",
            merged_at="2026-08-11T21:05:00Z",
        )
        errors = validate_package_governance(
            self.root,
            release=True,
            release_evidence=evidence_path,
            rollout_ledger=rollout_path,
        )
        self.assertTrue(
            any("cold-acceptance proceed decision must precede landing" in error for error in errors),
            errors,
        )

    def test_release_mode_rejects_distribution_drift_during_landing(self) -> None:
        evidence_path, rollout_path = self.write_release_fixture(landing_drift=True)
        errors = validate_package_governance(
            self.root,
            release=True,
            release_evidence=evidence_path,
            rollout_ledger=rollout_path,
        )
        self.assertTrue(
            any("landing changed marketplace or installed package bytes after acceptance" in error for error in errors),
            errors,
        )

    def test_release_mode_rejects_landing_not_reachable_from_main(self) -> None:
        evidence_path, rollout_path = self.write_release_fixture(landing_scenario="merge_off_main")
        errors = validate_package_governance(
            self.root,
            release=True,
            release_evidence=evidence_path,
            rollout_ledger=rollout_path,
        )
        self.assertTrue(
            any("landing commit must be reachable from marketplace branch main" in error for error in errors),
            errors,
        )

    def test_release_mode_rejects_rebased_candidate_claimed_as_fast_forward(self) -> None:
        evidence_path, rollout_path = self.write_release_fixture(
            landing_scenario="rebased_false_fast_forward"
        )
        errors = validate_package_governance(
            self.root,
            release=True,
            release_evidence=evidence_path,
            rollout_ledger=rollout_path,
        )
        self.assertTrue(
            any("release permits merge_commit landing only" in error for error in errors),
            errors,
        )

    def test_release_mode_rejects_true_fast_forward_landing(self) -> None:
        evidence_path, rollout_path = self.write_release_fixture(landing_scenario="fast_forward")
        errors = validate_package_governance(
            self.root,
            release=True,
            release_evidence=evidence_path,
            rollout_ledger=rollout_path,
        )
        self.assertTrue(
            any("release permits merge_commit landing only" in error for error in errors),
            errors,
        )

    def test_release_mode_rejects_merge_mislabeled_as_fast_forward(self) -> None:
        evidence_path, rollout_path = self.write_release_fixture(
            landing_drift=True,
            landing_scenario="merge_main_mislabeled_fast_forward",
        )
        errors = validate_package_governance(
            self.root,
            release=True,
            release_evidence=evidence_path,
            rollout_ledger=rollout_path,
        )
        self.assertTrue(
            any("release permits merge_commit landing only" in error for error in errors),
            errors,
        )

    def test_release_mode_rejects_side_branch_fold_mislabeled_as_fast_forward(self) -> None:
        evidence_path, rollout_path = self.write_release_fixture(
            landing_scenario="folded_side_branch_mislabeled_fast_forward"
        )
        errors = validate_package_governance(
            self.root,
            release=True,
            release_evidence=evidence_path,
            rollout_ledger=rollout_path,
        )
        self.assertTrue(
            any("release permits merge_commit landing only" in error for error in errors),
            errors,
        )

    def test_release_mode_rejects_swapped_parent_merge_mislabeled_as_fast_forward(self) -> None:
        evidence_path, rollout_path = self.write_release_fixture(
            landing_drift=True,
            landing_scenario="swapped_parent_merge_mislabeled_fast_forward",
        )
        errors = validate_package_governance(
            self.root,
            release=True,
            release_evidence=evidence_path,
            rollout_ledger=rollout_path,
        )
        self.assertTrue(
            any("release permits merge_commit landing only" in error for error in errors),
            errors,
        )

    def test_release_mode_rejects_merge_with_source_as_third_parent(self) -> None:
        evidence_path, rollout_path = self.write_release_fixture(
            landing_scenario="merge_source_as_third_parent"
        )
        errors = validate_package_governance(
            self.root,
            release=True,
            release_evidence=evidence_path,
            rollout_ledger=rollout_path,
        )
        self.assertTrue(
            any(
                "merge landing must preserve the accepted source commit as its second parent" in error
                for error in errors
            ),
            errors,
        )

    def test_release_mode_rejects_timezone_naive_landing_timestamp(self) -> None:
        evidence_path, rollout_path = self.write_release_fixture(
            merged_at="2026-08-11T21:05:00"
        )
        errors = validate_package_governance(
            self.root,
            release=True,
            release_evidence=evidence_path,
            rollout_ledger=rollout_path,
        )
        self.assertTrue(
            any("decision and landing timestamps must be valid timezone-aware date-times" in error for error in errors),
            errors,
        )

    def test_release_mode_rejects_malformed_decision_record_cleanly(self) -> None:
        evidence_path, rollout_path = self.write_release_fixture()
        evidence = yaml.safe_load(evidence_path.read_text(encoding="utf-8"))
        evidence["decision"] = "malformed"
        evidence_path.write_text(yaml.safe_dump(evidence, sort_keys=False), encoding="utf-8")

        errors = validate_package_governance(
            self.root,
            release=True,
            release_evidence=evidence_path,
            rollout_ledger=rollout_path,
        )

        self.assertTrue(
            any("release requires a valid decision record" in error for error in errors),
            errors,
        )

    def test_seeded_governance_defect_manifest_names_existing_tests(self) -> None:
        payload = yaml.safe_load(
            (self.root / "tests/fixtures/package-governance/manifest.yaml").read_text(encoding="utf-8")
        )
        declared = {row["test"] for row in payload["defects"]}
        available = {name for name in dir(type(self)) if name.startswith("test_")}
        self.assertEqual(set(), declared - available)


if __name__ == "__main__":
    unittest.main()
