"""Join completed anonymous grades to their key and apply recorded adjudication."""
import argparse
import hashlib
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--waves', type=Path, nargs='+', required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    result = []
    anchor_result = []
    seen = set()
    for wave in a.waves:
        key = {x['anonymous_id']: x for x in read(wave/'private-unblinding.json')}
        reviews = {x['anonymous_id']: x for x in read(wave/'root-review.json')} \
            if (wave/'root-review.json').exists() else {}
        grades = []
        for packet in (1, 2):
            path = wave/f'grades-packet-{packet}.json'
            rows = read(path)
            expected = {x['anonymous_id'] for x in read(wave/f'packet-{packet}.json')}
            assert {x['anonymous_id'] for x in rows} == expected, (path, 'Incomplete or duplicate packet')
            assert len(rows) == len(expected)
            grades.extend({**x, 'grade_source': str(path.resolve()),
                           'grader': 'gpt-6-luna(max)' if packet == 1 else 'gpt-6-sol(high)'}
                          for x in rows)
        assert {x['anonymous_id'] for x in grades} == set(key)
        for grade in grades:
            anon = grade['anonymous_id']
            identity = key[anon]
            pair = identity['condition'], identity['job_id']
            raw = Path(identity['raw_file'])
            assert hashlib.sha256(raw.read_bytes()).hexdigest() == identity['raw_sha256']
            reference_only = bool(identity.get('reference_only', False))
            row = {**grade, **identity, 'reference_only': reference_only,
                   'wave': str(wave.resolve())}
            if reference_only:
                # Keep the original grader record for calibration auditing. Do
                # not mix it into primary metrics or apply root adjudication.
                anchor_result.append(row)
                continue
            assert pair not in seen, ('Duplicate condition/job', pair)
            seen.add(pair)
            if anon in reviews:
                review = reviews[anon]
                row['pre_adjudication_complete_proof'] = grade['complete_proof']
                row['pre_adjudication_ancillary_math_error'] = grade['ancillary_math_error']
                row['complete_proof'] = review['root_complete_proof']
                row['ancillary_math_error'] = review['root_ancillary_math_error']
                row['root_review'] = review
            result.append(row)
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    anchor_out = a.out.with_name(f'{a.out.stem}.anchors{a.out.suffix or ".json"}')
    anchor_out.write_text(json.dumps(anchor_result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'grades': len(result), 'out': str(a.out),
                      'anchor_grades': len(anchor_result), 'anchor_out': str(anchor_out)}))


if __name__ == '__main__':
    main()
