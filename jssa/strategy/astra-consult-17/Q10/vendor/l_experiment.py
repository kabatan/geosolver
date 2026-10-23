"""Input-only pilot: C1 admissible search, C2 explicit-guard relaxation, C3 elimination.

No official answers or prior polynomials are loaded. Seeds and caps are preregistered.
"""
from pathlib import Path
import sys,os,json,time,math,ast,hashlib,resource
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'vendor'));sys.path.insert(0,str(HERE))
import numpy as np
from scipy.linalg import qr
import sympy as sp
from mpmath import mp
from certificate import Prover,encode,make_certificate,target_bounds,isolate,primitive,deadline,Limit
from verify_certificate import verify
from geosolver import GeometryProblem
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds
from geosolver.engine.standard.contracts.external_pipeline_config import ExternalPipelineConfig
from geosolver.engine.standard.search import scipy_multistart_backend as smb
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode

# The worker cannot load benchmark answers, prior identities, or another trial's results.
def blind_hook(event,args):
 if event=='open' and isinstance(args[0],(str,bytes)):
  path=os.fsdecode(args[0])
  if any(s in path for s in ['cases.jsonl','audit_source','audit-24','basins-323','/H/','stage-profile','source.git']):
   raise PermissionError('answer/source-blind worker blocked '+path)
sys.addaudithook(blind_hook)
resource.setrlimit(resource.RLIMIT_FSIZE,(16*1024*1024,16*1024*1024))
# All Python writes are restricted by the program to the trial directory.
def save(p,obj):
 raw=json.dumps(obj,indent=2,ensure_ascii=False,default=str)+'\n'
 if len(raw)>16*1024*1024:raise Limit('artifact size cap')
 p.write_text(raw)

def relaxation(dsl):
 d=json.loads(json.dumps(dsl)); kept=[]; removed=[]
 for c in d['conditions']:
  drop=c.get('operator') in ['<','>','<=','>=','!=']
  if 'predicate' in c:
   a=ast.parse(c['predicate'],mode='eval').body
   drop=isinstance(a,ast.Call) and isinstance(a.func,ast.Name) and a.func.id in ['ConvexPolygon','SimplePolygon','AcuteTriangle','ObtuseTriangle','Bound']
  (removed if drop else kept).append(c)
 d['conditions']=kept
 return d,removed

def evaluator(dsl):
 b=load_problem_bundle(GeometryProblem.model_validate(dsl).engine_document());return b,build_ir_evaluator(b)

def hard(ev,x,hp=False):
 try:
  if hp:
   with high_precision_mode():return bool(ev.evaluate_hp_hard_feasibility(x,precision=100,include_margins=False).hard_feasible)
  return bool(ev.evaluate_float_hard_feasibility(list(x),include_margins=False).hard_feasible)
 except Exception:return False

def polish(ev,x):
 """Independent-row/column Newton; fixed unused coordinates are numerical only."""
 with mp.workdps(100):
  xx=[mp.mpf(repr(float(v))) for v in x]
  def f(v):
   with high_precision_mode():return list(ev.evaluate_hp_residual(v,precision=100).residual_vector)
  base=f(xx)
  if not all(mp.isfinite(v) for v in base):raise ValueError('nonfinite HP residual')
  cols=[]
  for j in range(len(xx)):
   xp=list(xx);xm=list(xx);step=mp.mpf('1e-6')*max(1,abs(xx[j]));xp[j]+=step;xm[j]-=step
   cols.append([float((a-b)/(2*step)) for a,b in zip(f(xp),f(xm))])
  J=np.array(cols).T if cols else np.zeros((len(base),0))
  if J.size:
   sv=np.linalg.svd(J,compute_uv=False);rk=int(sum(sv>max(1,float(sv[0]))*1e-7))
  else:rk=0
  if rk:
   _,_,cidx=qr(J,pivoting=True,mode='economic');cidx=list(map(int,cidx[:rk]))
   _,_,ridx=qr(J[:,cidx].T,pivoting=True,mode='economic');ridx=list(map(int,ridx[:rk]))
   for it in range(30):
    vals=f(xx)
    if max([abs(v) for v in vals]+[mp.mpf(0)])<mp.mpf('1e-65'):break
    JJ=mp.matrix(rk,rk)
    for k,j in enumerate(cidx):
     step=mp.mpf('1e-45')*max(1,abs(xx[j]));xp=list(xx);xm=list(xx);xp[j]+=step;xm[j]-=step
     fp=f(xp);fm=f(xm)
     for i,r in enumerate(ridx):JJ[i,k]=(fp[r]-fm[r])/(2*step)
    delta=mp.lu_solve(JJ,mp.matrix([-vals[r] for r in ridx]))
    for k,j in enumerate(cidx):xx[j]+=delta[k]
   else:it=30
  else:cidx=[];ridx=[];it=0
  res=max([abs(v) for v in f(xx)]+[mp.mpf(0)])
  if not mp.isfinite(res) or res>=mp.mpf('1e-65'):raise ValueError('HP residual '+mp.nstr(res,8))
  with high_precision_mode():val=ev.evaluate_answer_hp(xx,precision=100).answer_hp
  if val is None or not mp.isfinite(val) or mp.im(val)!=0:raise ValueError('invalid target')
  return list(xx),mp.mpf(val),{'hp_residual':mp.nstr(res,12),'rank':rk,'numeric_fixed_columns':[j for j in range(len(xx)) if j not in cidx],'iterations':it}

def pslq(value,t):
 with mp.workdps(100):
  if value==0:return t,1
  for deg in range(1,7):
   rel=mp.pslq(mp.matrix([value**j for j in range(deg+1)]),tol=mp.mpf('1e-60'),maxcoeff=10**6,maxsteps=1000)
   if rel and rel[-1]:return primitive(sum(int(c)*t**j for j,c in enumerate(rel)),t),deg
 return None,None

def zero_dim(prover):
 lms=[g[0][0][1:] for g in prover.gb if g]
 if any(not any(m) for m in lms):return 'empty'
 return all(any(m[j]>0 and sum(v!=0 for v in m)==1 for m in lms) for j in range(len(prover.vs)))

def main():
 cid,arm,seed_s=sys.argv[1:4];seed=int(seed_s)
 out=HERE/'runs'/f'{cid}__{arm}__{seed}';out.mkdir(parents=True,exist_ok=False)
 case=json.loads((HERE/'inputs'/(cid+'.json')).read_text());assert set(case)=={'id','dsl'}
 dsl=case['dsl'];t0=time.perf_counter();res={'id':cid,'arm':arm,'seed':seed,'status':'running','attempts':[],
  'input_sha256':hashlib.sha256((HERE/'inputs'/(cid+'.json')).read_bytes()).hexdigest(),
  'official_answer_loaded':False,'existing_P_loaded':False,'msolve_available':False}
 def finish(status):
  res['status']=status;res['seconds']=time.perf_counter()-t0;save(out/'result.json',res)
  print(json.dumps({k:res.get(k) for k in ['id','arm','seed','status','seconds','certified_P','zero_dimensional','original_feasible_at_candidate']},ensure_ascii=False),flush=True)
 try:
  with deadline(45):
   sy,t,fs,vs,nd=encode(dsl)
  res['encoding_seconds']=time.perf_counter()-t0
  res.update(variables=len(vs),equations=len(fs),nondeg=list(map(str,nd)),target_symbol=str(t),bounds=list(map(str,target_bounds(dsl))))
  save(out/'system.json',{'variables':list(map(str,vs)),'equations':list(map(str,fs)),'nondeg':list(map(str,nd)),'target':str(t)})
  if arm=='C3':
   t1=time.perf_counter()
   with deadline(min(45,180-(t1-t0))):
    ordered=[v for v in vs if v!=t]+[t]
    # Extended lex basis is both the elimination and identity generator; no second GB.
    pr=Prover(fs,ordered,order='lex')
    res['zero_dimensional']=zero_dim(pr)
    polys=[pr.ring.to_sympy(pr.ring._sdm_to_vector(g,1)[0]) for g in pr.gb]
    ts=[g for g in polys if g.free_symbols<={t} and g!=0]
    if not ts:res['elimination_seconds']=time.perf_counter()-t1;finish('no_univariate');return
    q=primitive(min(ts,key=lambda g:sp.degree(g,t)),t)
    cofs=pr.coefficients(q)
    if cofs is None:raise AssertionError('eliminant not in original ideal')
    cert=make_certificate(fs,ordered,nd,q,cofs)
   res['elimination_and_certificate_seconds']=time.perf_counter()-t1
   t1=time.perf_counter();assert verify(cert);save(out/'certificate.json',cert)
   res['independent_verification_seconds']=time.perf_counter()-t1
   t1=time.perf_counter();res['root_check']=isolate(q,t,target_bounds(dsl));res['root_seconds']=time.perf_counter()-t1
   res['eliminant']=str(q)
   finish('certified' if res['root_check']['unique'] else 'multiple_or_no_allowed_roots');return
  original_bundle,original=evaluator(dsl)
  rb,removed=relaxation(dsl);res['removed_conditions']=removed if arm=='C2' else []
  bundle,ev=evaluator(rb) if arm=='C2' else (original_bundle,original)
  box=infer_problem_bounds(original_bundle);res['search_box']=box
  assert tuple(bundle.var_names)==tuple(original_bundle.var_names)
  cfg=ExternalPipelineConfig.production_baseline_tier(seed=seed,total_time_budget_sec=180.0).search
  rng=np.random.default_rng(seed);telemetry=smb._SearchTelemetry()
  res['setup_seconds']=time.perf_counter()-t0
  candidates=set();numeric_sec=0;pr=None
  for k in range(20):
   if numeric_sec>=60 or time.perf_counter()-t0>=180:break
   x=np.array([lo+rng.random()*(hi-lo) for lo,hi in box]);rec={'start_index':k,'start':list(x)}
   q0=time.perf_counter();remaining=min(60-numeric_sec,180-(q0-t0))
   try:
    with deadline(remaining):
     cand=smb._collect_local_start_record(bundle=bundle,evaluator=ev,bounds=box,config=cfg,seed=seed,start_index=k,start=x,
       deadline_monotonic=time.monotonic()+remaining,telemetry=telemetry)
     rec['search_seconds']=time.perf_counter()-q0
     if cand is None:raise ValueError('no candidate')
     rec.update(x=list(cand.x_float),float_residual=cand.residual_norm_float,guard_ok=cand.guard_ok,hard_feasible=cand.hard_feasible,
                original_hard=hard(original,cand.x_float),hard_tags=list(cand.hard_violation_tags))
     if cand.residual_norm_float>1e-8 or not math.isfinite(cand.residual_norm_float):raise ValueError('float residual')
     if not cand.guard_ok or cand.hard_feasible is False:raise ValueError('candidate violates retained conditions')
     hp0=time.perf_counter();xx,value,info=polish(ev,cand.x_float);rec.update(info)
     rec['hp_seconds']=time.perf_counter()-hp0
     with mp.workdps(100):
      rec['value']=mp.nstr(value,100);rec['hp_coordinates']=[mp.nstr(v,100) for v in xx]
      rec['original_hp_hard']=hard(original,xx,hp=True)
      rec['retained_hp_hard']=hard(ev,xx,hp=True)
     if not rec['retained_hp_hard']:raise ValueError('HP retained domain')
     if arm=='C1' and not rec['original_hp_hard']:raise ValueError('HP original feasibility')
     p0=time.perf_counter();p,degree=pslq(value,t);rec['pslq_seconds']=time.perf_counter()-p0
     if p is None:raise ValueError('PSLQ failed')
     rec['P']=str(p)
   except (Exception,smb._SearchDeadlineExceeded) as e:
    rec['candidate_status']=type(e).__name__+': '+str(e)[:180]
    numeric_sec+=time.perf_counter()-q0;res['numeric_seconds']=numeric_sec;res['attempts'].append(rec);save(out/'result.json',res)
    if isinstance(e,Limit) or isinstance(e,smb._SearchDeadlineExceeded):break
    continue
   numeric_sec+=time.perf_counter()-q0;res['numeric_seconds']=numeric_sec
   if str(p) in candidates:
    rec['candidate_status']='duplicate_P';res['attempts'].append(rec);continue
   candidates.add(str(p));ct0=time.perf_counter()
   try:
    with deadline(min(45,180-(ct0-t0))):
     if pr is None:pr=Prover(fs,vs)
     res['zero_dimensional']=zero_dim(pr)
     q=p;cofs=pr.coefficients(q);kind='P'
     if cofs is None:
      q=sp.Poly(p*p.subs(t,-t),t).sqf_part().monic().as_expr();cofs=pr.coefficients(q);kind='reflection_closure'
     if cofs is None:
      rec['candidate_status']='not_ideal_member';rec['certificate_seconds']=time.perf_counter()-ct0
      res['attempts'].append(rec);save(out/'result.json',res)
      if len(candidates)>=3:break
      continue
     cert=make_certificate(fs,vs,nd,q,cofs)
    rec['certificate_seconds']=time.perf_counter()-ct0
    v0=time.perf_counter();verified=verify(cert);rec['independent_verification_seconds']=time.perf_counter()-v0
    if not verified:raise AssertionError('exact identity check failed')
    save(out/f'certificate-{k}.json',cert)
    r0=time.perf_counter();root=isolate(q,t,target_bounds(dsl),p);rec['root_seconds']=time.perf_counter()-r0
    rec.update(certificate_kind=kind,Q=str(q),root_check=root,candidate_status='certified' if root['unique'] else 'multiple_or_no_allowed_roots')
    res['attempts'].append(rec);save(out/'result.json',res)
    if root['unique']:
     res.update(certified_P=str(p),Q=str(q),certificate_kind=kind,original_feasible_at_candidate=rec['original_hp_hard'],
                original_valid_figure_seen=any(r.get('original_hp_hard',False) and 'P' in r for r in res['attempts']))
     finish('certified');return
   except Exception as e:
    rec['candidate_status']=type(e).__name__+': '+str(e)[:200];rec['certificate_seconds']=time.perf_counter()-ct0
    res['attempts'].append(rec);save(out/'result.json',res)
    if isinstance(e,Limit):finish('proof_timeout');return
   if len(candidates)>=3:break
  finish('not_certified')
 except Exception as e:
  res['error']=type(e).__name__+': '+str(e)[:300]
  finish('timeout' if isinstance(e,Limit) else 'error')
if __name__=='__main__':main()
