"""Run once, before any one-sided numerical results exist."""
from common import *
from datetime import datetime, timezone

assert not (OUT/'pre-run-hashes.json').exists()
assert not (OUT/'results').exists()
frozen_check()
rows = selected()
files = [OUT/'README.md', OUT/'protocol.json', S7/'classification.csv', S7/'README.md']
files += sorted(OUT.glob('*.py')) + [S7/'helpers.py', S7/'measure.py']
for r in rows:
    key = r['case_id']
    files += [S7/'inputs'/f'{key}.json', S7/'results'/key/'reference.json', S7/'results'/key/'sigma-details.json']
files += sorted(p for p in FROZEN.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix in {'.py', '.json', '.toml'})
save(OUT/'pre-run-hashes.json', dict(created_utc=datetime.now(timezone.utc).isoformat(), source_hash=EXPECTED_SOURCE,
    case_ids=[r['case_id'] for r in rows], protocol=load(OUT/'protocol.json'), files={str(p):sha(p) for p in files}))
digest = sha(OUT/'pre-run-hashes.json')
(OUT/'pre-run-hashes.sha256').write_text(digest+'  pre-run-hashes.json\n')
print('Protocol and inputs frozen before calculation:', digest, 'cases:', len(rows))
