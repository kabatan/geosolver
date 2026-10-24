"""One fixed block of local starts; completed/started slots are never rerun."""
from __future__ import annotations
import json
import os
import sys
import time
from pathlib import Path
import numpy as np
from stage2_common import *


def run_block(index):
    from geosolver.engine.standard.search import scipy_multistart_backend as backend
    from geosolver.engine.standard.contracts.external_pipeline_config import ExternalPipelineConfig
    # Load SciPy before starting a timed slot; the slot times one optimization.
    import scipy.optimize
    assert_identity()
    locked=json.loads((OUT/'execution/implementation.lock.json').read_text())
    for name,sha in locked['files'].items(): assert digest(OUT/name)==sha,name
    jobs=json.loads((RAW/'local-jobs.json').read_text())
    rows=jobs[index]
    d=RAW/'local'/f'{index:04d}';d.mkdir(exist_ok=True)
    results=d/'records.jsonl';starts=d/'starts.jsonl'
    key=lambda r:(r['id'],r['arm'],r['k'])
    done={key(json.loads(line)) for line in results.read_text().splitlines()} if results.exists() else set()
    begun={key(json.loads(line)) for line in starts.read_text().splitlines()} if starts.exists() else set()
    cases={};prepared={};capture={}
    for name in ('least_squares','minimize'):
        original=getattr(backend,name)
        def observe(*a,_original=original,**kw):
            result=_original(*a,**kw)
            capture.update(x=[float(v) for v in result.x], nfev=int(result.nfev),
                           optimizer_status=int(result.status),optimizer_success=bool(result.success),
                           optimizer_message=str(result.message))
            return result
        setattr(backend,name,observe)
    config=ExternalPipelineConfig.production_baseline_tier(seed=410241,total_time_budget_sec=180).search
    for row in rows:
        cid,arm,k=row['id'],row['arm'],row['k']
        if key(row) in done:continue
        if key(row) in begun:
            append(results,dict(row,success=False,reason='interrupted_no_retry',x=None))
            continue
        if cid not in prepared:prepared[cid]=json.loads((RAW/'prepared'/f'{cid}.json').read_text())
        p=prepared[cid]
        if (cid,arm) not in cases:cases[cid,arm]=load_case(cid,arm)
        _,b,e,j=cases[cid,arm]
        x=p['starts'][k]
        rec=dict(row,start=x,method=p['arms'][arm]['method'],started_utc=utc(),success=False)
        append(starts,rec)
        capture.clear();telemetry=backend._SearchTelemetry();t=time.monotonic()
        stop='returned'
        try:
            with limit(2.0):
                candidate=backend._collect_local_start_record(bundle=b,evaluator=e,bounds=p['bounds'],
                    config=config,seed=410241,start_index=k,start=np.array(x,dtype=float),
                    deadline_monotonic=t+2.0,telemetry=telemetry,constraint_scales=None)
            if candidate is None:stop='local_returned_none'
        except (MeasurementDeadline,TimeoutError,backend._SearchDeadlineExceeded):stop='local_timeout'
        except Exception as err:stop=f'local_exception:{type(err).__name__}:{err}'
        rec.update(capture,local_seconds=time.monotonic()-t,stop=stop,
                   evaluation_count=telemetry.evaluation_count,evaluation_failures=telemetry.failure_count)
        if stop=='returned' and capture.get('x') is not None:
            check=check_point(j,capture['x'])
            rec.update(success=check['success'],reason=check['reason'],verification=check)
        else:rec.update(reason=stop,x=capture.get('x'))
        append(results,rec)
    save(d/'done.json',dict(utc=utc(),slots=len(rows),sha256=digest(results),
                           cpu=sorted(os.sched_getaffinity(0))))
    print(json.dumps(dict(block=index,slots=len(rows),done=True)),flush=True)


if __name__=='__main__':run_block(int(sys.argv[1]))
