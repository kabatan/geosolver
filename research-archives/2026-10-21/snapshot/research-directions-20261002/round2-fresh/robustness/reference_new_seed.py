import json,numpy as np
from explore import OUT,ALPHA
from verify import old,run
rng=np.random.default_rng(202610026);d=old();out={'seed':202610026,'design':d.serialize(),'trials':[]}
for level in [.01,.02,.03]:
 for trial in range(12):
  L=d.lengths*(1+rng.uniform(-level,level,26));a=ALPHA*(1+rng.uniform(-level,level,4));out['trials'].append({'level':level,'trial':trial,**run(d,L,a)})
 print(level,sum(t['success'] for t in out['trials'] if t['level']==level),flush=True);(OUT/'reference_new_seed.json').write_text(json.dumps(out,indent=2))
