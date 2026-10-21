import json
import time
from pathlib import Path

import sympy as sp
import geosolver.engine.standard.search.algebraic_branch_boxes as boxes
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.search.algebraic_branches import (
    _eligible, discover_polynomial_branches, _bounded_symbolic_work, AlgebraicWorkLimit)
from geosolver.engine.standard.search.cartesian_polynomials import CartesianPolynomials
from geosolver.engine.standard.search.finite_target_image import finite_original_target_image
from geosolver.problem.adapter import to_engine_document
from geosolver.problem.models import GeometryProblem

root = Path('/home/kabatan/work/solver')
captured = []
original_boxes = boxes.certified_branch_boxes
def capture(solutions, points):
    result = original_boxes(solutions, points)
    if result is not None:
        captured.extend(solutions)
    return result
boxes.certified_branch_boxes = capture
records = []
for line in (root/'benchmarks/cases.jsonl').read_text().splitlines():
    case = json.loads(line)
    if case.get('authoring_status') not in (None,'runnable'):
        continue
    bundle = load_problem_bundle(to_engine_document(GeometryProblem.model_validate(case['dsl'])))
    if not _eligible(bundle):
        continue
    payload = {'variables': bundle.var_names,
        'construction': [(x.name,x.expr) for x in bundle.spec.construction],
        'constraints': bundle.spec.constraints, 'targets': bundle.targets,
        'guards': bundle.spec.guards}
    captured.clear()
    discovery = discover_polynomial_branches(payload)
    if discovery is None or not captured:
        continue
    started_cpu, started = time.process_time(), time.perf_counter()
    reason, image = None, None
    try:
        with _bounded_symbolic_work(.5) as available:
            if not available:
                reason = 'timer_unavailable'
            else:
                variables = tuple(sp.Symbol(name, real=True) for name in bundle.var_names)
                image = finite_original_target_image(bundle.spec.answer_expr, dict(payload['construction']), variables, captured)
                reason = 'proved' if image is not None else 'unresolved_image'
    except AlgebraicWorkLimit:
        reason = 'cpu_timeout'
    except (ValueError, TypeError, ArithmeticError, NotImplementedError, sp.PolynomialError):
        reason = 'unsupported_target'
    records.append({'id':case['id'],'root_count':len(captured), 'reason':reason,
        'cpu_seconds':time.process_time()-started_cpu, 'seconds':time.perf_counter()-started,
        'image':image})
destination=root/'benchmarks/local-evaluation/optimization-speed-20261011/algebra-original-image-scan.json'
destination.write_text(json.dumps(records,indent=2)+'\n')
from collections import Counter
print(json.dumps({'finite':len(records),'reasons':dict(Counter(x['reason'] for x in records)),
    'cpu_seconds':sum(x['cpu_seconds'] for x in records),
    'proved_with_duplicate_images':sum(x['image'] is not None and len(x['image']['values'])<x['root_count'] for x in records)}))
