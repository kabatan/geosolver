"""Project unpolished HC solutions back to the identical original DSL and score."""
import csv
import json
from collections import Counter

import numpy as np
from measurement import OUT, context, score_point, finite_json

# These affect diagnostic grouping only, not the frozen residual/answer criteria.
IMAG_ATOL=1e-7
PROJECTED_MERGE_RTOL=1e-6
contexts={}
rows=[]
(OUT/'hc-scored').mkdir(exist_ok=True)
for path in sorted((OUT/'hc-runs').glob('*.json')):
    data=json.loads(path.read_text())
    row={k:data[k] for k in ['id','mode','method','seed','status']}
    if data['status']!='ok':
        row['error']=data.get('error'); rows.append(row); continue
    ctx=contexts.setdefault(data['id'],None)
    if ctx is None:
        ctx=context(data['id']); contexts[data['id']]=ctx
    source=json.loads((OUT/'inputs'/f"{data['id']}__{data['mode']}.json").read_text())
    names=source['variables']
    projection=[names.index('v_'+n) for n in ctx['bundle'].var_names]
    scored=[]
    distinct=[]
    hits=[]
    for j,point in enumerate(data['solutions']):
        z=np.array([complex(*v) for v in point])
        proj=z[projection]
        rec={'index':j,'full_real':bool(np.max(np.abs(z.imag))<=IMAG_ATOL),
             'projected_imag_max':float(np.max(np.abs(proj.imag)))}
        if rec['projected_imag_max']>IMAG_ATOL:
            rec['cls']='nonreal_projection'
        else:
            rec.update(score_point(ctx,proj.real))
            target=next((k for k,x in enumerate(distinct)
                         if np.max(np.abs(proj.real-x)/np.maximum(1.0,np.abs(x)))
                         <=PROJECTED_MERGE_RTOL),None)
            if target is None:
                distinct.append(proj.real.copy());target=len(distinct)-1
            rec['projected_cluster']=target
            if rec['cls']=='hit' and target not in hits:
                hits.append(target)
        scored.append(finite_json(rec))
    paths=data['paths']
    codes=dict(Counter(p['return_code'] for p in paths))
    row.update(D=source['total_degree_product'],tracked=data['tracked'],
        at_infinity=data['at_infinity'],failed=data['failed'],excess=data['excess'],
        n_success_paths=codes.get('success',0),
        n_singular_success_paths=sum(p['singular'] and p['return_code']=='success' for p in paths),
        n_hc_distinct=data['n_distinct_solutions'],n_hc_real=data['n_distinct_real'],
        n_projected_real_clusters=len(distinct),n_hit_clusters=len(hits),
        accepted_steps=sum(p['accepted_steps'] for p in paths),
        rejected_steps=sum(p['rejected_steps'] for p in paths),
        solve_seconds=data['solve_seconds'],outer_job_seconds=data['outer_job_seconds'],
        return_codes=json.dumps(codes,sort_keys=True),
        scored_counts=json.dumps(dict(Counter(r['cls'] for r in scored)),sort_keys=True))
    payload=dict(row,imag_atol=IMAG_ATOL,projected_merge_rtol=PROJECTED_MERGE_RTOL,
                 polished=False,scored_solutions=scored)
    (OUT/'hc-scored'/path.name).write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    rows.append(row)
fields=list(dict.fromkeys(k for r in rows for k in r))
with (OUT/'hc-summary.csv').open('w') as f:
    w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rows)
print(json.dumps({'jobs':len(rows),'ok':sum(r['status']=='ok' for r in rows),
                  'failed_paths':sum(r.get('failed',0) for r in rows)},indent=2))
