#!/usr/bin/env python3
"""Manage one explicit Bedrock data-hygiene runtime or repository; Python 3.11+."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid

SOURCE_PATH = 'plugins/bedrock/scripts/data-hygiene/pre-commit'
MANIFEST_PATH = 'plugins/bedrock/.claude-plugin/plugin.json'
DIGEST = re.compile(r'[0-9a-f]{64}')
COMMIT = re.compile(r'[0-9a-f]{40}(?:[0-9a-f]{24})?')
VERSION = re.compile(r'[0-9]+\.[0-9]+\.[0-9]+')
REPOSITORY = re.compile(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+')


class Refusal(Exception):
    """Neutral public operational failure; never carries private inputs."""


def require(condition):
    if not condition:
        raise Refusal()


def run(args, *, cwd=None, absent=False):
    result = subprocess.run([str(arg) for arg in args], cwd=cwd, stdin=subprocess.DEVNULL,
                            capture_output=True, timeout=60)
    if absent and result.returncode == 1:
        return None
    require(result.returncode == 0)
    return result.stdout


def git(repo, *args, absent=False):
    return run(['git', '-C', repo, *args], absent=absent)


def text(data):
    return data.decode('utf-8').strip()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def object_json(data):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value)
            value[key] = item
        return value
    value = json.loads(data, object_pairs_hook=unique)
    require(isinstance(value, dict))
    return value


def regular(path, *, mode=None):
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid())
    if mode is not None:
        require(stat.S_IMODE(info.st_mode) == mode)
    require(os.access(path, os.R_OK))
    return info


def directory(path):
    info = path.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
            and not info.st_mode & 0o022)


def runtime_path(value, *, create=False):
    root = Path(value)
    require(root.is_absolute() and '\n' not in str(root) and '\r' not in str(root))
    root = root.resolve() / 'data-hygiene'
    if create:
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory(root)
    versions = root / 'versions'
    if create:
        versions.mkdir(mode=0o700, exist_ok=True)
    directory(versions)
    return root


def source_identity(repo, tag, github_repo):
    require(REPOSITORY.fullmatch(github_repo) is not None)
    require(tag.startswith('v') and VERSION.fullmatch(tag[1:]) is not None)
    ref = 'refs/tags/' + tag
    require(text(git(repo, 'cat-file', '-t', ref)) == 'tag')
    tag_oid = text(git(repo, 'rev-parse', '--verify', ref))
    commit = text(git(repo, 'rev-parse', '--verify', ref + '^{commit}'))
    require(COMMIT.fullmatch(commit) is not None)
    origin = text(git(repo, 'config', '--get', 'remote.origin.url'))
    require(origin in {'https://github.com/' + github_repo,
                       'https://github.com/' + github_repo + '.git',
                       'git@github.com:' + github_repo + '.git'})
    manifest = object_json(git(repo, 'cat-file', 'blob', commit + ':' + MANIFEST_PATH))
    require(manifest.get('name') == 'bedrock' and manifest.get('version') == tag[1:])
    require(manifest.get('repository') == 'https://github.com/' + github_repo)
    entry = git(repo, 'ls-tree', commit, '--', SOURCE_PATH)
    require(entry.startswith(b'100755 blob '))
    payload = git(repo, 'cat-file', 'blob', commit + ':' + SOURCE_PATH)
    require(payload.startswith(b'#!/usr/bin/env bash\n'))
    receipt = {'schema_version': 1, 'package_version': tag[1:], 'source_commit': commit,
               'source_tag': tag, 'source_tag_object': tag_oid, 'github_repository': github_repo,
               'source_path': SOURCE_PATH, 'source_sha256': digest(payload),
               'deployed_sha256': digest(payload),
               'release_url': 'https://github.com/' + github_repo + '/releases/tag/' + tag,
               'acceptance_boundary': 'Cold acceptance and explicit proceed are external lifecycle evidence.'}
    return payload, receipt


def release_check(receipt):
    repo, tag = receipt['github_repository'], receipt['source_tag']
    release = object_json(run(['gh', 'api', 'repos/' + repo + '/releases/tags/' + tag]))
    require(release.get('draft') is False and release.get('published_at')
            and release.get('tag_name') == tag and release.get('html_url') == receipt['release_url'])
    ref = object_json(run(['gh', 'api', 'repos/' + repo + '/git/ref/tags/' + tag]))
    require(ref.get('object') == {'type': 'tag', 'sha': receipt['source_tag_object']}
            or (isinstance(ref.get('object'), dict) and ref['object'].get('type') == 'tag'
                and ref['object'].get('sha') == receipt['source_tag_object']))
    obj = object_json(run(['gh', 'api', 'repos/' + repo + '/git/tags/' + receipt['source_tag_object']]))
    require(isinstance(obj.get('object'), dict) and obj['object'].get('type') == 'commit'
            and obj['object'].get('sha') == receipt['source_commit'])


def verify_version(root, identity, *, location=None, source=None):
    require(DIGEST.fullmatch(identity) is not None)
    selected = location or root / 'versions' / identity
    directory(selected)
    require(selected.resolve().parent == (root / 'versions').resolve())
    require({p.name for p in selected.iterdir()} == {'pre-commit', 'receipt.json'})
    hook, record = selected / 'pre-commit', selected / 'receipt.json'
    regular(hook, mode=0o500); regular(record, mode=0o400)
    require(os.access(hook, os.X_OK) and digest(hook.read_bytes()) == identity)
    receipt = object_json(record.read_bytes())
    require(set(receipt) == {'schema_version', 'package_version', 'source_commit', 'source_tag',
                            'source_tag_object', 'github_repository', 'source_path', 'source_sha256',
                            'deployed_sha256', 'release_url', 'acceptance_boundary'})
    require(receipt['schema_version'] == 1 and receipt['source_path'] == SOURCE_PATH
            and receipt['source_sha256'] == identity and receipt['deployed_sha256'] == identity)
    require(isinstance(receipt['package_version'], str) and VERSION.fullmatch(receipt['package_version']))
    require(receipt['source_tag'] == 'v' + receipt['package_version'])
    require(isinstance(receipt['source_commit'], str) and COMMIT.fullmatch(receipt['source_commit']))
    require(isinstance(receipt['source_tag_object'], str) and COMMIT.fullmatch(receipt['source_tag_object']))
    require(isinstance(receipt['github_repository'], str) and REPOSITORY.fullmatch(receipt['github_repository']))
    require(receipt['release_url'] == 'https://github.com/' + receipt['github_repository'] + '/releases/tag/' + receipt['source_tag'])
    require(receipt['acceptance_boundary'] == 'Cold acceptance and explicit proceed are external lifecycle evidence.')
    if source:
        payload, expected = source_identity(source, receipt['source_tag'], receipt['github_repository'])
        require(receipt == expected and payload == hook.read_bytes())
    return receipt


def selected_version(root, *, source=None):
    require((root / 'current').is_symlink())
    link = os.readlink(root / 'current')
    require(re.fullmatch(r'versions/[0-9a-f]{64}', link) is not None)
    identity = link.split('/')[1]
    return verify_version(root, identity, source=source)


def atomic_bytes(path, content, mode):
    descriptor, temporary = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(content); stream.flush(); os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.lexists(temporary): os.unlink(temporary)


def select(root, identity):
    verify_version(root, identity)
    require(not os.path.lexists(root / 'current') or (root / 'current').is_symlink())
    pending = root / ('.selection-' + uuid.uuid4().hex)
    try:
        pending.symlink_to('versions/' + identity)
        os.replace(pending, root / 'current')
    finally:
        if pending.is_symlink(): pending.unlink()


def pattern_pointer(root, value):
    path = Path(value)
    require(path.is_absolute() and '\n' not in value and '\r' not in value and '\x00' not in value)
    require(path.is_file() and os.access(path, os.R_OK))
    require(not os.path.lexists(root / 'pattern-file.path') or not (root / 'pattern-file.path').is_symlink())
    atomic_bytes(root / 'pattern-file.path', (str(path) + '\n').encode(), 0o600)


def audit_pointer(root):
    pointer = root / 'pattern-file.path'
    regular(pointer, mode=0o600)
    raw = pointer.read_text()
    require(raw.endswith('\n') and raw.count('\n') == 1)
    value = Path(raw[:-1])
    require(value.is_absolute() and value.is_file() and os.access(value, os.R_OK))


def deploy(args):
    # Release verification completes before any runtime mutation.
    payload, receipt = source_identity(args.source_repo, args.tag, args.github_repo)
    release_check(receipt)
    require(Path(args.pattern_file).is_absolute() and Path(args.pattern_file).is_file()
            and os.access(args.pattern_file, os.R_OK))
    root = runtime_path(args.runtime_root, create=True)
    identity = digest(payload)
    destination = root / 'versions' / identity
    if os.path.lexists(destination):
        require(verify_version(root, identity) == receipt)
    else:
        staging = Path(tempfile.mkdtemp(prefix='.staging-', dir=root / 'versions'))
        try:
            (staging / 'pre-commit').write_bytes(payload)
            (staging / 'pre-commit').chmod(0o500)
            (staging / 'receipt.json').write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
            (staging / 'receipt.json').chmod(0o400)
            verify_version(root, identity, location=staging, source=args.source_repo)
            require(not os.path.lexists(destination))
            staging.chmod(0o500)
            os.rename(staging, destination)
        finally:
            if staging.exists():
                staging.chmod(0o700); shutil.rmtree(staging)
    pattern_pointer(root, args.pattern_file)
    select(root, identity)
    return {'status': 'deployed', 'digest': identity, 'receipt': receipt}


def repo_population(repo):
    require(text(git(repo, 'rev-parse', '--is-bare-repository')) == 'false')
    common = Path(text(git(repo, 'rev-parse', '--path-format=absolute', '--git-common-dir'))).resolve()
    expected = common / 'hooks/pre-commit'
    rows = git(repo, 'worktree', 'list', '--porcelain', '-z').split(b'\0')
    paths = [os.fsdecode(row[len(b'worktree '):]) for row in rows if row.startswith(b'worktree ')]
    require(paths and len(paths) == len(set(paths)))
    target = text(git(repo, 'rev-parse', '--show-toplevel'))
    require(Path(target).resolve() in {Path(p).resolve() for p in paths})
    for path in paths:
        require(git(path, 'config', '--get', 'core.hooksPath', absent=True) is None)
        require(Path(text(git(path, 'rev-parse', '--path-format=absolute', '--git-common-dir'))).resolve() == common)
        resolved = Path(text(git(path, 'rev-parse', '--path-format=absolute', '--git-path', 'hooks/pre-commit')))
        require(resolved == expected)
    return expected, {'common_directory': str(common), 'worktrees': paths, 'hook_path': str(expected),
                      'effective_core_hooksPath': None}


def dispatcher(root):
    template = Path(__file__).with_name('dispatcher.sh.tmpl').read_text()
    require(template.count('@@RUNTIME_ROOT@@') == 1)
    return template.replace('@@RUNTIME_ROOT@@', shlex.quote(str(root))).encode()


def repository(args, *, install):
    root = runtime_path(args.runtime_root)
    receipt = selected_version(root); audit_pointer(root)
    hook, result = repo_population(args.repo)
    expected = dispatcher(root)
    if os.path.lexists(hook):
        regular(hook, mode=0o755)
        require(hook.read_bytes() == expected)
    else:
        require(install)
        hook.parent.mkdir(exist_ok=True)
        directory(hook.parent)
        # Exclusive creation refuses a racing/unmanaged pre-commit; no overwrite.
        with hook.open('xb') as stream: stream.write(expected)
        hook.chmod(0o755)
    regular(hook, mode=0o755); require(hook.read_bytes() == expected)
    result.update(status='local pre-commit gate installed and audited',
                  runtime_sha256=receipt['deployed_sha256'], dispatcher_sha256=digest(expected))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('deploy-runtime', 'configure-pattern', 'audit-runtime', 'install-repo', 'audit-repo', 'rollback-runtime'):
        child = sub.add_parser(name)
        child.add_argument('--runtime-root', required=True)
        if name == 'deploy-runtime':
            child.add_argument('--source-repo', required=True)
            child.add_argument('--github-repo', required=True)
            child.add_argument('--tag', required=True)
            child.add_argument('--pattern-file', required=True)
        elif name == 'configure-pattern': child.add_argument('--pattern-file', required=True)
        elif name == 'audit-runtime': child.add_argument('--source-repo')
        elif name in ('install-repo', 'audit-repo'): child.add_argument('--repo', required=True)
        elif name == 'rollback-runtime': child.add_argument('--digest', required=True)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        if args.command == 'deploy-runtime': result = deploy(args)
        elif args.command in ('install-repo', 'audit-repo'):
            result = repository(args, install=args.command == 'install-repo')
        else:
            root = runtime_path(args.runtime_root)
            if args.command == 'configure-pattern':
                selected_version(root); pattern_pointer(root, args.pattern_file)
                result = {'status': 'configured'}
            elif args.command == 'rollback-runtime':
                audit_pointer(root); select(root, args.digest)
                result = {'status': 'rolled-back', 'digest': args.digest}
            else:
                receipt = selected_version(root, source=args.source_repo); audit_pointer(root)
                result = {'status': 'audited', 'receipt': receipt}
        print(json.dumps(result, sort_keys=True))
        return 0
    except (Refusal, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        print('data-hygiene: operation unavailable', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
