"""Deterministic regression tests for the HEB-110 safety overlay."""

from __future__ import annotations

import re
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_safety import route_safety_case, validate_safety_contracts


class SafetyContractTests(unittest.TestCase):
    def test_repository_satisfies_safety_contracts(self) -> None:
        # Arrange
        repository_root = Path(__file__).resolve().parents[1]

        # Act
        errors = validate_safety_contracts(repository_root)

        # Assert
        self.assertEqual([], errors)

    def test_cosmetic_finding_never_blocks_convergence(self) -> None:
        # Arrange
        case = {
            "severity": "COSMETIC",
            "classification": "resolvable",
            "status": "open",
        }

        # Act
        result = route_safety_case(case)

        # Assert
        self.assertEqual("CONVERGED", result)

    def test_cosmetic_decision_bearing_combination_is_invalid(self) -> None:
        # Arrange
        case = {
            "severity": "COSMETIC",
            "classification": "decision-bearing",
            "status": "open",
        }

        # Act
        result = route_safety_case(case)

        # Assert
        self.assertEqual("INVALID", result)

    def test_material_decision_bearing_finding_halts(self) -> None:
        # Arrange
        case = {
            "severity": "MATERIAL",
            "classification": "decision-bearing",
            "status": "open",
        }

        # Act
        result = route_safety_case(case)

        # Assert
        self.assertEqual("HALT_DECISION", result)


class SafetyValidatorNegativeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        repository_root = Path(__file__).resolve().parents[1]
        skills_source = repository_root / "plugins" / "bedrock" / "skills"
        fixtures_source = repository_root / "tests" / "fixtures" / "safety"
        shutil.copytree(skills_source, self.root / "plugins" / "bedrock" / "skills")
        shutil.copytree(fixtures_source, self.root / "tests" / "fixtures" / "safety")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def assert_has_error(self, needle: str) -> None:
        # Act
        errors = validate_safety_contracts(self.root)

        # Assert
        self.assertTrue(any(needle in error for error in errors), errors)

    def test_unpinned_action_reference_fails(self) -> None:
        # Arrange
        path = (
            self.root
            / "plugins/bedrock/skills/infrastructure-code/reference/05-delivery-pipeline.md"
        )
        text = path.read_text(encoding="utf-8")
        path.write_text(
            re.sub(
                r"(uses:\s*hashicorp/setup-terraform@)[0-9a-f]{40}",
                r"\1v3",
                text,
                count=1,
            ),
            encoding="utf-8",
        )

        self.assert_has_error("must use a full commit SHA")

    def test_unnamed_unpinned_action_reference_fails(self) -> None:
        path = self.root / "tests/fixtures/safety/pr-image-build.yml"
        path.write_text(path.read_text() + "\n      - uses: actions/setup-python@v5\n")
        self.assert_has_error("must use a full commit SHA")

    def test_maintained_actions_require_verified_node24_identities(self) -> None:
        cases = (
            (
                "plugins/bedrock/skills/infrastructure-code/reference/05-delivery-pipeline.md",
                "hashicorp/setup-terraform",
                "dfe3c3f87815947d99a8997f908cb6525fc44e9e",
                "b9cd54a3c349d3f38e8881555d616ced269862dd",
            ),
            (
                "tests/fixtures/safety/pr-image-build.yml",
                "actions/checkout",
                "fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09",
                "11d5960a326750d5838078e36cf38b85af677262",
            ),
        )
        for relative, action, current, old in cases:
            with self.subTest(surface=relative):
                path = self.root / relative
                original = path.read_text()
                # The maintained bytes themselves must use the verified identity.
                self.assertIn(f"uses: {action}@{current}", original)
                for identity in (old, "0" * 40):
                    with self.subTest(identity=identity):
                        path.write_text(original.replace(current, identity))
                        self.assert_has_error("must use the verified Node 24 action identity")
                # Removal cannot turn the runtime gate into a vacuous pass.
                path.write_text(original.replace(f"uses: {action}@{current}", "run: true"))
                self.assert_has_error("must use the verified Node 24 action identity")
                path.write_text(original)
        self.assertEqual([], validate_safety_contracts(self.root))

    def test_old_runtime_cannot_hide_in_yaml_syntax(self) -> None:
        cases = (
            (
                "tests/fixtures/safety/pr-image-build.yml",
                "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
            ),
            (
                "plugins/bedrock/skills/infrastructure-code/reference/05-delivery-pipeline.md",
                "hashicorp/setup-terraform@b9cd54a3c349d3f38e8881555d616ced269862dd",
            ),
        )
        for relative, old in cases:
            path = self.root / relative
            original = path.read_text()
            for step in (
                '- {uses: "' + old + '"}',
                '- "uses": "' + old + '"',
                '- uses: ' + old.upper(),
                '- &old {uses: "' + old + '"}\n- *old',
                '- uses: >-\n    ' + old,
            ):
                with self.subTest(surface=relative, step=step):
                    if path.suffix == ".md":
                        extra = "\n```yaml\n" + step + "\n```\n"
                    else:
                        extra = "\n" + "\n".join("      " + line for line in step.splitlines()) + "\n"
                    path.write_text(original + extra)
                    self.assert_has_error("must use the verified Node 24 action identity")
            path.write_text(original)

    def test_unpinned_flow_action_fails(self) -> None:
        path = self.root / "tests/fixtures/safety/pr-image-build.yml"
        path.write_text(path.read_text() + '\n      - {uses: "actions/setup-python@v5"}\n')
        self.assert_has_error("must use a full commit SHA")

    def test_yaml_current_identity_alias_and_cycle_are_safe(self) -> None:
        path = self.root / "tests/fixtures/safety/pr-image-build.yml"
        current = "actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09"
        path.write_text(path.read_text() + (
            '\n      - &good {"uses": "' + current + '"}\n      - *good\n'
            '\nsynthetic-cycle: &cycle [*cycle]\n'
        ))
        self.assertEqual([], validate_safety_contracts(self.root))

    def test_missing_action_ref_and_malformed_yaml_fail(self) -> None:
        path = self.root / "tests/fixtures/safety/pr-image-build.yml"
        original = path.read_text()
        path.write_text(original + "\n      - uses: actions/setup-python\n")
        self.assert_has_error("must use a full commit SHA")
        path.write_text(original + "\n      - uses: [\n")
        self.assert_has_error("cannot inspect Action references: invalid YAML")

    def test_duplicate_action_key_cannot_discard_old_identity(self) -> None:
        path = self.root / "tests/fixtures/safety/pr-image-build.yml"
        path.write_text(path.read_text() + (
            "\n      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262\n"
            "        uses: actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09\n"
        ))
        self.assert_has_error("duplicate YAML key 'uses'")

    def test_python_minor_site_packages_path_fails(self) -> None:
        # Arrange
        path = (
            self.root
            / "plugins/bedrock/skills/application-code/reference/01-code-structure.md"
        )
        text = path.read_text(encoding="utf-8")
        path.write_text(
            text.replace(
                "COPY --from=builder /opt/venv /opt/venv",
                "COPY --from=builder /usr/local/lib/python3.11/site-packages "
                "/usr/local/lib/python3.11/site-packages",
            ),
            encoding="utf-8",
        )

        self.assert_has_error("/usr/local/lib/python3.11/site-packages")

    def test_secret_state_denial_fails(self) -> None:
        # Arrange
        path = self.root / "plugins/bedrock/skills/infrastructure-code/SKILL.md"
        text = path.read_text(encoding="utf-8")
        path.write_text(text + "\nNo secrets in configuration or state.\n", encoding="utf-8")

        self.assert_has_error("No secrets in configuration or state")

    def test_pull_request_push_fails(self) -> None:
        # Arrange
        path = self.root / "tests/fixtures/safety/pr-image-build.yml"
        text = path.read_text(encoding="utf-8")
        path.write_text(text + "\n      - run: docker push example/image\n", encoding="utf-8")

        self.assert_has_error("docker push")

    def test_malformed_workflow_events_fail_cleanly(self) -> None:
        # Arrange
        path = self.root / "tests/fixtures/safety/pr-image-build.yml"
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace('"on":\n  pull_request:', '"on":'), encoding="utf-8")

        self.assert_has_error("must run for pull_request events")

    def test_non_string_manifest_identifier_fails_cleanly(self) -> None:
        # Arrange
        path = self.root / "tests/fixtures/safety/manifest.yaml"
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("- id: APP-002", "- id: [APP-002]"), encoding="utf-8")

        self.assert_has_error("id must be a string")

    def test_cosmetic_decision_halt_guidance_fails(self) -> None:
        # Arrange
        path = self.root / "plugins/bedrock/skills/design-review-loop/SKILL.md"
        text = path.read_text(encoding="utf-8")
        path.write_text(text + "\nA decision halts, even a COSMETIC one.\n", encoding="utf-8")

        self.assert_has_error("even a COSMETIC one")


if __name__ == "__main__":
    unittest.main()
