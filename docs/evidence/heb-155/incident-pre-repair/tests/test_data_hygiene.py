"""HEB-155 contract tests: invented data, disposable repositories, no network."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SURFACE = ROOT / 'plugins/bedrock/scripts/data-hygiene'
TOKEN = b'Invented-Zebra-Canary-731'


class HygieneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='heb155-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.repo = self.base / 'repo'
        self.repo.mkdir()
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith('GIT_') and k not in
                    ('DATA_HYGIENE_PATTERN_FILE', 'RECALL_HYGIENE_TERMS')}
        self.env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1',
                        GIT_AUTHOR_NAME='Fixture', GIT_COMMITTER_NAME='Fixture',
                        GIT_AUTHOR_EMAIL='fixture@example.invalid',
                        GIT_COMMITTER_EMAIL='fixture@example.invalid',
                        TMPDIR=str(self.base), LC_ALL='C')
        self.git('init', '-q')
        self.git('commit', '--allow-empty', '-qm', 'fixture base')
        self.pattern = self.base / 'invented.patterns'
        self.pattern.write_bytes(TOKEN + b'\n')
        self.env['DATA_HYGIENE_PATTERN_FILE'] = str(self.pattern)

    def run_command(self, args, *, cwd=None, env=None):
        return subprocess.run([str(x) for x in args], cwd=cwd or self.repo,
                              env=env or self.env, capture_output=True)

    def git(self, *args, cwd=None):
        r = self.run_command(['git', *args], cwd=cwd)
        self.assertEqual(0, r.returncode, r.stderr.decode(errors='replace'))
        return r.stdout

    def stage(self, name='content.txt', data=b'harmless\n'):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self.git('add', '--', name)
        return path

    def hook(self, code, *, env=None):
        r = self.run_command(['/bin/bash', SURFACE / 'pre-commit'], env=env)
        self.assertEqual(code, r.returncode, r.stdout + r.stderr)
        self.assertNotIn(TOKEN, r.stdout + r.stderr)
        self.assertNotIn(str(self.pattern).encode(), r.stdout + r.stderr)
        return r

    def shim(self, name, body):
        folder = self.base / 'shims'
        folder.mkdir(exist_ok=True)
        path = folder / name
        path.write_text('#!/bin/bash\n' + body + '\n')
        path.chmod(0o755)
        self.env['PATH'] = str(folder) + os.pathsep + os.environ['PATH']

    def test_normal_commit_refuses_invented_content(self):
        # Baseline has no package control: this assertion fails at git commit,
        # rather than at test import or collection.
        hook = SURFACE / 'pre-commit'
        if hook.is_file():
            shutil.copy2(hook, self.repo / '.git/hooks/pre-commit')
        self.stage(data=TOKEN + b' private fixture line\n')
        r = self.run_command(['git', 'commit', '-qm', 'fixture refused'])
        self.assertNotEqual(0, r.returncode, 'normal commit admitted invented protected content')
        self.assertNotIn(TOKEN, r.stdout + r.stderr)
        self.assertEqual(b'content.txt\n', self.git('diff', '--cached', '--name-only'))

    def test_safe_commit_and_empty_population(self):
        self.hook(0)
        self.stage()
        shutil.copy2(SURFACE / 'pre-commit', self.repo / '.git/hooks/pre-commit')
        r = self.run_command(['git', 'commit', '-qm', 'fixture safe'])
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual(b'', self.git('diff', '--cached', '--name-only'))

    def test_missing_nonregular_unreadable_empty_invalid_patterns(self):
        for kind in ('missing', 'directory', 'unreadable', 'empty', 'comments', 'nul'):
            with self.subTest(kind=kind):
                path = self.base / ('patterns-' + kind)
                if kind == 'directory': path.mkdir()
                elif kind != 'missing':
                    path.write_bytes({'empty': b'', 'comments': b' \t# comment\r\n\t \n',
                                      'nul': b'abc\x00def\n'}.get(kind, TOKEN + b'\n'))
                    if kind == 'unreadable': path.chmod(0)
                env = dict(self.env, DATA_HYGIENE_PATTERN_FILE=str(path))
                self.hook(2, env=env)

    def test_normalization_fixed_ascii_and_nonascii(self):
        self.pattern.write_bytes(b' \t# ignored\r\n\t \r\n  a.*[x]#tail \t\r\na.*[x]#tail\n\xc3\x89\n')
        self.stage(data=b'prefix A.*[X]#TAIL suffix\n\xc3\x89\n')
        self.assertEqual(b'content.txt:1\ncontent.txt:2\n', self.hook(1).stderr)
        self.stage(data=b'abcdx\na.*[x]\n\xc3\xa9\n')
        self.hook(0)

    def test_precedence_and_empty_environment_refusal(self):
        self.stage(data=TOKEN + b'\n')
        good = self.base / 'other-patterns'; good.write_bytes(b'other-invented-value\n')
        env = dict(self.env, RECALL_HYGIENE_TERMS=str(good))
        self.hook(1, env=env)
        env.pop('DATA_HYGIENE_PATTERN_FILE'); self.hook(0, env=env)
        for key in ('DATA_HYGIENE_PATTERN_FILE', 'RECALL_HYGIENE_TERMS'):
            self.hook(2, env=dict(self.env, **{key: ''}))

    def test_binary_paths_and_complete_locations(self):
        names = ['space name', 'colon:name', '-leading', 'control\nname\t']
        for name in names: self.stage(name, b'safe\x00\n' + TOKEN.lower() + b'\x00line\n' + TOKEN + b'\n')
        r = self.hook(1)
        lines = r.stderr.splitlines()
        self.assertEqual(8, len(lines))
        self.assertIn(b'colon:name:2', lines)
        self.assertIn(b"$'control\\nname\\t':2", lines)
        self.assertEqual(b'', r.stdout)

    def test_staged_not_working_tree_and_filename_exclusion(self):
        path = self.stage(TOKEN.decode(), b'clean\n')
        path.write_bytes(TOKEN)
        (self.repo / 'untracked').write_bytes(TOKEN)
        self.hook(0)
        self.stage('tracked', TOKEN + b'\n').write_bytes(b'clean\n')
        self.hook(1)

    def test_modification_copy_rename_typechange_symlink_and_deletion(self):
        for name in ('modified', 'renamed', 'typed', 'deleted', 'source'):
            self.stage(name)
        self.git('commit', '-qm', 'fixture initial')
        self.stage('modified', TOKEN)
        self.git('mv', 'renamed', 'new name'); self.stage('new name', TOKEN)
        self.stage('copied', TOKEN)
        (self.repo / 'typed').unlink(); (self.repo / 'typed').symlink_to(TOKEN.decode())
        self.git('add', '--', 'typed')
        self.git('rm', '-q', '--', 'deleted')
        for mode in ('true', 'false', 'copies'):
            self.git('config', 'diff.renames', mode)
            self.assertEqual({b'modified:1', b'new name:1', b'copied:1', b'typed:1'},
                             set(self.hook(1).stderr.splitlines()))

    def test_deleted_and_unmodified_historical_blobs_are_excluded(self):
        self.stage('old', TOKEN); self.git('commit', '-qm', 'fixture historical')
        self.hook(0)
        self.git('rm', '-q', '--', 'old'); self.hook(0)

    def test_gitlink_refuses(self):
        oid = self.git('rev-parse', 'HEAD').decode().strip()
        self.git('update-index', '--add', '--cacheinfo', '160000,' + oid + ',changed-link')
        self.hook(2)

    def test_matcher_and_self_control_faults(self):
        for status in (0, 1, 2, 37):
            with self.subTest(status=status):
                self.shim('grep', 'exit ' + str(status))
                self.hook(2)

    def test_enumeration_type_and_blob_read_faults(self):
        real = shutil.which('git')
        self.stage(data=TOKEN)
        for predicate in ('[[ "$1" == diff ]]', '[[ "$1" == cat-file && "$2" == -t ]]',
                          '[[ "$1" == cat-file && "$2" == blob ]]'):
            with self.subTest(predicate=predicate):
                self.shim('git', predicate + ' && exit 23\nexec ' + repr(real) + ' "$@"')
                self.hook(2)

    def test_redaction_fault_and_exact_clean_output(self):
        self.stage()
        self.assertEqual(b'data-hygiene: 1 staged blobs scanned\n', self.hook(0).stdout)
        self.shim('awk', 'exit 9'); self.hook(2)

    def test_amend_and_conflict_resolution_commit(self):
        shutil.copy2(SURFACE / 'pre-commit', self.repo / '.git/hooks/pre-commit')
        self.stage(data=TOKEN)
        self.assertNotEqual(0, self.run_command(['git', 'commit', '--amend', '-qm', 'fixture amend']).returncode)
        self.git('reset', '--hard', '-q', 'HEAD')
        self.stage('conflict', b'base\n'); self.git('commit', '-qm', 'fixture base content')
        branch = self.git('branch', '--show-current').decode().strip()
        self.git('checkout', '-qb', 'other')
        self.stage('conflict', b'other\n'); self.git('commit', '-qm', 'fixture other')
        self.git('checkout', '-q', branch)
        self.stage('conflict', b'main\n'); self.git('commit', '-qm', 'fixture main')
        self.assertNotEqual(0, self.run_command(['git', 'merge', 'other']).returncode)
        self.stage('conflict', TOKEN)
        self.assertNotEqual(0, self.run_command(['git', 'commit', '-qm', 'fixture resolved']).returncode)


class ManagerTests(HygieneTests):
    # Inherited hook tests run only in HygieneTests via load_tests below.
    def setUp(self):
        super().setUp()
        self.runtime = self.base / 'runtime root'
        self.source = self.base / 'source'
        self.source.mkdir()
        self.git('init', '-q', cwd=self.source)
        self.git('remote', 'add', 'origin', 'https://github.com/example/bedrock-fixture.git', cwd=self.source)
        target = self.source / 'plugins/bedrock/scripts/data-hygiene'
        target.mkdir(parents=True)
        shutil.copy2(SURFACE / 'pre-commit', target / 'pre-commit')
        manifest = self.source / 'plugins/bedrock/.claude-plugin/plugin.json'
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({'name': 'bedrock', 'version': '10.0.0',
                                       'repository': 'https://github.com/example/bedrock-fixture'}))
        self.git('add', '--', 'plugins', cwd=self.source)
        self.git('commit', '-qm', 'fixture source', cwd=self.source)
        self.git('tag', '-am', 'fixture release', 'v10.0.0', cwd=self.source)
        self.mock_release()

    def mock_release(self, *, draft=False, wrong_tag=False):
        tag_oid = self.git('rev-parse', 'refs/tags/v10.0.0', cwd=self.source).decode().strip()
        commit = self.git('rev-parse', 'refs/tags/v10.0.0^{}', cwd=self.source).decode().strip()
        responses = {
            'repos/example/bedrock-fixture/releases/tags/v10.0.0':
                {'tag_name': 'wrong' if wrong_tag else 'v10.0.0', 'draft': draft,
                 'published_at': 'fixture-published', 'html_url': 'https://github.com/example/bedrock-fixture/releases/tag/v10.0.0'},
            'repos/example/bedrock-fixture/git/ref/tags/v10.0.0': {'object': {'type': 'tag', 'sha': tag_oid}},
            'repos/example/bedrock-fixture/git/tags/' + tag_oid: {'object': {'type': 'commit', 'sha': commit}},
        }
        body = ('#!' + sys.executable + '\nimport json,sys\nr=' + repr(responses) +
                '\nif sys.argv[1:2]!=["api"] or sys.argv[2] not in r: sys.exit(42)\nprint(json.dumps(r[sys.argv[2]]))\n')
        folder = self.base / 'shims'; folder.mkdir(exist_ok=True)
        stub = folder / 'gh'; stub.write_text(body); stub.chmod(0o755)
        self.env['PATH'] = str(folder) + os.pathsep + os.environ['PATH']

    def manager(self, command, *args, code=0):
        r = self.run_command([sys.executable, SURFACE / 'manager.py', command,
                              '--runtime-root', self.runtime, *args])
        self.assertEqual(code, r.returncode, r.stdout + r.stderr)
        self.assertNotIn(TOKEN, r.stdout + r.stderr)
        return r

    def deploy(self, code=0):
        return self.manager('deploy-runtime', '--source-repo', self.source,
                            '--github-repo', 'example/bedrock-fixture', '--tag', 'v10.0.0',
                            '--pattern-file', self.pattern, code=code)

    def install(self):
        self.deploy()
        self.manager('install-repo', '--repo', self.repo)
        self.env.pop('DATA_HYGIENE_PATTERN_FILE')

    def test_deploy_audit_receipt_and_worktree_source_ignored(self):
        original = (SURFACE / 'pre-commit').read_bytes()
        (self.source / 'plugins/bedrock/scripts/data-hygiene/pre-commit').write_bytes(b'working tree drift')
        self.deploy()
        selected = (self.runtime / 'data-hygiene/current').resolve()
        self.assertEqual(original, (selected / 'pre-commit').read_bytes())
        self.assertEqual(hashlib.sha256(original).hexdigest(), selected.name)
        self.assertEqual(0, (selected / 'pre-commit').stat().st_mode & 0o222)
        self.manager('audit-runtime')
        self.manager('audit-runtime', '--source-repo', self.source)
        receipt = json.loads((selected / 'receipt.json').read_text())
        self.assertEqual(receipt['source_sha256'], receipt['deployed_sha256'])
        self.assertNotIn(str(self.pattern), json.dumps(receipt))
        self.assertNotIn(TOKEN.decode(), json.dumps(receipt))

    def test_release_draft_wrong_identity_lightweight_and_bad_version_refuse(self):
        self.mock_release(draft=True); self.deploy(code=2)
        self.mock_release(wrong_tag=True); self.deploy(code=2)
        self.mock_release()
        self.git('tag', '-d', 'v10.0.0', cwd=self.source)
        self.git('tag', 'v10.0.0', cwd=self.source); self.deploy(code=2)
        self.git('tag', '-d', 'v10.0.0', cwd=self.source)
        manifest = self.source / 'plugins/bedrock/.claude-plugin/plugin.json'
        manifest.write_text(json.dumps({'name': 'bedrock', 'version': '99.0.0'}))
        self.git('add', '--', str(manifest), cwd=self.source)
        self.git('commit', '-qm', 'fixture version drift', cwd=self.source)
        self.git('tag', '-am', 'fixture release', 'v10.0.0', cwd=self.source)
        self.mock_release(); self.deploy(code=2)
        self.assertFalse((self.runtime / 'data-hygiene/current').exists())

    def test_install_idempotence_all_hooks_worktree_audit_and_bypass(self):
        hooks = self.repo / '.git/hooks'
        originals = {}
        for name in ('post-checkout', 'post-commit', 'post-merge', 'pre-push', 'custom-hook'):
            p = hooks / name; p.write_text('#!/bin/sh\nexit 0\n'); p.chmod(0o755)
            originals[name] = (p.read_bytes(), p.stat().st_mode)
        self.install()
        dispatcher = hooks / 'pre-commit'; before = (dispatcher.read_bytes(), dispatcher.stat().st_mtime_ns)
        self.manager('install-repo', '--repo', self.repo)
        self.assertEqual(before, (dispatcher.read_bytes(), dispatcher.stat().st_mtime_ns))
        linked = self.base / 'linked worktree'
        self.git('worktree', 'add', '-qb', 'linked', str(linked))
        audit = json.loads(self.manager('audit-repo', '--repo', linked).stdout)
        self.assertEqual({str(self.repo), str(linked)}, set(audit['worktrees']))
        for name, value in originals.items():
            self.assertEqual(value, ((hooks / name).read_bytes(), (hooks / name).stat().st_mode))
        self.stage(); self.git('commit', '-qm', 'fixture safe managed')
        self.stage(data=TOKEN)
        r = self.run_command(['git', 'commit', '-qm', 'fixture refuse managed'])
        self.assertNotEqual(0, r.returncode); self.assertNotIn(TOKEN, r.stderr)
        self.git('commit', '--no-verify', '-qm', 'fixture accepted bypass')
        self.git('config', 'core.hooksPath', str(self.base / 'elsewhere'))
        self.manager('audit-repo', '--repo', self.repo, code=2)
        self.manager('install-repo', '--repo', self.repo, code=2)

    def test_fresh_clone_unmanaged_and_dispatcher_drift_refuse(self):
        self.deploy()
        clone = self.base / 'clone'; self.git('clone', '-q', str(self.repo), str(clone))
        self.manager('audit-repo', '--repo', clone, code=2)
        hook = self.repo / '.git/hooks/pre-commit'; hook.write_text('#!/bin/sh\nexit 0\n'); hook.chmod(0o755)
        self.manager('install-repo', '--repo', self.repo, code=2)
        self.assertEqual('#!/bin/sh\nexit 0\n', hook.read_text())
        hook.unlink(); self.manager('install-repo', '--repo', self.repo)
        hook.chmod(0o644); self.manager('audit-repo', '--repo', self.repo, code=2)
        self.manager('install-repo', '--repo', self.repo, code=2)

    def test_dispatcher_integrity_containment_and_neutral_failure(self):
        self.install(); self.stage()
        current = self.runtime / 'data-hygiene/current'; original = os.readlink(current)
        selected = current.resolve(); payload = selected / 'pre-commit'
        for target in ('/absolute', '../escape', 'versions/' + '0' * 64):
            current.unlink(); current.symlink_to(target)
            r = self.run_command(['.git/hooks/pre-commit'])
            self.assertEqual(2, r.returncode); self.assertEqual(b'data-hygiene: runtime unavailable\n', r.stderr)
            self.manager('audit-runtime', code=2)
        current.unlink(); current.symlink_to(original)
        payload.chmod(0o700)
        self.assertEqual(2, self.run_command(['.git/hooks/pre-commit']).returncode)
        self.manager('audit-runtime', code=2)
        payload.write_bytes(b'#!/bin/sh\nexit 0\n'); payload.chmod(0o500)
        self.assertEqual(2, self.run_command(['.git/hooks/pre-commit']).returncode)
        self.manager('audit-runtime', code=2)

    def test_pattern_pointer_and_missing_runtime(self):
        self.install(); self.stage(data=TOKEN)
        r = self.run_command(['.git/hooks/pre-commit']); self.assertEqual(1, r.returncode)
        self.assertNotIn(TOKEN, r.stderr)
        self.pattern.unlink()
        self.assertEqual(2, self.run_command(['.git/hooks/pre-commit']).returncode)
        self.manager('configure-pattern', '--pattern-file', self.pattern, code=2)

    def test_rollback_retains_versions_and_refuses_unknown(self):
        self.deploy()
        current = self.runtime / 'data-hygiene/current'; old = os.readlink(current)
        self.manager('rollback-runtime', '--digest', '0' * 64, code=2)
        self.assertEqual(old, os.readlink(current))
        self.manager('rollback-runtime', '--digest', old.split('/')[-1])
        self.assertEqual(old, os.readlink(current))
        self.manager('audit-runtime')


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite(loader.loadTestsFromTestCase(HygieneTests))
    for name in sorted(ManagerTests.__dict__):
        if name.startswith('test_'): suite.addTest(ManagerTests(name))
    return suite


if __name__ == '__main__':
    unittest.main()
