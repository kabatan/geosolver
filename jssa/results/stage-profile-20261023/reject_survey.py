"""Survey refinement statuses and rejection tags across run records (no re-execution)."""
import json, sys
from collections import Counter
from pathlib import Path

root = Path(sys.argv[1])
st_dbg, tag_dbg, st_cr, tags_ea, keys_bt, keys_vh = Counter(), Counter(), Counter(), Counter(), Counter(), Counter()
n = 0
for f in sorted(root.glob('runs/*/*.json')):
    d = json.load(open(f)); n += 1
    dg = (d.get('solver_result') or {}).get('diagnostics') or {}
    ps = dg.get('pipeline_summary') or {}
    for c in ps.get('debug_candidates') or []:
        st_dbg[c.get('refinement_status')] += 1
        tag_dbg[c.get('rejection_tag')] += 1
    for c in dg.get('candidate_records') or []:
        st_cr[c.get('refinement_status')] += 1
        bt = c.get('branch_trace')
        if isinstance(bt, dict): keys_bt.update(bt.keys())
        vh = c.get('verification_history')
        if isinstance(vh, list) and vh and isinstance(vh[0], dict): keys_vh.update(vh[0].keys())
    for t in (ps.get('exact_assembly') or {}).get('rejection_tags') or []:
        tags_ea[t] += 1
print('runs', n)
print('debug refinement_status', st_dbg.most_common(20))
print('debug rejection_tag', tag_dbg.most_common(30))
print('candidate_records refinement_status', st_cr.most_common(20))
print('exact_assembly rejection_tags (per run presence)', tags_ea.most_common(30))
print('branch_trace keys', keys_bt.most_common(20))
print('verification_history[0] keys', keys_vh.most_common(20))
