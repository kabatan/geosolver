"""Substitute saved representative diagrams into the unchanged original DSL.

No optimization, refinement, or new solution search. Run after the sweep so this
single numerical audit cannot add a fourth active stream.
"""
from __future__ import annotations
import ast
import time
from common import *

def dependencies(d, expression):
    defs={x['name']:x['expression'] for x in d['constructions']}
    names={n.id for n in ast.walk(ast.parse(str(expression),mode='eval')) if isinstance(n,ast.Name)}
    seen=set()
    while names-seen:
        current=(names-seen).pop();seen.add(current)
        if current in defs:
            names.update(n.id for n in ast.walk(ast.parse(defs[current],mode='eval')) if isinstance(n,ast.Name))
    return sorted(names & set(d['variables']))

def main():
    fingerprint()
    assert (BASE/'completed-jobs.json').exists(), 'Wait for the three main numerical lanes.'
    from mpmath import mp
    from geosolver.problem.models import GeometryProblem
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    from geosolver.engine.standard.evaluation.snapshots import numerical_snapshot
    from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
    from geosolver.problem.ir.compiler import safe_eval_expr_hp
    from geosolver.geometry.mp.mp_core_types import MPPoint
    from geosolver.runtime.deadline import runtime_session
    selection=read(BASE/'selection.json'); cache=read(EXTERNAL/'analysis-cache.json')
    if (EXTERNAL/'followup-cache.json').exists():
        assert (BASE/'completed-followup-jobs.json').exists()
        cache.update(read(EXTERNAL/'followup-cache.json'))
    cases={r['id']:r for r in selection['cases']}
    bundles={};structural={}
    for case in selection['cases']:
        d=read(BASE/case['variants']['base']['path'])
        b=load_problem_bundle(GeometryProblem.model_validate(d).engine_document())
        bundles[case['id']]=(b,build_ir_evaluator(b))
        first=next(c for c in d['conditions'] if c.get('operator')=='=')
        structural[case['id']]={'first_equality':first,
            'first_equality_variables':dependencies(d,f'({first["left"]})-({first["right"]})'),
            'original_variables':list(b.var_names),'original_equalities':len(b.spec.constraints)}
    rows=[];diagrams=[];started=time.monotonic()
    for entry in cache.values():
        bundle,evaluator=bundles[entry['id']]
        for j,candidate in enumerate(entry['projected_coordinates']):
            row={'key':entry['key'],'id':entry['id'],'arm':entry['arm'],'seed':entry['seed'],
                 'diagram_index':j,'candidate_uid':candidate['candidate_uid']}
            try:
                with mp.workdps(100),high_precision_mode(),runtime_session(time.monotonic()+20):
                    x=[mp.mpf(candidate['values'][n]) for n in bundle.var_names]
                    snapshot=numerical_snapshot(bundle.spec,bundle.var_names,x,bundle.base_context)
                    exprs=[*bundle.spec.constraints,*(t for t in bundle.targets if isinstance(t,str))]
                    context=snapshot.for_expressions(exprs)
                    norms=[]
                    for source,target in zip(bundle.spec.constraints,bundle.targets,strict=True):
                        l=safe_eval_expr_hp(source,context)
                        r=safe_eval_expr_hp(target,context) if isinstance(target,str) else mp.mpf(str(target))
                        norms.append(abs(l-r)/(1+abs(l)+abs(r)))
                    norm=max(norms,default=mp.mpf(0))
                    hard=evaluator.evaluate_hp_hard_feasibility(x,precision=100)
                    answer=evaluator.evaluate_answer_hp(x,precision=100).answer_hp
                    old=mp.mpf(candidate['answer']) if candidate['answer'] is not None else None
                    answer_error=abs(answer-old)/(1+abs(answer)+abs(old)) if answer is not None and old is not None else mp.inf
                    finite=all(mp.isfinite(v) for v in norms)
                    row.update({'normalized_original_residual':mp.nstr(norm,20),
                        'original_hard_feasible':hard.hard_feasible,'hard_failure_tags':list(hard.failure_tags),
                        'original_answer':None if answer is None else mp.nstr(answer,30),
                        'answer_relative_error':mp.nstr(answer_error,20),
                        'pass':bool(finite and norm<=mp.mpf('1e-20') and hard.hard_feasible and answer_error<=mp.mpf('1e-20'))})
                    context=snapshot.materialize(item.name for item in bundle.spec.construction)
                    points={item.name:[float(context[item.name].x),float(context[item.name].y)]
                            for item in bundle.spec.construction if isinstance(context[item.name],MPPoint)}
                    diagrams.append({**row,'variables':{n:float(v) for n,v in zip(bundle.var_names,x)},'points':points})
            except Exception as error:
                row.update({'pass':False,'error':type(error).__name__+': '+str(error)})
            rows.append(row)
    save(EXTERNAL/'original-substitutions.json',rows)
    save(EXTERNAL/'diagram-coordinates.json',diagrams)
    save(BASE/'geometry-audit.json',{'precision_dps':100,'normalized_residual_threshold':'1e-20',
        'scope':'one saved representative per projected diagram at relative tolerance1e-7; not an independent exact proof',
        'representatives':len(rows),'pass':sum(r['pass'] for r in rows),'failures':[r for r in rows if not r['pass']],
        'structure':structural,'elapsed_seconds':time.monotonic()-started,
        'external_rows_sha256':sha((EXTERNAL/'original-substitutions.json').read_bytes()),
        'external_figures_sha256':sha((EXTERNAL/'diagram-coordinates.json').read_bytes())})
    print(canonical({'representatives':len(rows),'passed':sum(r['pass'] for r in rows),'elapsed':time.monotonic()-started}))

if __name__=='__main__':main()
