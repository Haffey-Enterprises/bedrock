"""Post-repair review probes, invented fixtures only; independent review evidence."""
import hashlib,json,shlex,shutil,sys
from pathlib import Path
ROOT=Path('/Users/thaffey/.codex/worktrees/heb-154-integration/bedrock')
sys.path.insert(0,str(ROOT/'tests'))
from test_data_hygiene import HygieneTests,SURFACE
results={}
results['subject_sha256']=hashlib.sha256((SURFACE/'pre-commit').read_bytes()).hexdigest()
for name in ('private_open_race','control_read_status','blob_read_diagnostic'):
 case=HygieneTests('test_safe_commit_and_empty_population');case.setUp()
 try:
  case.stage();control=case.hook(0)
  if name=='private_open_race':
   case.shim('mktemp','/bin/rm -- '+shlex.quote(str(case.pattern))+'\nexec /usr/bin/mktemp "$@"')
  elif name=='control_read_status': case.shim('cat','/bin/cat "$@"\nexit 19')
  else:
   real=shutil.which('git',path='/usr/bin:/bin')
   case.shim('git','[[ "$1" == cat-file && "$2" == blob ]] && exit 23\nexec '+shlex.quote(real)+' "$@"')
  r=case.run_command(['/bin/bash',SURFACE/'pre-commit'])
  results[name]={'control_exit':control.returncode,'fault_exit':r.returncode,'stdout':r.stdout.decode(),'stderr':r.stderr.decode(),'invented_pattern_path_leaked':str(case.pattern).encode() in r.stdout+r.stderr}
 finally:case.doCleanups()
results['subject_unchanged']=results['subject_sha256']==hashlib.sha256((SURFACE/'pre-commit').read_bytes()).hexdigest()
print(json.dumps(results,indent=2))
