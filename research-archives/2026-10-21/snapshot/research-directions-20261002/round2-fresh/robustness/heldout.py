import json,time
import numpy as np
from explore import load,OUT,ALPHA
from verify import run,old
rows=json.loads((OUT/'refinement_validation.json').read_text())['results'];triangle=load(rows[5]['design'],360)
rng=np.random.default_rng(202610028);noise={level:[(rng.uniform(-level,level,26),rng.uniform(-level,level,4),rng.uniform(-level,level,(3,2))) for i in range(50)] for level in [.01,.02]}
out={'seed':202610028,'trials_per_level':50,'selection':'real candidate fixed before this subtask; triangle candidate selected on sensitivity and seed202610026 prior to this seed','error_model':'26 relative length errors, 4 relative ratio errors, 6 absolute anchor errors in units of minimum nominal anchor spacing; nominal control unchanged','candidates':[]};start=time.monotonic()
for name,d in [('real_negative',old()),('triangle_refined',triangle)]:
 res={'name':name,'design':d.serialize(),'trials':[]};out['candidates'].append(res);anchor=np.stack([d.poles.real,d.poles.imag],axis=-1);unit=min(abs(d.poles[i]-d.poles[j]) for i,j in [(0,1),(0,2),(1,2)])
 for level,randoms in noise.items():
  for trial,(le,ae,fe) in enumerate(randoms):
   ans=run(d,d.lengths*(1+le),ALPHA*(1+ae),anchors=anchor+fe*unit);res['trials'].append({'level':level,'trial':trial,**ans})
   if trial%10==9:print(name,level,trial+1,'pass',sum(t['success'] for t in res['trials'] if t['level']==level),'elapsed',time.monotonic()-start,flush=True)
   (OUT/'heldout.json').write_text(json.dumps(out,indent=2))
