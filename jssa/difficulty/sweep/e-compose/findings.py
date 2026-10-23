"""Read-only post-hoc diagnostics of the original 190 runs; no solver calls.

Run beside the unchanged experiment/analyze scripts in /tmp/q43e-clean after
analyze.py --check-coordinates and audit.py. The reference algebra below explains
observations only; it is never passed to the solver or used to revise grading.
"""
from __future__ import annotations

import ast
import csv
import itertools
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import median

from analyze import csv_write, exact_key
from experiment import HERE, RAW, ROOT, SEEDS, SOURCE, digest, read, save


def load_rows():
    rows = []
    for row in csv.DictReader((HERE / 'per-run.csv').open()):
        parsed = {}
        for key, value in row.items():
            if value in ('True', 'False'):
                parsed[key] = value == 'True'
            elif value == '':
                parsed[key] = None
            elif key in ('variant', 'kind', 'status', 'raw_sha256'):
                parsed[key] = value
            else:
                import json
                try:
                    parsed[key] = json.loads(value)
                except ValueError:
                    parsed[key] = value
        rows.append(parsed)
    return rows


def algebra_details(variant):
    """Exact arithmetic on frozen references, not an identification rerun."""
    import sympy as sp
    from mpmath import mp
    from geosolver.exact.polynomial_search_helpers import scale_candidates_for_value

    expr = sp.sympify(variant['references'][0])
    item = {'variant': variant['id'], 'reference_expression': str(expr)}
    if expr.has(sp.pi):
        return item | {'contains_pi': True}
    z = sp.Symbol('z')
    polynomial = sp.Poly(sp.minimal_polynomial(expr, z), z)
    item.update(contains_pi=False, degree=polynomial.degree(),
                primitive_coefficients=[int(x) for x in polynomial.all_coeffs()],
                coefficient_height=int(max(map(abs, polynomial.all_coeffs()))))
    with mp.workdps(80):
        scales = scale_candidates_for_value(mp.mpf(str(sp.N(expr, 80))))
        exponents = [int(mp.nint(mp.log10(s))) for s in scales]
    trials = []
    for exponent in exponents:
        p = sp.Poly(polynomial.as_expr().subs(z, z * sp.Rational(10)**exponent), z)
        _, p = p.clear_denoms(convert=True)
        _, p = p.primitive()
        trials.append({'power_of_ten': exponent,
                       'primitive_height': int(max(map(abs, p.all_coeffs()))),
                       'primitive_constant_abs': int(abs(p.TC()))})
    item['frozen_scale_heights'] = trials
    item['min_scaled_height'] = min(r['primitive_height'] for r in trials)
    return item


def expression_from_key(key):
    """Reconstruct the exact real root from the public answer descriptor."""
    import sympy as sp

    def algebraic(value):
        coefficients, index = value
        polynomial = sp.Poly.from_list([sp.Integer(c) for c in coefficients], sp.Symbol('x'))
        return sp.real_roots(polynomial)[index]

    if key[0] == 'algebraic':
        return algebraic(key[1:])
    assert key[0] == 'affine_pi', key
    return algebraic(key[1]) * sp.pi + algebraic(key[2])


def main():
    import sympy as sp
    from mpmath import mp

    summary = read(HERE / 'summary.json')
    assert summary['summarized_runs'] == summary['scheduled_runs'] == 190
    assert not summary['missing_receipts'] and not summary['contract_issues']
    assert summary['coordinate_checks'] and summary['source_hash_ok'] and summary['input_hash_ok']
    manifest = read(HERE / 'manifest.json')
    variants = {v['id']: v for v in manifest['variants']}
    rows = load_rows()
    lookup = {(r['variant'], r['seed']): r for r in rows}
    sets = read(HERE / 'sets.json')
    evidence, run_audit = [], []
    loads = []
    for row in rows:
        key = f"{row['variant']}__s{row['seed']}"
        raw = read(RAW / 'runs' / (key + '.json'))
        result = raw.get('solver_result') or {}
        diagnostics = result.get('diagnostics') or {}
        pipeline = diagnostics.get('pipeline_summary') or {}
        assembly = pipeline.get('exact_assembly') or {}
        exact_records = pipeline.get('exact_candidate_records') or []
        info = diagnostics.get('process_info') or {}
        receipt = read(RAW / 'receipts' / (key + '.json'))
        assert raw['variant'] == receipt['variant'] == row['variant']
        assert raw['seed'] == receipt['seed'] == row['seed']
        run_audit.append({'variant': row['variant'], 'seed': row['seed'],
                          'receipt_returncode': receipt.get('returncode'),
                          'raw_sha256': row['raw_sha256'], 'raw_bytes': row['raw_bytes'],
                          'receipt_sha256': digest((RAW / 'receipts' / (key + '.json')).read_bytes()),
                          'source_hash': raw.get('source_hash'),
                          'result_engine_source_hash': result.get('engine', {}).get('source_hash'),
                          'parent_import_root': raw.get('parent_import_root'),
                          'worker_import_root': info.get('import_root'),
                          'cpu': raw.get('cpu'), 'worker_cpu_affinity': info.get('cpu_affinity')})
        loads.append(raw['load_start'][0])
        numeric_errors = []
        if row['kind'] in ('pair_sum', 'quad_sum') and not row['correct']:
            with mp.workdps(200):
                expected = [mp.mpf(str(sp.N(sp.sympify(r), 200)))
                            for r in variants[row['variant']]['references']]
                for record in exact_records:
                    answer = record.get('candidate', {}).get('answer_hp')
                    if answer is not None:
                        value = mp.mpf(answer)
                        numeric_errors.append(min(abs(value - x) for x in expected))
        evidence.append({'variant': row['variant'], 'seed': row['seed'],
                         'kind': row['kind'], 'correct': row['correct'],
                         'numeric_figures': row['numeric_figures'],
                         'final_verified_candidates': assembly.get('numeric_feasible_count', 0),
                         'accepted_candidates': assembly.get('accepted_count', 0),
                         'exact_attempt_records': len(exact_records),
                         'identification_methods': dict(Counter(
                             r['exact_result']['identification_method'] for r in exact_records)),
                         'unidentified_records': sum(
                             r['exact_result']['exact_status'] != 'identified' for r in exact_records),
                         'verified_target_matches_reference_at_1e_100': bool(
                             numeric_errors and min(numeric_errors) < mp.mpf('1e-100')),
                         'min_verified_target_absolute_error_200dps': str(min(numeric_errors))
                         if numeric_errors else None,
                         'wall_seconds': row['wall_seconds'], 'cpu_seconds': row['cpu_seconds'],
                         'phase_timings': row['phase_timings'],
                         'rejection_tags': row['rejection_tags']})
    csv_write(HERE / 'stage-evidence.csv', evidence)
    csv_write(HERE / 'run-integrity.csv', run_audit)

    compositions = []
    for kind, groups in [('pair', manifest['pairs']), ('quad', manifest['quads'])]:
        for group, components in enumerate(groups):
            for seed in SEEDS:
                single = [lookup[(f'single-{i:02d}', seed)] for i in components]
                joint = lookup[(f'{kind}-sum-{group:02d}', seed)]
                individual_sets = [sets[f'single-{i:02d}__s{seed}']['actual_exact_keys']
                                   for i in components]
                # All chosen references here are singleton sets; assert rather
                # than silently substituting references for returned answers.
                assert all(len(s) == 1 for s in individual_sets)
                expressions = [expression_from_key(s[0]) for s in individual_sets]
                actual_sum_key = exact_key(str(sum(expressions)))
                expected_keys = {exact_key(e) for e in variants[joint['variant']]['references']}
                wall_sum = sum(s['wall_seconds'] for s in single)
                cpu_sum = sum(s['cpu_seconds'] for s in single)
                compositions.append({'kind': kind, 'group': group, 'seed': seed,
                                     'components': components,
                                     'all_singles_correct': all(s['correct'] for s in single),
                                     'returned_answer_sum_correct': {actual_sum_key} == expected_keys,
                                     'joint_correct': joint['correct'],
                                     'single_wall_sum': wall_sum,
                                     'single_cpu_sum': cpu_sum,
                                     'joint_wall_seconds': joint['wall_seconds'],
                                     'joint_cpu_seconds': joint['cpu_seconds'],
                                     'joint_wall_over_single_sum': joint['wall_seconds']/wall_sum,
                                     'joint_cpu_over_single_sum': joint['cpu_seconds']/cpu_sum,
                                     'joint_capped_cost_over_single_sum':
                                     joint['capped_cost_seconds']/wall_sum})
    csv_write(HERE / 'composition-costs.csv', compositions)

    parts = []
    for i, base in enumerate(manifest['selected']):
        eq = variants[f'half0-{i:02d}']['split_equalities']
        full_conditions = read(HERE / 'inputs' / f'single-{i:02d}.json')['conditions']
        for h, seed in itertools.product((0, 1), SEEDS):
            variant = f'half{h}-{i:02d}'
            part = lookup[(variant, seed)]
            single = lookup[(f'single-{i:02d}', seed)]
            changed = read(HERE / 'inputs' / (variant + '.json'))['conditions'] != full_conditions
            checks = sets[f'{variant}__s{seed}']['original_condition_checks']
            parts.append({'problem_index': i, 'problem': base['id'], 'half': h, 'seed': seed,
                          'original_equalities': eq, 'conditions_changed': changed,
                          'matches_reference_set': part['matches_reference_set'],
                          'numeric_figures': part['numeric_figures'],
                          'full_feasible_figures': part['full_feasible_figures'],
                          'min_full_residual': min((float(c.get('residual', 'inf'))
                                                    for c in checks), default=None),
                          'wall_seconds': part['wall_seconds'], 'single_wall_seconds': single['wall_seconds'],
                          'wall_ratio': part['wall_seconds']/single['wall_seconds'],
                          'timeout': part['timeout'], 'answer_count': part['answer_count'],
                          'extra_answers': part['extra_answers'], 'missing_answers': part['missing_answers']})
    csv_write(HERE / 'decomposition-details.csv', parts)
    algebra = [algebra_details(v) for v in manifest['variants']
               if v['kind'] in ('single', 'pair_sum', 'quad_sum')]
    save(HERE / 'reference-algebra.json', algebra)

    # The half0-02 relaxation removes triangle side lengths but retains the
    # symmetric conditions on p,q,r. Check the area identity by exact algebra.
    p, q, r = sp.symbols('p q r')
    a, b, c = sp.Matrix([0, 1]), sp.Matrix([0, 0]), sp.Matrix([1, 0])
    d, e, f = a+p*(b-a), b+q*(c-b), c+r*(a-c)
    ratio = sp.expand(sp.det(sp.Matrix.hstack(e-d, f-d)))
    identity = 1-p-q-r+p*q+q*r+r*p
    assert sp.expand(ratio - identity) == 0
    constant_value = 1-sp.Rational(2, 3)+(sp.Rational(2, 3)**2-sp.Rational(2, 5))/2
    assert constant_value == sp.Rational(16, 45)
    save(HERE / 'arithmetic-checks.json', {
        'scope': 'Post-hoc exact arithmetic only, no new solver runs.',
        'half0-02_oriented_area_ratio': str(ratio),
        'triangle_shape_independent': True,
        'p_plus_q_plus_r': '2/3', 'p2_plus_q2_plus_r2': '2/5',
        'derived_area_ratio': str(constant_value)
    })

    start = read(RAW / 'execution-start.json')
    end = read(RAW / 'execution-end.json')
    save(HERE / 'findings.json', {
        'scope': 'Post-hoc summaries only; original 190 trials and grading unchanged.',
        'scheduled': len(rows), 'all_receipts_returned_zero': all(r['receipt_returncode'] == 0 for r in run_audit),
        'all_source_hashes_match': all(r['source_hash'] == r['result_engine_source_hash'] == SOURCE for r in run_audit),
        'started_utc': start['utc'], 'finished_utc': end['utc'],
        'campaign_wall_seconds': (datetime.fromisoformat(end['utc']) - datetime.fromisoformat(start['utc'])).total_seconds(),
        'one_minute_load_at_job_start': {'min': min(loads), 'median': median(loads), 'max': max(loads)},
        'composition': {kind: {
            'n': sum(r['kind'] == kind for r in compositions),
            'joint_correct': sum(r['kind'] == kind and r['joint_correct'] for r in compositions),
            'returned_sum_correct': sum(r['kind'] == kind and r['returned_answer_sum_correct'] for r in compositions),
            'wall_ratio_range': [min(r['joint_wall_over_single_sum'] for r in compositions if r['kind'] == kind),
                                 max(r['joint_wall_over_single_sum'] for r in compositions if r['kind'] == kind)],
            'both_seed_fail_groups': [g for g in range(10 if kind == 'pair' else 5)
                                     if all(not r['joint_correct'] for r in compositions
                                            if r['kind'] == kind and r['group'] == g)]
        } for kind in ('pair', 'quad')},
        'decomposition': {
            'changed_runs': sum(p['conditions_changed'] for p in parts),
            'changed_matching_runs': sum(p['conditions_changed'] and p['matches_reference_set'] for p in parts),
            'changed_with_full_feasible_figure': sum(p['conditions_changed'] and p['full_feasible_figures'] > 0 for p in parts),
            'answer_matches_without_original_figure': [p for p in parts
                if p['matches_reference_set'] and p['full_feasible_figures'] == 0],
            'neither_half_matches_reference_set_in_both_seeds': [i for i in range(20)
                if all(not p['matches_reference_set'] for p in parts if p['problem_index'] == i)],
            'half1_mismatches_reference_set_in_both_seeds': [i for i in range(20)
                if all(not p['matches_reference_set'] for p in parts if p['problem_index'] == i and p['half'] == 1)]
        },
        'analysis_script_sha256': digest(Path(__file__).read_bytes()),
        'frozen_grader_file_sha256': digest((ROOT / 'benchmarks/research_runner.py').read_bytes()),
        'frozen_scoring_function_sha256': {
            n.name: digest(ast.get_source_segment((ROOT/'benchmarks/research_runner.py').read_text(), n).encode())
            for n in ast.parse((ROOT/'benchmarks/research_runner.py').read_text()).body
            if isinstance(n, ast.FunctionDef) and n.name in ('_answer_keys', 'reference_expressions')
        }
    })


if __name__ == '__main__':
    main()
