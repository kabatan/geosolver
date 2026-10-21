"""Freeze two independent blind grades (and any adjudication) before unblinding."""
import hashlib
import json
from pathlib import Path
import statistics
import time

D = Path(__file__).resolve().parent
ROOT = D.parents[2]
R = ROOT / 'qwen/.runtime/research_direction_audit_20260925'
B = D / 'bridge-blind'
FIELDS = ('mapping_proof', 'exact_value', 'complete')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    paths = [B/'grades-primary.json', B/'grades-secondary.json']
    reviews = [{g['id']: g for g in read(p)['grades']} for p in paths]
    ids = {f'P{i:03d}' for i in range(1, 9)}
    assert all(set(review) == ids for review in reviews)
    adjudication_path = B/'adjudication.json'
    adjudication = {}
    if adjudication_path.exists():
        paths.append(adjudication_path)
        adjudication = {g['id']: g for g in read(adjudication_path)['grades']}
    final, disagreements = {}, []
    for identity in sorted(ids):
        first, second = (review[identity] for review in reviews)
        assert all(type(review[field]) is bool for review in (first, second) for field in FIELDS)
        differences = [field for field in FIELDS if first[field] != second[field]]
        if differences and identity not in adjudication:
            disagreements.append({'id': identity, 'fields': differences})
        final[identity] = adjudication.get(identity, first)
    if disagreements:
        print(json.dumps({'unresolved_blind_disagreements': disagreements}, indent=2))
        raise SystemExit(1)
    assert all(type(g[field]) is bool for g in final.values() for field in FIELDS)
    packet = read(B/'packet.json')
    packet_freeze = read(B/'packet-freeze.json')
    assert sha(B/'packet.json') == packet_freeze['packet_sha256']
    assert sha(R/'blind-mapping.json') == packet_freeze['mapping_sha256']
    freeze = {'created_unix': time.time(), 'files': {p.name: sha(p) for p in paths},
              'packet_sha256': sha(B/'packet.json'),
              'mapping_sha256': sha(R/'blind-mapping.json'), 'final_blind_grades': final}
    freeze_path = B/'grades-freeze.json'
    with freeze_path.open('x') as f:
        json.dump(freeze, f, indent=2, ensure_ascii=False)
        f.write('\n')
    # No arm identities are read before the immutable grade snapshot above.
    mapping = read(R/'blind-mapping.json')
    answers = {x['id']: x for x in packet}
    joined = []
    for row in mapping:
        answer = answers[row['id']]
        assert sha(Path(row['source_path'])) == row['source_sha256']
        joined.append({**row, **final[row['id']],
                       'tokens': answer['tokens'], 'finish_reason': answer['finish_reason']})
    groups = {}
    for arm in ('treatment', 'control'):
        rows = [r for r in joined if r['arm'] == arm]
        assert len(rows) == 4
        groups[arm] = {'n': len(rows), **{field: sum(r[field] for r in rows) for field in FIELDS},
                       'tokens_total': sum(r['tokens'] for r in rows),
                       'tokens_median': statistics.median(r['tokens'] for r in rows),
                       'natural_stop': sum(r['finish_reason'] == 'stop' for r in rows),
                       'generation_seconds': read(R/f'eval-mapped-{arm}/receipt.json')['elapsed_seconds']}
    result = {'grade_freeze_sha256': sha(freeze_path), 'groups': groups, 'rows': joined}
    (D/'BRIDGE_PILOT_SCORES.json').write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n')
    print(json.dumps(groups, indent=2))


if __name__ == '__main__':
    main()
