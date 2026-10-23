"""Frozen seed-1 spatial replay; no new local search."""
from explore import OUT, ROOT, read, starts, write_csv
import csv, json, time, hashlib, datetime
import numpy as np
from scipy.spatial.distance import cdist
from collections import Counter

IDS=['AIME-2022-I-11','HMMT-2011-equilateral-hexagon','JMO-2024-PRE-03',
     'HMMT-2023-FEB-GEO-02','aime-2000-2-8','HMMT-2025-FEB-GEO-09','HMMT-2022-FEB-GEO-05']

def wilson(k,n):
    z=1.959963984540054; p=k/n; den=1+z*z/n
    mid=(p+z*z/(2*n))/den
    half=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [float(mid-half),float(mid+half)]

def main():
    t=time.monotonic(); lock=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
      registration_sha256=hashlib.sha256((OUT/'preregistration.md').read_bytes()).hexdigest(),
      code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    # This is written before computing any registered seed-1 contrast.
    (OUT/'validation-lock.json').write_text(json.dumps(lock,indent=2))
    rows=[]
    for cid in IDS:
        d0=read(cid); d1=read(cid,1); assert d0['box']==d1['box']
        box=np.array(d0['box']);width=box[:,1]-box[:,0]
        hits=np.array([r['x'] for r in d0['records'] if r['cls']=='hit'])
        anchors=(hits-box[:,0])/width; u0=starts(d0);u1=starts(d1)
        a0=cdist(u0,anchors).min(1);a1=cdist(u1,anchors).min(1)
        lo,hi=np.quantile(a0,[.25,.75]); row=dict(id=cid,q25=lo,q75=hi)
        for seed,d,a in [(0,d0,a0),(1,d1,a1)]:
            y=np.array([r['cls']=='hit' for r in d['records']]); near=a<=lo;far=a>=hi
            kn=int(y[near].sum());nn=int(near.sum());kf=int(y[far].sum());nf=int(far.sum())
            cn=wilson(kn,nn); cf=wilson(kf,nf)
            row.update({f'seed{seed}_{k}':v for k,v in dict(near_n=nn,near_hits=kn,near_p=kn/nn,
                far_n=nf,far_hits=kf,far_p=kf/nf,delta=kf/nf-kn/nn,
                near_ci_low=cn[0],near_ci_high=cn[1],far_ci_low=cf[0],far_ci_high=cf[1],
                delta_conservative_low=cf[0]-cn[1],delta_conservative_high=cf[1]-cn[0]).items()})
        row['passes_problem']=row['seed1_near_n']>=20 and row['seed1_far_n']>=20 and row['seed1_delta']>=.15
        rows.append(row)
    write_csv('validation.csv',rows)
    med=float(np.median([r['seed1_delta'] for r in rows]));npass=sum(r['passes_problem'] for r in rows)
    result=dict(registered_problems=7,passed_problems=npass,P1=npass>=5,median_delta_seed1=med,P2=med>=.2,
                combined_pass=bool(npass>=5 and med>=.2),seconds=time.monotonic()-t,
                new_local_searches=0,results=rows)
    (OUT/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':
    from pathlib import Path
    main()
