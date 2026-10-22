import sys, math
sys.path.insert(0,'jssa/difficulty')
import numpy as np
import gn_common as g
from probe_common import smb, build
from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds
from probe_basins import construction_coordinates, answer_float
case, ef, yf = sys.argv[1:4]; K=int(sys.argv[4]); NC=int(sys.argv[5])
e_dsl,e_b,e_ev=build(ef); _,y_b,y_ev=build(yf)
base=list(e_b.var_names); box=np.array(infer_problem_bounds(e_b),dtype=float)
extra=sorted({v[2:] for v in y_b.var_names if v[:2] in ('x_','y_') and v not in base})
hc=construction_coordinates(e_dsl,extra)
rng=np.random.default_rng([0,K]); u0=box[:,0]+rng.random(len(base))*(box[:,1]-box[:,0])
vals=dict(zip(base,u0)); h0={var:answer_float(ev,[vals[n] for n in names]) for var,(names,ev) in hc.items()}
tel=smb._SearchTelemetry()
vf=lambda b,ev: smb._AugmentedResidualVectorFn(bundle=b,evaluator=ev,n_constraints=len(b.spec.constraints),deadline_monotonic=None,telemetry=tel,constraint_scales=None)
def jac(f,x,r):
    J=np.empty((r.size,x.size))
    for j in range(x.size):
        h=g.FD_STEP*max(1,abs(x[j]));xp=x.copy();xp[j]+=h;J[:,j]=(np.asarray(f(xp))-r)/h
    return J
for tag,(b,ev,x) in {'E':(e_b,e_ev,u0.copy()),'Y':(y_b,y_ev,np.array([vals[n] if n in vals else h0[n] for n in y_b.var_names]))}.items():
    f=vf(b,ev); r=np.asarray(f(x)); J=jac(f,x,r); d=np.linalg.lstsq(J,-r,rcond=None)[0]
    print(tag,'rows',r.size,'|r|^2=%.4f'%(r@r))
    for k in [0,3,6,7,9,13,14]:
        a=2.0**-k; rn=np.asarray(f(x+a*d)); m=r+a*J@d
        print(f'  a=1/{2**k:<6d} actual |C|^2={rn[:NC]@rn[:NC]:10.4g} |G|^2={rn[NC:]@rn[NC:]:10.4g}  model |C|^2={m[:NC]@m[:NC]:8.4g} |G|^2={m[NC:]@m[NC:]:8.3g}  ratio actual/pred dec={(r@r-rn@rn)/(r@r-m@m):8.3g}')
