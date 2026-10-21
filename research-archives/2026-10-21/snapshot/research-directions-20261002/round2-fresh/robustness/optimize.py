import json,itertools,time
import numpy as np
from explore import load,OUT
from verify import old
start=time.monotonic();out=[]
for name,d in [('real',old()),('triangle',load(json.loads((OUT/'search.json').read_text())[0],360))]:
 for K,ls,arms in itertools.product(-np.geomspace(.08,3,22),[1.02,1.08,1.15,1.3,1.6,2.0],[1.02,1.08,1.15,1.3,1.6,2.]):
  d.choose(float(K),ls,arms);r=d.evaluate(stride=18);out.append({'geometry':name,**d.serialize(),**r})
 out.sort(key=lambda x:x['sensitivity_per_separation']);(OUT/'optimized.json').write_text(json.dumps(out,indent=2));print(name,len(out),time.monotonic()-start,'best',out[0],flush=True)
