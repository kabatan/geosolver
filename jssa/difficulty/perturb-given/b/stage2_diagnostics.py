"""Fixed Q40b post-run differences at saved figures; never search or refine."""
from __future__ import annotations

import argparse
import itertools
import json
import signal
import time

from stage2_common import HERE, OUT, read, sha, utc, write

SELECTED = read(HERE / 'shared/selected.json')
PLAN = read(HERE / 'execution-plan.json')['runs']
SEEDS = (404001, 404002, 404003)
VARIANTS = ('original', 'e3_plus', 'e3_minus', 'e2_plus', 'e2_minus', 'e1_random')
HS = ('1e-6', '1e-7')
DEST = OUT / 'diagnostics'


class DiagnosticDeadline(BaseException):
    pass


def check_case(case_index):
    from mpmath import mp
    from geosolver.problem.models import GeometryProblem
    from geosolver.problem.ir.parser import load_ir
    from geosolver.problem.ir.compiler import safe_eval_expr_hp
    from geosolver.engine.standard.evaluation.high_precision_expressions import to_mpf_value
    from geosolver.engine.standard.evaluation.selection_trace import capture_selection_trace
    from geosolver.engine.standard.evaluation.snapshots import numerical_snapshot
    from geosolver.engine.standard.evaluation.verification_numerics import same_branches
    from geosolver.engine.standard.interpreter.context import _get_geometry_context
    from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode

    selected = SELECTED[case_index]
    identifier = selected['canonical_id']
    path = DEST / (identifier + '.json')
    assert not path.exists(), 'diagnostic result already exists'
    local = [(i, p) for i, p in enumerate(PLAN) if p['canonical_id'] == identifier]
    records = {(p['seed'], p['variant']): read(OUT / 'runs' / f'{i:04d}' / 'record.json', {}) for i, p in local}
    dsls = {v: read(HERE / 'shared/dsl' / identifier / (v + '.json')) for v in VARIANTS}
    original = dsls['original']
    names = original['variables']
    n = len(names)
    equalities = {v: [c for c in d['conditions'] if c.get('operator') == '='] for v, d in dsls.items()}
    m = len(equalities['original'])
    specs = {v: load_ir(GeometryProblem.model_validate(d).engine_document()) for v, d in dsls.items()}
    context = dict(_get_geometry_context())
    figures = {}
    for key, record in records.items():
        if record.get('success'):
            figures[key] = read(HERE / record['receipt_path'])

    def point(figure):
        if set(figure['variable_names']) != set(names):
            raise ValueError('cannot restore internal coordinates to original DSL variables')
        mapped = dict(zip(figure['variable_names'], figure['verified_coordinates'], strict=True))
        return tuple(mp.mpf(mapped[name]) for name in names)

    def bounds(record):
        if set(record.get('bounds_variable_names') or ()) != set(names):
            return None
        pairs = dict(zip(record['bounds_variable_names'], record['inferred_bounds'], strict=True))
        return [(mp.mpf(str(pairs[name][0])), mp.mpf(str(pairs[name][1]))) for name in names]

    def evaluate(variant, coordinates):
        spec = specs[variant]
        residuals, row_scales = [], []
        with capture_selection_trace() as trace:
            snap = numerical_snapshot(spec, tuple(names), coordinates, context)
            for c in equalities[variant]:
                left, right = str(c['left']), str(c['right'])
                ctx = snap.for_expressions((left, right))
                a = to_mpf_value(safe_eval_expr_hp(left, ctx), precision=80, context='Q40b original left')
                b = to_mpf_value(safe_eval_expr_hp(right, ctx), precision=80, context='Q40b original right')
                if not mp.isfinite(a) or not mp.isfinite(b):
                    raise ValueError('undefined/nonfinite difference point')
                residuals.append(a - b)
                row_scales.append(max(mp.mpf(1), abs(a), abs(b)))
        return residuals, row_scales, tuple(trace)

    def singular_values(variant, x, column_scales, row_scales, h):
        _, _, base_trace = evaluate(variant, x)
        jacobian = mp.matrix(m, n)
        for j in range(n):
            shifted_plus, shifted_minus = list(x), list(x)
            shifted_plus[j] += h * column_scales[j]
            shifted_minus[j] -= h * column_scales[j]
            plus, _, plus_trace = evaluate(variant, tuple(shifted_plus))
            minus, _, minus_trace = evaluate(variant, tuple(shifted_minus))
            if not same_branches(base_trace, plus_trace) or not same_branches(base_trace, minus_trace):
                raise ValueError('branch changed at a central difference point')
            for i in range(m):
                jacobian[i, j] = (plus[i] - minus[i]) / (2 * h * row_scales[i])
        values = mp.svd(jacobian, compute_uv=False)
        values = [abs(values[i]) for i in range(len(values))]
        if not values or max(values) == 0:
            raise ValueError('sigma_max is zero')
        smallest, largest = min(values), max(values)
        return {'sigma_min': str(smallest), 'sigma_max': str(largest),
                'ratio': str(smallest / largest), 'singular_values': [str(x) for x in values],
                'degenerate': smallest / largest <= mp.mpf('1e-8'),
                'regular': smallest / largest >= mp.mpf('1e-6'),
                'm': m, 'n': n, 'no_padding_of_underdetermined_spectrum': True}

    output = {'canonical_id': identifier, 'cohort': selected['cohort'], 'm': m, 'n_vars': n,
              'original_variables': names, 'precision_dps': 80, 'h': HS,
              'solver_calls': 0, 'refinements': 0, 'additional_searches': 0,
              'seeds': {}, 'candidate_distances': {}, 'box_changes': [],
              'M': False, 'started_utc': utc(), 'analysis_code_sha256': sha(__file__)}
    started = time.perf_counter()
    with mp.workdps(80), high_precision_mode():
        original_bounds = next((bounds(records[s, 'original']) for s in SEEDS
                                if bounds(records[s, 'original']) is not None), None)
        if original_bounds is None:
            output['missing_reason'] = 'original search box unavailable'
            write(path, output, exclusive=True)
            return output
        scales = tuple(max(mp.mpf(1), hi - lo) for lo, hi in original_bounds)
        output['column_scales'] = [str(x) for x in scales]
        for (seed, variant), record in records.items():
            current_bounds = bounds(record)
            if current_bounds is not None and variant != 'original':
                ratios = [(hi - lo) / (ohi - olo) if ohi != olo else None
                          for (lo, hi), (olo, ohi) in zip(current_bounds, original_bounds, strict=True)]
                if any(r is not None and (r < mp.mpf('.8') or r > mp.mpf('1.25')) for r in ratios):
                    output['box_changes'].append({'seed': seed, 'variant': variant,
                                                   'width_ratios': [str(r) for r in ratios]})
        for seed in SEEDS:
            result = {'M': False, 'M_valid': False, 'jacobians': {}}
            output['seeds'][str(seed)] = result
            if (seed, 'original') not in figures:
                result['missing_reason'] = 'same-seed original failed'
                continue
            try:
                ox = point(figures[seed, 'original'])
                _, rows, _ = evaluate('original', ox)
                result['row_scales'] = [str(x) for x in rows]
            except Exception as exc:
                result['missing_reason'] = type(exc).__name__ + ': ' + str(exc)
                continue
            for variant in VARIANTS:
                jac = {}
                result['jacobians'][variant] = jac
                if (seed, variant) not in figures:
                    jac['missing_reason'] = 'trial failed'
                    continue
                try:
                    x = point(figures[seed, variant])
                    for h in HS:
                        jac[h] = singular_values(variant, x, scales, rows, mp.mpf(h))
                    if any(jac[HS[0]][k] != jac[HS[1]][k] for k in ('degenerate', 'regular')):
                        jac['missing_reason'] = 'threshold verdict differs across h'
                    else:
                        jac['valid'] = True
                except Exception as exc:
                    jac['missing_reason'] = type(exc).__name__ + ': ' + str(exc)
            if m < n:
                result['missing_reason'] = 'm<n: mechanism M not applicable'
                continue
            three = [result['jacobians'].get(v, {}) for v in ('original', 'e2_plus', 'e2_minus')]
            if not all(j.get('valid') for j in three):
                result['missing_reason'] = 'original/e2 pair diagnostics incomplete'
                continue
            decisions = []
            for h in HS:
                base, plus, minus = [j[h] for j in three]
                base_min = mp.mpf(base['sigma_min'])
                factors = [mp.mpf(j['sigma_min']) >= 10 * base_min if base_min > 0
                           else mp.mpf(j['sigma_min']) > 0 for j in (plus, minus)]
                decisions.append([base['degenerate'], plus['regular'], minus['regular'], *factors])
            result['M_components_by_h'] = dict(zip(HS, decisions, strict=True))
            if decisions[0] != decisions[1]:
                result['missing_reason'] = 'mechanism verdict differs across h'
                continue
            result['M_valid'] = True
            result['M'] = all(decisions[0])
        output['M_seed_count'] = sum(x['M'] for x in output['seeds'].values())
        output['M'] = output['M_seed_count'] >= 2
        for variant in VARIANTS:
            distances = []
            duplicates = 0
            missing = []
            for a, b in itertools.combinations(SEEDS, 2):
                if (a, variant) not in figures or (b, variant) not in figures:
                    continue
                try:
                    x, y = point(figures[a, variant]), point(figures[b, variant])
                    distance = mp.sqrt(mp.fsum(((u - v) / s) ** 2 for u, v, s in zip(x, y, scales, strict=True)) / n)
                    if distance <= mp.mpf('1e-6'):
                        duplicates += 1
                    else:
                        distances.append({'seed_pair': [a, b], 'rms': str(distance)})
                except Exception as exc:
                    missing.append(type(exc).__name__ + ': ' + str(exc))
            output['candidate_distances'][variant] = {'pairs': distances, 'same_candidate_pairs': duplicates,
                'minimum_distinct_rms': str(min(mp.mpf(d['rms']) for d in distances)) if distances else None,
                'missing': missing}
    output['elapsed_s'] = time.perf_counter() - started
    output['ended_utc'] = utc()
    write(path, output, exclusive=True)
    return output


def main(index):
    def alarm(signum, frame):
        raise DiagnosticDeadline()
    signal.signal(signal.SIGALRM, alarm)
    signal.setitimer(signal.ITIMER_REAL, 195)
    try:
        value = check_case(index)
    except DiagnosticDeadline:
        selected = SELECTED[index]
        value = {'canonical_id': selected['canonical_id'], 'M': False,
                 'missing_reason': '195s diagnostic deadline; no additional search or retry', 'utc': utc()}
        write(DEST / (selected['canonical_id'] + '.json'), value, exclusive=True)
    except Exception as exc:
        selected = SELECTED[index]
        value = {'canonical_id': selected['canonical_id'], 'M': False,
                 'missing_reason': type(exc).__name__ + ': ' + str(exc),
                 'no_retry': True, 'utc': utc()}
        write(DEST / (selected['canonical_id'] + '.json'), value, exclusive=True)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    print(json.dumps({k: value.get(k) for k in ('canonical_id', 'M', 'M_seed_count', 'm', 'n_vars', 'missing_reason', 'elapsed_s')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('index', type=int)
    main(parser.parse_args().index)
