"""Run only synthetic transports, retaining output and fixture evidence outside the repo."""
import argparse, os, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--evidence-dir',required=True,type=Path)
parser.add_argument('--hygiene-file',type=Path)
args=parser.parse_args()
args.evidence_dir.mkdir(parents=True,exist_ok=False)
hygiene=args.hygiene_file
if hygiene is None:
    hygiene=args.evidence_dir/'synthetic-hygiene.txt'
    hygiene.write_text('SYNTHETIC_EXCLUDED_FIXTURE_TOKEN\n')
env=dict(os.environ,BEDROCK_HYGIENE_FILE=str(hygiene.resolve()),BEDROCK_FIXTURE_EVIDENCE_ROOT=str(args.evidence_dir.resolve()),PYTHONDONTWRITEBYTECODE='1')
env.pop('PYTHONPATH',None)
env.pop('ANTHROPIC_API_KEY',None)
with (args.evidence_dir/'pytest.txt').open('x') as out:
    result=subprocess.run([sys.executable,'-m','pytest','-q','-p','no:cacheprovider','--basetemp',str(args.evidence_dir/'fixtures'),str(ROOT/'tests')],cwd=ROOT,env=env,stdout=out,stderr=subprocess.STDOUT)
print((args.evidence_dir/'pytest.txt').read_text())
raise SystemExit(result.returncode)
