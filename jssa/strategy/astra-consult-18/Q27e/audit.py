"""Audit output joins, fixed criteria, source hashes, and local document links."""
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent


def rows(name):
    with (OUT / name).open() as f:
        return list(csv.DictReader(f))


def main():
    joined = rows('joined-discovery.csv')
    assert len(joined) == len({r['id'] for r in joined}) == 323
    assert sum(r['human'] != 'nan' for r in joined) == 131
    assert sum(bool(r['group_local']) for r in joined) == 109
    manifest = json.loads((OUT / 'input-manifest.json').read_text())
    other = json.loads((OUT / 'validation-input-manifest.json').read_text())
    checked = {}
    for rel, value in list(manifest.items()) + list(other.items()):
        assert 'sealed-raw' not in rel and 'unseen-1983' not in rel
        digest = value['sha256'] if isinstance(value, dict) else value
        assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == digest, rel
        checked[rel] = digest
    lock = json.loads((OUT / 'registration-lock.json').read_text())
    for rel, digest in lock['files'].items():
        assert hashlib.sha256((OUT / rel).read_bytes()).hexdigest() == digest, rel
    pairs = rows('validation-pairs.csv')
    assert len(pairs) == 18
    assert all(r['correct_hard'] == r['correct_easy'] == 'True' for r in pairs)
    counts = dict(Counter(int(r['seed']) for r in pairs if float(r['ratio']) >= 10))
    assert counts == {0: 6, 1: 2, 2: 2}
    summary = json.loads((OUT / 'validation-summary.json').read_text())
    assert not summary['P1']['pass'] and summary['P2']['pass'] and summary['P3']['pass']
    assert summary['seed1_records'] == 55142 and summary['new_solver_runs'] == 0
    assert summary['full_correct'] == 953
    local = rows('validation-local-groups.csv')
    assert len(local) == 31 and all(r['retains_extreme'] == 'True' for r in local)
    links = []
    for doc in OUT.glob('*.md'):
        for link in re.findall(r'\]\(([^)]+)\)', doc.read_text()):
            if '://' in link or link.startswith('#'):
                continue
            target = doc.parent / link.split('#')[0]
            assert target.exists(), (doc, link)
            links.append(str(target))
    files = [p for p in OUT.iterdir() if p.is_file()]
    assert max(p.stat().st_size for p in files) < 2_000_000
    result = {'passed': True, 'input_files_checked': len(checked), 'local_links_checked': len(links), 'output_file_count_before_audit': len(files), 'largest_output_bytes': max(p.stat().st_size for p in files), 'pair_tenfold_counts': counts, 'P1_pass': False, 'new_solver_runs': 0}
    (OUT / 'audit.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
