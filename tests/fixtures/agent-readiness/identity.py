"""Verify the installed integrated core before the offline SDK binding is exercised."""
import bootstrap
import hashlib, importlib.metadata as md, json
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def verify_binding():
    component=json.loads((ROOT.parents[2]/'plugins/bedrock/skills/agent-builder/assets/python/component.json').read_text())
    dist=md.distribution('agent-core')
    if dist.version!=component['version'] or md.version('anthropic')!='1.8.0':
        raise RuntimeError('dependency_version_mismatch')
    for name,wanted in component['source_files'].items():
        if hashlib.sha256(Path(dist.locate_file(name)).read_bytes()).hexdigest()!=wanted:
            raise RuntimeError('installed_core_hash_mismatch')
    return component
