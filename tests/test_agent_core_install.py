"""Fast checks of bundled component identity; clean installs run separately."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from scripts.build_agent_core import validate_declarations
ROOT=Path(__file__).resolve().parents[1]
SKILL=ROOT/'plugins/bedrock/skills/agent-builder'
spec=importlib.util.spec_from_file_location('core_installer',SKILL/'scripts/install_core.py')
installer=importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)

class CoreIdentityTests(unittest.TestCase):
    def test_current_bundle(self):
        self.assertEqual('0.2.0',installer.load_component(SKILL/'assets/python')['version'])

    def test_changed_wheel_and_lock_are_rejected(self):
        for kind in ('wheel','requirements-lock.txt'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as directory:
                assets=Path(directory)/'python'
                shutil.copytree(SKILL/'assets/python',assets)
                component=json.loads((assets/'component.json').read_text())
                target=assets/(component['wheel'] if kind=='wheel' else kind)
                target.write_bytes(target.read_bytes()+b'corrupt')
                with self.assertRaisesRegex(ValueError,'digest mismatch'):
                    installer.load_component(assets)

    def test_manifest_cannot_escape_asset_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            assets=Path(directory)
            (assets/'component.json').write_text(json.dumps({'wheel':'../outside.whl'}))
            with self.assertRaisesRegex(ValueError,'invalid bundled wheel path'):
                installer.load_component(assets)

    def test_sibling_dependency_drift_is_rejected(self):
        validate_declarations(ROOT)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            shutil.copytree(ROOT/'plugins',root/'plugins',ignore=shutil.ignore_patterns('__pycache__'))
            path=root/'plugins/bedrock/skills/agent-builder/reference/dependencies.json'
            dependency=json.loads(path.read_text())
            dependency['sibling']['contract_version']='999.0.0'
            path.write_text(json.dumps(dependency))
            with self.assertRaisesRegex(ValueError,'sibling skill contract differs'):
                validate_declarations(root)
