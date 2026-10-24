"""One preregistered 180-second public solver run in a new process."""
from __future__ import annotations
import json
import os
import sys
import time
from stage2_common import *


def main(index):
    from geosolver.application.service import solve
    from geosolver.engine.runner import EngineRunner
    from geosolver.problem.models import GeometryProblem, SolveOptions
    assert_identity()
    for name,sha in json.loads((OUT/'execution/full-implementation.lock.json').read_text())['files'].items():
        assert digest(OUT/name)==sha,name
    row=json.loads((RAW/'full-jobs.json').read_text())[index]
    d=RAW/'full'/f'{index:04d}';d.mkdir(exist_ok=True)
    assert not (d/'start.json').exists(),'No retry'
    prep=json.loads((RAW/'prepared'/f'{row["id"]}.json').read_text())
    os.environ.update(Q41_OBSERVE_DIR=str(d),Q41_DIMENSION=str(prep['arms'][row['arm']]['n']))
    receipt=dict(row,index=index,started_utc=utc(),load=os.getloadavg(),cpu=sorted(os.sched_getaffinity(0)))
    save(d/'start.json',receipt)
    t0=time.monotonic();os.environ['Q41_T0']=repr(t0)
    try:
        # This is t=0 immediately before DSL reading, not the worker's timer.
        problem=GeometryProblem.model_validate_json((OUT/'dsl'/row['id']/f'{row["arm"]}.json').read_text())
        result=solve(problem,SolveOptions(time_limit_seconds=180,cores=1,seed=row['seed']),
                     runner=EngineRunner(worker_module='q41_worker'))
        save(d/'solver-result.json',result.model_dump(mode='json'))
        receipt.update(solver_status=result.status.value,termination=result.termination_reason.value)
    except Exception as error:
        receipt.update(solver_status='exception',error=f'{type(error).__name__}: {error}')
    receipt.update(finished_utc=utc(),seconds=time.monotonic()-t0,load_after=os.getloadavg(),
                   candidate_file=str(d/'candidates.jsonl'),verification='pending')
    save(d/'done.json',receipt)
    print(json.dumps(receipt),flush=True)


if __name__=='__main__':main(int(sys.argv[1]))
