"""Private audit of constructed labels; these identities NEVER generate data/prompts.

Run after the complete case files are frozen. A mismatch is an oracle audit
failure, not grounds to select individual cases based on a desired relation.
"""
import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path


def known_check(cid, g):
    if cid == "H01":
        return g["AM"] - g["BC"] ** 2 / (4 * g["AM"])
    if cid == "H04":
        return math.sqrt(g["BT"] * (g["BT"] + g["BC"]))
    if cid == "H07":
        return g["AB"] * g["MF"] * (1 - g["AB"] ** 2 / (4 * g["ON"] ** 2))
    if cid == "H13":
        return g["BK"] / (2 * math.sqrt(1 - g["cos_ACB"] ** 2))
    if cid == "H14":
        return g["AR"] * math.sqrt(g["AH"] ** 2 - g["AR"] ** 2) / 2
    if cid == "H15":
        return math.sqrt((g["AB"] ** 2 + g["BD"] ** 2) / 2 - g["AD"] ** 2 / 4)
    if cid == "DA01":
        return g["AB"] * g["CA"] / math.sqrt(2 * g["AB"] ** 2 + 2 * g["CA"] ** 2 - g["BC"] ** 2)
    if cid == "DA05":
        return g["BC"] ** 2 / (4 * g["MD"]) - g["MD"]
    raise ValueError(cid)


def load(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def main(args):
    rows, public = load(args.private), load(args.public)
    assert len(rows) == 448 and len(public) == 64
    assert len({x['case_id'] for x in rows}) == len(rows)
    by_id = {x['case_id']: x for x in rows}
    counts = Counter((x['source_id'], x['split']) for x in rows)
    for source in sorted({x['source_id'] for x in rows}):
        assert {split: counts[source, split] for split in ['visible', 'repair', 'selection', 'final']} == {
            'visible': 4, 'repair': 4, 'selection': 24, 'final': 24}
    for x in public:
        assert x['split'] in ('visible', 'repair') and 'private_witness' not in x
        expected = by_id[x['case_id']]
        assert all(x[k] == expected[k] for k in ['source_id', 'split', 'givens', 'answer'])
    events = []
    for x in rows:
        assert all(isinstance(v, (int, float)) and math.isfinite(v) for v in x['givens'].values())
        assert math.isfinite(x['answer']) and x['answer'] > 0
        checked = known_check(x['source_id'], x['givens'])
        err = abs(checked - x['answer'])
        events.append({'case_id': x['case_id'], 'source_id': x['source_id'],
                       'absolute_error': err, 'relative_error': err / max(abs(x['answer']), 1e-12),
                       'pass': err <= 1e-8 + 1e-8 * abs(x['answer'])})
    result = {'status': 'pass' if all(x['pass'] for x in events) else 'fail',
              'case_count': len(rows), 'public_case_count': len(public),
              'scope': 'Known theorem identities are used only for this private post-generation audit. No model prompts, label generation, sampling or case filtering use this script.',
              'hashes': {str(p): hashlib.sha256(Path(p).read_bytes()).hexdigest()
                         for p in [args.private, args.public, __file__]},
              'max_relative_error': max(x['relative_error'] for x in events), 'events': events}
    Path(args.out).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('events', 'hashes')}))
    assert result['status'] == 'pass', 'Investigate oracle discrepancy; do not silently filter cases.'


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--private', required=True)
    ap.add_argument('--public', required=True)
    ap.add_argument('--out', required=True)
    main(ap.parse_args())
