import argparse
import json
import time
from pathlib import Path

from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.search.algebraic_branches import _eligible, discover_polynomial_branches
from geosolver.problem.adapter import to_engine_document
from geosolver.problem.models import GeometryProblem

parser = argparse.ArgumentParser()
parser.add_argument("output")
args = parser.parse_args()
root = Path('/home/kabatan/work/solver')
records = []
for line in (root / 'benchmarks/cases.jsonl').read_text().splitlines():
    case = json.loads(line)
    if case.get('authoring_status') not in (None, 'runnable'):
        continue
    bundle = load_problem_bundle(to_engine_document(GeometryProblem.model_validate(case['dsl'])))
    if not _eligible(bundle):
        continue
    payload = {'variables': bundle.var_names,
        'construction': [(x.name,x.expr) for x in bundle.spec.construction],
        'constraints': bundle.spec.constraints, 'targets': bundle.targets,
        'guards': bundle.spec.guards, 'report_work': True}
    start = time.perf_counter()
    result = discover_polynomial_branches(payload)
    records.append({'id': case['id'], 'seconds': time.perf_counter()-start, **result})
Path(args.output).write_text(json.dumps(records, indent=2)+'\n')
print(json.dumps({'eligible':len(records), 'seconds':sum(r['seconds'] for r in records),
    'finite':sum(r['result'] is not None for r in records)}))
