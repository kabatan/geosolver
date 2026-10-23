"""Post-validation elementary diagnostics; evaluates starts, no local search."""
from explore import OUT, ROOT, read, starts, write_csv
import csv, json, math, sys, time
import numpy as np
from scipy.spatial.distance import cdist

def main():
    t=time.monotonic()
    sys.path.insert(0,str(ROOT/'jssa/difficulty'))
    from probe_basins import load_case
    from geosolver import GeometryProblem
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    cid='JMO-2024-PRE-03'
    ev=build_ir_evaluator(load_problem_bundle(GeometryProblem.model_validate(load_case(cid)['dsl']).engine_document()))
    d0=read(cid);box=np.array(d0['box']);width=box[:,1]-box[:,0]
    anchors=(np.array([r['x'] for r in d0['records'] if r['cls']=='hit'])-box[:,0])/width
    d=cdist(starts(d0),anchors).min(1);lo,hi=np.quantile(d,[.25,.75]);rows=[]
    for seed in [0,1]:
        raw=read(cid,seed);u=starts(raw);x=box[:,0]+u*width;dist=cdist(u,anchors).min(1)
        y=np.array([r['cls']=='hit' for r in raw['records']]);f=[]
        for z in x:
            try:f.append(bool(ev.evaluate_float_hard_feasibility(list(z),include_margins=False).hard_feasible))
            except Exception:f.append(False)
        f=np.array(f)
        for name,m in [('near',dist<=lo),('far',dist>=hi),('all',np.ones(len(u),bool))]:
            for state in [True,False]:
                mm=m&(f==state);n=int(mm.sum());h=int(y[mm].sum())
                rows.append(dict(id=cid,seed=seed,group=name,feasible=state,n=n,hits=h,p=h/n if n else None))
    write_csv('feasibility-diagnostic.csv',rows)
    c=26/5;s=(9*math.sqrt(5)-1)/4
    roots=[(s-math.sqrt(s*s-4*c))/2,(s+math.sqrt(s*s-4*c))/2]
    values=[]
    for z in [26.,50.,104.,1e3,1e5]:
        ss=z+c/z;q=math.sqrt(ss*ss-20)
        f=ss+9*q-20;fp=(1+9*ss/q)*(1-c/(z*z))
        values.append(dict(t=z,scalar_residual=f,newton_one_step=z-f/fp))
    raw=read('AIME-2025-II-12');rs=raw['records'];far=[r for r in rs if r['start'][0]>=26]
    result=dict(posthoc=True,new_local_searches=0,seconds=time.monotonic()-t,
        scalar_example=dict(c=c,target=s,roots=roots,
          stored_max_root_error=max(min(abs(r['x'][0]-q) for q in roots) for r in rs),
          stored_starts_ge26=len(far),these_to_lower_root=sum(abs(r['x'][0]-roots[0])<1e-5 for r in far),
          newton_limit_at_infinity=2,scalar_function_values=values),feasibility=rows)
    (OUT/'diagnostic.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
