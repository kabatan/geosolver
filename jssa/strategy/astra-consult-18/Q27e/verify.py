"""Fixed saved-seed validation. Does not invoke a solver or change input files."""
import csv
import datetime
import hashlib
import json
import math
import time
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent


def read_csv(p):
    with p.open() as f:
        return list(csv.DictReader(f))


def save_csv(name, rows):
    with (OUT / name).open('w') as f:
        w = csv.DictWriter(f, fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
        w.writeheader()
        w.writerows(rows)


def main():
    started = time.monotonic()
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    lock = json.loads((OUT / 'registration-lock.json').read_text())
    for name, digest in lock['files'].items():
        assert hashlib.sha256((OUT / name).read_bytes()).hexdigest() == digest, name
    rows = read_csv(OUT / 'joined-discovery.csv')
    by_id = {r['id']: r for r in rows}
    hr = [r for r in rows if r['human'] != 'nan']
    local = [r for r in hr if r['group_local']]
    full_path = ROOT / 'jssa/results/stage-profile-20261023/per-case.csv'
    full_rows = read_csv(full_path)
    full = {(r['case_id'], int(r['seed'])): r for r in full_rows}
    def cost(cid, seed):
        r = full[cid, seed]
        return float(r['wall_time_s']) if r['correct'] == 'True' else 180.
    def convergence(cid, seed):
        r = full[cid, seed]
        den = int(r['candidates_sent_to_refinement'])
        return int(r['candidates_converged']) / den if den else float('nan')
    pair_rows = []
    pairs = read_csv(OUT / 'matched-reversal-pairs.csv')
    for pair in pairs:
        for seed in [0, 1, 2]:
            a, b = pair['human_hard'], pair['human_easy']
            ratio = cost(b, seed) / cost(a, seed)
            pair_rows.append({'human_hard': a, 'human_easy': b, 'seed': seed, 'cost_hard': cost(a, seed), 'cost_easy': cost(b, seed), 'ratio': ratio, 'tenfold': ratio >= 10, 'correct_hard': full[a, seed]['correct'], 'correct_easy': full[b, seed]['correct'], 'source_hard': full[a, seed]['final_answer_source'], 'source_easy': full[b, seed]['final_answer_source'], 'convergence_hard': convergence(a, seed), 'convergence_easy': convergence(b, seed)})
    save_csv('validation-pairs.csv', pair_rows)
    pair_counts = {s: sum(r['tenfold'] for r in pair_rows if r['seed'] == s) for s in [0, 1, 2]}
    anchors = sorted({r['human_easy'] for r in pairs})
    p2_detail = {a: sum(all(next(r for r in pair_rows if r['human_hard'] == p['human_hard'] and r['human_easy'] == a and r['seed'] == s)['tenfold'] for s in [1, 2]) for p in pairs if p['human_easy'] == a) for a in anchors}
    p3_count = sum(convergence(a, s) <= .5 for a in anchors for s in [1, 2])
    ranks_full = {}
    for seed in [0, 1, 2]:
        for contest in ['AIME', 'HMMT']:
            sub = [r for r in hr if r['contest'] == contest]
            ranks = rankdata([cost(r['id'], seed) for r in sub]) / len(sub)
            ranks_full.update({(r['id'], seed): rank for r, rank in zip(sub, ranks)})
    fixed_full = []
    summary_full = []
    for group in ['human_hard_solver_easy', 'human_easy_solver_hard']:
        selected = [r for r in hr if r['group_full'] == group]
        for seed in [0, 1, 2]:
            for r in selected:
                cid = r['id']; gap = float(r['human_rank_full']) - ranks_full[cid, seed]
                retained = gap >= .4 if group == 'human_hard_solver_easy' else gap <= -.4
                fixed_full.append({'id': cid, 'group': group, 'seed': seed, 'cost': cost(cid, seed), 'source': full[cid, seed]['final_answer_source'], 'correct': full[cid, seed]['correct'], 'rank_gap': gap, 'retains_extreme': retained})
            subset = [r for r in fixed_full if r['group'] == group and r['seed'] == seed]
            summary_full.append({'group': group, 'seed': seed, 'n': len(subset), 'median_cost': float(np.median([r['cost'] for r in subset])), 'correct': sum(r['correct'] == 'True' for r in subset), 'bypass': sum(r['source'] in ['algebraic_branch_discovery', 'direct_constant_no_variables'] for r in subset), 'retains_extreme': sum(r['retains_extreme'] for r in subset), 'same_gap_sign': sum(r['rank_gap'] > 0 if group == 'human_hard_solver_easy' else r['rank_gap'] < 0 for r in subset)})
    save_csv('validation-full-groups.csv', fixed_full)
    raw1 = {}
    manifest = {'jssa/results/stage-profile-20261023/per-case.csv': hashlib.sha256(full_path.read_bytes()).hexdigest()}
    raw_count = 0; short_count = 0; missing_start = 0; missing_x = 0
    for r in rows:
        assert time.monotonic() - started < 90
        p = ROOT / 'jssa/difficulty/minima/raw-323-seed1' / (r['id'] + '.json')
        data = p.read_bytes()
        manifest[str(p.relative_to(ROOT))] = hashlib.sha256(data).hexdigest()
        raw = json.loads(data)
        rr = raw.get('records', [])
        raw_count += len(rr)
        if float(r['n_vars']) > 0 and len(rr) < 200:
            short_count += 1
        missing_start += sum('start' not in x for x in rr)
        missing_x += sum('x' not in x for x in rr)
        pp = sum(x['cls'] == 'hit' for x in rr) / len(rr) if rr else float('nan')
        raw1[r['id']] = {'p': pp, 'n': len(rr), 'hits': sum(x['cls'] == 'hit' for x in rr), 'all_nfev': float(np.median([x['nfev'] for x in rr])) if rr else float('nan')}
    rank_local = {}
    for contest in ['AIME', 'HMMT']:
        sub = [r for r in local if r['contest'] == contest]
        ranks = rankdata([-raw1[r['id']]['p'] for r in sub]) / len(sub)
        rank_local.update({r['id']: rank for r, rank in zip(sub, ranks)})
    fixed_local = []; summary_local = []
    for group in ['human_hard_solver_easy', 'human_easy_solver_hard']:
        sub = [r for r in local if r['group_local'] == group]
        for r in sub:
            cid = r['id']; gap = float(r['human_rank_local']) - rank_local[cid]
            retained = gap >= .4 if group == 'human_hard_solver_easy' else gap <= -.4
            fixed_local.append({'id': cid, 'group': group, 'p0': float(r['p']), 'p1': raw1[cid]['p'], 'n1': raw1[cid]['n'], 'hit1': raw1[cid]['hits'], 'rank_gap1': gap, 'retains_extreme': retained, 'nfev0': float(r['all_nfev_median']), 'nfev1': raw1[cid]['all_nfev'], 'stable_correct_grid': r['stable_correct_grid']})
        selected = [r for r in fixed_local if r['group'] == group]
        summary_local.append({'group': group, 'n': len(selected), 'median_p0': float(np.median([r['p0'] for r in selected])), 'median_p1': float(np.median([r['p1'] for r in selected])), 'retains_extreme': sum(r['retains_extreme'] for r in selected), 'same_gap_sign': sum(r['rank_gap1'] > 0 if group == 'human_hard_solver_easy' else r['rank_gap1'] < 0 for r in selected)})
    save_csv('validation-local-groups.csv', fixed_local)
    high = [r for r in fixed_local if r['group'] == 'human_hard_solver_easy']
    low = [r for r in fixed_local if r['group'] == 'human_easy_solver_hard']
    swaps = [{'high_id': a['id'], 'low_id': b['id'], 'p0_high': a['p0'], 'p0_low': b['p0'], 'p1_high': a['p1'], 'p1_low': b['p1']} for a in high for b in low if a['p0'] > b['p0'] and a['p1'] < b['p1']]
    (OUT / 'local-order-reversals.json').write_text(json.dumps(swaps, indent=2))
    s = {'validation_started_utc': timestamp, 'elapsed_seconds': time.monotonic() - started, 'new_solver_runs': 0, 'seed1_records': raw_count, 'seed1_short_problems': short_count, 'seed1_missing_start_records': missing_start, 'seed1_missing_x_records': missing_x, 'full_runs': len(full_rows), 'full_correct': sum(r['correct'] == 'True' for r in full_rows), 'P1': {'counts': pair_counts, 'pass': all(pair_counts[s] >= 4 for s in [1, 2])}, 'P2': {'persistent_pairs_by_anchor': p2_detail, 'pass': all(v >= 1 for v in p2_detail.values())}, 'P3': {'count': p3_count, 'out_of': 4, 'pass': p3_count >= 3}, 'full_fixed_groups': summary_full, 'local_fixed_groups': summary_local, 'local_pair_order_swaps': len(swaps)}
    encoded = json.dumps(s, ensure_ascii=False, indent=2, default=lambda x: x.item())
    (OUT / 'validation-summary.json').write_text(encoded)
    (OUT / 'validation-input-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(encoded)


if __name__ == '__main__':
    main()
