import sys,json,hashlib
from pathlib import Path
ROOT=Path('/Users/thaffey/.codex/worktrees/heb-154-integration/bedrock')
sys.path.insert(0,str(ROOT/'tests'))
from test_data_hygiene import ManagerTests,SURFACE
case=ManagerTests('test_explicit_default_hook_path_is_not_a_redirection');case.setUp()
try:
 case.install()
 control=case.manager('audit-repo','--repo',case.repo)
 elsewhere=case.base/'different-hooks';elsewhere.mkdir()
 (elsewhere/'pre-commit').symlink_to(case.repo/'.git/hooks/pre-commit')
 case.git('config','core.hooksPath',str(elsewhere))
 r=case.run_command([sys.executable,SURFACE/'manager.py','audit-repo','--runtime-root',case.runtime,'--repo',case.repo])
 print(json.dumps({'manager_sha256':hashlib.sha256((SURFACE/'manager.py').read_bytes()).hexdigest(),'control_exit':control.returncode,'redirect_audit_exit':r.returncode,'stdout':r.stdout.decode(),'stderr':r.stderr.decode(),'native_post_commit_resolves_default':case.git('rev-parse','--path-format=absolute','--git-path','hooks/post-commit').decode().strip()==str(case.repo/'.git/hooks/post-commit')},indent=2))
finally:case.doCleanups()
