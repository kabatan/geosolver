"""Read-only exploration of existing data; all outputs stay beside this script.

Discovery uses local seed 0 and completed-solver seed 0 only. No solver calls.
"""
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
SOURCES = {}


def read(path):
    p = ROOT / path
    assert 'unseen-1983' not in p.parts and 'sealed-raw' not in p.parts
    b = p.read_bytes()
    SOURCES[path] = {'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()}
    return b.decode()


def table(path, key='id'):
    rows = list(csv.DictReader(read(path).splitlines()))
    return {r[key]: r for r in rows}


def num(x):
    try:
        return float(x)
    except (ValueError, TypeError):
        return float('nan')


def median(xs):
    xs = [x for x in xs if math.isfinite(x)]
    return float(np.median(xs)) if xs else float('nan')


def write_csv(name, rows):
    if not rows:
        return
    cols = list(dict.fromkeys(k for r in rows for k in r))
    with (OUT / name).open('w') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def main():
    base = table('jssa/difficulty/minima/basins-323.csv')
    human = table('jssa/difficulty/ghost-1023/human_feat.csv', 'case_id')
    full_rows = list(csv.DictReader(read('jssa/results/stage-profile-20261023/per-case.csv').splitlines()))
    full = {r['case_id']: r for r in full_rows if r['seed'] == '0'}
    feasibility = table('jssa/difficulty/start-feasibility-1023/per-problem.csv')
    ghost = table('jssa/difficulty/ghost-pairs-match/per-problem.csv')
    false = table('jssa/difficulty/false-attractors/per-problem.csv')
    hidden = table('jssa/strategy/astra-consult-18/q22a-hidden-coincidence/features.csv')
    algebra = table('jssa/strategy/astra-consult-17/H/sources/comparison-cases.csv')
    number = table('jssa/strategy/astra-consult-18/q21b-number-theory/problem-summary.csv')
    cond = table('jssa/strategy/astra-consult-18/q21d-conditioning/per-problem.csv')
    cases = {r['id']: r for r in map(json.loads, read('benchmarks/cases.jsonl').splitlines())}
    rows = []
    records_total = 0
    raw_fieldsets = Counter()
    for cid, b in base.items():
        h, f = human[cid], full[cid]
        r = {'id': cid, 'contest': h['contest'], 'human': num(h['human'])}
        for k in ['n_vars', 'n_cons', 'n_pts', 'n_circ', 'n_eq', 'n_ineq', 'has_angle', 'has_tangent', 'dsl_len', 'pos']:
            r[k] = num(h[k])
        for k in ['p', 'n_starts', 'frac_left_box', 'frac_error', 'frac_stuck', 'frac_wrong_answer', 'frac_wrong_branch', 'n_basins', 'n_basins_ge2', 'n_correct_basins', 'n_wrong_basins_ge2', 'top_wrong_share', 'n_levels_ge2', 'top_level_share']:
            r[k] = num(b[k])
        r['correct0'] = f['correct'] == 'True'
        r['source0'] = f['final_answer_source']
        r['cost0'] = num(f['wall_time_s']) if r['correct0'] else 180.
        for k in ['wall_time_s', 'search_time_s', 'refinement_time_s', 'identification_verification_time_s', 'rescue_time_s', 'candidates_sent_to_refinement', 'candidates_converged', 'candidates_rejected_as_false', 'candidates_accepted']:
            r[k + '0'] = num(f[k])
        r['refine_per_candidate0'] = r['refinement_time_s0'] / max(1, r['candidates_sent_to_refinement0'])
        r['refine_fraction0'] = r['refinement_time_s0'] / max(1e-9, r['wall_time_s0'])
        r['identify_fraction0'] = r['identification_verification_time_s0'] / max(1e-9, r['wall_time_s0'])
        r['search_fraction0'] = r['search_time_s0'] / max(1e-9, r['wall_time_s0'])
        r['conv_fraction0'] = r['candidates_converged0'] / max(1, r['candidates_sent_to_refinement0'])
        ff = feasibility.get(cid, {})
        r['phi'] = num(ff.get('n_feas')) / max(1, num(ff.get('starts')))
        r['p_feas'] = num(ff.get('hit_feas')) / num(ff['n_feas']) if num(ff.get('n_feas')) > 0 else float('nan')
        r['p_infeas'] = num(ff.get('hit_infeas')) / num(ff['n_infeas']) if num(ff.get('n_infeas')) > 0 else float('nan')
        r['p_feas_minus_infeas'] = r['p_feas'] - r['p_infeas']
        g = ghost.get(cid, {})
        r['collision_failure_fraction'] = num(g.get('collision_failure')) / max(1, num(g.get('n_records')) - num(g.get('success')))
        r['found_pair_count'] = num(g.get('n_found_pairs'))
        fa = false.get(cid, {})
        r['failure_cause'] = fa.get('main_cause', '')
        r['degenerate_failure_fraction'] = num(fa.get('ab_fraction'))
        hh = hidden.get(cid, {})
        r['hidden_status'] = hh.get('status', '')
        for k in ['construction_depth', 'solution_dependent_count', 'solution_depth', 'hidden_depth', 'hidden_count_1e-07', 'hidden_collinear_1e-07', 'hidden_concyclic_1e-07', 'hidden_equal_length_1e-07', 'hidden_similar_1e-07', 'hidden_tangent_1e-07']:
            r[k] = num(hh.get(k))
        a = algebra[cid]
        r['msolve_class'] = a['msolve_class']
        for k in ['poly_vars', 'poly_eqs', 'max_degree', 'bezout', 'real_solutions', 'verified_configurations']:
            r[k] = num(a[k])
        n = number[cid]
        for k in ['n_answers', 'degree', 'height', 'heuristic_digits', 'radical_depth', 'first_correct_grid', 'stable_correct_grid']:
            r[k] = num(n[k])
        c = cond[cid]
        r['condition_status'] = c['status']
        for k in ['cond', 'kx', 'ktau', 'q', 'smin', 'weak_alignment', 'box_cond']:
            r[k] = num(c[k])
        dsl = cases[cid]['dsl']
        ops = Counter(con['expression'].split('(')[0] for con in dsl.get('constructions', []))
        r['operations'] = '|'.join(sorted(ops))
        for op in ['Midpoint', 'Intersect', 'FootOfPerpendicular', 'Circumcenter', 'Triangle', 'Line', 'Circle', 'Point', 'Rotate', 'Reflect', 'Incenter', 'Orthocenter']:
            r['op_' + op] = ops[op]
        raw = json.loads(read(f'jssa/difficulty/minima/raw-323/{cid}.json'))
        rr = raw.get('records', [])
        records_total += len(rr)
        raw_fieldsets.update(tuple(sorted(x)) for x in rr)
        r['raw_n'] = len(rr)
        r['raw_hits'] = sum(x['cls'] == 'hit' for x in rr)
        for tag, selected in [('all', rr), ('hit', [x for x in rr if x['cls'] == 'hit']), ('miss', [x for x in rr if x['cls'] != 'hit'])]:
            for field in ['nfev', 'sec', 'res']:
                vals = [num(x.get(field)) for x in selected]
                r[f'{tag}_{field}_median'] = median(vals)
        nfev = [num(x.get('nfev')) for x in rr]
        finite_nfev = [x for x in nfev if math.isfinite(x)]
        r['nfev_mean'] = float(np.mean(finite_nfev)) if finite_nfev else float('nan')
        r['eval_cost_to_hit'] = r['nfev_mean'] / r['p'] if r['p'] > 0 else float('nan')
        sv = [v for hit in raw.get('first_hit', {}).values() for v in hit.get('svals', [])]
        r['first_sval_min'] = min(sv) if sv else float('nan')
        rows.append(r)
    human_rows = [r for r in rows if math.isfinite(r['human'])]
    local = [r for r in human_rows if r['n_vars'] > 0 and math.isfinite(r['p'])]
    for subset, suffix, difficulties in [(human_rows, 'full', [('human', 1), ('cost0', 1)]), (local, 'local', [('human', 1), ('p', -1)])]:
        for contest in ['AIME', 'HMMT']:
            group = [r for r in subset if r['contest'] == contest]
            for key, sign in difficulties:
                ranks = rankdata([sign * r[key] for r in group], method='average') / len(group)
                for r, rank in zip(group, ranks):
                    r[key + '_rank_' + suffix] = float(rank)
    for r in human_rows:
        r['gap_full'] = r['human_rank_full'] - r['cost0_rank_full']
        r['group_full'] = 'human_hard_solver_easy' if r['gap_full'] >= .4 else ('human_easy_solver_hard' if r['gap_full'] <= -.4 else 'middle')
    for r in local:
        r['gap_local'] = r['human_rank_local'] - r['p_rank_local']
        r['group_local'] = 'human_hard_solver_easy' if r['gap_local'] >= .4 else ('human_easy_solver_hard' if r['gap_local'] <= -.4 else 'middle')
    write_csv('joined-discovery.csv', rows)
    write_csv('extremes-full.csv', sorted(human_rows, key=lambda r: r['gap_full']))
    write_csv('extremes-local.csv', sorted(local, key=lambda r: r['gap_local']))
    group_stats = []
    features = ['human', 'n_vars', 'n_cons', 'n_pts', 'n_eq', 'n_ineq', 'dsl_len', 'p', 'cost0', 'candidates_sent_to_refinement0', 'conv_fraction0', 'refine_per_candidate0', 'search_fraction0', 'refine_fraction0', 'identify_fraction0', 'frac_left_box', 'frac_stuck', 'frac_wrong_answer', 'n_levels_ge2', 'n_basins_ge2', 'n_correct_basins', 'top_wrong_share', 'phi', 'p_feas_minus_infeas', 'collision_failure_fraction', 'degenerate_failure_fraction', 'degree', 'height', 'radical_depth', 'first_correct_grid', 'stable_correct_grid', 'poly_vars', 'max_degree', 'real_solutions', 'cond', 'q', 'construction_depth', 'solution_dependent_count', 'solution_depth', 'hidden_count_1e-07', 'all_nfev_median', 'hit_nfev_median', 'miss_nfev_median']
    for kind, subset in [('full', human_rows), ('local', local)]:
        for group in ['human_hard_solver_easy', 'human_easy_solver_hard', 'middle']:
            selected = [r for r in subset if r['group_' + kind] == group]
            for feature in features:
                values = [r[feature] for r in selected if math.isfinite(r[feature])]
                group_stats.append({'kind': kind, 'group': group, 'feature': feature, 'n_group': len(selected), 'n_measured': len(values), 'median': median(values), 'mean': float(np.mean(values)) if values else float('nan')})
    write_csv('group-statistics.csv', group_stats)
    pairs = []
    for a in human_rows:
        for b in human_rows:
            if a['contest'] != b['contest'] or a['n_vars'] != b['n_vars'] or a['human_rank_full'] - b['human_rank_full'] < .5:
                continue
            ratio = b['cost0'] / a['cost0']
            if ratio < 10:
                continue
            pairs.append({'human_hard': a['id'], 'human_easy': b['id'], 'contest': a['contest'], 'n_vars': a['n_vars'], 'human_gap': a['human'] - b['human'], 'cost_hard': a['cost0'], 'cost_easy': b['cost0'], 'ratio': ratio, 'p_hard': a['p'], 'p_easy': b['p'], 'source_hard': a['source0'], 'source_easy': b['source0'], 'cond_hard': a['cond'], 'cond_easy': b['cond']})
    write_csv('matched-reversal-pairs.csv', sorted(pairs, key=lambda x: -x['ratio']))
    summary = {'n_problems': len(rows), 'n_human': len(human_rows), 'n_human_local': len(local), 'local_records_seed0': records_total, 'human_by_contest': dict(Counter(r['contest'] for r in human_rows)), 'discovery_full_seed': 0, 'raw_record_fields': {','.join(k): v for k, v in raw_fieldsets.items()}, 'matched_pairs': len(pairs), 'matched_unique_problems': len(set(x[k] for x in pairs for k in ['human_hard', 'human_easy']))}
    for kind, subset in [('full', human_rows), ('local', local)]:
        summary[kind] = {}
        for group in ['human_hard_solver_easy', 'human_easy_solver_hard', 'middle']:
            selected = [r for r in subset if r['group_' + kind] == group]
            summary[kind][group] = {'n': len(selected), 'ids': [r['id'] for r in selected], 'sources': dict(Counter(r['source0'] for r in selected)), 'fail_causes': dict(Counter(r['failure_cause'] for r in selected)), 'msolve': dict(Counter(r['msolve_class'] for r in selected)), 'condition_status': dict(Counter(r['condition_status'] for r in selected))}
    (OUT / 'discovery-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    (OUT / 'input-manifest.json').write_text(json.dumps(SOURCES, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
