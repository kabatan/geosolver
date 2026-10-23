"""Unregistered, post-result compile-only check of a rejected second candidate."""
import copy
import json
from pathlib import Path

from geosolver import GeometryProblem
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator

OUT=Path(__file__).resolve().parent


def main():
    base=copy.deepcopy(json.loads((OUT/'stimuli.json').read_text())[0]['variants']['power_near']['dsl'])
    base['id']='posthoc-static-circle'
    base['conditions']=base['conditions'][:1]
    base['target']='Distance(P,A)'
    padded=copy.deepcopy(base)
    padded['conditions'].append({'left':'Distance(A,B)**2','operator':'=','right':'9'})
    output={'registered_trial':False,'optimizer_calls':0,
            'meaning':'A=(-3/2,0), B=(3/2,0)なのでAB²=9は恒等的に真。探索は実施しない。',
            'variants':{}}
    vectors=[]
    for name,dsl in [('base',base),('padded',padded)]:
        b=load_problem_bundle(GeometryProblem.model_validate(dsl).engine_document())
        e=build_ir_evaluator(b)
        ns=len(b.var_names); ms=len(b.spec.constraints)
        samples=[]
        for xy in [[0,1],[.3,-.7],[2,1.5]]:
            samples.append({'x':xy,'residual':list(map(float,e.evaluate_float_residual(xy).residual_vector))})
        output['variants'][name]={'dsl':dsl,'n_vars':ns,'n_constraints':ms,
             'guards':list(b.spec.guards),'hard_checks':repr(b.hard_feasibility_checks),
             'dispatch_predicted_from_source':'Powell' if ns>ms else 'LM',
             'dispatch_executed':False,'samples':samples}
        vectors.append(samples)
    output['retained_zero_row']=output['variants']['padded']['n_constraints']==output['variants']['base']['n_constraints']+1
    output['sample_objectives_equal']=all(sum(z*z for z in a['residual'])==sum(z*z for z in b['residual']) for a,b in zip(*vectors))
    output['guards_same']=output['variants']['base']['guards']==output['variants']['padded']['guards']
    output['hard_checks_same']=output['variants']['base']['hard_checks']==output['variants']['padded']['hard_checks']
    (OUT/'static-dispatch.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in output.items() if k!='variants'},ensure_ascii=False))
    print(json.dumps({k:{f:v[f] for f in ['n_vars','n_constraints','dispatch_predicted_from_source']} for k,v in output['variants'].items()}))


if __name__=='__main__':
    main()
