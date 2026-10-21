import ast
import inspect
import json
import time
from collections import Counter
from pathlib import Path

import geosolver.engine.standard.search.algebraic_branches as module
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.search.target_elimination import target_elimination_receipt
from geosolver.problem.adapter import to_engine_document
from geosolver.problem.models import GeometryProblem

def probe(equations, geometry, variables, payload):
    target = geometry.scalar(geometry.parse(payload['answer_expr']))
    proof = target_elimination_receipt(equations, target, variables)
    return {'reason': 'proved' if proof is not None else 'unresolved', 'proof':proof}

class Intercept(ast.NodeTransformer):
    def visit_Assign(self, node):
        if any(isinstance(t,ast.Name) and t.id=='consequences' for t in node.targets):
            return ast.copy_location(ast.Return(ast.Call(
                ast.Name('target_probe',ast.Load()),
                [ast.Name(n,ast.Load()) for n in ('equations','geometry','variables','payload')], [])), node)
        return node

scope=vars(module).copy()
scope['target_probe']=probe
tree=ast.fix_missing_locations(Intercept().visit(ast.parse(inspect.getsource(module._discover_polynomial_branches))))
exec(compile(tree,'<research-target-projection>','exec'),scope)
discover=scope['_discover_polynomial_branches']
root=Path('/home/kabatan/work/solver')
records=[]
for line in (root/'benchmarks/cases.jsonl').read_text().splitlines():
    case=json.loads(line)
    if case.get('authoring_status') not in (None,'runnable'):
        continue
    bundle=load_problem_bundle(to_engine_document(GeometryProblem.model_validate(case['dsl'])))
    if not module._eligible(bundle):
        continue
    payload={'variables':bundle.var_names,
        'construction':[(x.name,x.expr) for x in bundle.spec.construction],
        'constraints':bundle.spec.constraints,'targets':bundle.targets,
        'guards':bundle.spec.guards,'answer_expr':bundle.spec.answer_expr}
    work=module._DiscoveryWork()
    start_cpu,start=time.process_time(),time.perf_counter()
    result=discover(payload,work)
    records.append({'id':case['id'],'cpu_seconds':time.process_time()-start_cpu,
        'seconds':time.perf_counter()-start, 'work':work.snapshot(),
        **(result or {'reason':'unsupported_or_budget','proof':None})})
destination=root/'benchmarks/local-evaluation/optimization-speed-20261011/algebra-target-elimination-scan.json'
destination.write_text(json.dumps(records,indent=2)+'\n')
print(json.dumps({'eligible':len(records),'reasons':dict(Counter(x['reason'] for x in records)),
    'cpu_seconds':sum(x['cpu_seconds'] for x in records),
    'positive_dimensional_proved':sum(x['proof'] is not None and not x['proof']['zero_dimensional_configuration_ideal'] for x in records)}))
