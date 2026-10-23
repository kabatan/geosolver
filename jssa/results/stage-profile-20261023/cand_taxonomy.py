"""Per-candidate fate taxonomy from run records: refinement outcome x final verification (no re-execution)."""
import csv, json, sys
from collections import Counter, defaultdict
from pathlib import Path

root = Path(sys.argv[1]); out = Path(sys.argv[2])
rows = []
fate_all = Counter(); fate_slow = Counter(); vstat = Counter(); htags = Counter()
for f in sorted(root.glob('runs/*/*.json')):
    d = json.load(open(f))
    sr = d.get('solver_result') or {}
    dg = sr.get('diagnostics') or {}
    ps = dg.get('pipeline_summary') or {}
    pt = dg.get('phase_timings') or {}
    accepted = set()
    for r in ps.get('exact_candidate_records') or []:
        c = r.get('candidate') or {}
        if (r.get('exact_result') or {}).get('exact_status') == 'identified':
            accepted.add(c.get('candidate_id'))
    fates = Counter()
    for c in dg.get('candidate_records') or []:
        rs = c.get('refinement_status')
        vh = c.get('verification_history') or []
        last = vh[-1] if vh and isinstance(vh[-1], dict) else {}
        if rs == 'direct_evaluation':
            fate = 'direct'
        elif rs != 'target_reached':
            fate = 'refine_fail:' + str(rs)
        elif c.get('candidate_id') in accepted:
            fate = 'accepted'
        else:
            tags = last.get('hard_failure_tags') or []
            if tags:
                t = str(tags[0]).split('[')[0]
                fate = 'reached_but_rejected:' + t
            elif last.get('verified') is False:
                fate = 'reached_but_rejected:unverified'
            else:
                fate = 'reached_not_accepted:other'
            for t in tags: htags[str(t).split('[')[0]] += 1
        vstat[last.get('status')] += 1
        fates[fate] += 1
    slow = (sr.get('elapsed_seconds') or 0) > 30
    fate_all.update(fates)
    if slow: fate_slow.update(fates)
    rows.append({'case': f.parent.name, 'seed': f.stem, 'status': sr.get('status'),
                 'elapsed': sr.get('elapsed_seconds'), 't_refinement': pt.get('refinement'),
                 't_exact': pt.get('exact_assembly'), 'n_cand': sum(fates.values()),
                 **{k: v for k, v in fates.items()}})
keys = sorted({k for r in rows for k in r})
with open(out, 'w', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=keys); w.writeheader(); w.writerows(rows)
tot = sum(fate_all.values()); ts = sum(fate_slow.values())
print('candidates all', tot)
for k, v in fate_all.most_common(): print(f'  {k}: {v} ({v/tot:.1%})')
print('candidates in runs >30s', ts)
for k, v in fate_slow.most_common(): print(f'  {k}: {v} ({v/ts:.1%})')
print('final verification status', vstat.most_common(10))
print('hard failure tag kinds (rejected after reaching target)', htags.most_common(12))
