"""Frozen seed split confirmation of saved endpoints; no local solver execution."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib, json, math, time
import numpy as np
from explore import ROOT, OUT, inputs, read, table, q, hill, clean, savejson, savecsv, local_summary, col, med


def cost(rr,b,overhead=0):
    n=col(rr,'nfev'); h=np.array([r['cls']=='hit' for r in rr]); b=np.inf if b is None else b
    p=(h&(n<=b)).mean()
    return (np.minimum(n,b).mean()+overhead)/p if p else np.inf


def wilson(k,n):
    if not n: return (np.nan,np.nan)
    z=1.959963984540054; p=k/n; den=1+z*z/n
    a=(p+z*z/(2*n))/den; b=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return (a-b,a+b)


def loadseed(seed):
    dirname='raw-323' if seed==0 else 'raw-323-seed1'
    data={}; pp=[]; rows=[]; schema=Counter()
    for path in sorted((ROOT/'jssa/difficulty/minima'/dirname).glob('*.json')):
        j=json.loads(read(path.relative_to(ROOT))); data[j['case_id']]=j
        r=local_summary(j)
        if r is None: continue
        pp.append(r)
        for x in j['records']:
            schema.update(x.keys())
            rows.append(dict(id=j['case_id'],method=r['method'],n_vars=j['n_vars'],cls=x['cls'],nfev=x['nfev'],sec=x['sec'],k=x['k'],problem_cv=r['nfev_cv']))
    savecsv(f'local-seed{seed}.csv',pp)
    top=sorted(rows,key=lambda r:-r['nfev'])[:math.ceil(.01*len(rows))]
    topsec=sorted(rows,key=lambda r:-r['sec'])[:math.ceil(.01*len(rows))]
    hist=[]
    for method in ['LM','Powell']:
        rr=[r for r in rows if r['method']==method]; g=[r for r in pp if r['method']==method]
        hist.append(dict(method=method,problems=len(g),records=len(rr),truncated=sum(r['n']<200 for r in g),nfev=q(col(rr,'nfev')),sec=q(col(rr,'sec')),cv_gt1=sum(r['nfev_cv']>1 for r in g),top1_nfev=sum(r['method']==method for r in top),top1_sec=sum(r['method']==method for r in topsec)))
    summary=dict(problems=len(pp),records=len(rows),truncated=sum(r['n']<200 for r in pp),method_summary=hist,
                 schema=dict(schema),nfev=q(col(rows,'nfev')),sec=q(col(rows,'sec')),
                 nfev_hill={str(f):hill(col(rows,'nfev'),f) for f in [.02,.05,.1,.2]},
                 sec_hill={str(f):hill(col(rows,'sec'),f) for f in [.02,.05,.1,.2]},
                 cv_gt1_ids=[r['id'] for r in pp if r['nfev_cv']>1],
                 nfev_gt1000=sum(r['nfev']>1000 for r in rows),gt1000_non_powell=sum(r['nfev']>1000 and r['method']!='Powell' for r in rows),
                 top1_count=len(top),top1_class=dict(Counter(r['cls'] for r in top)),
                 warmup_ratio=q(col(pp,'warmup_ratio')),record_counts=q(col(pp,'n')))
    return data,pp,summary


def main():
    start=time.monotonic(); stamp=datetime.now(timezone.utc).isoformat()
    lock=json.loads((OUT/'registration-lock.json').read_text())
    for name,expected in lock['hashes'].items():
        assert hashlib.sha256((OUT/name).read_bytes()).hexdigest()==expected,name
    sel=json.loads((OUT/'selection.json').read_text())
    savejson('confirmation-start.json',dict(started_at_utc=stamp,code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),registration_hashes_verified=True))
    data0,pp0,s0=loadseed(0); data1,pp1,s1=loadseed(1)
    rrout=[]; classcounts=[]
    for chosen in sel:
        id=chosen['id']; j=data1[id]; rr=j['records']; m=chosen['threshold']; n=col(rr,'nfev'); h=np.array([r['cls']=='hit' for r in rr]); fast=n<=m; slow=~fast
        nF=int(fast.sum()); nS=int(slow.sum()); hF=int(h[fast].sum()); hS=int(h[slow].sum())
        pF=hF/nF if nF else np.nan; pS=hS/nS if nS else np.nan; delta=pS-pF
        valid=nF>=20 and nS>=20
        loF,hiF=wilson(hF,nF); loS,hiS=wilson(hS,nS)
        b=chosen['cutoff']; cbase=cost(rr,None); cb=cost(rr,b); overhead=j['n_vars']+1
        row=dict(**chosen,n1=len(rr),hits1=int(h.sum()),n_fast1=nF,n_slow1=nS,hit_fast1=hF,hit_slow1=hS,p_fast1=pF,p_slow1=pS,delta1=delta,
                 delta_conservative_low=loS-hiF,delta_conservative_high=hiS-loF,valid=valid,
                 replicate=bool(valid and (delta>=.1 if chosen['group']=='L' else delta<=-.1 if chosen['group']=='E' else False)),
                 ratio1=cb/cbase if np.isfinite(cbase) else np.inf,base_cost1=cbase,cutoff_cost1=cb,
                 overhead_ratio1=cost(rr,b,overhead)/cost(rr,None,overhead) if np.isfinite(cost(rr,None,overhead)) else np.inf)
        rrout.append(row)
        for seed,data in [(0,data0),(1,data1)]:
            for side in ['fast','slow']:
                g=[r for r in data[id]['records'] if (r['nfev']<=m)==(side=='fast')]
                counts=Counter(r['cls'] for r in g)
                for cls,count in counts.items(): classcounts.append(dict(id=id,group=chosen['group'],seed=seed,side=side,cls=cls,count=count))
    savecsv('confirmation-per-problem.csv',rrout); savecsv('confirmation-classes.csv',classcounts)
    groups=[]
    for label in ['L','E','M']:
        g=[r for r in rrout if r['group']==label]
        groups.append(dict(group=label,n=len(g),valid=sum(r['valid'] for r in g),replicated=sum(r['replicate'] for r in g),delta0=med(g,'delta0'),delta1=med(g,'delta1'),ratio0=med(g,'ratio0'),ratio1=med(g,'ratio1'),overhead_ratio1=med(g,'overhead_ratio1'),ratio1_le_08=sum(r['ratio1']<=.8 for r in g),ratio1_ge_12=sum(r['ratio1']>=1.2 for r in g)))
    L,E,M=groups
    p1=L['replicated']>=8 and L['delta1']>=.25
    p2=E['replicated']>=62
    p3=E['ratio1']<=.85 and L['ratio1']>=.9
    # The secondary candidates use the same frozen seed-0 definitions.
    profile=table('jssa/results/stage-profile-20261023/per-case.csv')
    local0={r['id']:r for r in pp0}; local1={r['id']:r for r in pp1}
    zeroids={r['id'] for r in pp0 if r['hits']==0}
    highslow={r['case_id'] for r in profile if r['seed']=='0' and local0.get(r['case_id'],{}).get('p',-1)>=.9 and float(r['wall_time_s'])>=30}
    fullrows=[]
    for r in profile:
        id=r['case_id']; r={**r}; r['id']=id
        r['zero_seed0']=id in zeroids; r['highp_slow_seed0']=id in highslow
        r['local_n0']=local0.get(id,{}).get('n'); r['local_p0']=local0.get(id,{}).get('p')
        r['local_n1']=local1.get(id,{}).get('n'); r['local_p1']=local1.get(id,{}).get('p')
        if id in zeroids or id in highslow: fullrows.append(r)
    savecsv('pipeline-fixed-cohorts.csv',fullrows)
    fullsummary=[]
    for seed in [0,1,2]:
        g=[r for r in profile if r['seed']==str(seed)]; w=col(g,'wall_time_s'); zero=[r for r in g if r['case_id'] in zeroids]
        fullsummary.append(dict(seed=seed,runs=len(g),correct=sum(r['correct']=='True' for r in g),wall=q(w),top10_share=np.sort(w)[-math.ceil(.1*len(w)):].sum()/w.sum(),
                                wall_hill={str(f):hill(w,f) for f in [.02,.05,.1,.2]},zero_cohort_correct=sum(r['correct']=='True' for r in zero),zero_cohort_wall=q(col(zero,'wall_time_s')),zero_cohort_under10=sum(float(r['wall_time_s'])<10 for r in zero),zero_cohort_sources=dict(Counter(r['final_answer_source'] for r in zero))))
    zrows=[]
    for id in sorted(zeroids):
        g=[r for r in profile if r['case_id']==id]
        zrows.append(dict(id=id,n0=local0[id]['n'],n1=local1[id]['n'],p0=local0[id]['p'],p1=local1[id]['p'],all_three_correct=all(r['correct']=='True' for r in g),median_wall=med(g,'wall_time_s')))
    savecsv('pipeline-zero-cohort.csv',zrows)
    sizes=[]
    for seed,pp in [(0,pp0),(1,pp1)]:
        for d in sorted(set(r['n_vars'] for r in pp)):
            g=[r for r in pp if r['n_vars']==d]
            sizes.append(dict(seed=seed,n_vars=d,problems=len(g),p=med(g,'p'),median_nfev=med(g,'nfev_median'),scaled_nfev=med(g,'normalized_nfev_median'),local_sec=med(g,'sec_median')))
    savecsv('confirmation-size-strata.csv',sizes)
    summary=dict(started_at_utc=stamp,elapsed_seconds=time.monotonic()-start,groups=groups,P1=p1,P2=p2,P3=p3,
                 seed0=s0,seed1=s1,cv_gt1_overlap=len(set(s0['cv_gt1_ids'])&set(s1['cv_gt1_ids'])),
                 full_solver=fullsummary,full_all=dict(runs=len(profile),correct=sum(r['correct']=='True' for r in profile),wall=q(col(profile,'wall_time_s'))),
                 zero_cohort=dict(n=len(zeroids),n_full200_seed0=sum(r['n0']==200 for r in zrows),n_also_zero_seed1=sum(r['p1']==0 for r in zrows),n_all_three_correct=sum(r['all_three_correct'] for r in zrows),n_zero_both_all_correct=sum(r['p1']==0 and r['all_three_correct'] for r in zrows)),
                 highp_slow_ids=sorted(highslow),all_numeric_cases=len(pp0),selected=len(sel),
                 warnings=['Observed completion effort is not time to first hit.','Threshold and policy selected using seed 0; historical seed 1 is not a new unseen problem set.','Renewal costs resample completed records, omit unrecorded interrupted attempts and do not measure full solver wall time.'])
    savejson('confirmation-summary.json',summary); savejson('input-manifest-confirm.json',inputs)
    for name,expected in lock['hashes'].items(): assert hashlib.sha256((OUT/name).read_bytes()).hexdigest()==expected,name
    print(json.dumps(clean({k:v for k,v in summary.items() if k not in ['seed0','seed1']}),ensure_ascii=False,indent=2))


if __name__=='__main__':
    from pathlib import Path
    main()
