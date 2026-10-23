"""Answer-blind single-start experiments using frozen 60db4b6 components.

This module never reads grading/, cases.jsonl, or historical endpoint coordinates.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import resource
import time
import warnings
from pathlib import Path

import numpy as np
import PyNomad
from scipy.optimize import least_squares
from geosolver import GeometryProblem
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
from geosolver.engine.standard.search.nomad_config import NomadConfig
from geosolver.engine.standard.search.nomad_blackbox_adapter import NomadBlackboxAdapter
from geosolver.engine.standard.search import scipy_multistart_backend as smb

OUT = Path(__file__).resolve().parent
BUDGET = 1200
TIME_CAP = 6.0
ARMS = ['N','L','Nfine','Nlp','Lnp','Nu','Lu','Nrs','Lrs','Ls','Lrestart']
CUTOFFS = (200, 800, 1200)

def clean(obj):
    if isinstance(obj, np.ndarray): return clean(obj.tolist())
    if isinstance(obj, np.generic): return clean(obj.item())
    if isinstance(obj, float) and not math.isfinite(obj): return None
    if isinstance(obj, dict): return {str(k):clean(v) for k,v in obj.items()}
    if isinstance(obj, (list,tuple)): return [clean(x) for x in obj]
    return obj

def dump(path, obj):
    data = json.dumps(clean(obj),ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n'
    assert len(data.encode()) < 5_000_000
    temp = path.with_suffix('.tmp')
    temp.write_text(data)
    temp.replace(path)

class Limit(Exception): pass

class Point:
    def __init__(self,x): self.x=list(x); self.payload=None
    def size(self): return len(self.x)
    def get_coord(self,i): return self.x[i]
    def setBBO(self,b): self.payload=b

class Capture:
    def __init__(self,ev): self.ev=ev; self.res=None; self.hard=None
    def __getattr__(self,n): return getattr(self.ev,n)
    def evaluate_float_residual(self,values):
        self.res=self.ev.evaluate_float_residual(values); return self.res
    def evaluate_float_hard_feasibility(self,*args,**kw):
        self.hard=self.ev.evaluate_float_hard_feasibility(*args,**kw); return self.hard

class Oracle:
    def __init__(self,bundle,ev,bounds,penalty,scales=None):
        self.bundle=bundle; self.ev=Capture(ev); self.bounds=np.asarray(bounds)
        self.penalty=penalty; self.scales=scales
        self.n=0; self.invalid=0; self.infeasible=0; self.outside=0
        self.best=None; self.best_objective=None; self.snapshots={}; self.improvements=[]; self.first_points=[]
        self.deadline=time.monotonic()+TIME_CAP; self.limit=BUDGET
        self.adapter=NomadBlackboxAdapter(ev,NomadConfig(max_bb_eval=BUDGET),0,0,constraint_scales=scales)
        self.telemetry=smb._SearchTelemetry()
        self.dim=max(len(bundle.spec.constraints)+2,len(bundle.var_names))
    def evaluate(self,x):
        if self.n>=self.limit: raise Limit('evaluation_budget')
        if time.monotonic()>=self.deadline: raise Limit('time_cap')
        x=np.asarray(x,dtype=float); self.n+=1
        self.ev.res=None; self.ev.hard=None
        if self.penalty=='N':
            point=Point(x)
            ok=self.adapter(point)
            rec=self.adapter.records.pop()
            raw=rec.residual_norm_float; feasible=bool(rec.guard_ok and rec.hard_feasible)
            valid=ok==1 and math.isfinite(raw)
            # The square of this vector exactly reproduces the NOMAD finite score.
            if valid:
                result=self.ev.res
                vec=np.asarray(result.residual_vector,dtype=float)
                if self.scales is not None: vec=vec/np.asarray(self.scales)
                vec=np.r_[vec,0.0,0.0 if rec.hard_feasible else 1000.0]
                score=float(point.payload)
            else:
                vec=np.full(self.dim,1e10); score=float(np.dot(vec,vec))
        else:
            vec=smb._evaluate_augmented_residual_vector(bundle=self.bundle,evaluator=self.ev,values=x,n_constraints=len(self.bundle.spec.constraints),telemetry=self.telemetry,constraint_scales=self.scales)
            r=self.ev.res; h=self.ev.hard
            raw=float(r.residual_norm_float) if r is not None else math.inf
            valid=r is not None and r.evaluation_status is EvaluationStatus.OK and r.is_finite and math.isfinite(raw)
            feasible=bool(h is not None and h.hard_feasible)
            score=float(np.dot(vec,vec))
        if len(vec)<self.dim: vec=np.pad(vec,(0,self.dim-len(vec)))
        self.last_score=score
        inside=bool(np.all(x>=self.bounds[:,0]) and np.all(x<=self.bounds[:,1]))
        self.invalid+=not valid; self.infeasible+=not feasible; self.outside+=not inside
        point_record={'x':x.tolist(),'res':raw,'score':score,'eval':self.n,'feasible':feasible,'inside':inside,'valid':valid}
        if len(self.first_points)<8: self.first_points.append(point_record)
        if self.best_objective is None or score<self.best_objective['score']:
            self.best_objective=point_record
        if valid and feasible and inside and (self.best is None or raw<self.best['res']):
            self.best=point_record
            if len(self.improvements)<64: self.improvements.append({'eval':self.n,'res':raw})
            else: self.improvements[-1]={'eval':self.n,'res':raw}
        if self.n in CUTOFFS: self.snapshots[str(self.n)]=self.best
        return vec, valid

def make_oracle(bundle,ev,bounds,penalty,scales=None):
    oracle=Oracle(bundle,ev,bounds,penalty,scales)
    # Capture the actual frozen adapter's evaluation; never call F twice per point.
    oracle.adapter.evaluator=oracle.ev
    return oracle

def run_arm(arm,bundle,ev,bounds,x0,seed,scales):
    unit=arm in ['Nu','Lu','Nrs','Lrs','Ls','Lrestart']
    penalty='N' if arm in ['N','Nfine','Lnp','Nu','Nrs'] else 'L'
    scale=scales if arm in ['Nrs','Lrs'] else None
    oracle=make_oracle(bundle,ev,bounds,penalty,scale)
    lo,hi=np.asarray(bounds).T; width=hi-lo
    to_x=lambda y: lo+width*np.asarray(y) if unit else np.asarray(y)
    y0=(np.asarray(x0)-lo)/width if unit else np.asarray(x0)
    started=time.monotonic(); cpu=time.process_time()
    status='complete'; detail=None; stages=[]; final=None
    if arm.startswith('N'):
        params=NomadConfig(max_bb_eval=BUDGET,max_time_sec=TIME_CAP).build_params(dimension=len(x0),seed=seed,search_mode='disco_mads')
        params+= [f'MAX_EVAL {BUDGET}']
        if arm=='Nfine':
            params += [f'INITIAL_FRAME_SIZE {j} {float(w)*.001:.17g}' for j,w in enumerate(width)]
        lower=np.zeros(len(lo)) if unit else lo
        upper=np.ones(len(lo)) if unit else hi
        def callback(point):
            nonlocal status
            y=np.array([point.get_coord(i) for i in range(point.size())])
            try: v,valid=oracle.evaluate(to_x(y))
            except Limit as e: status=str(e); return 0
            except Exception as e: status='evaluation_error'; return 0
            if not valid and penalty=='N': return 0
            point.setBBO(str(oracle.last_score).encode())
            return 1
        try:
            PyNomad.setSeed(seed)
            result=PyNomad.optimize(callback,y0.tolist(),lower.tolist(),upper.tolist(),params)
            detail={k:clean(v) for k,v in result.items() if k not in ('x_best',)}
            if result.get('x_best') is not None: final=to_x(result['x_best']).tolist()
        except Exception as e:
            status='optimizer_error'; detail=repr(e)
    else:
        schedule=[(.1,.2),(.03,.4),(.01,.6),(0.,1.)] if arm=='Ls' else [(0.,.2),(0.,.4),(0.,.6),(0.,1.)] if arm=='Lrestart' else [(0.,1.)]
        y=y0.copy()
        rng=np.random.default_rng(np.random.SeedSequence([seed,932]))
        z=rng.standard_normal((8,len(y))); z=np.r_[z,-z]
        for sigma,fraction in schedule:
            oracle.limit=int(BUDGET*fraction)
            stage_best=[math.inf,y.copy()]
            cached=[None,None,None]
            def both(yy):
                yy=np.asarray(yy)
                if cached[0] is not None and np.array_equal(yy,cached[0]): return cached[1],cached[2]
                if sigma:
                    if oracle.n+len(z)>oracle.limit: raise Limit('evaluation_budget')
                    vectors=np.array([oracle.evaluate(to_x(yy+sigma*zz))[0] for zz in z])
                    v=np.mean(vectors,axis=0)
                    jac=vectors.T@z/(len(z)*sigma)
                else:
                    v=oracle.evaluate(to_x(yy))[0]; jac=None
                cost=float(np.dot(v,v))
                if cost<stage_best[0]: stage_best[:]=[cost,yy.copy()]
                # Cache only the paired residual/Jacobian smoothing calculation;
                # plain finite differences are charged on every call.
                if sigma: cached[:]=[yy.copy(),v,jac]
                return v,jac
            try:
                res=least_squares(lambda yy:both(yy)[0],y,method='lm',jac=(lambda yy:both(yy)[1]) if sigma else '2-point',max_nfev=BUDGET,ftol=1e-14,xtol=1e-14,gtol=1e-14)
                y=res.x; stage_status=str(res.status)
            except Limit as e:
                y=stage_best[1]; stage_status=str(e)
                if str(e)=='time_cap': status='time_cap'
            except Exception as e:
                y=stage_best[1]; stage_status='optimizer_error:'+repr(e); status='optimizer_error'
            stages.append({'sigma':sigma,'evals_total':oracle.n,'status':stage_status,'x':to_x(y).tolist()})
            if time.monotonic()>=oracle.deadline: status='time_cap'; break
        final=to_x(y).tolist()
    if oracle.n>=BUDGET and status=='complete': status='evaluation_budget'
    if time.monotonic()>=oracle.deadline and status=='complete': status='time_cap'
    # Early convergence does not trigger a new random restart or extra budget.
    for cutoff in CUTOFFS:
        oracle.snapshots.setdefault(str(cutoff),oracle.best)
    return clean({'arm':arm,'status':status,'evals':oracle.n,'invalid':oracle.invalid,'infeasible':oracle.infeasible,'outside':oracle.outside,'seconds':time.monotonic()-started,'cpu_seconds':time.process_time()-cpu,'best':oracle.best,'best_objective':oracle.best_objective,'snapshots':oracle.snapshots,'improvements':oracle.improvements,'first_points':oracle.first_points,'final_x':final,'stages':stages,'native_result':detail})

def run_task(case_id,seed,k):
    resource.setrlimit(resource.RLIMIT_FSIZE,(4_900_000,4_900_000))
    data=json.loads((OUT/'inputs'/f'{case_id}.json').read_text())
    start=next(r for r in data['starts'] if r['seed']==seed and r['k']==k)
    bundle=load_problem_bundle(GeometryProblem.model_validate(data['dsl']).engine_document())
    ev=build_ir_evaluator(bundle)
    # Residual scales depend only on equation residuals at 32 fixed uniform probes.
    lo,hi=np.asarray(data['bounds']).T
    identity=int.from_bytes(hashlib.sha256(case_id.encode()).digest()[:4],'little')
    rng=np.random.default_rng(np.random.SeedSequence([32999,identity]))
    values=[]
    for u in rng.random((32,len(lo))):
        r=ev.evaluate_float_residual((lo+(hi-lo)*u).tolist())
        if r.is_finite and len(r.residual_vector)==len(bundle.spec.constraints): values.append(np.abs(r.residual_vector))
    scales=np.maximum(1.,np.median(values,axis=0)).tolist() if values else np.ones(len(bundle.spec.constraints)).tolist()
    # Rotation avoids always executing the same arm first under shared load.
    rotation=(k+(seed-32001)*3)%len(ARMS)
    order=ARMS[rotation:]+ARMS[:rotation]
    result={'id':case_id,'seed':seed,'k':k,'x0':start['x'],'input_sha256':hashlib.sha256((OUT/'inputs'/f'{case_id}.json').read_bytes()).hexdigest(),'budget':BUDGET,'time_cap':TIME_CAP,'scale_probes':32,'scales':scales,'order':order,'arms':[], 'pid':os.getpid(),'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'loadavg':os.getloadavg()}
    path=OUT/'runs'/case_id/f'{seed}-{k}.json'
    path.parent.mkdir(exist_ok=True,parents=True)
    for arm in order:
        result['arms'].append(run_arm(arm,bundle,ev,data['bounds'],start['x'],seed*100+k,scales))
        dump(path,result)
    result['complete']=True
    result['finished_utc']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
    dump(path,result)

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('case_id'); ap.add_argument('seed',type=int); ap.add_argument('k',type=int)
    a=ap.parse_args()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',RuntimeWarning)
        run_task(a.case_id,a.seed,a.k)
