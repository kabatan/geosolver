"""Posthoc integrity, returned-point policy and initial-feasibility audit.

Reads references only for offline grading. Does not call an optimizer.
"""
import csv
import hashlib
import importlib.metadata
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone

import numpy as np
from geosolver import GeometryProblem
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from analyze import answer_float, reference_values, write_csv
from campaign import verify
from experiment import OUT, ARMS, dump


def main():
    verify()
    selected = json.loads((OUT/'selection.json').read_text())
    primary = list(csv.DictReader((OUT/'per-start.csv').open()))
    rowmap = {(r['id'], int(r['seed']), int(r['k']), r['arm']): r for r in primary}
    endpoint_rows = []
    strata = defaultdict(lambda: {'n': 0, 'N_hits': 0, 'L_hits': 0})
    resources = defaultdict(lambda: {'n': 0, 'evals': [], 'seconds': [], 'outside_evals': 0, 'invalid_evals': 0, 'native_time_stops': 0, 'any_time_stop': 0})
    first_exact = first_total = prepared = 0
    first_error = 0.0
    sources = Counter()
    loadavg = []
    raw_count = 0
    failures = []
    for case in selected:
        cid = case['id']
        inp = json.loads((OUT/'inputs'/f'{cid}.json').read_text())
        bounds = np.asarray(inp['bounds'])
        b = load_problem_bundle(GeometryProblem.model_validate(inp['dsl']).engine_document())
        ev = build_ir_evaluator(b)
        refs = reference_values(json.loads((OUT/'grading'/f'{cid}.json').read_text())['answer'])
        for start in inp['starts']:
            seed, k = start['seed'], start['k']
            raw = json.loads((OUT/'runs'/cid/f'{seed}-{k}.json').read_text())
            assert raw['complete'] and len(raw['arms']) == len(ARMS)
            assert {r['arm'] for r in raw['arms']} == set(ARMS)
            assert raw['x0'] == start['x']
            assert raw['budget'] == 1200 and raw['time_cap'] == 6
            assert raw['input_sha256'] == hashlib.sha256((OUT/'inputs'/f'{cid}.json').read_bytes()).hexdigest()
            raw_count += 1
            prepared += raw['scale_probes']
            loadavg.append(raw['loadavg'][0])
            base = next(r for r in raw['arms'] if r['arm'] == 'N')['first_points'][0]
            stratum = 'invalid' if not base['valid'] else 'valid_feasible' if base['feasible'] else 'valid_infeasible'
            s = strata[(case['group'], stratum)]
            s['n'] += 1
            for arm in ['N', 'L']:
                s[f'{arm}_hits'] += int(rowmap[(cid, seed, k, arm)]['hit'])
            for arm in raw['arms']:
                a = arm['arm']
                assert 0 <= arm['evals'] <= 1200
                if a != 'Ls' and arm['first_points']:
                    err = float(np.max(np.abs(np.asarray(arm['first_points'][0]['x']) - np.asarray(start['x']))))
                    first_total += 1
                    first_exact += err == 0
                    first_error = max(first_error, err)
                if arm['best'] is not None:
                    x = np.asarray(arm['best']['x'])
                    assert np.all(x >= bounds[:, 0]) and np.all(x <= bounds[:, 1])
                nr = arm.get('native_result')
                native_time = isinstance(nr, dict) and 'allowed time' in nr.get('stop_reason', '')
                rs = resources[(case['group'], a)]
                rs['n'] += 1
                rs['evals'].append(arm['evals'])
                rs['seconds'].append(arm['seconds'])
                rs['outside_evals'] += arm['outside']
                rs['invalid_evals'] += arm['invalid']
                rs['native_time_stops'] += native_time
                rs['any_time_stop'] += native_time or arm['status'] == 'time_cap'
                if arm['status'].endswith('error'):
                    failures.append({'id': cid, 'seed': seed, 'k': k, 'arm': a, 'status': arm['status'], 'detail': nr})
                x = arm.get('final_x')
                if x is not None and len(x) != len(start['x']):
                    x = None  # Empty native x_best means no returned point.
                valid = feasible = inside = hit = coarse = False
                res = value = None
                if x is not None:
                    xx = np.asarray(x)
                    inside = bool(np.all(xx >= bounds[:, 0]) and np.all(xx <= bounds[:, 1]))
                    rr = ev.evaluate_float_residual(x)
                    res = float(rr.residual_norm_float)
                    valid = bool(rr.is_finite and math.isfinite(res))
                    feasible = bool(valid and ev.evaluate_guard(x)[0] and ev.evaluate_float_hard_feasibility(x, include_margins=False).hard_feasible)
                    coarse = bool(feasible and inside and res <= 1e-4)
                    if coarse:
                        value = answer_float(ev, x)
                    hit = bool(feasible and inside and res <= 1e-8 and value is not None and math.isfinite(value) and any(abs(value-r) <= 1e-6*max(1., abs(r)) for r in refs))
                p = rowmap[(cid, seed, k, a)]
                endpoint_rows.append({'id': cid, 'group': case['group'], 'seed': seed, 'k': k, 'arm': a, 'initial_stratum': stratum, 'primary_hit': int(p['hit']), 'final_hit': int(hit), 'final_coarse': int(coarse), 'final_res': res if res is None or math.isfinite(res) else None, 'final_value': value, 'final_valid': valid, 'final_feasible': feasible, 'final_inside': inside, 'has_final': x is not None})
    write_csv('endpoint-audit.csv', endpoint_rows)
    resource_rows = []
    for (group, a), r in resources.items():
        resource_rows.append({'group': group, 'arm': a, 'n': r['n'], 'mean_evals': float(np.mean(r['evals'])), 'median_evals': float(np.median(r['evals'])), 'max_evals': max(r['evals']), 'mean_seconds': float(np.mean(r['seconds'])), 'max_seconds': max(r['seconds']), 'outside_evals': r['outside_evals'], 'invalid_evals': r['invalid_evals'], 'native_time_stops': r['native_time_stops'], 'any_time_stop': r['any_time_stop']})
    write_csv('resource-summary.csv', resource_rows)
    policy = []
    for group in ['hard', 'control']:
        for a in ARMS:
            r = [r for r in endpoint_rows if r['group'] == group and r['arm'] == a]
            policy.append({'group': group, 'arm': a, 'n': len(r), 'primary_hits': sum(x['primary_hit'] for x in r), 'final_hits': sum(x['final_hit'] for x in r), 'final_coarse': sum(x['final_coarse'] for x in r), 'final_outside': sum(x['has_final'] and not x['final_inside'] for x in r), 'missing_final': sum(not x['has_final'] for x in r)})
    dump(OUT/'endpoint-summary.json', {'posthoc': True, 'optimization_calls': 0, 'policy': policy, 'initial_strata': [{'group': g, 'stratum': s, **v} for (g, s), v in strata.items()]})
    receipts = [json.loads(p.read_text()) for p in (OUT/'receipts').glob('*.json')]
    assert sum(len(r['runs']) for r in receipts) == raw_count
    assert all(r['workers_max'] <= 3 for r in receipts)
    assert all(x['status'] == 0 for r in receipts for x in r['runs'])
    for r in receipts:
        for run in r['runs']:
            sources[run.get('experiment_sha256', 'not_recorded_in_pre_amendment_receipt')] += 1
    sizes = [(p.stat().st_size, str(p.relative_to(OUT))) for p in OUT.rglob('*') if p.is_file()]
    assert max(sizes)[0] < 5_000_000
    summary = json.loads((OUT/'summary.json').read_text())
    assert summary['complete'] and summary['planned_trials'] == len(primary) == 4928
    assert summary['candidate_audit_failures'] == 0
    assert sum(int(r['evals']) for r in primary) == summary['total_search_evals']
    assert first_exact == first_total
    report = {'verified_utc': datetime.now(timezone.utc).isoformat(), 'hash_chain_and_frozen_source': 'pass', 'complete_start_tasks': raw_count, 'complete_trials': len(primary), 'same_initial_points_exact': first_exact, 'same_initial_points_checked': first_total, 'max_initial_coordinate_error': first_error, 'Ls_note': 'same stored center; first raw evaluations are the preregistered Gaussian samples', 'all_candidate_bounds_and_input_hashes': 'pass', 'preparation_residual_evals': prepared, 'max_search_evals': summary['max_actual_evals'], 'max_search_seconds': max(r['max_seconds'] for r in resource_rows), 'native_time_stops': sum(r['native_time_stops'] for r in resource_rows), 'time_limited_including_native': sum(r['any_time_stop'] for r in resource_rows), 'worker_limit': 3, 'max_chunk_seconds': max(r['seconds'] for r in receipts), 'max_worker_seconds': max(x['seconds'] for r in receipts for x in r['runs']), 'all_worker_exit_codes_zero': True, 'experiment_code_versions_by_tasks': dict(sources), 'preserved_optimizer_reporting_errors': failures, 'shared_machine_loadavg1_min_median_max': [min(loadavg), float(np.median(loadavg)), max(loadavg)], 'largest_file_at_audit': {'bytes': max(sizes)[0], 'path': max(sizes)[1]}, 'versions': {p: importlib.metadata.version(p) for p in ['numpy', 'scipy', 'PyNomadBBO']}}
    dump(OUT/'verification.json', report)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
