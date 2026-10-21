import json,time
import numpy as np
from explore import load,OUT,ALPHA
from verify import run,old
start=time.monotonic();a=json.loads((OUT/'optimized.json').read_text());selected=[]
for geom in ['real','triangle']:
 opts=[x for x in a if x['geometry']==geom]
 for x in opts:
  # Cover top designs with genuinely different dimensions.
  if all(np.linalg.norm(np.log(np.array([abs(x['K']),x['long'],x['arm']])/np.array([abs(y['K']),y['long'],y['arm']])))>.25 for y in selected if y['geometry']==geom):selected.append(x)
  if sum(x['geometry']==geom for x in selected)>=3:break
rng=np.random.default_rng(202610026);noise={level:[(rng.uniform(-level,level,26),rng.uniform(-level,level,4)) for i in range(12)] for level in [.01,.02,.03]};out={'seed':202610026,'results':[]}
for index,x in enumerate(selected):
 d=load(x,360);res={'candidate':index,'design':x,'base':run(d,d.lengths,ALPHA),'trials':[]};out['results'].append(res)
 for level,randoms in noise.items():
  for trial,(le,ae) in enumerate(randoms):
   ans=run(d,d.lengths*(1+le),ALPHA*(1+ae));res['trials'].append({'level':level,'trial':trial,**ans})
  print(index,x['geometry'],'level',level,'pass',sum(t['success'] for t in res['trials'] if t['level']==level),'elapsed',time.monotonic()-start,flush=True)
  (OUT/'refinement_validation.json').write_text(json.dumps(out,indent=2))
