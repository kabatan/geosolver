"""Check joins, count denominators, and AST-based dependency depths independently."""
from __future__ import annotations

import ast
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def loadcsv(path):
    with path.open() as h:
        return list(csv.DictReader(h))


def main():
    cases = [json.loads(s) for s in (ROOT / 'benchmarks/cases.jsonl').read_text().splitlines()]
    features = {r['case_id']: r for r in loadcsv(HERE / 'exploration-per-problem.csv')}
    assert len(features) == len(cases) == 323
    profile = loadcsv(ROOT / 'jssa/results/stage-profile-20261023/per-case.csv')
    assert len(profile) == len({(r['case_id'], r['seed']) for r in profile}) == 969
    assert set(Counter(r['case_id'] for r in profile).values()) == {3}
    assert sum(r['correct'] == 'True' for r in profile) == 953
    unmatched, parse_fail, cycles, changed = [], [], [], []
    for case in cases:
        dsl = case['dsl']
        cons = {c['name']: c['expression'] for c in dsl['constructions']}
        assert int(float(features[case['id']]['n_cons'])) == len(cons)
        assert int(float(features[case['id']]['n_vars'])) == len(dsl['variables'])
        deps = {}
        for name, expr in cons.items():
            try:
                tree = ast.parse(expr, mode='eval')
                deps[name] = {x.id for x in ast.walk(tree) if isinstance(x, ast.Name)} & set(cons)
            except SyntaxError:
                parse_fail.append((case['id'], name, expr))
        levels = {}
        while len(levels) < len(deps):
            todo = [name for name, ds in deps.items() if name not in levels and ds <= set(levels)]
            if not todo:
                cycles.append(case['id'])
                break
            for name in todo:
                levels[name] = 1 + max([levels[k] for k in deps[name]] or [0])
        depth = max(levels.values(), default=0)
        if depth != int(float(features[case['id']]['construction_depth'])):
            changed.append((case['id'], depth, features[case['id']]['construction_depth']))
    assert not parse_fail, parse_fail
    assert not cycles, cycles
    assert not changed, changed
    source = loadcsv(HERE / 'human-source-join.csv')
    assert len(source) == len({r['case_id'] for r in source}) == 131
    max_rating_difference = max(abs(float(r['rating_difference'])) for r in source)
    assert max_rating_difference < 1e-12
    totals = {}
    for seed, directory in [(0, 'raw-323'), (1, 'raw-323-seed1')]:
        n, hits, varying, zero = 0, 0, 0, 0
        for case in cases:
            a = json.loads((ROOT / 'jssa/difficulty/minima' / directory / (case['id'] + '.json')).read_text())
            rs = a.get('records', [])
            assert int(float(features[case['id']][f'n{seed}'])) == len(rs)
            h = sum(r.get('cls') == 'hit' for r in rs)
            assert h == int(float(features[case['id']][f'h{seed}']))
            if rs:
                assert len(rs) == a['starts_done']
                assert len(rs) == sum(a['counts'].values())
                assert sum(a['hits_by_ref']) == h
                assert len({r['k'] for r in rs}) == len(rs)
                varying += 1
                zero += h == 0
            n += len(rs)
            hits += h
        totals[str(seed)] = {'nonempty_problems': varying, 'starts': n, 'hits': hits, 'no_hits': zero}
    hashes = json.loads((HERE / 'input-sha256.json').read_text())
    for path, expected in hashes.items():
        actual = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        assert actual == expected, path
    result = {'ok': True, 'cases': 323, 'full_solver_runs': 969, 'full_solver_correct': 953,
              'human_join': 131, 'max_rating_difference': max_rating_difference,
              'independent_ast_depth_matches': 323, 'ast_parse_failures': 0,
              'dependency_cycles': 0, 'source_hashes_checked': len(hashes), 'local_records': totals,
              'limits': ['This checks calculations and joins, not causal identification or external validity.']}
    (HERE / 'verification.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
