"""Post-hoc diagnostic: ordinary lex elimination, WITHOUT coefficient certificate."""
from pathlib import Path
import os,sys,json,time,resource,subprocess
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE/'vendor'))
import sympy as sp
from certificate import encode,deadline,Limit,isolate,target_bounds
def save(p,obj):
    text=json.dumps(obj,indent=2,default=str)+'\n';assert len(text.encode())<16*1024**2;p.write_text(text)
def worker(cid):
    resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3));resource.setrlimit(resource.RLIMIT_FSIZE,(16*1024**2,16*1024**2))
    out=HERE/'diagnostic'/cid;out.mkdir(parents=True,exist_ok=False)
    r=dict(id=cid,status='running',certificate=False,post_hoc=True);t0=time.perf_counter()
    try:
      with deadline(120):
        dsl=json.loads((HERE/'inputs'/f'{cid}.json').read_text())['dsl'];sy,t,fs,vs,nd=encode(dsl)
        r['encoding_seconds']=time.perf_counter()-t0
        order=[v for v in vs if v!=t]+[t]
        g=sp.groebner(fs,*order,domain=sp.QQ,order='lex',method='buchberger')
        r['groebner_seconds']=time.perf_counter()-t0-r['encoding_seconds']
        r['zero_dimensional']=bool(g.is_zero_dimensional)
        # Cap the saved basis; all calculations have the same process resource limits.
        save(out/'basis.json',dict(variables=list(map(str,order)),basis=list(map(str,g.polys))))
        uni=[p.as_expr() for p in g.polys if p.as_expr()!=0 and p.as_expr().free_symbols<={t}]
        if uni:
            q=min(uni,key=lambda e:sp.degree(e,t));r['E']=str(sp.factor(q));r['target']=str(t)
            r['roots']=[str(v) for v in sp.Poly(q,t).real_roots()]
            r['root_check']=isolate(q,t,target_bounds(dsl));r['status']='unique_value_polynomial' if r['root_check']['unique'] else 'multiple_or_no_allowed_roots'
        else:r['status']='no_univariate'
    except Exception as e:
        r.update(status='timeout' if isinstance(e,Limit) else 'memory_limit' if isinstance(e,MemoryError) else 'error',error=type(e).__name__+': '+str(e)[:200])
    r['seconds']=time.perf_counter()-t0;save(out/'result.json',r)
    print(json.dumps({k:r.get(k) for k in ['id','status','seconds','E']},ensure_ascii=False),flush=True)
def batch():
    from concurrent.futures import ThreadPoolExecutor
    ids=json.loads((HERE/'registration-lock.json').read_text())['ids']
    env=dict(os.environ,PYTHONHASHSEED='0',PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(ROOT/'src'),TMPDIR=str(HERE/'tmp'))
    def run(cid):
        t0=time.perf_counter()
        try:
            p=subprocess.run([sys.executable,'-B',__file__,cid],cwd=ROOT,env=env,capture_output=True,text=True,timeout=130)
            print(p.stdout.strip() or p.stderr[-500:],flush=True)
            proc=dict(returncode=p.returncode,stderr=p.stderr[-2000:],cold_seconds=time.perf_counter()-t0)
        except subprocess.TimeoutExpired:proc=dict(returncode='process_timeout',cold_seconds=time.perf_counter()-t0)
        d=HERE/'diagnostic'/cid;d.mkdir(exist_ok=True,parents=True);save(d/'process.json',proc)
        if not (d/'result.json').exists():save(d/'result.json',dict(id=cid,status='process_error',seconds=proc['cold_seconds']))
    with ThreadPoolExecutor(max_workers=4) as ex:list(ex.map(run,ids))
if __name__=='__main__':
    if len(sys.argv)>1:worker(sys.argv[1])
    else:batch()
