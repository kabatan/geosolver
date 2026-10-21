"""Direct diagnostic of optional plan construction; no solver acceptance changes."""
import argparse
import json
from pathlib import Path
import signal
import time

from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.refinement.analytic_jacobian import compile_jacobian
from geosolver.problem.adapter import to_engine_document
from geosolver.problem.models import GeometryProblem


class PlanLimit(BaseException):
    pass


def stop(*_):
    raise PlanLimit


parser = argparse.ArgumentParser()
parser.add_argument("output")
args = parser.parse_args()
root = Path('/home/kabatan/work/solver')
signal.signal(signal.SIGPROF, stop)
records = []
for line in (root / 'benchmarks/cases.jsonl').read_text().splitlines():
    case = json.loads(line)
    bundle = load_problem_bundle(to_engine_document(GeometryProblem.model_validate(case['dsl'])))
    if not 2 <= len(bundle.var_names) <= 12 or bundle.spec.logical_plans:
        continue
    payload = (tuple(bundle.var_names), tuple((x.name,x.expr) for x in bundle.spec.construction),
               tuple(bundle.spec.constraints), tuple(str(x) for x in bundle.targets))
    start = time.process_time()
    signal.setitimer(signal.ITIMER_PROF, 1.5)
    try:
        result = compile_jacobian(payload)
        status = 'available' if result is not None else 'unsupported'
    except PlanLimit:
        result = None
        status = 'cpu_timeout'
    finally:
        signal.setitimer(signal.ITIMER_PROF, 0)
    records.append({'id':case['id'], 'cpu_seconds':time.process_time()-start, 'status':status,
                    'size':len(json.dumps(result)) if result else 0})
Path(args.output).write_text(json.dumps(records,indent=2)+'\n')
print(json.dumps({'eligible':len(records),'available':sum(r['status']=='available' for r in records),
                   'timeouts':sum(r['status']=='cpu_timeout' for r in records),'cpu_seconds':sum(r['cpu_seconds'] for r in records)}))
