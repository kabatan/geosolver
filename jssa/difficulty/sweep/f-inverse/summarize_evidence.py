"""Summarize existing Q43f evidence only; never launch a solver or change grading."""
from __future__ import annotations

import csv
import hashlib
import itertools
import json
import statistics as st
from collections import Counter
from pathlib import Path

import figures as f
from mpmath import mp

HERE = Path(__file__).resolve().parent
RAW = Path('/tmp/q43f-inverse-20261024/production-180')


def load(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = load(HERE / 'manifest.json')
    assert f.source_tree_hash() == manifest['source_hash']
    # Preserve the original experiment, exact grader, and verification program.
    unchanged = {
        'manifest.json': 'af6cbd9d3b3750df8d6f9e80e214185726856b601cf6cecfae50918bf504e4af',
        'run.py': '3d00a6686891ea4f85f2e329f55265626a5e4c21588e9979f0249363e3b6667d',
        'prepare.py': 'd47d20c649ebfdbfa44eb5c132803c31561d1800160e810982772a9bc6badd6b',
        'analyze.py': 'c4ac70d798969551a7a69165e46b1110465108c01c80d510a0242350b3b066a5',
        'verify.py': '2d042750a1ee95d9beafe0f2a67347f11d6c28c50284a152538aa55821b1cbdb',
    }
    for name, digest in unchanged.items():
        assert sha(HERE / name) == digest, name
    rows = list(csv.DictReader((HERE / 'per-run.csv').open()))
    arms = list(csv.DictReader((HERE / 'per-arm.csv').open()))
    inverse = [r for r in arms if r['arm'] != 'forward']
    receipts = [load(p) for p in sorted(RAW.glob('runs/*/*/*.receipt.json'))]
    expected = {(i['id'], i['arm'], s) for i in manifest['inputs'] for s in manifest['solver_seeds']}
    assert {(r['id'], r['arm'], r['seed']) for r in receipts} == expected
    assert len(receipts) == len(rows) == 228
    assert len(list(RAW.glob('runs/*/*/*.solver.json'))) == 228
    assert not list(RAW.glob('runs/*/*/*.tmp'))
    cases = list(dict.fromkeys(i['id'] for i in manifest['inputs']))
    ordered = []
    for seed in manifest['solver_seeds']:
        for cid in sorted(cases, key=lambda s: hashlib.sha256(f'order:{seed}:{s}'.encode()).hexdigest()):
            case_arms = [i for i in manifest['inputs'] if i['id'] == cid]
            offset = seed % len(case_arms)
            ordered.extend((i['id'], i['arm'], seed) for i in case_arms[offset:] + case_arms[:offset])
    for r in receipts:
        assert ordered[r['ordinal']] == (r['id'], r['arm'], r['seed'])
    initial = RAW.parent / 'runs'
    initial_receipts = [load(p) for p in initial.glob('*/*/*.receipt.json')]
    initial_errors = [p.read_text() for p in initial.glob('*/*/*.stderr.txt')]
    assert len(initial_receipts) == len(initial_errors) == 228
    assert all(r['status'] == 'artifact_missing' and r['returncode'] == 1 for r in initial_receipts)
    assert all('time_limit_seconds must be between 180 and 900' in s for s in initial_errors)

    def raw(cid, arm, seed):
        p = RAW / 'runs' / cid / arm / f'{seed}.solver.json'
        return p, load(p)

    def metrics(cid, arm):
        a = next(a for a in arms if a['id'] == cid and a['arm'] == arm)
        return {k: json.loads(a[k]) for k in (
            'recovered', 'seconds_by_seed', 'ratios_by_seed', 'cpu_ratios_by_seed',
            'reference_hits_by_seed', 'values_by_seed')}

    collapse = []
    for seed in manifest['solver_seeds']:
        p, result = raw('JMO-2018-PRE-06', 'inverse-06', seed)
        cs = result['diagnostics']['candidate_records']
        for c in cs:
            with mp.workdps(80):
                v = list(map(mp.mpf, c['x_hp']))
                points = [v[k:k+2] for k in (0, 2, 4)]
                distances = [mp.sqrt(sum((x-y)**2 for x, y in zip(a, b)))
                             for a, b in itertools.combinations(points, 2)]
                collapse.append(dict(seed=seed, candidate_uid=c['candidate_uid'],
                    accepted=c['accepted'], refinement_status=c['refinement_status'],
                    min_XYZ_distance=mp.nstr(min(distances), 16),
                    max_XYZ_distance=mp.nstr(max(distances), 16),
                    max_XYZ_distance_over_ABC_diameter=mp.nstr(max(distances)/mp.sqrt(2), 16),
                    AX=mp.nstr(mp.sqrt(v[0]**2+v[1]**2), 30),
                    raw_path=str(p), raw_sha256=sha(p)))

    hmmt_candidates = []
    for arm in ('forward', 'inverse-01'):
        for seed in manifest['solver_seeds']:
            p, result = raw('HMMT-2014-FEB-GEO-04', arm, seed)
            cs = result['diagnostics']['candidate_records']
            hmmt_candidates.append(dict(arm=arm, seed=seed, candidates=len(cs),
                accepted=sum(bool(c['accepted']) for c in cs),
                refinement_statuses=dict(Counter(c['refinement_status'] for c in cs)),
                raw_path=str(p), raw_sha256=sha(p)))

    # The main figure observer merges mirror images by pairwise distances.
    # Retain both scalar-answer branches here, without altering that metric.
    cid = 'AIME-2014-I-10'
    inputs = {i['arm']: i for i in manifest['inputs'] if i['id'] == cid}
    _, _, base_ev = f.build_input(inputs['forward'])
    _, bundle, evaluator = f.build_input(inputs['inverse-00'])
    mirror_branches = []
    for seed in manifest['solver_seeds']:
        p, result = raw(cid, 'inverse-00', seed)
        seen = set()
        for c in result['diagnostics']['candidate_records']:
            if not c['accepted']:
                continue
            key = mp.nstr(mp.mpf(c['answer_hp']), 12)
            if key in seen:
                continue
            seen.add(key)
            checked = f.evaluate_figure(bundle, evaluator, base_ev, c)
            assert checked['verified_numerically']
            mirror_branches.append(dict(seed=seed, raw_path=str(p), raw_sha256=sha(p), **checked))
        assert len(seen) == 2

    structure = load(HERE / 'structure.json')
    result = dict(
        unchanged_original_bytes=unchanged,
        problem_count=24, inverse_conditions=52, seeds=manifest['solver_seeds'],
        completed_production_runs=228, missing_runs=0, interrupted_trials_missing=0,
        fixed_order_verified=True, initial_validation_failures=228, total_attempts=456,
        production_completion=load(RAW / 'completion.json'),
        first_started_utc=min(r['started_utc'] for r in receipts),
        production_source_hashes=dict(Counter(r['executed_source_hash'] for r in receipts)),
        production_import_roots=dict(Counter(r['executed_import_root'] for r in receipts)),
        load_1min_min=min(r['load_start'][0] for r in receipts),
        load_1min_max=max(r['load_start'][0] for r in receipts),
        inverse_all_three_seeds_recovered=sum(int(a['recovered']) == 3 for a in inverse),
        inverse_all_three_seeds_same_returned_set=sum(a['same_returned_set_all_seeds'] == 'True' for a in inverse),
        problems_with_any_reference_miss=sorted({a['id'] for a in inverse if int(a['recovered']) < 3}),
        problems_with_other_values=sorted({a['id'] for a in inverse if int(a['other_value_runs'])}),
        inverse_conditions_with_other_values=sum(int(a['other_value_runs']) > 0 for a in inverse),
        median_of_condition_paired_capped_time_ratios=st.median(float(a['median_time_ratio']) for a in inverse),
        time_definition='Observed run completion time, not first discovery time; use 180 seconds for known-value non-recovery.',
        jmo_collapse_candidates=collapse,
        hmmt_candidate_counts=hmmt_candidates,
        selected_metrics={cid + '/' + arm: metrics(cid, arm) for cid, arm in (
            ('JMO-2018-PRE-06', 'forward'), ('JMO-2018-PRE-06', 'inverse-06'),
            ('HMMT-2014-FEB-GEO-04', 'forward'), ('HMMT-2014-FEB-GEO-04', 'inverse-01'),
            ('HMMT-2020-FEB-GUTS-13', 'forward'), ('HMMT-2020-FEB-GUTS-13', 'inverse-00'),
            ('HMMT-2020-FEB-GUTS-13', 'inverse-01'),
            ('AIME-2014-I-10', 'forward'), ('AIME-2014-I-10', 'inverse-00'))},
        selected_search_bounds=[{k: r[k] for k in ('id', 'arm', 'variables', 'bounds')}
                               for r in structure if r['id'] in ('JMO-2018-PRE-06', 'HMMT-2014-FEB-GEO-04')],
        aime_mirror_answer_branches=mirror_branches,
        limitations=[
            'Exploratory results only; repeated seeds are not independent problems.',
            'The JMO inverse also changes inferred search bounds; collapse alone is not an isolated cause.',
            '80-digit substitution is numerical evidence, not an exhaustive or symbolic proof.',
            'The geometric signature merges reflections; scalar answer branches are retained separately here.',
        ],
    )
    f.save(HERE / 'evidence-summary.json', result)
    print(json.dumps({k: result[k] for k in ('completed_production_runs', 'missing_runs',
        'inverse_all_three_seeds_recovered', 'problems_with_other_values',
        'load_1min_min', 'load_1min_max')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
