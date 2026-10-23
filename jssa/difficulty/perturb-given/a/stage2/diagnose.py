"""Preregistered diagnostics of saved endpoints; no optimization or refinement."""
from common import *
import argparse
from itertools import combinations
import sqlite3
import time
import numpy as np


def residual(evaluator, x, m):
    try:
        value = evaluator.evaluate_float_residual(x)
        vector = np.asarray(value.residual_vector, dtype=float)
        if vector.shape != (m,) or not np.all(np.isfinite(vector)):
            return None
        return vector
    except Exception:
        return None


def singular_values(matrix, n):
    values = np.linalg.svd(matrix, compute_uv=False)
    return np.concatenate([values, np.zeros(max(0,n-len(values)))])


def jacobian(evaluator, x, bounds, d, m):
    x=np.asarray(x,dtype=float); widths=np.diff(np.asarray(bounds),axis=1).ravel(); n=len(x)
    js=[]
    for h in (1e-6,5e-7):
        columns=[]
        for j in range(n):
            dx=np.zeros(n); dx[j]=h*widths[j]
            plus=residual(evaluator,x+dx,m); minus=residual(evaluator,x-dx,m)
            if plus is None or minus is None:
                return {'valid':False,'reason':'nonfinite central difference','rank':None}
            columns.append((plus-minus)/(2*dx[j]))
        matrix=np.column_stack(columns)
        if not np.all(np.isfinite(matrix)):
            return {'valid':False,'reason':'nonfinite finite-difference matrix','rank':None}
        js.append(matrix)
    try:
        raw=[singular_values(j,n) for j in js]
    except np.linalg.LinAlgError:
        return {'valid':False,'reason':'raw SVD did not converge','rank':None}
    result={'raw_singular_values':raw,'raw_ratio':[float(s[-1]/s[0]) if s[0] else 0.0 for s in raw],
            'steps_z':[1e-6,5e-7],'valid':False,'rank':None}
    if d is None or len(d)!=m:
        return result | {'reason':'row scale unavailable'}
    zs=[j*widths[None,:]/np.asarray(d)[:,None] for j in js]
    if not all(np.all(np.isfinite(j)) for j in zs):
        return result | {'reason':'nonfinite scaled matrix'}
    try:
        scaled=[singular_values(j,n) for j in zs]
    except np.linalg.LinAlgError:
        return result | {'reason':'scaled SVD did not converge'}
    rel=float(np.linalg.norm(zs[0]-zs[1])/max(1e-12,np.linalg.norm(zs[1])))
    small=[float(s[-1]) for s in scaled]
    ratio=max(*small,1e-12)/max(min(small),1e-12)
    rank_threshold=max(1e-12,1e-8*float(scaled[1][0]))
    stable=bool(rel<=.05 and ratio<=2)
    return result | {'scaled_singular_values':scaled,'scaled_ratio':[float(s[-1]/s[0]) if s[0] else 0.0 for s in scaled],
            'relative_frobenius_difference':rel,'sigma_min_step_ratio':ratio,
            'valid':stable,'reason':None if stable else 'step sensitivity exceeds registered tolerance',
            'sigma_min':small[1] if stable else None,
            'rank':int(np.count_nonzero(scaled[1]>rank_threshold)) if stable else None,
            'rank_threshold':rank_threshold,'reported_step_z':5e-7}


def cluster(points, eps):
    groups=[]
    for point in sorted(points,key=lambda p:tuple(p['z'])):
        z=np.asarray(point['z']); n=len(z)
        for group in groups:
            if all(np.linalg.norm(z-np.asarray(other['z']))/math.sqrt(n)<=eps for other in group):
                group.append(point); break
        else: groups.append([point])
    return groups


def diagnose(case_id, seconds):
    verify_source()
    db=sqlite3.connect(f'file:{EXTERNAL}/trials.sqlite?mode=ro',uri=True)
    assert db.execute("SELECT count(*) FROM trials WHERE case_id=? AND status='unstarted'",(case_id,)).fetchone()[0]==0, 'Case not finished'
    allrows=[dict(case_id=case_id,seed=s,k=k,variant=v,status=status,**{'record':json.loads(data)})
             for s,k,v,status,data in db.execute('SELECT seed,k,variant,status,data FROM trials WHERE case_id=? ORDER BY idx',(case_id,))]
    builds={v:json.loads(data) for v,data in db.execute('SELECT variant,data FROM builds WHERE case_id=?',(case_id,))}
    db.close()
    folder=EXTERNAL/'diagnostics'/case_id
    folder.mkdir(parents=True,exist_ok=True)
    stop=time.monotonic()+seconds
    original=builds.get('original',{})
    scale_path=folder/'scale.json'
    if not scale_path.exists():
        if original.get('status')!='built':
            write(scale_path,{'valid':False,'reason':'original build unavailable','d':None})
        else:
            _,ev=assemble(case_id,'original')
            points=starts(case_id,404001,original['original_bounds'])[:,original['positions']]
            m=original['n_eq']; values=[]
            # Store rowwise finite values; an invalid row does not erase other finite rows.
            for x in points:
                try:
                    v=np.asarray(ev.evaluate_float_residual(x).residual_vector,dtype=float)
                    if v.shape!=(m,): v=np.full(m,np.nan)
                except Exception: v=np.full(m,np.nan)
                values.append(v)
            array=np.asarray(values); counts=np.sum(np.isfinite(array),axis=0)
            valid=bool(np.all(counts>=20))
            d=[max(1.,float(np.median(np.abs(array[np.isfinite(array[:,j]),j])))) for j in range(m)] if valid else None
            write(scale_path,{'valid':valid,'d':d,'finite_counts':counts,'start_residuals':array,
                              'reason':None if valid else 'fewer than 20 finite values in at least one row',
                              'source_hash':SOURCE_HASH,'at_utc':utc()})
    d=read(scale_path)['d']
    for variant in VARIANTS:
        destination=folder/(variant+'.json')
        if destination.exists(): continue
        if time.monotonic()>stop-10: break
        meta=builds.get(variant,{})
        if meta.get('status')!='built':
            write(destination,{'variant':variant,'valid':False,'reason':'build unavailable','references':{},'branch':{}})
            continue
        _,ev=assemble(case_id,variant)
        bounds=np.asarray(meta['bounds']); lo=bounds[:,0]; widths=bounds[:,1]-lo
        strict={seed:[row for row in allrows if row['seed']==seed and row['variant']==variant and row['record'].get('hit_strict')] for seed in SEEDS}
        points=[]; references={}
        for seed in SEEDS:
            for row in strict[seed][:20]:
                point={'seed':seed,'k':row['k'],'x':row['record']['endpoint']}
                point['z']=((np.asarray(point['x'])-lo)/widths).tolist()
                points.append(point)
        point_cache=folder/(variant+'-jacobians.json')
        cache=read(point_cache) if point_cache.exists() else {}

        def get_jac(point):
            key=sha(np.asarray(point['x'],dtype='<f8').tobytes())
            if key not in cache:
                if time.monotonic()>stop-5:
                    raise TimeoutError('diagnostic chunk ended; saved endpoints are unchanged')
                cache[key]=clean_json(jacobian(ev,point['x'],meta['bounds'],d,meta['n_eq']))
                write(point_cache,cache)
            return cache[key]

        try:
            for seed in SEEDS:
                if strict[seed]:
                    row=strict[seed][0]
                    ref={'seed':seed,'k':row['k'],'x':row['record']['endpoint']}
                    references[str(seed)]={**ref,'jacobian':get_jac(ref)}
                else: references[str(seed)]={'reason':'no strict hit','jacobian':{'valid':False,'sigma_min':None}}
            branch={}
            for eps in (1e-4,1e-5,1e-3):
                groups=cluster(points,eps)
                reps=[g[0] for g in groups]
                result={'epsilon':eps,'points_per_seed':{str(s):min(20,len(strict[s])) for s in SEEDS},
                        'cluster_count':len(groups),'sizes':[len(g) for g in groups],
                        'representatives':reps,'valid':False,'B':None}
                reasons=[]
                if any(len(strict[s])<20 for s in SEEDS): reasons.append('fewer than 20 strict hits in at least one seed')
                if len(groups)<2: reasons.append('fewer than two observed clusters')
                if not reasons:
                    jacs=[get_jac(p) for p in reps]
                    result['representative_jacobians']=jacs
                    if any(not j['valid'] for j in jacs): reasons.append('unstable or unavailable representative Jacobian')
                    if any(j['rank']!=meta['n_vars'] for j in jacs): reasons.append('rank deficiency / possible continuous family')
                if not reasons:
                    result.update(valid=True,B=min(float(np.linalg.norm(np.asarray(a['z'])-b['z'])/math.sqrt(meta['n_vars'])) for a,b in combinations(reps,2)))
                result['reasons']=reasons
                branch[str(eps)]=result
            write(destination,{'variant':variant,'references':references,'branch':branch,
                               'strict_hit_counts':{str(s):len(strict[s]) for s in SEEDS},
                               'source_hash':SOURCE_HASH,'at_utc':utc()})
        except TimeoutError:
            break
    complete=all((folder/(v+'.json')).exists() for v in VARIANTS)
    print(json.dumps({'case_id':case_id,'diagnostics_complete':complete,'at_utc':utc()}))
    return complete


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('case_id'); parser.add_argument('--seconds',type=float,default=180)
    args=parser.parse_args(); assert 10<=args.seconds<=185
    diagnose(args.case_id,args.seconds)
