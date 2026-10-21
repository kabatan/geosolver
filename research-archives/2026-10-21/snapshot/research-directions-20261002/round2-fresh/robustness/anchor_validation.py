"""Perturb bar lengths, ternary-hole ratios AND all fixed joint coordinates."""
import json,time
import numpy as np
from explore import load,OUT,ALPHA
from verify import run,old
rows=json.loads((OUT/'refinement_validation.json').read_text())['results'];triangle=load(rows[5]['design'],360)
candidates=[('real_negative',old()),('triangle_refined',triangle)]
rng=np.random.default_rng(202610027);noise={level:[(rng.uniform(-level,level,26),rng.uniform(-level,level,4),rng.uniform(-level,level,(3,2))) for i in range(12)] for level in [.001,.003,.01,.03]}
out={'seed':202610027,'error_model':'All 26 lengths and 4 ratios independently multiplied by 1+Uniform(-epsilon,epsilon); 6 anchor coordinates independently translated by Uniform(-epsilon,epsilon) * min nominal anchor separation. Nominal uncalibrated control path unchanged.','candidates':[]};start=time.monotonic()
for name,d in candidates:
 res={'name':name,'design':d.serialize(),'trials':[]};out['candidates'].append(res);anchor=np.stack([d.poles.real,d.poles.imag],axis=-1);unit=min(abs(d.poles[i]-d.poles[j]) for i,j in [(0,1),(0,2),(1,2)])
 for level,randoms in noise.items():
  for trial,(le,ae,fe) in enumerate(randoms):
   ans=run(d,d.lengths*(1+le),ALPHA*(1+ae),anchors=anchor+fe*unit);res['trials'].append({'level':level,'trial':trial,**ans})
  print(name,level,sum(t['success'] for t in res['trials'] if t['level']==level),'elapsed',time.monotonic()-start,flush=True);(OUT/'anchor_validation.json').write_text(json.dumps(out,indent=2))
if False:pass
