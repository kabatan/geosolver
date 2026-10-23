"""Existing-data exploration using only stdlib/numpy and seed 0. No solver run."""
from pathlib import Path
from collections import Counter, defaultdict
import csv, hashlib, io, json, math, time
import numpy as np

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
inputs=[]

def read(path):
    p=ROOT/path; b=p.read_bytes()
    inputs.append(dict(path=str(p.relative_to(ROOT)),bytes=len(b),sha256=hashlib.sha256(b).hexdigest()))
    return b

def table(path):
    return list(csv.DictReader(io.StringIO(read(path).decode())))

def clean(v):
    if isinstance(v,dict): return {str(k):clean(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)): return [clean(x) for x in v]
    if isinstance(v,np.generic): return clean(v.item())
    if isinstance(v,float) and not math.isfinite(v): return None
    return v

def savejson(name,x):
    (OUT/name).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2)+'\n')

def savecsv(name,rows):
    if not rows: return
    with (OUT/name).open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

def q(a):
    a=np.asarray(a,float); a=a[np.isfinite(a)]
    if not len(a): return {}
    return dict(n=len(a),mean=a.mean(),median=np.median(a),p90=np.quantile(a,.9),
                p95=np.quantile(a,.95),p99=np.quantile(a,.99),max=a.max(),cv=a.std()/a.mean() if a.mean() else None)

def hill(a,f):
    a=np.sort(np.asarray(a,float)); a=a[np.isfinite(a)&(a>0)]
    k=max(5,int(len(a)*f))
    if len(a)<=k: return None
    v=np.log(a[-k:]/a[-k-1]).sum()
    return k/v if v else None

def col(rows,k): return np.array([r[k] for r in rows],float)
def selected(rows,fields,n=15): return [{k:r[k] for k in fields} for r in rows[:n]]
def med(rows,k): return float(np.median(col(rows,k))) if rows else None

def local_summary(j):
    rr=j.get('records',[])
    if not rr: return None
    hit=np.array([r['cls']=='hit' for r in rr]); n=col(rr,'nfev'); sec=col(rr,'sec'); d=j['n_vars']
    m=float(np.median(n)); fast=n<=m; slow=~fast
    r=dict(id=j['case_id'],n_vars=d,n_constraints=j['n_constraints'],method='Powell' if d>j['n_constraints'] else 'LM',
           n=len(rr),requested=j['starts_requested'],hits=int(hit.sum()),p=hit.mean(),elapsed=j.get('elapsed'),
           nfev_mean=n.mean(),nfev_median=m,nfev_p90=np.quantile(n,.9),nfev_p99=np.quantile(n,.99),nfev_max=n.max(),nfev_cv=n.std()/n.mean(),
           sec_median=np.median(sec),sec_mean=sec.mean(),sec_p99=np.quantile(sec,.99),first_sec=sec[0],
           warmup_ratio=sec[0]/np.median(sec[1:]) if len(sec)>1 else np.nan,normalized_nfev_median=m/(d+1),
           hit_nfev_median=np.median(n[hit]) if hit.any() else np.nan,miss_nfev_median=np.median(n[~hit]) if (~hit).any() else np.nan,
           p_fast=hit[fast].mean(),p_slow=hit[slow].mean() if slow.any() else np.nan,n_fast=int(fast.sum()),n_slow=int(slow.sum()),
           hit_slow=int(hit[slow].sum()),hit_fast=int(hit[fast].sum()),nref=len(j.get('references',[])))
    r['hit_miss_nfev_ratio']=r['hit_nfev_median']/r['miss_nfev_median']
    r['p_slow_minus_fast']=r['p_slow']-r['p_fast']
    base=n.mean()/hit.mean() if hit.any() else np.inf
    choices=[]
    for b in sorted(set([int((d+1)*z) for z in [4,8,16,32,64,128]]+[int(n.max())])):
        p=(hit&(n<=b)).mean(); c=np.minimum(n,b).mean()/p if p else np.inf
        choices.append((c,b,p))
    c,b,pb=min(choices)
    r.update(restart_baseline=base,restart_cutoff=b,restart_cost=c,restart_ratio=c/base if np.isfinite(base) else np.nan,restart_p=pb)
    return r

def main():
    started=time.monotonic(); per=[]; pool=defaultdict(list); status=Counter(); schema=Counter()
    for p in sorted((ROOT/'jssa/difficulty/minima/raw-323').glob('*.json')):
        j=json.loads(read(p.relative_to(ROOT))); status[j['status']]+=1
        r=local_summary(j)
        if r is None: continue
        per.append(r)
        for x in j['records']:
            schema.update(x.keys())
            for k in ['sec','nfev']: pool[k].append(x[k])
            pool['nfev_scaled'].append(x['nfev']/(r['n_vars']+1))
            pool['nfev_problem_scaled'].append(x['nfev']/r['nfev_median'])
            pool['sec_problem_scaled'].append(x['sec']/r['sec_median'])
            if x['k']>0: pool['sec_without_first'].append(x['sec'])
    savecsv('exploration-local-seed0.csv',per); index={r['id']:r for r in per}
    profile=table('jssa/results/stage-profile-20261023/per-case.csv'); joint=[]
    for x in profile:
        if x['seed']!='0': continue
        r={k:(float(v) if k.endswith('_s') else int(v) if k.startswith('candidates_') else v=='True' if k=='correct' else v) for k,v in x.items()}
        r['id']=r.pop('case_id'); r.update(index.get(r['id'],dict(n_vars=0,p=np.nan)))
        r['refinement_fraction']=r['refinement_time_s']/r['wall_time_s']; joint.append(r)
    # Different schemas for zero-variable rows; standardize output columns.
    fields=list(dict.fromkeys(k for r in joint for k in r)); savecsv('exploration-profile-seed0.csv',[{k:r.get(k) for k in fields} for r in joint])
    strata=[]
    for d in sorted(set(r['n_vars'] for r in per)):
        g=[r for r in per if r['n_vars']==d]; pg=[r for r in joint if r['n_vars']==d]
        strata.append(dict(n_vars=d,problems=len(g),p_median=med(g,'p'),median_nfev=med(g,'nfev_median'),scaled_nfev=med(g,'normalized_nfev_median'),local_sec=med(g,'sec_median'),full_sec=med(pg,'wall_time_s'),nfev_min=min(col(g,'nfev_median')),nfev_max=max(col(g,'nfev_median')),full_min=min(col(pg,'wall_time_s')),full_max=max(col(pg,'wall_time_s'))))
    savecsv('exploration-size-strata.csv',strata)
    feas=table('jssa/difficulty/start-feasibility-1023/per-problem.csv')
    reversals=[r for r in feas if int(r['n_feas'])>=20 and int(r['n_infeas'])>=20 and int(r['hit_infeas'])/int(r['n_infeas'])-int(r['hit_feas'])/int(r['n_feas'])>=.2]
    ms=table('jssa/strategy/astra-consult-17/H/sources/comparison-cases.csv')
    prec=table('jssa/strategy/astra-consult-18/q21b-number-theory/precision.csv')
    precrows=[]
    for d in sorted(set(int(r['precision']) for r in prec)):
        g=[r for r in prec if int(r['precision'])==d]
        precrows.append(dict(precision=d,runs=len(g),correct=sum(r['status']=='correct' for r in g),seconds_median=med(g,'seconds'),seconds_p99=np.quantile(col(g,'seconds'),.99)))
    savecsv('exploration-precision.csv',precrows)
    ref=table('jssa/difficulty/multiplicity/per-candidate.csv')
    gmb=table('jssa/results/gmb-success-definition/per-trial.csv')
    common=table('jssa/difficulty/common-start/summary.csv')
    wall=col(joint,'wall_time_s'); fastslow=[r for r in joint if r['p']>=.9 and r['wall_time_s']>=30]; zerohit=[r for r in joint if r['p']==0 and r['correct']]
    tail={c:dict(quantiles=q(a),hill_by_top_fraction={str(f):hill(a,f) for f in [.02,.05,.1,.2]}) for c,a in pool.items()}
    summary=dict(raw_status=dict(status),raw_records=len(pool['nfev']),raw_schema=dict(schema),raw_problems=len(per),
                 method_counts=dict(Counter(r['method'] for r in per)),truncated_problems=sum(r['n']<r['requested'] for r in per),tail=tail,
                 wall_seed0=q(wall),wall_hill={str(f):hill(wall,f) for f in [.02,.05,.1,.2]},wall_top10_share=np.sort(wall)[-math.ceil(len(wall)*.1):].sum()/wall.sum(),
                 warmup_ratio=q(col(per,'warmup_ratio')),first_time_share=sum(col(per,'first_sec'))/sum(pool['sec']),local_cv_gt1=sum(r['nfev_cv']>1 for r in per),
                 restart_counts=dict(estimable=sum(np.isfinite(r['restart_ratio']) for r in per),less_half=sum(r['restart_ratio']<=.5 for r in per),less_08=sum(r['restart_ratio']<=.8 for r in per)),
                 restart_best=selected(sorted(per,key=lambda r:r['restart_ratio'] if np.isfinite(r['restart_ratio']) else np.inf),['id','n_vars','n','p','restart_cutoff','restart_ratio','hit_miss_nfev_ratio']),
                 slow_success=selected(sorted([r for r in per if r['n_fast']>=30 and r['n_slow']>=30],key=lambda r:-r['p_slow_minus_fast']),['id','n_vars','p','p_fast','p_slow','p_slow_minus_fast','nfev_median']),
                 heavy_per_problem=selected(sorted(per,key=lambda r:-r['nfev_cv']),['id','n_vars','method','n','p','nfev_cv','nfev_median','nfev_p99','nfev_max']),
                 local_fast_full_slow=selected(sorted(fastslow,key=lambda r:-r['wall_time_s']),['id','n_vars','p','wall_time_s','final_answer_source','candidates_sent_to_refinement','candidates_converged','refinement_time_s','search_time_s']),
                 local_fast_full_slow_count=len(fastslow),local_zero_full_solved=selected(sorted(zerohit,key=lambda r:r['wall_time_s']),['id','n_vars','p','wall_time_s','final_answer_source']),local_zero_full_solved_count=len(zerohit),
                 source_timing=[dict(source=s,runs=len(g),wall=q(col(g,'wall_time_s')),refine=q(col(g,'refinement_time_s')),search=q(col(g,'search_time_s'))) for s in sorted(set(r['final_answer_source'] for r in joint)) for g in [[r for r in joint if r['final_answer_source']==s]]],
                 size_strata=strata,feasibility_reversal=len(reversals),msolve_class_counts=dict(Counter(r['msolve_class'] for r in ms)),msolve_roots_count=sum(bool(r['real_solutions']) for r in ms),
                 refinement_rows=len(ref),refinement_problems=len(set(r['id'] for r in ref)),gmb_rows=len(gmb),gmb_problems=len(set(r['case_id'] for r in gmb)),gmb_time_available=any('time' in c or 'sec' in c for c in gmb[0]),common_start_problems=len(common),elapsed_seconds=time.monotonic()-started)
    savejson('exploration-summary.json',summary); savejson('input-manifest-explore.json',inputs)
    print(json.dumps(clean({k:v for k,v in summary.items() if k not in ['raw_schema','source_timing']}),ensure_ascii=False,indent=2))

if __name__=='__main__': main()
