#!/usr/bin/env python3
"""Build or verify the source-derived wheel shipped with agent-builder."""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata as metadata
import yaml
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = Path('plugins/bedrock/skills/agent-builder/assets/python')

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def validate_declarations(root: Path) -> None:
    plugin = root / 'plugins/bedrock'
    registry = yaml.safe_load((plugin / 'governance/registry.yaml').read_text())
    dependency = json.loads((plugin / 'skills/agent-builder/reference/dependencies.json').read_text())
    contracts = {row['name']: row['contract_version'] for row in registry['skills']}
    sibling = dependency['sibling']
    if contracts.get(sibling['skill']) != sibling['contract_version']:
        raise ValueError('sibling skill contract differs from dependency declaration')
    builder_identity = (plugin / 'skills/agent-builder/PACKAGE_IDENTITY.json').read_bytes()
    if builder_identity != (plugin / 'skills'/sibling['skill']/'PACKAGE_IDENTITY.json').read_bytes():
        raise ValueError('sibling skill package identity differs')
    component = json.loads((plugin / 'skills/agent-builder/assets/python/component.json').read_text())
    if component['version'] != dependency['python_core']['version']:
        raise ValueError('core dependency version differs from bundled component')
    shared = next(row for row in registry['shared_components'] if row['id'] == 'agent-core')
    if shared['version'] != component['version'] or shared['license'] != 'MIT':
        raise ValueError('shared component registry differs from distribution')
    schema = json.loads((plugin / 'skills/agent-code/reference/agent-execution.schema.json').read_text())
    if schema['properties']['schema_version']['const'] != dependency['portable_evidence_version']:
        raise ValueError('portable evidence version differs from dependency declaration')

def build(root: Path, *, check: bool) -> None:
    validate_declarations(root)
    package = root / 'packages/agent-core'
    assets = root / ASSETS
    for requirement in (package / 'build-requirements.txt').read_text().splitlines():
        if requirement and not requirement.startswith('#'):
            name, version = requirement.split('==')
            if metadata.version(name) != version:
                raise ValueError('unqualified wheel build tool: ' + name)
    with tempfile.TemporaryDirectory(prefix='bedrock-core-build-') as temporary:
        temp = Path(temporary)
        shutil.copytree(package, temp / 'source', ignore=shutil.ignore_patterns('__pycache__', '*.egg-info', 'build', '.pytest_cache'))
        env = dict(os.environ, SOURCE_DATE_EPOCH='315532800')
        subprocess.run([sys.executable, '-m', 'pip', 'wheel', '--no-deps', '--no-build-isolation', '--wheel-dir', str(temp / 'wheels'), str(temp / 'source')], env=env, check=True)
        wheels = list((temp / 'wheels').glob('*.whl'))
        if len(wheels) != 1:
            raise ValueError('expected exactly one core wheel')
        wheel = wheels[0]
        with zipfile.ZipFile(wheel) as archive:
            members = {name: digest(archive.read(name)) for name in archive.namelist()}
        source = {str(p.relative_to(package / 'src')): digest(p.read_bytes()) for p in sorted((package / 'src/agent_core').rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
        if {k:v for k,v in members.items() if k.startswith('agent_core/')} != source:
            raise ValueError('wheel runtime differs from authoritative source')
        if any(not (name.startswith('agent_core/') or name.startswith('agent_core-0.2.0.dist-info/')) for name in members):
            raise ValueError('unexpected wheel payload')
        if package.joinpath('LICENSE').read_bytes() != root.joinpath('LICENSE').read_bytes():
            raise ValueError('core license must be Bedrock license')
        payload = {'schema_version':1, 'distribution':'agent-core', 'version':'0.2.0', 'wheel':wheel.name, 'wheel_sha256':digest(wheel.read_bytes()), 'source_files':source, 'wheel_files':members, 'requirements_sha256':digest((package/'requirements-lock.txt').read_bytes()), 'build_requirements_sha256':digest((package/'build-requirements.txt').read_bytes())}
        manifest = (json.dumps(payload, indent=2, sort_keys=True)+'\n').encode()
        expected = {wheel.name:wheel.read_bytes(), 'component.json':manifest, 'requirements-lock.txt':(package/'requirements-lock.txt').read_bytes()}
        if check:
            if {p.name for p in assets.iterdir() if p.is_file()} != set(expected):
                raise ValueError('bundled core asset population differs')
            for name,data in expected.items():
                if (assets/name).read_bytes()!=data:
                    raise ValueError(f'stale bundled asset: {name}')
        else:
            assets.mkdir(parents=True, exist_ok=True)
            extra = {p.name for p in assets.iterdir() if p.is_file()} - set(expected)
            if extra:
                raise ValueError(f'refusing to replace unexpected assets: {sorted(extra)}')
            for name,data in expected.items():
                (assets/name).write_bytes(data)
        print('PASS: source, wheel payload, license and bundled dependency identity agree')

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--check', action='store_true')
    args=parser.parse_args()
    build(args.root.resolve(), check=args.check)
