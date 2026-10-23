"""Synthetic-only plumbing checks, not evidence on the selected 28 cases."""
import json
import numpy as np
from geosolver import GeometryProblem
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from experiment import run_arm, ARMS, make_oracle, dump, OUT

dsl={'id':'synthetic-linear','variables':['x'],'constructions':[], 'conditions':[{'left':'x','operator':'=','right':'1'}],'target':'x'}

def main():
    # Use the same public DSL schema as benchmark input, without reading answers.
    b=load_problem_bundle(GeometryProblem.model_validate(dsl).engine_document()); e=build_ir_evaluator(b)
    rows=[run_arm(a,b,e,[[-2,2]],[.2],123,[1.]) for a in ARMS]
    assert all(r['evals']<=1200 for r in rows)
    assert all(r['status']!='optimizer_error' for r in rows),[(r['arm'],r['native_result']) for r in rows]
    assert all(r['best'] and r['best']['res']<1e-5 for r in rows),[(r['arm'],r['best']) for r in rows]
    # Verify finite penalty exchange reproduces the scalar frozen adapter score.
    o=make_oracle(b,e,[[-2,2]],'N')
    v,_=o.evaluate([.2]); assert abs(np.dot(v,v)-o.last_score)<1e-10
    dump(OUT/'synthetic-check.json',rows)
    print(json.dumps({'synthetic_pass':True,'arms':len(rows),'evaluations':{r['arm']:r['evals'] for r in rows}}))

if __name__=='__main__': main()
