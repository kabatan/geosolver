"""Locked-prediction audit and fixed-denominator analysis; no solver calls."""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import random
import statistics
from collections import Counter
from decimal import Decimal

from stage2_common import HERE, OUT, SOURCE, read, sha, utc, write

PLAN = read(HERE / 'execution-plan.json')['runs']
SELECTED = read(HERE / 'shared/selected.json')
SEEDS = (404001, 404002, 404003)
VARIANTS = ('original', 'e3_plus', 'e3_minus', 'e2_plus', 'e2_minus', 'e1_random')
ANALYSIS = OUT / 'analysis'


def audit():
    from stage2 import locked_check
    lock = locked_check()
    errors = []
    rows = []
    expected = {(p['canonical_id'], p['seed'], p['variant']) for p in PLAN}
    assert len(expected) == 720
    for index, plan in enumerate(PLAN):
        folder = OUT / 'runs' / f'{index:04d}'
        row = read(folder / 'record.json')
        if row is None:
            errors.append({'index': index, 'reason': 'missing_record'})
            row = {**plan, 'run_order': index, 'success': False, 'status': 'missing',
                   'cpu_s': None, 'wall_s': None, 'group': plan['cohort']}
        else:
            for name in ('canonical_id', 'seed', 'variant', 'dsl_sha256', 'block', 'position'):
                if row[name] != plan[name]:
                    errors.append({'index': index, 'reason': 'plan_mismatch', 'field': name})
            if row['source_hash'] != SOURCE or row['environment_hash'] != lock['environment_sha256']:
                errors.append({'index': index, 'reason': 'identity_mismatch'})
            if row['identify_calls'] != 0 or row['measurement_violations']:
                errors.append({'index': index, 'reason': 'measurement_contract',
                               'details': row['measurement_violations']})
            if row['cpu_measurement'] == 'parent_last_sample' and (folder / 'worker-start.json').exists():
                errors.append({'index': index, 'reason': 'worker_end_clock_missing'})
            for clock in ('cpu_s', 'wall_s', 'parent_cpu_s', 'cleanup_s'):
                if row[clock] is None or not math.isfinite(row[clock]) or row[clock] < 0:
                    errors.append({'index': index, 'reason': 'invalid_clock', 'clock': clock})
            if row['success']:
                figure_path = HERE / row['receipt_path']
                figure = read(figure_path)
                commit = read(folder / 'figure-commit.json')
                if (not figure or not commit or sha(figure_path) != row['figure_sha256']
                        or commit['sha256'] != row['figure_sha256']):
                    errors.append({'index': index, 'reason': 'figure_receipt_hash'})
                else:
                    v = figure['verification']
                    if (not v['verified'] or not v['hard_feasible']
                            or Decimal(v['normalized_residual']) > Decimal('1e-30')
                            or figure['verified_coordinates'] != v['values']
                            or figure['candidate_uid'] != row['candidate_uid']
                            or figure['variable_names'] == []
                            or figure['identify_calls'] != 0
                            or figure['wall_s'] > 180 or figure['discovery']['cpu_s'] > 180):
                        errors.append({'index': index, 'reason': 'invalid_verification_receipt'})
            if sha(HERE / row['dsl_path']) != plan['dsl_sha256']:
                errors.append({'index': index, 'reason': 'dsl_changed'})
        row = dict(row)
        row['C'] = min(row['cpu_s'], 180) if row['success'] else 180.0
        row['W'] = min(row['wall_s'], 180) if row['success'] else 180.0
        rows.append(row)
    for cohort in ('development', 'unseen'):
        assert len([r for r in rows if r['cohort'] == cohort]) == 360
    for folder in sorted((OUT / 'runs').iterdir()):
        if folder.is_dir():
            for path in folder.glob('*.json'):
                if path.stat().st_size >= 5_000_000:
                    errors.append({'path': str(path), 'reason': 'oversize_receipt'})
    result = {'audited_utc': utc(), 'run_count': len(rows), 'unique_triples': len(expected),
              'prediction_sha256': sha(HERE / 'prediction.lock.json'),
              'implementation_sha256': sha(HERE / 'implementation.lock.json'),
              'valid_cost_comparison': not errors, 'errors': errors,
              'statuses': dict(Counter(r['status'] for r in rows)),
              'all_identify_calls_zero': all(r.get('identify_calls', 0) == 0 for r in rows)}
    write(ANALYSIS / 'audit.json', result)
    return rows, result


def distribution(rows):
    return {'count': len(rows), 'successes': sum(r['success'] for r in rows),
            'success_rate': sum(r['success'] for r in rows) / len(rows),
            'statuses': dict(Counter(r['status'] for r in rows)),
            **{key: {'mean': statistics.mean(r[key] for r in rows),
                     'median': statistics.median(r[key] for r in rows),
                     'min': min(r[key] for r in rows), 'max': max(r[key] for r in rows)}
               for key in ('C', 'W')}}


def csv_file(path, rows):
    if not rows:
        return
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    for row in rows:
        writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                         for k, v in row.items()})
    data = stream.getvalue()
    assert len(data.encode()) < 5_000_000
    path.write_text(data, encoding='utf-8')


def aggregate():
    rows, audit_result = audit()
    lookup = {(r['canonical_id'], r['seed'], r['variant']): r for r in rows}
    summary = {'all': distribution(rows), 'by_variant': {}, 'by_cohort_variant': {}}
    for variant in VARIANTS:
        summary['by_variant'][variant] = distribution([r for r in rows if r['variant'] == variant])
        for cohort in ('development', 'unseen'):
            summary['by_cohort_variant'][cohort + '/' + variant] = distribution(
                [r for r in rows if r['variant'] == variant and r['cohort'] == cohort])
    summary['perturbed'] = distribution([r for r in rows if r['variant'] != 'original'])
    write(ANALYSIS / 'success-and-cost-distributions.json', summary)
    per_seed = []
    per_problem = []
    for selected in SELECTED:
        identifier = selected['canonical_id']
        seed_rows = []
        for seed in SEEDS:
            original = lookup[identifier, seed, 'original']
            perturbed = [lookup[identifier, seed, v] for v in VARIANTS[1:]]
            item = {'canonical_id': identifier, 'cohort': selected['cohort'], 'seed': seed}
            for cost in ('C', 'W'):
                log_r = statistics.mean(math.log((original[cost] + .01) / (r[cost] + .01))
                                        for r in perturbed)
                g = math.exp(statistics.mean(math.log(r[cost] + .01) for r in perturbed)) - .01
                item['r_' + cost] = math.exp(log_r)
                item['log_r_' + cost] = log_r
                item['g_' + cost] = g
                item['original_' + cost] = original[cost]
            item['improved'] = item['r_C'] >= 1.25 and item['original_C'] - item['g_C'] >= 1
            item['worsened'] = item['r_C'] <= .8 and item['g_C'] - item['original_C'] >= 1
            seed_rows.append(item)
        improved = sum(s['improved'] for s in seed_rows)
        worsened = sum(s['worsened'] for s in seed_rows)
        per_problem.append({'canonical_id': identifier, 'cohort': selected['cohort'],
            'classification': 'improved' if improved >= 2 else 'worsened' if worsened >= 2 else 'unchanged_or_uncertain',
            'improving_seeds': improved, 'worsening_seeds': worsened,
            'mean_log_r_C': statistics.mean(s['log_r_C'] for s in seed_rows),
            'mean_log_r_W': statistics.mean(s['log_r_W'] for s in seed_rows),
            'given_kinds': sorted({g['kind'] for g in selected['given_slots']}),
            'n_vars': selected['n_vars']})
        per_seed.extend(seed_rows)
    K = sum(r['classification'] == 'improved' for r in per_problem)
    L = sum(r['classification'] == 'worsened' for r in per_problem)
    sign_p = sum(math.comb(K + L, j) for j in range(K, K + L + 1)) / 2 ** (K + L) if K + L else 1
    group = {}
    for cohort in ('development', 'unseen'):
        selected = [r for r in per_problem if r['cohort'] == cohort]
        group[cohort] = {'improved': sum(r['classification'] == 'improved' for r in selected),
                         'worsened': sum(r['classification'] == 'worsened' for r in selected),
                         'denominator': 20}
    rng = random.Random(404040)
    groups = [[r['mean_log_r_C'] for r in per_problem if r['cohort'] == c] for c in ('development', 'unseen')]
    bootstrap = []
    for _ in range(10_000):
        values = [values[rng.randrange(20)] for values in groups for _ in range(20)]
        bootstrap.append(math.exp(statistics.mean(values)))
    bootstrap.sort()
    interval = [bootstrap[249], bootstrap[9749]]
    G_C = math.exp(statistics.mean(r['mean_log_r_C'] for r in per_problem))
    G_W = math.exp(statistics.mean(r['mean_log_r_W'] for r in per_problem))
    all_failed = [{"canonical_id": s['canonical_id'], 'variant': variant}
                  for s in SELECTED for variant in VARIANTS[1:]
                  if not any(lookup[s['canonical_id'], seed, variant]['success'] for seed in SEEDS)]
    auxiliary = {}
    for name, variants in [('e3', VARIANTS[1:3]), ('e2', VARIANTS[3:5]), ('e1', VARIANTS[5:])]:
        selected_rows = [r for r in rows if r['variant'] in variants]
        aux = distribution(selected_rows)
        for cost in ('C', 'W'):
            logs = [math.log((lookup[s['canonical_id'], seed, 'original'][cost] + .01)
                             / (lookup[s['canonical_id'], seed, variant][cost] + .01))
                    for s in SELECTED for seed in SEEDS for variant in variants]
            aux['G_' + cost] = math.exp(statistics.mean(logs))
        auxiliary[name] = aux
    loads = [r['load_average_start'][0] for r in rows if 'load_average_start' in r]
    metrics = {'calculated_utc': utc(), 'audit_valid': audit_result['valid_cost_comparison'],
        'improved': K, 'worsened': L, 'remaining': 40 - K - L, 'sign_test_p': sign_p,
        'G_CPU': G_C, 'G_wall': G_W, 'CPU_95pct_interval': interval, 'cohorts': group,
        'seed_counts': {str(seed): {'improved': sum(s['improved'] for s in per_seed if s['seed'] == seed),
                                  'worsened': sum(s['worsened'] for s in per_seed if s['seed'] == seed)} for seed in SEEDS},
        'P1': K >= 16 and L <= 6 and sign_p <= .05,
        'P2': G_C >= 1.25 and G_W >= 1.15 and interval[0] > 1,
        'P3': all(v['improved'] >= 5 and v['improved'] > v['worsened'] for v in group.values()),
        'all_three_failed_perturbed_variants': len(all_failed),
        'feasibility_causal_audit_passed': len(all_failed) < 41,
        'auxiliary_by_epsilon': auxiliary,
        'load_average_start_1min': {'min': min(loads), 'median': statistics.median(loads), 'max': max(loads)} if loads else None,
        'warning': 'CPU is primary. Shared-machine load also affects wall-budget-dependent solver paths. Wall results are conditional on recorded load.',
    }
    write(ANALYSIS / 'metrics.json', metrics)
    write(ANALYSIS / 'all-three-failed-variants.json', all_failed)
    write(ANALYSIS / 'problem-results.json', per_problem)
    csv_file(ANALYSIS / 'per-problem.csv', per_problem)
    csv_file(ANALYSIS / 'per-seed.csv', per_seed)
    fields = ['run_order', 'canonical_id', 'cohort', 'variant', 'epsilon', 'seed', 'status', 'success',
              'cpu_s', 'wall_s', 'C', 'W', 'parent_cpu_s', 'cleanup_s', 'timeout_kind', 'candidate_uid',
              'precision_dps', 'normalized_residual', 'hard_feasible', 'identify_calls', 'source_hash',
              'dsl_hash', 'environment_hash', 'receipt_path', 'load_average_start', 'load_average_end']
    csv_file(ANALYSIS / 'all-720-runs.csv', [{f: r.get(f) for f in fields} for r in rows])
    print(json.dumps({k: metrics[k] for k in ('audit_valid', 'improved', 'worsened', 'G_CPU', 'G_wall', 'CPU_95pct_interval', 'P1', 'P2', 'P3', 'all_three_failed_perturbed_variants')}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('audit', 'aggregate'))
    args = parser.parse_args()
    if args.command == 'audit':
        print(json.dumps(audit()[1], ensure_ascii=False))
    else:
        aggregate()
