"""Re-derive current carriers using the existing package instruments; no provider calls."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import yaml

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))
from scripts.sync_package_identity import synchronize
from scripts.validate_rule_trigger_audit import _relative_files, _semantic_unit_count, _derived_counts
from scripts.validate_plugin import validate_repository

assert not synchronize(root, write=True)
day = subprocess.check_output(['date', '+%Y-%m-%d'], env={**os.environ, 'TZ': 'America/New_York'}, text=True).strip()
context_path = root / 'docs/evidence/heb-118/context-budget.json'
context = json.loads(context_path.read_text())
rows = []
for path in sorted((root / 'plugins/bedrock/skills').glob('*/SKILL.md')):
    text = path.read_text()
    description = yaml.safe_load(text.split('---', 2)[1])['description']
    rows.append({'name': path.parent.name, 'description_characters': len(description),
                 'entrypoint_words': len(re.findall(r"\b[\w'-]+\b", text))})
context['captured_at'] = day
context['source_commit_baseline'] = 'f0ac9a0d81dbdb37cdb7b29b61b59f114802a489'
context['skills'] = rows
context['measurement']['catalog_description_characters'] = sum(row['description_characters'] for row in rows)
context['measurement']['skill_entrypoint_words'] = sum(row['entrypoint_words'] for row in rows)
context['limitations'] = ('HEB-184 re-derived catalog and entrypoint measurements from the complete current skill population. '
    'Host projected tokens and routing population are historical HEB-154 observations, not current planning or composed-candidate acceptance. '
    'HEB-161 owns live routing and fresh cross-host qualification. Reproduction: docs/evidence/heb-184/refresh.py.')
context_path.write_text(json.dumps(context, indent=2) + '\n')
ledger_path = root / 'docs/evidence/heb-136/rule-trigger-audit.yaml'
ledger = yaml.safe_load(ledger_path.read_text())
markdown = sorted(_relative_files(root, '*.md'))
structured = sorted(set().union(*(_relative_files(root, pattern) for pattern in ['*.json', '*.yaml', '*.yml'])))
old_markdown = ledger['scope']['markdown_inspections']
old_structured = {row['path']: row['inspection'] for row in ledger['scope']['structured_files']}
assert all(p in old_markdown or '/planning/' in p for p in markdown)
assert all(p in old_structured or '/planning/' in p for p in structured)
ledger['scope'].update(expected_markdown_carriers=len(markdown), markdown_carriers=markdown,
    markdown_inspections={p: old_markdown.get(p, 'inspected') for p in markdown},
    expected_structured_files=len(structured), structured_files=[{'path': p, 'inspection': old_structured.get(p, 'inspected')} for p in structured])
provenance = 'plugins/bedrock/skills/planning/reference/provenance.md'
lines = (root / provenance).read_text().splitlines()
findings = [row for row in ledger['findings'] if not row['id'].startswith('planning-')]
for ident, prefix, summary, trigger, failure in [
    ('planning-preservation', '| Preserve |', 'Preserve evidence before recommending delay or repair.', 'Actor judges that delay or repair is harmless.', 'Unnoticed evidence loss remains possible.'),
    ('planning-alignment', '| Assumed agreement |', 'Separate settled authority from an open owner choice.', 'Actor assumes agreement or mistakes a proposal for a disposition.', 'An unratified choice may be treated as settled.')]:
    findings.append({'id': ident, 'carrier': provenance, 'line': next(i for i, line in enumerate(lines, 1) if line.startswith(prefix)),
        'summary': summary, 'trigger_event': trigger, 'trigger_class': 'internal-state', 'frequency': 'medium',
        'salience': 'low', 'enforcement': 'discipline', 'disposition': 'known-weak', 'expected_failure': failure,
        'ratification': 'ratified'})
ledger['findings'] = findings
ledger['counts'] = _derived_counts(findings, carriers_examined=len(markdown), semantic_units_screened=_semantic_unit_count(root))
ledger['counting_basis']['last_refreshed_at'] = day + ' ET'
ledger['counting_basis']['last_refresh'] = ('HEB-184: planning instruction and provenance read whole; current adoption and invocation policy inspected. '
    'The accepted provenance explicitly dispositions preservation and assumed agreement as known-weak internal triggers. '
    'Their source frequency is unknown; medium is this ledger taxonomy mapping, not an empirical frequency estimate. '
    'Other planning rule groups are workflow events with disclosed residual misses. Unchanged carriers retain prior inspections; '
    'this is not a new whole-corpus semantic audit. Populations and screen units use the existing audit detector. '
    'Prior ledger and context inputs are retained in the baseline archive identified by HEB-184 preflight evidence.')
ledger_path.write_text(yaml.safe_dump(ledger, sort_keys=False, allow_unicode=True, width=100))
errors, inventory = validate_repository(root, run_host_cli=False, validate_retained_evidence=False)
if errors:
    raise SystemExit('\n'.join(errors))
(root / 'docs/evidence/heb-109/metadata-inventory.json').write_text(json.dumps(inventory, indent=2) + '\n')
print(json.dumps({'skills': [row['name'] for row in inventory['skills']], 'audit': ledger['counts'],
                  'catalog_characters': context['measurement']['catalog_description_characters']}))
