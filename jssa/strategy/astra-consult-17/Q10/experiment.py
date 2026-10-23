"""Q10 preregistered same-budget, answer-free A/B comparison."""
from pathlib import Path
import sys,os,json,time,hashlib,resource,math
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'vendor'));sys.path.insert(0,str(HERE))
import certificate
from certificate import Prover,encode,make_certificate,target_bounds,isolate,primitive,deadline,Limit
from verify_certificate import verify
# Reuse L's immutable numerical helpers, not L's data or experimental intervention.
from l_experiment import evaluator,hard,polish,pslq,zero_dim,np,sp,mp,smb,ExternalPipelineConfig,infer_problem_bounds
resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
resource.setrlimit(resource.RLIMIT_FSIZE,(16*1024**2,16*1024**2))

def save(path,obj):
    raw=json.dumps(obj,indent=2,ensure_ascii=False,default=str)+'\n'
    if len(raw.encode())>16*1024**2:raise Limit('16 MiB artifact cap')
    path.write_text(raw)

def direct(fs,vs,t,nd):
    ordered=[v for v in vs if v!=t]+[t]
    pr=Prover(fs,ordered,order='lex')
    polys=[pr.ring.to_sympy(pr.ring._sdm_to_vector(g,1)[0]) for g in pr.gb]
    ts=[g for g in polys if g and g.free_symbols<={t}]
    if not ts:return None,None,zero_dim(pr)
    q=primitive(min(ts,key=lambda g:sp.degree(g,t)),t)
    cofs=pr.coefficients(q)
    assert cofs is not None
    return q,make_certificate(fs,ordered,nd,q,cofs),zero_dim(pr)

def main():
    cid,arm=sys.argv[1:3];assert arm in ['A','B'];seed=10423
    out=HERE/'runs'/f'{cid}__{arm}';out.mkdir(parents=True,exist_ok=False)
    t0=time.perf_counter();raw=(HERE/'inputs'/f'{cid}.json').read_bytes();case=json.loads(raw)
    assert set(case)=={'id','dsl'};dsl=case['dsl']
    res=dict(id=cid,arm=arm,seed=seed,status='running',attempts=[],input_sha256=hashlib.sha256(raw).hexdigest(),
             official_answer_loaded=False,existing_P_loaded=False,budget_seconds=120)
    def finish(status):
        res.update(status=status,seconds=time.perf_counter()-t0);save(out/'result.json',res)
        print(json.dumps({k:res.get(k) for k in ['id','arm','status','seconds','Q','certificate_kind']},ensure_ascii=False),flush=True)
    def certify(q,cert,p=None,name='certificate.json'):
        v0=time.perf_counter();assert verify(cert);save(out/name,cert)
        res['verification_seconds']=res.get('verification_seconds',0)+time.perf_counter()-v0
        r0=time.perf_counter();root=isolate(q,t,target_bounds(dsl),p)
        res['root_seconds']=res.get('root_seconds',0)+time.perf_counter()-r0
        res.update(Q=str(q),root_check=root)
        return root['unique']
    save(out/'result.json',res)
    try:
      with deadline(120-(time.perf_counter()-t0)):
        sy,t,fs,vs,nd=encode(dsl)
        res.update(encoding_seconds=time.perf_counter()-t0,variables=len(vs),equations=len(fs),target_symbol=str(t),
                   nondeg=list(map(str,nd)),nondeg_audit=sy.q10_nondeg_audit,bounds=list(map(str,target_bounds(dsl))))
        save(out/'system.json',dict(variables=list(map(str,vs)),equations=list(map(str,fs)),nondeg=list(map(str,nd)),target=str(t)))
        save(out/'result.json',res)
        if arm=='A':
            a0=time.perf_counter();q,cert,zdim=direct(fs,vs,t,nd)
            res.update(proof_seconds=time.perf_counter()-a0,zero_dimensional=zdim,certificate_kind='E')
            if q is None:finish('no_univariate');return
            unique=certify(q,cert)
            finish('certified' if unique else 'multiple_or_no_allowed_roots');return
        bundle,ev=evaluator(dsl);box=infer_problem_bounds(bundle)
        cfg=ExternalPipelineConfig.production_baseline_tier(seed=seed,total_time_budget_sec=120.0).search
        rng=np.random.default_rng(seed);telemetry=smb._SearchTelemetry()
        res.update(search_box=box,setup_seconds=time.perf_counter()-t0)
        candidates=set();numeric_sec=0.;pr=None
        for k in range(20):
            if numeric_sec>=60:break
            x=np.array([lo+rng.random()*(hi-lo) for lo,hi in box]);rec=dict(start_index=k,start=list(x))
            n0=time.perf_counter();remaining=min(60-numeric_sec,120-(n0-t0))
            try:
                with deadline(remaining):
                    cand=smb._collect_local_start_record(bundle=bundle,evaluator=ev,bounds=box,config=cfg,seed=seed,start_index=k,start=x,
                        deadline_monotonic=time.monotonic()+remaining,telemetry=telemetry)
                    rec['search_seconds']=time.perf_counter()-n0
                    if cand is None:raise ValueError('no candidate')
                    rec.update(x=list(cand.x_float),float_residual=cand.residual_norm_float,guard_ok=cand.guard_ok,hard_feasible=cand.hard_feasible)
                    if not math.isfinite(cand.residual_norm_float) or cand.residual_norm_float>1e-8:raise ValueError('float residual')
                    if not cand.guard_ok or cand.hard_feasible is False:raise ValueError('original feasibility')
                    h0=time.perf_counter();xx,value,info=polish(ev,cand.x_float);rec.update(info,hp_seconds=time.perf_counter()-h0)
                    with mp.workdps(100):
                        rec.update(value=mp.nstr(value,100),hp_coordinates=[mp.nstr(v,100) for v in xx],original_hp_hard=hard(ev,xx,hp=True))
                    if not rec['original_hp_hard']:raise ValueError('original HP feasibility')
                    p0=time.perf_counter();p,degree=pslq(value,t);rec['pslq_seconds']=time.perf_counter()-p0
                    if p is None:raise ValueError('PSLQ failed')
                    rec['P']=str(p)
            except (Exception,smb._SearchDeadlineExceeded) as e:
                rec['candidate_status']=type(e).__name__+': '+str(e)[:180]
                numeric_sec+=time.perf_counter()-n0;res['numeric_seconds']=numeric_sec;res['attempts'].append(rec);save(out/'result.json',res)
                if isinstance(e,(Limit,smb._SearchDeadlineExceeded)):break
                continue
            numeric_sec+=time.perf_counter()-n0;res['numeric_seconds']=numeric_sec
            res['attempts'].append(rec);save(out/'result.json',res)
            if str(p) in candidates:rec['candidate_status']='duplicate_P';continue
            candidates.add(str(p));a0=time.perf_counter()
            if pr is None:pr=Prover(fs,vs,order='grevlex')
            res['zero_dimensional']=zero_dim(pr)
            q=p;cofs=pr.coefficients(q);kind='P'
            rec['P_member']=cofs is not None
            if cofs is None:
                q=primitive(sp.Poly(p*p.subs(t,-t),t).sqf_part().as_expr(),t)
                cofs=pr.coefficients(q);kind='reflection_closure'
                rec['reflection_member']=cofs is not None
            if cofs is None:
                q,cert,zdim=direct(fs,vs,t,nd);kind='E_fallback'
                if q is None:
                    rec['candidate_status']='no_univariate';res['proof_seconds']=time.perf_counter()-a0
                    finish('no_univariate');return
            else:cert=make_certificate(fs,vs,nd,q,cofs)
            res.update(proof_seconds=time.perf_counter()-a0,certificate_kind=kind,P=str(p))
            unique=certify(q,cert,p,name=f'certificate-{k}.json')
            rec.update(candidate_status='certified' if unique else 'multiple_or_no_allowed_roots',Q=str(q),certificate_kind=kind,root_check=res['root_check'])
            finish(rec['candidate_status']);return
        finish('no_numeric_candidate')
    except Exception as e:
        res['error']=type(e).__name__+': '+str(e)[:300]
        finish('timeout' if isinstance(e,Limit) else 'memory_limit' if isinstance(e,MemoryError) else 'error')
if __name__=='__main__':main()
