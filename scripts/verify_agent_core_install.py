#!/usr/bin/env python3
"""Exercise the distributed skill in a clean venv with contrary identity controls."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import venv

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-dir',type=Path,required=True)
    args=parser.parse_args()
    evidence=args.evidence_dir.resolve()
    evidence.mkdir(parents=True,exist_ok=False)
    # Only distributed skill bytes enter this installation fixture.
    skill=evidence/'agent-builder'
    shutil.copytree(ROOT/'plugins/bedrock/skills/agent-builder',skill)
    env=evidence/'venv'
    venv.EnvBuilder(with_pip=True, symlinks=sys.platform != "win32").create(env)
    python=str(env/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python'))
    installer=skill/'scripts/install_core.py'
    command=[sys.executable,str(installer),'--python',python]
    results=[]
    def run(name,cmd,expected,marker=None):
        result=subprocess.run(cmd,capture_output=True,text=True)
        output=result.stdout+result.stderr
        (evidence/(name+'.txt')).write_text(output)
        passed=(result.returncode==0) if expected=='pass' else (result.returncode!=0 and (marker is None or marker in output))
        results.append({'name':name,'command':cmd,'returncode':result.returncode,'expected':expected,'passed':passed,'log':name+'.txt'})
        (evidence/'results.json').write_text(json.dumps(results,indent=2)+'\n')
        if not passed:
            raise RuntimeError(f'{name}: unexpected outcome; see {evidence/(name+".txt")}')
        return output
    run('missing-install',command+['--check'],'reject','No module named')
    run('clean-install',command,'pass')
    run('reload',command+['--check'],'pass')
    location=subprocess.check_output([python,'-I','-c','import agent_core; print(agent_core.__file__)'],text=True).strip()
    installed=Path(location)
    original=installed.read_bytes()
    installed.write_bytes(original+b'\n# contrary subject for installed-byte discrimination\n')
    try:
        run('wrong-installed-core',command+['--check'],'reject','installed core source digest mismatch')
    finally:
        installed.write_bytes(original)
    run('restored-install',command+['--check'],'pass')
    component=json.loads((skill/'assets/python/component.json').read_text())
    wheel=skill/'assets/python'/component['wheel'];original=wheel.read_bytes()
    wheel.write_bytes(original+b'wrong-wheel')
    try:
        run('wrong-bundled-wheel',command,'reject','bundled core wheel digest mismatch')
    finally:
        wheel.write_bytes(original)
    results.append({'name':'subject','python':sys.version,'component':component,'installer_sha256':hashlib.sha256(installer.read_bytes()).hexdigest()})
    (evidence/'results.json').write_text(json.dumps(results,indent=2)+'\n')
    print('PASS: clean skill-only install/reload, absent install, wrong installed core, and wrong bundled wheel controls')
    print(evidence/'results.json')

if __name__=='__main__':
    main()
