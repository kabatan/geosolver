"""Frozen archival validation. Never runs a solver or reads sealed data."""
import json
import time
from datetime import datetime, timezone
import hashlib
from collections import Counter
import numpy as np
from explore import ROOT, OUT, table, read_bytes, write_csv, dump, avg, median, fit_predict, manifest


def main():
    t0=time.monotonic()
    # Register hashes before opening any seed-1 file.
    lock={"utc":datetime.now(timezone.utc).isoformat(),"files":{}}
    for name in ['preregistration.md','validate.py','explore.py','census-seed0.csv','curve-fits.json']:
        lock['files'][name]=hashlib.sha256((OUT/name).read_bytes()).hexdigest()
    if (OUT/'registration-lock.json').exists():
        old=json.loads((OUT/'registration-lock.json').read_text())
        assert old['files']==lock['files'], 'Registration changed after freezing'
    else:
        dump('registration-lock.json',lock)
    base=table('jssa/strategy/astra-consult-18/Q27d/census-seed0.csv')
    rows=[]; metadata=[]
    for r0 in base:
        r=dict(r0)
        cid=r['id']
        old=json.loads(read_bytes(f'jssa/difficulty/minima/raw-323/{cid}.json'))
        new=json.loads(read_bytes(f'jssa/difficulty/minima/raw-323-seed1/{cid}.json'))
        assert old['seed']==0 and new['seed']==1
        metadata.append({'id':cid,**{k:old.get(k)==new.get(k) for k in ['n_vars','n_constraints','references','box','init_from','starts_requested']}})
        rec=new.get('records',[])
        assert rec, cid
        n=len(rec);h=sum(s['cls']=='hit' for s in rec)
        r.update(n1=n,h1=h,p1=h/n,p20_1=avg([s['cls']=='hit' for s in rec[:20]]) if n>=20 else None)
        assert abs(r['p1']-new['p_any'])<1e-12
        rows.append(r)
    write_csv('census-both-seeds.csv',rows)
    write_csv('seed-metadata.csv',metadata)
    T=[r for r in rows if 1.75<=r['alpha']<2]
    assert sorted(r['id'] for r in T)==sorted(['HMMT-2007-FEB-GEO-10','HMMT-2009-FEB-GEO-10','HMMT-2012-FEB-GEO-02','HMMT-2017-FEB-GEO-05','HMMT-2024-FEB-GEO-08','JMO-2025-PRE-12'])
    weights={4:4/6,5:1/6,6:1/6}
    L=[r for r in rows if 1.5<=r['alpha']<1.75 and r['d'] in weights]
    U=[r for r in rows if 2<=r['alpha']<2.25 and r['d'] in weights]
    groups={'T':T,'L':L,'U':U}
    for label,rs in groups.items():
        for r in rs: r['validation_group']=label
    write_csv('validation-groups.csv',T+L+U)
    def standardized(rs,k):
        return sum(w*avg([r[k] for r in rs if r['d']==d]) for d,w in weights.items())
    primary={}
    for k in ['p','p1']:
        t=avg([r[k] for r in T]);l=standardized(L,k);u=standardized(U,k)
        primary[k]={'T':t,'L_standardized':l,'U_standardized':u,'L_minus_T':l-t,'U_minus_T':u-t}
    mean1=primary['p1']['T']; small=sum(r['p1']<=.2 for r in T)
    loo=[avg([r['p1'] for r in T if r['id']!=drop['id']]) for drop in T]
    primary.update(P1=mean1<=.12 and small>=5,P1_small_count=small,
                   P2=primary['p1']['L_minus_T']>=.2 and primary['p1']['U_minus_T']>=.2,
                   P3=max(loo)<=.15,leave_one_out_means=loo,
                   counts={k:len(v) for k,v in groups.items()})
    rng=np.random.default_rng(271023)
    def resample(rs,k):
        x=np.array([r[k] for r in rs]);return float(np.mean(x[rng.integers(len(x),size=len(x))]))
    boot=[]
    for _ in range(4000):
        t=resample(T,'p1')
        l=sum(w*resample([r for r in L if r['d']==d],'p1') for d,w in weights.items())
        u=sum(w*resample([r for r in U if r['d']==d],'p1') for d,w in weights.items())
        boot.append([t,l-t,u-t])
    primary['bootstrap95_problem_units']={k:np.quantile(np.array(boot)[:,i],[.025,.975]).tolist()
                 for i,k in enumerate(['T_mean','L_minus_T','U_minus_T'])}
    first20={}
    for g,rs in groups.items():
        rs=[r for r in rs if r['n']>=20 and r['n1']>=20]
        first20[g]={'n_problems':len(rs),'p0':avg([r['p_first20'] for r in rs]),'p1':avg([r['p20_1'] for r in rs])}
    primary['first20_unstandardized']=first20
    dump('validation.json',primary)
    size=[]
    for d in sorted({r['d'] for r in rows}):
        rs=[r for r in rows if r['d']==d]
        size.append({'d':d,'problems':len(rs),'p0':avg([r['p'] for r in rs]),'p1':avg([r['p1'] for r in rs]),
                    'n0':sum(r['n'] for r in rs),'n1':sum(r['n1'] for r in rs),
                    'p1_sd':float(np.std([r['p1'] for r in rs],ddof=1)) if len(rs)>1 else None,
                    'mean_binomial_se1':avg([(r['p1']*(1-r['p1'])/r['n1'])**.5 for r in rs])})
    write_csv('dimension-seed-replay.csv',size)
    d=np.array([r['d'] for r in rows],float);y0=np.array([r['p'] for r in rows]);y1=np.array([r['p1'] for r in rows])
    fits=[]
    for kind in ['constant','exponential','power','logistic','step']:
        pred,pars=fit_predict(kind,d,y0,d)
        fits.append({'kind':kind,'parameters_seed0':pars,'rmse_seed1':float(np.sqrt(np.mean((pred-y1)**2)))})
    dump('curve-seed-replay.json',fits)
    idmap={r['id']:r for r in rows}
    inv=table('jssa/strategy/astra-consult-18/Q27d/dimension-inversions.csv')
    preserved=[]
    for r in inv:
        gap=idmap[r['high_id']]['p1']-idmap[r['low_id']]['p1']
        preserved.append({**r,'gap1':gap,'sign_reproduced':gap>0,'gap_half_reproduced':gap>=.5})
    write_csv('dimension-inversions-replay.csv',preserved)
    zero=[r for r in rows if r['h']==0]
    bothzero=[r for r in zero if r['h1']==0]
    secondary={'local_n1':sum(r['n1'] for r in rows), 'metadata_match':all(all(v for k,v in r.items() if k!='id') for r in metadata),
        'p0_zero':len(zero),'p0_zero_full_all3':sum(r['full_correct']==3 for r in zero),
        'p0_zero_full_any':sum(r['full_correct']>0 for r in zero),'p0_zero_full_runs_correct':sum(r['full_correct'] for r in zero),
        'both_zero':len(bothzero),'both_zero_full_all3':sum(r['full_correct']==3 for r in bothzero),
        'both_zero_total_starts':sum(r['n']+r['n1'] for r in bothzero),
        'inversion_pairs':len(inv),'inversion_sign_replayed':sum(r['sign_reproduced'] for r in preserved),
        'inversion_half_replayed':sum(r['gap_half_reproduced'] for r in preserved),
        'inversion_unique_problems':len({r[k] for r in inv for k in ['low_id','high_id']}),
        'elapsed_s':time.monotonic()-t0}
    write_csv('zero-hit-replay.csv',zero)
    dump('secondary-replay.json',secondary)
    dump('validation-manifest.json',manifest)
    print('PRIMARY',json.dumps(primary))
    print('TROUGH',json.dumps([{k:r[k] for k in ['id','d','m','n','h','p','n1','h1','p1']} for r in T]))
    print('DIMENSIONS',json.dumps(size))
    print('FITS',json.dumps(fits))
    print('SECONDARY',json.dumps(secondary))


if __name__=='__main__': main()
