"""Track every physical coordinate under independent bar/ratio tolerances.
No fabrication claim or interval certificate. Deterministic numerical verification.
"""
import json,time
import numpy as np
from explore import Design,load,OUT,N,IX,ALPHA

def newton(d,X,w,L,alpha,anchors=None,maxsteps=20):
 X=X.copy()
 for it in range(maxsteps):
  r,J=d.rows(X,w,L,alpha,anchors);err=np.max(abs(r))
  if err<1e-11:return X,err,True
  try:dx=np.linalg.solve(J,-r[...,None])[...,0].reshape(X.shape)
  except np.linalg.LinAlgError:return X,err,False
  if np.max(abs(dx))>.5:return X,err,False
  X+=dx
 return X,err,False

def run(d,L,alpha,steps=360,anchors=None):
 home,err,ok=newton(d,d.points(d.homez)[:,:N],d.home,L,alpha,anchors,maxsteps=30)
 if not ok:return {'success':False,'stage':'home','residual':float(err)}
 out=[];minsv=np.inf;maxerr=0.;maxstep=0.;sep=np.inf
 for j,path in enumerate(d.paths):
  X=home.copy()
  for i,w in enumerate(path[1:]):
   nxt,err,ok=newton(d,X,w,L,alpha,anchors)
   if not ok:return {'success':False,'stage':f'loop{j}_{i}','residual':float(err)}
   maxstep=max(maxstep,float(np.max(abs(nxt-X))));X=nxt;maxerr=max(maxerr,float(err))
   pp=X[:,IX['P']];sep=min(sep,min(np.linalg.norm(pp[a]-pp[b]) for a,b in [(0,1),(0,2),(1,2)]))
   if i%12==0:
    _,J=d.rows(X,w,L,alpha,anchors);minsv=min(minsv,float(np.min(np.linalg.svd(J,compute_uv=False)[:,-1])))
  dist=np.linalg.norm(X[:,None]-home[None,:],axis=(2,3));perm=np.argmin(dist,axis=1)
  if np.max(np.min(dist,axis=1))>1e-6:return {'success':False,'stage':f'loop{j}_endpoint','endpoint_error':float(np.max(np.min(dist,axis=1)))}
  out.append(perm.tolist())
 return {'success':out==d.permutations,'permutations':out,'min_singular_sampled':minsv,'max_residual':maxerr,'max_coordinate_step':maxstep,'min_memory_joint_separation':sep}

def old(K=-.6,long=1,arm=2.3958349462896438):
 d=Design([-1,0,1],2.2j,[0,1],[.32,.32]);crit=3**(-.25)*np.exp(1j*(np.pi/4+np.arange(4)*np.pi/2));critw=np.conj((3*crit**2-1)/(crit**3-crit));d.branches=[int(np.argmin(abs(d.critical_w-c))) for c in [critw[1],critw[0]]];d.track(360);d.K=K;d.long=long;d.short=np.sqrt(long**2-K);d.arm=arm;dic=d.serialize();return load(dic,360)

def main():
 candidates=json.loads((OUT/'search.json').read_text());des=load(candidates[0],360);oldes=old()
 designs=[('negative_real',oldes),('negative_triangle',des)]
 rng=np.random.default_rng(202610025);noise={level:[(rng.uniform(-level,level,26),rng.uniform(-level,level,4)) for i in range(12)] for level in [.001,.003,.01,.03]}
 out={'seed':202610025,'levels':list(noise),'designs':{}};start=time.monotonic()
 for name,d in designs:
  base=run(d,d.lengths,ALPHA);res={'design':d.serialize(),'base':base,'trials':[]};out['designs'][name]=res
  print(name,'BASE',base,flush=True)
  for level,randoms in noise.items():
   for trial,(le,ae) in enumerate(randoms):
    ans=run(d,d.lengths*(1+le),ALPHA*(1+ae));res['trials'].append({'level':level,'trial':trial,**ans})
   print(name,'level',level,'pass',sum(x['success'] for x in res['trials'] if x['level']==level),'elapsed',time.monotonic()-start,flush=True)
   (OUT/'comparison.json').write_text(json.dumps(out,indent=2))
if __name__=='__main__':main()
