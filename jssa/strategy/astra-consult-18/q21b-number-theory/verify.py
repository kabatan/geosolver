"""Independent accounting and exact recoding checks for the Q21b artifacts."""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path

import sympy as sp

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(name):
    with (OUT / name).open() as f:
        return list(csv.DictReader(f))


def primitive(expr, x):
    p = sp.Poly(expr, x, domain=sp.QQ).clear_denoms()[1]
    p = p.primitive()[1]
    if p.LC() < 0:
        p = -p
    return [int(c) for c in p.all_coeffs()]


manifest = json.loads((OUT / 'manifest.json').read_text())
checks = {}
for group in ['source_hashes', 'input_hashes']:
    changed = [name for name, expected in manifest[group].items()
               if not (ROOT / name).exists() or sha(ROOT / name) != expected]
    assert not changed, (group, changed)
    checks[group] = {'checked': len(manifest[group]), 'changed': changed}
saved_manifest = json.loads((OUT / 'saved-candidate-manifest.json').read_text())
changed = [r['path'] for r in saved_manifest if sha(ROOT / r['path']) != r['sha256']]
assert not changed, changed
checks['saved_inputs'] = {'checked': len(saved_manifest), 'changed': changed}
assert sha(OUT / 'protocol.md') == manifest['protocol_sha256']
assert sha(OUT / 'analyze.py') == manifest['script_sha256_at_census']

values = json.loads((OUT / 'values.json').read_text())
algebraic = [v for v in values if 'coefficients' in v]
index = {(v['id'], v['answer_index']): v for v in algebraic}
assert len(values) == 338 and len(algebraic) == 331
assert len({v['id'] for v in values}) == 323
assert len({v['id'] for v in algebraic}) == 316
assert all(v['status'] == 'ok' for v in values)
checks['census'] = {'problems': 323, 'values': 338, 'algebraic_values': 331}

raw = [json.loads(line) for line in (OUT / 'precision.jsonl').read_text().splitlines()]
by_p = defaultdict(list)
by_id = defaultdict(dict)
for r in raw:
    by_p[r['precision']].append(r)
    by_id[r['id'], r['answer_index']][r['precision']] = r
    expected = index[r['id'], r['answer_index']]['coefficients']
    assert (r['status'] == 'correct') == (r['got'] == expected)
assert len(raw) == 3310
assert all(len(group) == 331 for group in by_p.values())
for row in read_csv('precision-summary.csv'):
    p = int(row['precision'])
    counts = Counter(r['status'] for r in by_p[p])
    for status in ['correct', 'wrong', 'none']:
        assert counts[status] == int(row[status + '_values'])
    per_problem = defaultdict(list)
    for r in by_p[p]:
        per_problem[r['id']].append(r['status'] == 'correct')
    assert sum(all(results) for results in per_problem.values()) == int(row['correct_problems'])
checks['precision'] = {'calls': len(raw), 'all_rows_and_aggregates_agree': True}

x = sp.Symbol('x')
recoded = json.loads((OUT / 'recoding-replay.json').read_text())
unique = {(r['id'], r['answer_index'], r['q']): r for r in recoded}
blocked = []
for (case_id, j, q), r in unique.items():
    v = index[case_id, j]
    d = v['degree']
    poly = sp.Poly.from_list(v['coefficients'], x).as_expr()
    shifted = poly if q == 1 else sp.expand(q**d * poly.subs(x, x-sp.Rational(1, q)))
    assert primitive(shifted, x) == r['expected']
    assert len(r['expected']) - 1 == d
    assert r['height'] == max(map(abs, r['expected']))
    if r['blocked_by_q_power']:
        assert sp.isprime(q) and 10 % q != 0 and v['coefficients'][0] % q != 0
        assert q**d > 10**8
        # This wider fixed scale grid is separate from the implementation's scale choice.
        for k in range(-6, 7):
            scaled = primitive(shifted.subs(x, sp.Rational(10)**k*x), x)
            assert scaled[0] % q**d == 0
        assert all(a['status'] != 'correct' for a in recoded
                   if (a['id'], a['answer_index'], a['q']) == (case_id, j, q))
        blocked.append([case_id, q])
checks['recoding'] = {'unique_targets': len(unique), 'exact_transform_matches': True,
                      'blocked_targets': blocked, 'checked_scales_per_blocked_target': 13}

reversals = read_csv('bound-reversals.csv')
bounds = json.loads((OUT / 'bound-experiment.json').read_text())
lookup = {(r['id'], r['precision'], r['coefficient_bound']): r for r in bounds}
for r in reversals:
    a = lookup[r['id'], int(r['precision']), int(r['low_B'])]
    b = lookup[r['id'], int(r['precision']), int(r['high_B'])]
    assert a['eligible'] and b['eligible'] and a['status'] == 'correct' and b['status'] == 'wrong'
checks['bound_reversals'] = {'comparisons': len(reversals),
                            'problems': len({r['id'] for r in reversals}),
                            'problem_precision_pairs': len({(r['id'], r['precision']) for r in reversals})}
final = read_csv('final-verifier.csv')
assert len(final) == 8 and all(r['accepted'] == 'False' for r in final)
checks['final_verifier'] = {'checked': len(final), 'rejected': 8}

summary = json.loads((OUT / 'summary.json').read_text())
assert summary['protocol_hash'] == sha(OUT / 'protocol.md')
assert summary['followup_protocol_hash'] == sha(OUT / 'followup-protocol.md')
assert sum(int(r['n']) for r in read_csv('human-strata.csv')) == 131
assert not any(p.stat().st_size > 8 * 1024 * 1024 for p in OUT.rglob('*') if p.is_file())
checks['protocol_hashes_unchanged'] = True
checks['each_artifact_under_8_MiB'] = True
checks['status'] = 'PASS'
(OUT / 'verification.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(checks, ensure_ascii=False))
