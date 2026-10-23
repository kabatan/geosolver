"""Freeze selection before any sweep solve; uses no performance observations."""
from __future__ import annotations

import ast
import datetime as dt
import os
import subprocess
import tempfile

from common import *

POINT_CALLS = {'Point', 'Intersect', 'IntersectLines', 'Midpoint', 'FootOfPerpendicular',
               'PointOnSegment', 'PointOnLine', 'PointOnCircle', 'Circumcenter', 'Incenter',
               'Reflect', 'Centroid', 'ContactPoint', 'IncircleContactPoint', 'Orthocenter',
               'Center', 'Rotate'}
POOLS = [('development', 'benchmarks/cases.jsonl', 10),
         ('unseen_a', 'jssa/difficulty/unseen-2/a/cases.jsonl', 5),
         ('unseen_b', 'jssa/difficulty/unseen-2/b/cases.jsonl', 5)]


def point_names(dsl):
    result = []
    for item in dsl['constructions']:
        expr = ast.parse(item['expression'], mode='eval').body
        if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name) and expr.func.id in POINT_CALLS:
            result.append(item['name'])
    return result


def main():
    assert not (BASE / 'selection.json').exists(), 'Do not replace an existing selection.'
    source = verify_source()
    assert not subprocess.check_output(['git', 'diff', FROZEN, '--', 'src'], cwd=ROOT)
    probe = 'import geosolver,json;from geosolver.runtime.integrity import source_tree_hash;print(json.dumps(dict(import_file=geosolver.__file__,source_hash=source_tree_hash())))'
    with tempfile.TemporaryDirectory(prefix='q43c-import-') as td:
        child = json.loads(subprocess.check_output([str(PYTHON), '-B', '-c', probe], env=environment(), cwd=td))
    assert child == source
    from geosolver import GeometryProblem, validate
    selected, excluded, pools = [], [], []
    for label, filename, count in POOLS:
        rows = [json.loads(x) for x in (ROOT / filename).read_text().splitlines()]
        eligible = []
        for row in rows:
            names = point_names(row['dsl'])
            if len(names) < 3:
                excluded.append({'pool': label, 'id': row['id'], 'reason': 'fewer than three static point constructions'})
            else:
                eligible.append(row)
        ordered = sorted(eligible, key=lambda r: (rank(label, r['id']), r['id']))
        pools.append({'pool': label, 'path': filename, 'sha256': sha(ROOT / filename),
                      'total': len(rows), 'eligible': len(eligible), 'selected': count,
                      'reserved_ids': [r['id'] for r in ordered[count:]]})
        for row in ordered[:count]:
            cid, dsl = row['id'], row['dsl']
            points = sorted(point_names(dsl), key=lambda n: (rank('points:' + cid, n), n))
            p, q, r = points[:3]
            targets = {'original': dsl['target'], 'length': f'Distance({p}, {q})',
                       'area': f'Area({p}, {q}, {r})', 'angle': f'Angle({p}, {q}, {r})',
                       'ratio': f'Distance({p}, {q}) / Distance({q}, {r})'}
            files = {}
            for kind, target in targets.items():
                variant = dsl | {'target': target}
                assert {k: v for k, v in variant.items() if k != 'target'} == {k: v for k, v in dsl.items() if k != 'target'}
                report = validate(GeometryProblem.model_validate(variant))
                files[kind] = {'path': f'inputs/{cid}/{kind}.json', 'target': target,
                               'valid': report.valid, 'validation': report.model_dump(mode='json') if not report.valid else None,
                               'dsl_sha256': digest(variant)}
                save(BASE / files[kind]['path'], variant)
            selected.append({'id': cid, 'pool': label, 'source_cases': filename,
                             'selection_rank': rank(label, cid), 'n_vars': len(dsl['variables']),
                             'point_order': points, 'triple': [p, q, r], 'variants': files})
            save(BASE / 'references' / f'{cid}.json', {'answer': row['answer'], 'source': row.get('source'),
                                                     'truth_status': row.get('truth_status', 'development benchmark reference')})
    # Deterministic interleaving within every problem/seed; no result-dependent scheduling.
    jobs = []
    for seed in SEEDS:
        for case in sorted(selected, key=lambda c: rank('schedule:' + str(seed), c['id'])):
            for kind in sorted(KINDS, key=lambda k: rank(f'kind:{seed}:{case["id"]}', k)):
                jobs.append({'index': len(jobs), 'id': case['id'], 'pool': case['pool'], 'kind': kind,
                             'seed': seed, 'input': case['variants'][kind]['path'], 'time_limit_seconds': 180})
    allowed = sorted(os.sched_getaffinity(0))
    physical = {}
    for cpu in allowed:
        folder = Path(f'/sys/devices/system/cpu/cpu{cpu}/topology')
        key = ((folder / 'physical_package_id').read_text().strip(), (folder / 'core_id').read_text().strip())
        physical.setdefault(key, cpu)
    cpus = sorted(physical.values())[-3:]
    from geosolver.runtime.integrity import installed_dependencies
    save(BASE / 'selection.json', {'created_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
         'task': 'Q43c', 'selection_seed': SELECTION_SEED, 'solver_seeds': SEEDS,
         'rule': 'Within each pool sort SHA256(431024:pool:id), take 10/5/5. Eligible iff >=3 statically point-returning constructions. Sort points by SHA256(431024:points:id:name), take first three. No outcome-based exclusion or replacement.',
         'point_calls': sorted(POINT_CALLS), 'pools': pools, 'excluded': excluded,
         'cases': selected, 'planned_runs': len(jobs), 'parallelism': 3, 'cpus': cpus,
         'source': source, 'child_import_probe': child, 'frozen_commit': FROZEN,
         'src_diff_vs_frozen_empty': True, 'runtime_dependencies': installed_dependencies(),
         'raw_directory': str(RAW), 'loadavg_at_freeze': os.getloadavg(),
         'heldout_note': 'unseen_a/b are post-freeze input pools, already used by other tasks. They are fresh for target swapping, not globally untouched confirmation data.',
         'prediction_preregistered': False})
    save(BASE / 'schedule.json', jobs)
    print(json.dumps({'cases': [(c['id'], c['n_vars'], c['triple']) for c in selected],
                      'jobs': len(jobs), 'cpus': cpus, 'invalid_variants': sum(not v['valid'] for c in selected for v in c['variants'].values())}, ensure_ascii=False))


if __name__ == '__main__':
    main()
