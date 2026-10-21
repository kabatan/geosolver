"""Audit anonymous duplicate grades, then publish the fully calibrated comparison.

The check mode deliberately prints only anonymous identities. Reference answers
receive the same pre-unblinding root adjudications as primary answers.
"""
import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parents[2] / 'qwen/.runtime/program_self_training_20260926'


def read(path):
    return json.loads(path.read_text())


def save(path, rows):
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')


def collect():
    rows = []
    for name in ['wave1', 'wave2', 'base-calibration']:
        wave = RUNTIME / 'grading' / name
        key = {r['anonymous_id']: r for r in read(wave / 'private-unblinding.json')}
        reviews = {r['anonymous_id']: r for r in read(wave / 'root-review.json')} \
            if (wave / 'root-review.json').exists() else {}
        for i in [1, 2]:
            path = wave / f'grades-packet-{i}.json'
            grades = read(path)
            expected = {r['anonymous_id'] for r in read(wave / f'packet-{i}.json')}
            assert len(grades) == len(expected)
            assert {r['anonymous_id'] for r in grades} == expected
            for grade in grades:
                identity = key[grade['anonymous_id']]
                assert hashlib.sha256(Path(identity['raw_file']).read_bytes()).hexdigest() == identity['raw_sha256']
                row = {**grade, **identity, 'wave': str(wave), 'grade_source': str(path),
                       'grader': 'gpt-6-luna(max)' if i == 1 else 'gpt-6-sol(high)'}
                if grade['anonymous_id'] in reviews:
                    r = reviews[grade['anonymous_id']]
                    row.update(pre_adjudication_complete_proof=grade['complete_proof'],
                               pre_adjudication_ancillary_math_error=grade['ancillary_math_error'],
                               complete_proof=r['root_complete_proof'],
                               ancillary_math_error=r['root_ancillary_math_error'], root_review=r)
                rows.append(row)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--publish', action='store_true')
    args = ap.parse_args()
    rows = collect()
    groups = defaultdict(list)
    for row in rows:
        groups[row['raw_sha256']].append(row)
    conflicts = []
    for group in groups.values():
        if len({(r['complete_proof'], bool(r['ancillary_math_error'])) for r in group}) > 1:
            conflicts.append([{k: r[k] for k in ['anonymous_id', 'complete_proof',
                'ancillary_math_error', 'decisive_step', 'grade_source']} for r in group])
    save(RUNTIME / 'grading/anonymous-duplicate-conflicts.json', conflicts)
    print(json.dumps({'graded_rows': len(rows), 'distinct_answers': len(groups),
                      'duplicate_conflicts': conflicts}, ensure_ascii=False))
    if not args.publish:
        return
    assert not conflicts, 'Adjudicate anonymous duplicate conflicts before publishing'
    primary = [r for r in rows if r['condition'] in ['code', 'numeric'] and not r['reference_only']]
    base = [r for r in rows if r['condition'] == 'base']
    assert len(primary) == 40 and len(base) == 20
    assert len({r['job_id'] for r in base}) == 20
    original_path = HERE / 'base-proof-grades.pre-calibration.json'
    if not original_path.exists():
        original_path.write_bytes((HERE / 'base-proof-grades.json').read_bytes())
    original = {r['job_id']: r for r in read(original_path)}
    changes = []
    for row in base:
        old = original[row['job_id']]
        assert old['raw_sha256'] == row['raw_sha256']
        if (old['complete_proof'], bool(old['ancillary_math_error'])) != (row['complete_proof'], bool(row['ancillary_math_error'])):
            changes.append({'job_id': row['job_id'], 'anonymous_id': row['anonymous_id'],
                            'old': old, 'recalibrated': row})
    save(HERE / 'base-proof-grades.json', base)
    save(HERE / 'proof-grades-unblinded.json', primary)
    save(HERE / 'grading-calibration.json', {'all_rows': rows, 'baseline_changes': changes,
         'scope': 'All 20 base and 40 new proofs blindly graded; eight new outputs graded twice for consistency. Original old-study artifacts unchanged.'})
    print(json.dumps({'published_new': len(primary), 'published_base': len(base),
                      'baseline_changed_rows': len(changes)}))


if __name__ == '__main__':
    main()
