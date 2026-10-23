"""Six fixed cases, 60 saved starts each; frozen local search, 2s/start."""
import hashlib
import json
import time
from collections import Counter

import numpy as np
from measurement import OUT, ROOT, IDS, context, classify, finite_json, smb

SEED=211025
contexts={cid:context(cid,SEED) for cid in IDS}
starts={}
for cid,ctx in contexts.items():
    b=np.array(ctx['bounds'],dtype=float)
    rng=np.random.default_rng(SEED)
    starts[cid]=(b[:,0]+rng.random((60,len(b)))*(b[:,1]-b[:,0])).tolist()
files=[OUT/'run_local.py',OUT/'measurement.py',OUT/'protocol.md',
       ROOT/'jssa/difficulty/probe_basins.py',
       ROOT/'src/geosolver/engine/standard/search/scipy_multistart_backend.py']
lock={'created_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
      'seed':SEED,'starts':starts,'hashes':{
          str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
# Save every start before the first call to the local solver.
(OUT/'local-starts-lock.json').write_text(json.dumps(lock,indent=2)+'\n')
(OUT/'local-runs').mkdir(exist_ok=True)
for cid,ctx in contexts.items():
    t_start=time.monotonic()
    case_deadline=t_start+180
    records=[]
    for k,start in enumerate(starts[cid]):
        t0=time.monotonic()
        rec={'k':k,'start':start}
        n0=ctx['telemetry'].evaluation_count
        if t0>=case_deadline:
            rec.update(cls='case_budget_timeout')
        else:
            try:
                cand=smb._collect_local_start_record(
                    bundle=ctx['bundle'],evaluator=ctx['evaluator'],bounds=ctx['bounds'],
                    config=ctx['config'],seed=SEED,start_index=k,start=np.array(start),
                    deadline_monotonic=min(case_deadline,t0+2.0),telemetry=ctx['telemetry'])
                rec.update(classify(ctx,cand))
            except (smb._SearchDeadlineExceeded,TimeoutError):
                rec.update(cls='start_timeout')
            except Exception as e:
                rec.update(cls='error',error=f'{type(e).__name__}: {e}')
        rec.update(sec=time.monotonic()-t0,nfev=ctx['telemetry'].evaluation_count-n0)
        records.append(finite_json(rec))
    counts=dict(Counter(r['cls'] for r in records))
    data={'id':cid,'seed':SEED,'n':60,'n_hit':counts.get('hit',0),
          'p':counts.get('hit',0)/60,'counts':counts,
          'box':ctx['bounds'],'variables':list(ctx['bundle'].var_names),
          'references':ctx['refs'],'seconds':time.monotonic()-t_start,
          'records':records}
    (OUT/'local-runs'/f'{cid}.json').write_text(json.dumps(finite_json(data),indent=2)+'\n')
    print(json.dumps({k:v for k,v in data.items() if k!='records'}),flush=True)
