"""Track the FULL rod constraints, with independent fabrication errors.

Unlike rational_linkage.py's analytic root matching, this script follows only
36 constraint equations by Newton continuation. Each three-pin rigid rod has
an independently perturbed intermediate pin ratio, as well as rod length.
This remains an exploratory numerical check, not a proof or physical test.
"""
import json
import time
import numpy as np
import rational_linkage as r


def pack(p):
    return np.array([[p[n].real,p[n].imag] for n in r.VARIABLES]).ravel()


def unpack(x):
    p={n:complex(v) for n,v in zip(r.FIXED,r.POLES)}
    p.update({n:complex(x[2*j],x[2*j+1]) for j,n in enumerate(r.VARIABLES)})
    return p


def solve(x,w,le,re):
    x=x.copy()
    for iteration in range(20):
        f,J=r.rows(unpack(x),w,le,re)
        norm=np.linalg.norm(f)
        if norm<1e-10: return x,iteration,True
        try: step=np.linalg.solve(J,-f)
        except np.linalg.LinAlgError: return x,iteration,False
        factor=1.
        for _ in range(12):
            y=x+factor*step
            fn,_=r.rows(unpack(y),w,le,re)
            if np.linalg.norm(fn)<norm: x=y;break
            factor*=.5
        else: return x,iteration,False
    return x,20,False


def attempt(scale,seed,nsteps=240):
    rng=np.random.default_rng(seed)
    le=rng.uniform(-scale,scale,26)
    re=rng.uniform(-scale,scale,4)
    homes=[]; drift=0.
    for z in r.HOME:
        x0=pack(r.points(z));x,it,ok=solve(x0,r.W0,le,re)
        if not ok: return {"success":False,"reason":"home continuation failed"}
        drift=max(drift,float(np.linalg.norm(x[:2]-x0[:2])));homes.append(x)
    homes=np.array(homes); out={};minsig=1.;maxiters=0
    for name,b,expected in [('A',r.CRIT_W[1],[1,0,2]),('B',r.CRIT_W[0],[0,2,1])]:
        path=r.loop(b,nsteps);xs=homes.copy()
        for k,w in enumerate(path[1:]):
            for j in range(3):
                xs[j],it,ok=solve(xs[j],w,le,re);maxiters=max(maxiters,it)
                if not ok: return {"success":False,"reason":"path correction failed","loop":name,"step":k,"state":j,"home_drift":drift}
                if k%12==0:
                    _,J=r.rows(unpack(xs[j]),w,le,re)
                    minsig=min(minsig,float(np.linalg.svd(J,compute_uv=False)[-1]))
        d=np.linalg.norm(xs[:,None,:]-homes[None,:,:],axis=2)
        perm=np.argmin(d,axis=1).tolist();error=float(np.max(np.min(d,axis=1)))
        out[name]={"permutation":perm,"max_endpoint_error":error}
        if perm!=expected or error>1e-6:
            return {"success":False,"reason":"wrong permutation or endpoint","loop":name,"result":out[name],"home_drift":drift}
    return {"success":True,"loops":out,"min_sampled_sigma":minsig,"max_newton_iterations":maxiters,"home_drift":drift}


def main():
    result={"errors":"Each of 26 rigid link lengths has iid uniform relative error ±scale; four ternary pin ratios have iid uniform absolute error ±scale. Output control loops unchanged.",
            "full_constraint_continuation":True,"runs":[]}
    t=time.monotonic()
    for scale in [0.,1e-5,1e-4,3e-4,1e-3,3e-3,1e-2]:
        for seed in range(4):
            x=attempt(scale,seed)
            result['runs'].append({"scale":scale,"seed":seed,**x})
            print(scale,seed,x['success'],x.get('reason',''),flush=True)
        (r.OUT/'perturbation_result.json').write_text(json.dumps(result,indent=2)+'\n')
    result['elapsed_seconds']=time.monotonic()-t
    (r.OUT/'perturbation_result.json').write_text(json.dumps(result,indent=2)+'\n')
    print('elapsed',result['elapsed_seconds'])


if __name__=='__main__': main()
