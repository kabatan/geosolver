"""Reference construction only, followed by independent local derivatives."""
import ast
from functools import partial
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback

OUT = Path(__file__).resolve().parent
M = json.loads((OUT / 'pre-run-hashes.json').read_text())
sys.dont_write_bytecode = True
sys.path.insert(0, M['frozen_source'])
from mpmath import mp
from geosolver.problem.models import GeometryProblem
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.evaluation.high_precision_expressions import build_solution_context_high_precision
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.problem.ir.compiler import safe_eval_expr_hp
from geosolver.engine.standard.problem.tangency_contacts import contact_tangency_source, distance_contact_sources
from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate, _variable_scales
from geosolver.runtime.integrity import source_tree_hash

def save(p, v):
    p.write_text(json.dumps(v, ensure_ascii=False, indent=2, default=str)+'\n')

def num(v, digits=200):
    return mp.nstr(v, digits)

def inventory(item, bundle):
    constructions = tuple((v.name, v.expr) for v in bundle.spec.construction)
    equalities = tuple(zip(bundle.spec.constraints, map(str,bundle.targets), strict=True))
    distance_sources = distance_contact_sources(constructions, equalities)
    defs = {n: ast.parse(s, mode='eval').body for n,s in constructions}
    def resolve(n):
        seen=set()
        while isinstance(n,ast.Name) and n.id in defs and n.id not in seen:
            seen.add(n.id); n=defs[n.id]
        return n
    def call(n,name,count):
        return isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id==name and len(n.args)==count
    def same(a,b):
        return ast.dump(resolve(a),include_attributes=False)==ast.dump(resolve(b),include_attributes=False)
    circles=[(name,resolve(node)) for name,node in defs.items() if call(resolve(node),'Circle',2)]
    result=[]
    for index,c in enumerate(item['dsl']['conditions']):
        if c.get('operator')!='=' or 'left' not in c:
            continue
        lhs,rhs=str(c['left']),str(c['right'])
        a,b=ast.parse(lhs,mode='eval').body,ast.parse(rhs,mode='eval').body
        descriptor=None
        for source,node,other in [(lhs,a,b),(rhs,b,a)]:
            if call(node,'IsTangent',2) and isinstance(other,ast.Constant) and other.value==0:
                left,right=[ast.get_source_segment(source,n) for n in node.args]
                descriptor=dict(index=index, condition=f'{lhs} = {rhs}',kind='tangent',left=left,right=right,
                    t2_source=contact_tangency_source(left,right,constructions,equalities))
                break
        if descriptor is None:
            for distance,radius in [(a,b),(b,a)]:
                distance=resolve(distance)
                if not call(distance,'Distance',2): continue
                for center,line in [distance.args, list(reversed(distance.args))]:
                    if not call(resolve(line),'Line',2): continue
                    for name,circle in circles:
                        if same(center,circle.args[0]) and same(radius,circle.args[1]):
                            bi=next((i for i,(l,r) in enumerate(equalities) if l==lhs and r==rhs),None)
                            descriptor=dict(index=index,condition=f'{lhs} = {rhs}',kind='tangent',
                                left=ast.unparse(line),right=name,t2_source=distance_sources.get(bi))
                if descriptor: break
        if descriptor:
            result.append(descriptor)
    return result

def context(bundle, point, expressions, dps):
    return build_solution_context_high_precision(bundle.spec,list(bundle.var_names),list(point),
                                                 bundle.base_context,dps,expressions=expressions)

def objects(bundle, point, row, dps):
    ctx=context(bundle,point,[row['left'],row['right']],dps)
    return [getattr(v,'circle',v) for v in [safe_eval_expr_hp(row['left'],ctx),safe_eval_expr_hp(row['right'],ctx)]]

def t1(bundle, point, row):
    a,b=objects(bundle,point,row,200)
    if hasattr(a,'radius') and hasattr(b,'radius'):
        d=a.center.distance_to(b.center)
        return d-(a.radius+b.radius) if row['branch']=='outer' else d-abs(a.radius-b.radius)
    line,circle=(a,b) if hasattr(a,'a') else (b,a)
    delta=line.a*circle.center.x+line.b*circle.center.y+line.c
    return delta**2-circle.radius**2

def t2(bundle, point, row):
    ctx=context(bundle,point,[row['t2_source']],200)
    return mp.mpf(safe_eval_expr_hp(row['t2_source'],ctx))

def classify(g):
    if not mp.isfinite(g): return '不定'
    return '重根型' if g<mp.mpf('1e-50') else ('単根型' if g>mp.mpf('1e-10') else '不定')

def gradient(bundle, point, row, method, divisor):
    fn=t1 if method=='g1' else t2
    with mp.workdps(200),high_precision_mode():
        samples=[]
        for exponent in [70,60]:
            grad=[]
            for j,value in enumerate(point):
                h=mp.mpf(10)**(-exponent)*max(1,abs(value))
                plus=list(point); minus=list(point)
                plus[j]=value+h; minus[j]=value-h
                grad.append((fn(bundle,plus,row)-fn(bundle,minus,row))/(2*h))
            g=mp.sqrt(mp.fsum(v*v for v in grad))/divisor
            samples.append((g,grad))
        g,grad=samples[0]; check,checkgrad=samples[1]
        judgement=classify(g) if classify(g)==classify(check) else '不定'
        return {method:num(g),method+'_judgment':judgement,method+'_check':num(check),
            method+'_difference':num(abs(g-check)),method+'_gradient':[num(v) for v in grad],
            method+'_check_gradient':[num(v) for v in checkgrad],method+'_value':num(fn(bundle,point,row))}

def make_reference(item,bundle,evaluator,folder):
    if item['selection'] is None:
        return dict(status='reference_unavailable',reason='S1両構成に凍結版の最終検証通過候補なし')
    from geosolver.runtime.deadline import runtime_session
    from geosolver.engine.standard.refinement.mpmath_refiner import MpmathRefiner, _run_findroot_closure, _convert_problem_bounds
    from geosolver.engine.standard.interpreter.answer import _eval_exact_to_mpf
    deadline=time.monotonic()+180
    with mp.workdps(700):
        references=[_eval_exact_to_mpf(s,700) for s in item['reference_expressions']]
    if not all(v is not None and mp.isfinite(v) for v in references):
        return dict(status='reference_unavailable',reason='独立参照式を評価できず')
    with mp.workdps(180), high_precision_mode(), runtime_session(deadline):
        values=[mp.mpf(s) for s in item['selection']['values']]
        verification=verify_final_candidate(evaluator=evaluator,values=values)
        witness=dict(verified=verification.verified,status=verification.status,
                     precision_dps=verification.precision_dps,values=[num(v,710) for v in verification.values])
        save(folder/'verification.json',witness)
    if not verification.verified:
        return dict(status='reference_unavailable',reason='固定した候補の再検証不通過',verification=witness)
    with mp.workdps(620),high_precision_mode(),runtime_session(deadline):
        closed=_run_findroot_closure(evaluator=evaluator,start_point=list(verification.values),
            bounds=_convert_problem_bounds(bundle),dps=620,target_residual=mp.mpf('1e-580'),
            solver_tolerance=mp.mpf('1e-1160'),max_steps=1240,deadline_monotonic=deadline,
            residual_fn=partial(MpmathRefiner()._residual_vector_for_stage,bundle,evaluator,smooth_zero_constraints=True),
            one_sided_at_cusp=any('Angle(' in str(c) for c in bundle.spec.constraints))
        if closed is None:
            return dict(status='reference_unavailable',reason='凍結版の一度の620桁closureが残差基準に到達せず',verification=witness)
        coordinates=[num(v,620) for v in closed[0]]
        point=[mp.mpf(s) for s in coordinates]
        residual=evaluator.evaluate_hp_residual(point,precision=620)
        norm=mp.sqrt(mp.fsum(v*v for v in residual.residual_vector))
        hard=evaluator.evaluate_hp_hard_feasibility(point,precision=620,include_margins=True)
        ev=evaluator.evaluate_answer_hp(point,precision=620)
        result=dict(coordinates=coordinates,var_names=list(bundle.var_names),original_residual_norm=num(norm,40),
            hard_feasible=bool(hard.hard_feasible),evaluation_status=ev.evaluation_status.value,
            refinement_dps=620,stored_significant_digits=620,verification=witness)
        if not hard.hard_feasible or ev.answer_hp is None or norm>mp.mpf('1e-580'):
            return result|dict(status='reference_unavailable',reason='保存座標のhard/residual/target門を通らず')
    with mp.workdps(700),high_precision_mode():
        answer=evaluator.evaluate_answer_hp([mp.mpf(s) for s in coordinates],precision=700).answer_hp
        ref=min(references,key=lambda v:abs(v-answer))
        error=abs(answer-ref); relative=error/max(1,abs(ref))
        result.update(answer=num(answer,700),reference=num(ref,700),absolute_error=num(error,50),
            relative_error=num(relative,50),absolute_digits=num(-mp.log10(error) if error else mp.inf,30))
        if not mp.isfinite(answer) or error>mp.mpf('1e-200') or relative>mp.mpf('1e-200'):
            return result|dict(status='reference_unavailable',reason='目標値と独立参照値の200桁一致を確認できず')
    return result|dict(status='ok')

def run(key,cpu):
    os.sched_setaffinity(0,{int(cpu)})
    assert source_tree_hash()==M['source_hash']
    task=next(t for t in M['items'] if t['case_id']==key)
    ip=Path(task['input'])
    assert hashlib.sha256(ip.read_bytes()).hexdigest()==M['files'][str(ip)]
    item=json.loads(ip.read_text())
    folder=Path(M['scratch'])/key; folder.mkdir()
    save(folder/'started.json',dict(time=time.time(),pid=os.getpid(),cpu=cpu))
    bundle=load_problem_bundle(GeometryProblem.model_validate(item['dsl']).engine_document())
    evaluator=build_ir_evaluator(bundle)
    rows=inventory(item,bundle)
    result=dict(case_id=key,conditions=rows)
    try:
        reference=make_reference(item,bundle,evaluator,folder)
        result['reference']=reference
        save(folder/'reference.json',reference)
        if reference['status']=='ok':
            with mp.workdps(200),high_precision_mode():
                point=[mp.mpf(s) for s in reference['coordinates']]
                scales=_variable_scales(evaluator,point)
                divisor=max([mp.mpf(1),*scales])
                result.update(variable_scales=[num(s) for s in scales],scale_divisor=num(divisor))
                for row in rows:
                    a,b=objects(bundle,point,row,200)
                    if hasattr(a,'radius') and hasattr(b,'radius'):
                        d=a.center.distance_to(b.center)
                        row['branch']='outer' if abs(d-a.radius-b.radius)<=abs(d-abs(a.radius-b.radius)) else 'inner'
                    else: row['branch']='line_circle'
                    row.update(gradient(bundle,point,row,'g1',divisor))
                    if row['t2_source']:
                        row.update(gradient(bundle,point,row,'g2',divisor))
            result['status']='ok'
        else:
            result.update(status='reference_unavailable',reason=reference['reason'])
    except Exception as e:
        result.update(status='error',reason=repr(e),traceback=traceback.format_exc())
    save(folder/'result.json',result)
    print(key,result['status'],result.get('reason',''),flush=True)

if __name__=='__main__':
    run(*sys.argv[1:3])
