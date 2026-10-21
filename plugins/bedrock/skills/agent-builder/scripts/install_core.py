#!/usr/bin/env python3
"""Install/check Bedrock's bundled core in an explicitly selected project venv."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

ASSETS = Path(__file__).resolve().parents[1] / 'assets/python'

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load_component(assets: Path) -> dict:
    component = json.loads((assets / 'component.json').read_text())
    wheel = component['wheel']
    if Path(wheel).name != wheel or not wheel.endswith('.whl'):
        raise ValueError('invalid bundled wheel path')
    if sha(assets / wheel) != component['wheel_sha256']:
        raise ValueError('bundled core wheel digest mismatch')
    if sha(assets / 'requirements-lock.txt') != component['requirements_sha256']:
        raise ValueError('bundled dependency lock digest mismatch')
    return component

# Executed by the target interpreter with -I: neither cwd nor PYTHONPATH can
# substitute a source checkout for the installed distribution.
PROBE = r'''
import hashlib, importlib.metadata as md, json, pathlib, sys
if sys.prefix == sys.base_prefix:
    raise SystemExit('target must be a project virtual environment')
import agent_core
component=json.loads(sys.stdin.read())
dist=md.distribution('agent-core')
if dist.version != component['version'] or agent_core.CORE_VERSION != component['version']:
    raise SystemExit('installed core version mismatch')
for name, expected in component['source_files'].items():
    path=pathlib.Path(dist.locate_file(name)).resolve()
    if not path.is_relative_to(pathlib.Path(sys.prefix).resolve()):
        raise SystemExit('core resolves outside target virtual environment')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
        raise SystemExit('installed core source digest mismatch: '+name)
expected_init=pathlib.Path(dist.locate_file('agent_core/__init__.py')).resolve()
if pathlib.Path(agent_core.__file__).resolve()!=expected_init:
    raise SystemExit('wrong core import subject')
schema={'type':'object','properties':{'ok':{'const':True}},'required':['ok'],'additionalProperties':False}
assert agent_core.parse_structured('{"ok":true}',schema).data == {'ok':True}
try:
    agent_core.parse_structured('{"ok":true,"ok":false}',schema)
except agent_core.StructuredOutputError:
    pass
else:
    raise SystemExit('duplicate-key rejection did not execute')
budget=agent_core.Budget(max_model_attempts=1,max_tool_iterations=1)
budget.record_model_attempt(tokens=1,spend=0.001)
budget.check('tool')
try:
    budget.check('model')
except agent_core.BudgetExhausted:
    pass
else:
    raise SystemExit('model attempt ceiling did not execute')
print(json.dumps({'python':sys.version.split()[0],'executable':sys.executable,'import_path':str(expected_init),'core_version':agent_core.CORE_VERSION,'dependencies':{name:md.version(name) for name in ('agent-core','attrs','jsonschema','jsonschema-specifications','referencing','rpds-py','typing-extensions')}}))
'''

def check(python: str, component: dict) -> dict:
    result = subprocess.run([python, '-I', '-c', PROBE], input=json.dumps(component), text=True, capture_output=True)
    if result.returncode:
        raise ValueError("installed core verification failed: " + result.stderr.strip())
    return json.loads(result.stdout)

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', required=True, help='Target project virtualenv interpreter')
    parser.add_argument('--check', action='store_true', help='Verify without installing')
    parser.add_argument('--bedrock-revision', help='Full immutable source commit for the project dependency record')
    parser.add_argument('--record', type=Path, help='Write a dependency record only after successful install and checks')
    args = parser.parse_args()
    if args.record and (not args.bedrock_revision or not re.fullmatch('[0-9a-f]{40}', args.bedrock_revision)):
        parser.error('--record requires --bedrock-revision as a full commit SHA')
    if args.record and args.record.exists():
        parser.error('dependency record already exists; review the project upgrade before replacing it')
    component = load_component(ASSETS)
    subprocess.run([args.python,'-I','-c',"import sys; assert sys.prefix != sys.base_prefix, 'target must be a project virtual environment'"], check=True)
    if not args.check:
        with tempfile.TemporaryDirectory(prefix='bedrock-core-install-') as temporary:
            requirements=Path(temporary)/'requirements.txt'
            requirements.write_text((ASSETS/'requirements-lock.txt').read_text()+'\n'+(ASSETS/component['wheel']).as_uri()+' --hash=sha256:'+component['wheel_sha256']+'\n')
            subprocess.run([args.python,'-I','-m','pip','install','--require-hashes','--only-binary=:all:','-r',str(requirements)],check=True)
    subprocess.run([args.python,'-I','-m','pip','check'],check=True)
    observed=check(args.python,component)
    # A version match alone is insufficient; require the qualified dependency pins.
    for line in (ASSETS/'requirements-lock.txt').read_text().splitlines():
        if not line or line.startswith('#'):
            continue
        name,version=line.split()[0].split('==')
        if observed['dependencies'][name]!=version:
            raise ValueError('installed dependency differs from qualified lock: '+name)
    record={'schema_version':1,'repository':'https://github.com/Haffey-Enterprises/bedrock','bedrock_revision':args.bedrock_revision,'component':component['distribution'],'component_version':component['version'],'wheel':component['wheel'],'wheel_sha256':component['wheel_sha256'],'requirements_sha256':component['requirements_sha256'],'observed':observed}
    if args.record:
        args.record.parent.mkdir(parents=True,exist_ok=True)
        with args.record.open('x') as output:
            output.write(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
