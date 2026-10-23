"""Descriptive joins; no fitting, prediction model, or solver execution."""
from __future__ import annotations
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
from scipy.stats import spearmanr, rankdata
from measure import HERE, ROOT, clean, write_json


def read_csv(path):
    return list(csv.DictReader(path.open()))


def rho(rows, key, outcome, partial=False):
    data = [r for r in rows if r.get(key) is not None and r.get(outcome) is not None]
    n=len(data)
    if n<3:
        return {'n':n,'rho':None}
    x=np.array([r[key] for r in data]); y=np.array([r[outcome] for r in data])
    if partial:
        C=np.column_stack([np.ones(n),rankdata([r['n_vars'] for r in data])])
        x=rankdata(x); y=rankdata(y)
        x=x-C@np.linalg.lstsq(C,x,rcond=None)[0]
        y=y-C@np.linalg.lstsq(C,y,rcond=None)[0]
        value=float(np.corrcoef(x,y)[0,1])
    else:
        value=float(spearmanr(x,y).statistic)
    return {'n':n,'rho':value}


def main():
    data=json.loads((HERE/'measurements.json').read_text())
    basins={r['id']:r for r in read_csv(ROOT/'jssa/difficulty/minima/basins-323.csv')}
    humans={r['case_id']:r for r in read_csv(ROOT/'jssa/difficulty/ghost-1023/human_feat.csv')}
    stages=defaultdict(list)
    for r in read_csv(ROOT/'jssa/results/stage-profile-20261023/per-case.csv'):
        stages[r['case_id']].append(r)
    rows=[]
    for r in data:
        b=basins.get(r['id'],{}); hu=humans.get(r['id'],{}); ss=stages.get(r['id'],[])
        row={k:r.get(k) for k in ('id','status','n_vars','n_hits','n_raw','n_smooth','raw_residual_max','smooth_residual_max','target','hit_k')}
        row.update(p=float(b['p']) if b.get('p') else None,n_starts=int(b['n_starts']) if b.get('n_starts') else None,
                   human=float(hu['human']) if hu.get('human') else None,contest=hu.get('contest'))
        n_cand=sum(int(s['candidates_sent_to_refinement']) for s in ss)
        t_ref=sum(float(s['refinement_time_s']) for s in ss)
        row.update(refinement_seconds_mean=t_ref/len(ss) if ss else None,
                   refinement_seconds_per_candidate=t_ref/n_cand if n_cand else None,
                   candidates_mean=n_cand/len(ss) if ss else None,
                   converged_fraction=sum(int(s['candidates_converged']) for s in ss)/n_cand if n_cand else None)
        row.update({k:r.get('main',{}).get(k) for k in ('cond','kx','ktau','q','smin','smax','grad_norm','weak_alignment')})
        row['raw_cond']=r.get('raw_metric',{}).get('cond')
        row['box_cond']=r.get('box_metric',{}).get('cond')
        row['box_q']=r.get('box_metric',{}).get('q')
        if row.get('cond') is not None:
            row['sharpness_ratio']=row['cond']**2
            row['min_curvature']=row['smin']**2
        rows.append(row)
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with (HERE/'per-problem.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,keys);w.writeheader();w.writerows(rows)
    regular=[r for r in rows if r['status']=='regular_stable']
    summary={'counts':dict(Counter(r['status'] for r in rows)), 'n_regular':len(regular),
             'n_regular_multivar':sum(r['n_vars']>=2 for r in regular),
             'q_le_001':sum(r['q']<=.01 for r in regular),
             'q_le_01_descriptive_only':sum(r['q']<=.1 for r in regular),
             'box_q_le_001':sum(r['box_q'] is not None and r['box_q']<=.01 for r in regular),
             'n_human_regular':sum(r['human'] is not None for r in regular)}
    required=max(10,math.ceil(.1*len(regular)))
    passed=summary['q_le_001']>=required
    summary.update(separation_prevalence_required=required,
                   separation_prevalence_gate_passed=passed,
                   # Natural-input confirmation is a separate, subsequent step.
                   strong_claim_gate_passed=None if passed else False)
    summary['quantiles']={k:dict(zip(['min','q25','median','q75','max'],np.quantile([r[k] for r in regular if r.get(k) is not None],[0,.25,.5,.75,1]).tolist()))
                          for k in ('cond','kx','ktau','q','p','refinement_seconds_per_candidate')}
    summary['spearman']={k:{o:rho(regular,k,o) for o in ('p','refinement_seconds_mean','refinement_seconds_per_candidate','candidates_mean')}
                         for k in ('cond','kx','ktau','raw_cond','box_cond')}
    summary['partial_rank_nvars']={k:{o:rho(regular,k,o,True) for o in ('p','refinement_seconds_mean','refinement_seconds_per_candidate')}
                                  for k in ('cond','kx','ktau')}
    summary['human_by_contest']={c:{k:rho([r for r in regular if r['contest']==c],k,'human') for k in ('cond','kx','ktau','p')}
                                for c in ('AIME','HMMT','JMO')}
    quartiles=[]
    for i, part in enumerate(np.array_split(sorted(regular,key=lambda r:(r['cond'],r['id'])),4)):
        part=list(part)
        quartiles.append({'quartile':i+1,'n':len(part),**{k:float(np.median([r[k] for r in part])) for k in ('cond','p','refinement_seconds_mean','refinement_seconds_per_candidate','candidates_mean')}})
    summary['condition_quartiles']=quartiles
    summary['smallest_q']=sorted(regular,key=lambda r:r['q'])[:6]
    summary['highest_condition']=sorted(regular,key=lambda r:r['cond'],reverse=True)[:6]
    write_json('summary.json',summary)
    selected=[r['id'] for r in regular if r['q']<=.01][:3]+[r['id'] for r in regular if r['q']>.01][:3]
    write_json('selected-controls.json',selected)
    print(json.dumps(clean(summary),ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
