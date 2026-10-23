"""Q21e locked pilot: only this directory is written; never run full solver."""
from __future__ import annotations
import os
for key in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS']:
    os.environ[key] = '1'
os.environ['PYTHONDONTWRITEBYTECODE']='1'
import argparse, csv, hashlib, itertools, json, math, multiprocessing, resource, signal, subprocess, sys, time
from datetime import datetime, timezone
from fractions import Fraction as F
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
ALPHAS=[1,1.25,1.5,1.75,2]
KS=[4,6,8]


def now(): return datetime.now(timezone.utc).isoformat()
def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(path,obj):
    Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def clean(v):
    if isinstance(v,dict): return {k:clean(x) for k,x in v.items()}
    if isinstance(v,(tuple,list)): return [clean(x) for x in v]
    if isinstance(v,np.ndarray): return clean(v.tolist())
    if isinstance(v,(np.integer,)): return int(v)
    if isinstance(v,(np.floating,)): v=float(v)
    if isinstance(v,float) and not math.isfinite(v): return None
    return v

def make_family(k,b,fam):
    rng=np.random.default_rng([210523,k,b])
    occupied={(F(0),F(0)),(F(1),F(0)),(F(0),F(1))}
    planted=[]
    while len(planted)<k:
        p=tuple(F(int(a),32) for a in rng.integers(-24,25,size=2))
        if p not in occupied: occupied.add(p); planted.append(p)
    points={n:([F(0)]*k,F(x),F(y)) for n,x,y in [('A',0,0),('B',1,0),('C',0,1)]}
    constructions=[{'name':n,'expression':f'Point({x}, {y})'} for n,x,y in [('A',0,0),('B',1,0),('C',0,1)]]
    for i in range(k):
        w=[F(int(i==j)) for j in range(k)]
        points[f'P{i}']=(w,F(0),F(0))
        constructions.append({'name':f'P{i}','expression':f'Point(x{i}, y{i})'})
    parents=[]
    if fam=='M':
        rr=np.random.default_rng([210524,k,b])
        for j in range(k):
            eligible=[]
            for a,c in itertools.combinations(points,2):
                wa,xa,ya=points[a]; wc,xc,yc=points[c]
                if not any(wa) and not any(wc): continue
                q=([(u+v)/2 for u,v in zip(wa,wc)],(xa+xc)/2,(ya+yc)/2)
                if any(q==z for z in points.values()): continue
                eligible.append((a,c,q))
            a,c,q=eligible[int(rr.integers(len(eligible)))]
            points[f'Q{j}']=q
            constructions.append({'name':f'Q{j}','expression':f'Midpoint({a}, {c})'})
            parents.append([a,c])
    obs=[]; seen=set()
    for a,c in itertools.combinations(points,2):
        wa,xa,ya=points[a]; wc,xc,yc=points[c]
        w=[u-v for u,v in zip(wa,wc)]; bx=xa-xc; by=ya-yc
        if not any(w): continue
        px=sum(w[i]*planted[i][0] for i in range(k))+bx
        py=sum(w[i]*planted[i][1] for i in range(k))+by
        val=px*px+py*py
        if not val: continue
        key=tuple(w[i]*w[j]*(1 if i==j else 2) for i in range(k) for j in range(i,k))+tuple(2*bx*u for u in w)+tuple(2*by*u for u in w)+(bx*bx+by*by,)
        if key in seen: continue
        seen.add(key)
        obs.append({'a':a,'b':c,'w':[float(x) for x in w],'bx':float(bx),'by':float(by),'value':float(val),'rational':str(val)})
    rr=np.random.default_rng([210525,k,b,int(fam=='M')]); rr.shuffle(obs)
    variables=[n for i in range(k) for n in [f'x{i}',f'y{i}']]
    ans=[float(x) for p in planted for x in p]
    rows=[]
    for alpha in ALPHAS:
        m=math.ceil(2*k*alpha)
        cid=f'{fam}-k{k}-b{b:02d}-a{alpha:g}'
        selected=obs[:m]
        dsl={'id':cid,'variables':variables,'constructions':constructions,
             'conditions':[{'left':f"Distance({o['a']}, {o['b']})**2",'operator':'=','right':o['rational']} for o in selected],
             'target':'Distance(P0, P1)**2'}
        rows.append({'id':cid,'family':fam,'k':k,'d':2*k,'alpha':alpha,'m':m,'base':b,'planted':ans,'midpoint_parents':parents,'observations':selected,'dsl':dsl,'generation_ok':len(selected)==m})
    return rows

def independent(case,x):
    k=case['k']; xx=np.array(x,dtype=float).reshape(k,2)
    obs=case['observations']; w=np.array([o['w'] for o in obs])
    delta=w@xx+np.array([[o['bx'],o['by']] for o in obs])
    res=np.sum(delta*delta,axis=1)-np.array([o['value'] for o in obs])
    jac=np.empty((len(obs),2*k))
    jac[:,0::2]=2*delta[:,0,None]*w
    jac[:,1::2]=2*delta[:,1,None]*w
    return res,jac

def prepare():
    path=HERE/'cases.jsonl'
    cases=[c for k in KS for b in range(10) for fam in ['D','M'] for c in make_family(k,b,fam)]
    for case in cases:
        res,jac=independent(case,case['planted'])
        assert np.max(np.abs(res))<1e-12
        case['planted_singular_values']=np.linalg.svd(jac,compute_uv=False).tolist()
        case['ranks']={str(t):int(np.sum(np.array(case['planted_singular_values'])>case['planted_singular_values'][0]*t)) for t in [1e-6,1e-8,1e-10]}
    payload=''.join(json.dumps(c,ensure_ascii=False,allow_nan=False)+'\n' for c in cases)
    if path.exists(): assert path.read_text()==payload, 'Generated input changed'
    else: path.write_text(payload)
    # No optimization: only parser/evaluator consistency, both families and sizes.
    from geosolver import GeometryProblem
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    checks=[]
    for c in cases:
        if c['base']!=0 or c['alpha']!=2: continue
        bundle=load_problem_bundle(GeometryProblem.model_validate(c['dsl']).engine_document())
        ev=build_ir_evaluator(bundle)
        mp=dict(zip(c['dsl']['variables'],c['planted']))
        at=[mp[n] for n in bundle.var_names]
        rr=ev.evaluate_float_residual(at)
        checks.append({'id':c['id'],'n_vars':len(bundle.var_names),'n_constraints':len(bundle.spec.constraints),'max_res':float(np.max(np.abs(rr.residual_vector))),'guard':bool(ev.evaluate_guard(at)[0]),'hard':bool(ev.evaluate_float_hard_feasibility(at,include_margins=False).hard_feasible)})
        assert checks[-1]['max_res']<1e-10 and checks[-1]['guard'] and checks[-1]['hard']
        assert checks[-1]['n_constraints']==c['m']
    dump(HERE/'preflight.json',{'time':now(),'cases':len(cases),'generation_failed':sum(not c['generation_ok'] for c in cases),'checks':checks,'local_search_calls':0})
    print('Prepared',len(cases),'cases; evaluator checks',len(checks),flush=True)

def init_worker():
    resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
    resource.setrlimit(resource.RLIMIT_FSIZE,(20*1024**2,20*1024**2))
    signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError('input_watchdog')))


def worker(case):
    t0=time.monotonic(); result={'id':case['id'],'family':case['family'],'k':case['k'],'d':case['d'],'m':case['m'],'alpha':case['alpha'],'base':case['base'],'rank':case['ranks']['1e-08'],'records':[]}
    signal.setitimer(signal.ITIMER_REAL,30)
    try:
        from geosolver import GeometryProblem
        from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
        from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
        from geosolver.engine.standard.search import scipy_multistart_backend as smb
        from geosolver.engine.standard.contracts.external_pipeline_config import ExternalPipelineConfig
        if not case['generation_ok']: raise RuntimeError('insufficient_observations')
        bundle=load_problem_bundle(GeometryProblem.model_validate(case['dsl']).engine_document())
        ev=build_ir_evaluator(bundle)
        assert len(bundle.var_names)==case['d'] and len(bundle.spec.constraints)==case['m']
        names=list(bundle.var_names); canonical=case['dsl']['variables']
        result['native_method']='lm'; result['native_max_nfev']=smb._LM_MAX_NFEV
        result['build_sec']=time.monotonic()-t0
        config=ExternalPipelineConfig.production_baseline_tier(seed=0,total_time_budget_sec=180.0).search
        for seed in range(3):
            start0=np.random.default_rng([210526,case['k'],case['base'],seed]).uniform(-1,1,case['d'])
            startmap=dict(zip(canonical,start0)); start=np.array([startmap[n] for n in names])
            rec={'seed':seed,'start':start0.tolist(),'S':0,'R':0,'status':'not_run'}
            telemetry=smb._SearchTelemetry(); ts=time.monotonic()
            try:
                cand=smb._collect_local_start_record(bundle=bundle,evaluator=ev,bounds=[(-1e6,1e6)]*case['d'],config=config,seed=seed,start_index=seed,start=start,deadline_monotonic=ts+5,telemetry=telemetry)
                rec['status']='candidate' if cand is not None else 'none'
                if cand is not None:
                    native=list(cand.x_float); coord=dict(zip(names,native)); x=[coord[n] for n in canonical]
                    rec['x']=x; rec['native_res_norm']=float(cand.residual_norm_float)
                    rr=ev.evaluate_float_residual(native)
                    rrmax=float(np.max(np.abs(rr.residual_vector)))
                    independent_res,_=independent(case,x)
                    rmax=float(np.max(np.abs(independent_res)))
                    hard=bool(ev.evaluate_float_hard_feasibility(native,include_margins=False).hard_feasible)
                    rec.update(max_res=rrmax,independent_max_res=rmax,guard=bool(cand.guard_ok),hard=hard,tags=list(cand.hard_violation_tags))
                    rec['S']=int(np.all(np.isfinite(x)) and rrmax<=1e-8 and rmax<=1e-8 and bool(cand.guard_ok) and hard and 'out_of_bounds' not in cand.hard_violation_tags)
                    rec['planted_error']=float(np.max(np.abs(np.array(x)-case['planted'])))
                    rec['R']=int(rec['S'] and rec['planted_error']<=1e-5)
            except smb._SearchDeadlineExceeded:
                rec['status']='start_timeout'
            except TimeoutError:
                rec['status']='input_timeout'; raise
            except Exception as e:
                rec['status']='error'; rec['error']=f'{type(e).__name__}: {str(e)[:300]}'
            finally:
                rec.update(sec=time.monotonic()-ts,nfev=telemetry.evaluation_count)
                result['records'].append(rec)
    except Exception as e:
        result['error']=f'{type(e).__name__}: {str(e)[:300]}'
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
    for seed in range(len(result['records']),3):
        result['records'].append({'seed':seed,'S':0,'R':0,'status':'not_run_after_error','sec':0,'nfev':0})
    result['wall_sec']=time.monotonic()-t0
    return clean(result)


def run():
    if (HERE/'freeze.json').exists(): raise RuntimeError('Refusing rerun: freeze exists')
    freeze={'time_utc':now(),'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'files':{p.name:digest(p) for p in [HERE/'preregistration.md',HERE/'experiment.py',HERE/'cases.jsonl']},'src_backend_sha256':digest(ROOT/'src/geosolver/engine/standard/search/scipy_multistart_backend.py'),'workers':2,'threads':1}
    dump(HERE/'freeze.json',freeze)
    cases=[json.loads(l) for l in (HERE/'cases.jsonl').read_text().splitlines()]
    np.random.default_rng(210528).shuffle(cases) # avoid density/time-order confounding
    (HERE/'raw').mkdir(exist_ok=True)
    t0=time.monotonic(); done=0
    pool=multiprocessing.get_context('fork').Pool(2,initializer=init_worker)
    it=pool.imap_unordered(worker,cases,chunksize=1)
    try:
        while done<len(cases):
            remaining=2700-(time.monotonic()-t0)
            if remaining<=0: break
            try: out=it.next(timeout=min(30,remaining))
            except multiprocessing.TimeoutError: continue
            dump(HERE/'raw'/f"{out['id']}.json",out)
            done+=1
            if done%20==0:
                print(json.dumps({'done':done,'total':len(cases),'wall_sec':round(time.monotonic()-t0,1)}),flush=True)
        if done==len(cases): pool.close()
        else: pool.terminate()
    finally:
        pool.join()
    dump(HERE/'run-status.json',{'end_utc':now(),'completed':done,'planned':len(cases),'wall_sec':time.monotonic()-t0,'campaign_limit_sec':2700})
    print('Campaign complete',done,flush=True)


def analyze():
    freeze=json.loads((HERE/'freeze.json').read_text())
    assert all(digest(HERE/name)==value for name,value in freeze['files'].items())
    cases=[json.loads(l) for l in (HERE/'cases.jsonl').read_text().splitlines()]
    data=[]; records=[]
    for c in cases:
        path=HERE/'raw'/f"{c['id']}.json"
        if path.exists(): result=json.loads(path.read_text())
        else: result={'id':c['id'],'records':[{'seed':s,'S':0,'R':0,'status':'campaign_timeout','sec':0,'nfev':0} for s in range(3)]}
        row={key:c[key] for key in ['id','family','k','d','m','alpha','base']}
        row.update(rank=c['ranks']['1e-08'],L=int(c['ranks']['1e-08']==c['d']),S=sum(r['S'] for r in result['records'])/3,R=sum(r['R'] for r in result['records'])/3,timeouts=sum('timeout' in r['status'] for r in result['records']),errors=sum(r['status'] in ['error','none','not_run_after_error'] for r in result['records']))
        data.append(row)
        for r in result['records']: records.append({**row,**r})
    def writecsv(name,rows):
        with (HERE/name).open('w') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    writecsv('per-case.csv',data)
    scalar_records=[{k:r.get(k) for k in ['id','family','d','alpha','base','seed','S','R','L','status','sec','nfev','max_res','independent_max_res','planted_error']} for r in records]
    writecsv('per-start.csv',scalar_records)
    rng=np.random.default_rng(210527); table=[]
    for fam in ['D','M']:
        for k in KS:
            for a in ALPHAS:
                z=sorted([r for r in data if r['family']==fam and r['k']==k and r['alpha']==a],key=lambda r:r['base'])
                vals=np.array([r['S'] for r in z]); boot=vals[rng.integers(0,10,size=(2000,10))].mean(axis=1)
                table.append({'family':fam,'k':k,'d':2*k,'m':int(a*2*k),'alpha':a,'n_bases':len(z),'pS':float(vals.mean()),'S_lo':float(np.quantile(boot,.025)),'S_hi':float(np.quantile(boot,.975)),'pR':float(np.mean([r['R'] for r in z])),'L':float(np.mean([r['L'] for r in z])),'timeouts':sum(r['timeouts'] for r in z),'errors':sum(r['errors'] for r in z)})
    writecsv('cell-summary.csv',table)
    predictions={}
    for fam in ['D','M']:
        rows={a:sorted([r for r in data if r['family']==fam and r['k']==8 and r['alpha']==a],key=lambda r:r['base']) for a in ALPHAS}
        delta=np.array([y['S']-x['S'] for x,y in zip(rows[1],rows[2])]); boot=delta[rng.integers(0,10,size=(2000,10))].mean(axis=1)
        cells=sorted([r for r in table if r['family']==fam and r['k']==8],key=lambda r:r['alpha'])
        small=sorted([r for r in table if r['family']==fam and r['k']==4],key=lambda r:r['alpha'])
        band=[c['L']>=.8 and c['pS']<=.6 for c in cells]
        jump=max(np.diff([c['pS'] for c in cells])); smalljump=max(np.diff([c['pS'] for c in small]))
        predictions[fam]={'P1_delta':float(delta.mean()),'P1_ci':[float(np.quantile(boot,.025)),float(np.quantile(boot,.975))],'P1':bool(delta.mean()>=.2 and np.quantile(boot,.025)>0),'P2_band_flags':band,'P2':bool(any(x and y for x,y in zip(band,band[1:])) and cells[-1]['pS']>=.8),'P3_jump_large':float(jump),'P3_jump_small':float(smalljump),'P3':bool(jump>=.3 and jump-smalljump>=.1)}
    summary={'predictions':predictions,'P1_both':all(p['P1'] for p in predictions.values()),'P2_any':any(p['P2'] for p in predictions.values()),'P3_any':any(p['P3'] for p in predictions.values()),'cases':len(data),'starts':len(records),'successes':sum(r['S'] for r in records),'recoveries':sum(r['R'] for r in records),'statuses':{s:sum(r['status']==s for r in records) for s in sorted({r['status'] for r in records})},'src_backend_hash_unchanged':digest(ROOT/'src/geosolver/engine/standard/search/scipy_multistart_backend.py')==freeze['src_backend_sha256'],'frozen_inputs_unchanged':True}
    dump(HERE/'summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','run','analyze']);args=p.parse_args()
    globals()[args.command]()
