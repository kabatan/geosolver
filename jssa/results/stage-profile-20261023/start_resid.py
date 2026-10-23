"""Refinement outcome vs. the candidate's residual when it left search (from run records, no re-execution)."""
import json, math, sys
from collections import Counter, defaultdict
from pathlib import Path

root = Path(sys.argv[1])
bins = [1e-12, 1e-8, 1e-4, 1e-2, 1, 10, 100, float('inf')]
def b(x):
    for e in bins:
        if x <= e: return e
tab = defaultdict(Counter); matched = unmatched = 0
for f in sorted(root.glob('runs/*/*.json')):
    d = json.load(open(f))
    dg = (d.get('solver_result') or {}).get('diagnostics') or {}
    ps = dg.get('pipeline_summary') or {}
    led = {c.get('candidate_id'): c for c in ps.get('candidate_ledger') or []}
    for c in dg.get('candidate_records') or []:
        rs = c.get('refinement_status')
        if rs == 'direct_evaluation': continue
        e = led.get(c.get('candidate_id'))
        if not e or not isinstance(e.get('residual_norm'), (int, float)):
            unmatched += 1; continue
        matched += 1
        fate = 'reached' if rs == 'target_reached' else 'failed'
        tab[b(float(e['residual_norm']))][fate] += 1
print('matched', matched, 'unmatched', unmatched)
print('search residual <= bin : reached / failed (reach rate)')
for e in bins:
    r, fl = tab[e]['reached'], tab[e]['failed']
    if r + fl: print(f'  <= {e:g}: {r} / {fl} ({r/(r+fl):.0%})')
