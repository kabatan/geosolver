"""Verify the sealed experiment and final artifact integrity without search."""
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from campaign import verify

OUT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    verify()
    raw = json.loads((OUT/'raw-manifest.json').read_text())
    assert len(raw) == 448
    assert all(sha(OUT/p) == h for p, h in raw.items())
    rows = list(csv.DictReader((OUT/'per-start.csv').open()))
    assert len(rows) == 4928 and all(r['audit_ok'] == 'True' for r in rows)
    assert Counter(r['arm'] for r in rows) == Counter({a: 448 for a in ['N','L','Nfine','Nlp','Lnp','Nu','Lu','Nrs','Lrs','Ls','Lrestart']})
    groups = json.loads((OUT/'group-summary.json').read_text())
    for g in groups:
        r = [r for r in rows if r['group'] == g['group'] and r['arm'] == g['arm'] and (g['seed'] == 0 or int(r['seed']) == g['seed'])]
        assert len(r) == g['n'] and sum(int(x['hit']) for x in r) == g['hits']
    links = 0
    for name in ['answer.md', 'README.md', 'case-study.md', 'literature.md']:
        for link in re.findall(r'\]\(([^)]+)\)', (OUT/name).read_text()):
            if '://' not in link and not link.startswith('#'):
                assert (OUT/link.split('#')[0]).exists(), (name, link)
                links += 1
    files = sorted(p for p in OUT.rglob('*') if p.is_file() and p.name != 'delivery-verification.json')
    sizes = [(p.stat().st_size, str(p.relative_to(OUT))) for p in files]
    assert max(sizes)[0] < 5_000_000
    report = {'utc': datetime.now(timezone.utc).isoformat(), 'sealed_inputs_prediction_source_and_amendment_chain': 'pass', 'raw_hashes_verified': len(raw), 'trials_and_group_counts': 'pass', 'local_report_links_verified': links, 'file_count_excluding_this_record': len(files), 'largest_file_bytes': max(sizes)[0], 'largest_file': max(sizes)[1], 'all_files_under_5MB': True, 'optimization_calls': 0, 'artifact_sha256': {str(p.relative_to(OUT)): sha(p) for p in files}}
    data = json.dumps(report, ensure_ascii=False, indent=2)+'\n'
    assert len(data.encode()) < 5_000_000
    (OUT/'delivery-verification.json').write_text(data)
    print(json.dumps({k:v for k,v in report.items() if k != 'artifact_sha256'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
