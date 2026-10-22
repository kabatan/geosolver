"""Per-run stage profile from existing frozen-solver run records (no re-execution)."""
import csv, json, statistics, sys
from collections import Counter
from pathlib import Path

root = Path(sys.argv[1])  # .../jssa-main-j6-20261022
out = Path(sys.argv[2])
PH = ['initial_probe', 'search', 'refinement', 'exact_assembly', 'rescue', 'discrete_completion']
rows = []
for f in sorted(root.glob('runs/*/*.json')):
    d = json.load(open(f))
    sr = d.get('solver_result') or {}
    dg = sr.get('diagnostics') or {}
    ps = dg.get('pipeline_summary') or {}
    pt = dg.get('phase_timings') or {}
    ct = dg.get('counters') or {}
    ledger = ps.get('candidate_ledger') or []
    by_id = {c.get('candidate_id'): c for c in ledger}
    aid = ps.get('answer_source_candidate_id')
    src = by_id.get(aid) or {}
    if not src and aid is not None:
        for c in list(ps.get('debug_candidates') or []) + list(dg.get('candidate_records') or []):
            if c.get('candidate_id') == aid and c.get('candidate_uid'):
                parts = str(c['candidate_uid']).split('/')
                src = {'origin_phase': parts[0], 'origin_backend': parts[1] if len(parts) > 1 else None,
                       'candidate_uid': c['candidate_uid']}
                break
    stf = ps.get('search_staged_fallback') or {}
    nvar = len(ledger[0]['values']) if ledger and ledger[0].get('values') is not None else None
    row = {
        'case': f.parent.name, 'seed': f.stem, 'status': sr.get('status'),
        'elapsed': sr.get('elapsed_seconds') or d.get('process', {}).get('elapsed_seconds'),
        'timed_out': d.get('process', {}).get('timed_out'),
        'backend': dg.get('pipeline_backend'),
        'nvar': nvar,
        'algebraic': bool((ps.get('initial_probe') or {}).get('algebraic_branch_discovery')) or None,
        'fallback_triggered': stf.get('triggered'), 'selected_stage': stf.get('selected_stage'),
        'answer_origin_phase': src.get('origin_phase'), 'answer_origin_backend': src.get('origin_backend'),
        'answer_uid': src.get('candidate_uid'),
        'search_evals': (ps.get('search') or {}).get('evaluation_count'),
        'ref_attempted': (ps.get('refinement') or {}).get('attempted_count'),
        'ref_converged': (ps.get('refinement') or {}).get('converged_count'),
        'exact_accepted': (ps.get('exact_assembly') or {}).get('accepted_count'),
        'exact_rejected': (ps.get('exact_assembly') or {}).get('rejected_false_positive_count'),
        'rescue_triggered': (ps.get('phase_rescue') or {}).get('triggered'),
        'ajac_requests': ct.get('analytic_jacobian_plan_requests'),
        'ajac_unsupported': ct.get('analytic_jacobian_plan_unsupported'),
        'warm_newton_attempts': ct.get('warm_newton_attempts'), 'warm_newton_successes': ct.get('warm_newton_successes'),
    }
    for p in PH:
        row['t_' + p] = pt.get(p)
    rows.append(row)
with open(out, 'w', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

def num(x):
    return x if isinstance(x, (int, float)) else 0.0
print('runs', len(rows), Counter(r['status'] for r in rows))
tot = {p: sum(num(r['t_' + p]) for r in rows) for p in PH}
T = sum(tot.values())
print('time share by phase (all runs):', {p: f"{tot[p]/T:.1%}" for p in PH}, f'total {T:.0f}s')
slow = [r for r in rows if num(r['elapsed']) > 30]
dom = Counter(max(PH, key=lambda p: num(r['t_' + p])) for r in slow)
print('runs >30s:', len(slow), 'dominant phase:', dict(dom))
dom_all = Counter(max(PH, key=lambda p: num(r['t_' + p])) for r in rows)
print('dominant phase all runs:', dict(dom_all))
print('answer origin:', Counter((r['answer_origin_phase'], r['answer_origin_backend']) for r in rows if r['status'] == 'solved'))
print('fallback triggered:', Counter(r['fallback_triggered'] for r in rows), 'selected:', Counter(r['selected_stage'] for r in rows))
print('backend:', Counter(r['backend'] for r in rows))
print('analytic jac unsupported (all requests):', sum(1 for r in rows if r['ajac_requests'] and r['ajac_unsupported'] == r['ajac_requests']), 'of', sum(1 for r in rows if r['ajac_requests']))
for nm in ['AIME-2015-I-07', 'HMMT-2019-FEB-GEO-10']:
    for r in rows:
        if r['case'].upper() == nm.upper():
            print(nm, r['seed'], r['status'], round(num(r['elapsed']), 1), 'nvar', r['nvar'], {p: round(num(r['t_' + p]), 1) for p in PH}, 'ref', r['ref_converged'], '/', r['ref_attempted'], 'exact rej', r['exact_rejected'], 'ajac', r['ajac_unsupported'], '/', r['ajac_requests'], 'origin', r['answer_origin_phase'], r['answer_origin_backend'])
