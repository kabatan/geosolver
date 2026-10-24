"""Permitted procedure functions extracted without executing historical manifests."""
import ast
import json
import time
from pathlib import Path
from functools import partial
from mpmath import mp
from geosolver.problem.models import GeometryProblem
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.evaluation.high_precision_expressions import build_solution_context_high_precision
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.problem.ir.compiler import safe_eval_expr_hp
from geosolver.engine.standard.problem.tangency_contacts import contact_tangency_source, distance_contact_sources
from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate
from geosolver.runtime.integrity import source_tree_hash

def save(p,v):
    data=json.dumps(v,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n'
    assert len(data.encode())<3_000_000
    Path(p).write_text(data)

def num(v,digits=200):
    return mp.nstr(v,digits,min_fixed=0,max_fixed=0) if v else '0.0e+0'

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

def fresh_solve(item,folder):
    from geosolver import solve
    from geosolver.engine.runner import EngineExecution
    from geosolver.runtime.protocol import WorkerRequest
    from geosolver.runtime.worker import execute
    import geosolver.engine.standard.orchestration.run_external_pipeline as pipeline
    import geosolver.engine.standard.orchestration.assemble_exact_results as assembly
    original_refine=pipeline.run_refinement
    original_verify=assembly.verify_final_candidate
    initial=[];selected=[]
    def observe_refine(**kw):
        if not initial:
            initial.extend([list(c.x_float) for c in kw['search_result'].candidates])
            save(folder/'initial.json',dict(source='first ordinary refinement handoff',points=initial))
        return original_refine(**kw)
    def observe_verify(**kw):
        result=original_verify(**kw)
        if result.verified and not selected:
            witness=dict(verified=True,status=result.status,precision_dps=result.precision_dps,
                values=[mp.nstr(v,710) for v in result.values])
            selected.append(dict(arm='fresh_frozen_solve',rank=0,candidate_uid=None,
                values=witness['values'],witness=witness))
            save(folder/'solve-first-verified.json',selected[0])
        return result
    class MemoryRunner:
        # Ordinary public solve and worker.execute, avoiding expanded artifact files.
        # The default solver tier and 2-second save reserve are unchanged.
        def run(self,doc,*,seed,cores,time_limit_seconds,deadline_monotonic):
            request=WorkerRequest(engine_document=doc,seed=seed,effective_cores=cores,
                deadline_monotonic=deadline_monotonic,
                config_snapshot=dict(time_limit_seconds=time_limit_seconds,cores=cores,seed=seed))
            return EngineExecution(artifact=execute(request),stdout='',stderr='')
    receipt=folder/'solve-started.json'
    with receipt.open('x') as f:
        json.dump(dict(seed=0,time_limit_seconds=180,source_hash=s4.source_tree_hash(),started=time.time()),f)
    pipeline.run_refinement=observe_refine;assembly.verify_final_candidate=observe_verify
    started=time.monotonic()
    try:
        result=solve(item['dsl'],dict(seed=0,cores=1,time_limit_seconds=180),runner=MemoryRunner())
        save(folder/'solve.json',dict(status=str(result.status),elapsed=time.monotonic()-started,
            error=None if result.error is None else result.error.model_dump(),
            requested_resources=result.requested_resources.model_dump(),
            source_hash=result.engine.source_hash,verified_diagram=bool(selected),
            runner='in-memory ordinary geosolver.runtime.worker.execute'))
    finally:
        pipeline.run_refinement=original_refine;assembly.verify_final_candidate=original_verify
    if selected:
        selected[0]['initial_points']=initial
        return selected[0]
    return None

def fixed_scales(item,bundle,points):
    """Same original-row divisor rule as S1; no reference coordinates used."""
    from geosolver.problem.ir.parser import load_ir
    from geosolver.engine.standard.evaluation.high_precision_expressions import evaluate_target_high_precision
    from geosolver.engine.standard.evaluation.snapshots import evaluate_scalar_expression
    spec=load_ir(s4.GeometryProblem.model_validate(item['dsl']).engine_document())
    targets=tuple(spec.v) if spec.v is not None else (0,)*len(spec.constraints)
    scales=[mp.mpf(1) for _ in targets];counts=[0 for _ in targets]
    with mp.workdps(700),s4.high_precision_mode():
        for point in points:
            try:
                ctx=s4.build_solution_context_high_precision(spec,list(bundle.var_names),point,
                    bundle.base_context,700,expressions=[*spec.constraints,*(t for t in targets if isinstance(t,str))])
                for i,expr in enumerate(spec.constraints):
                    try:
                        lhs=mp.mpf(evaluate_scalar_expression(expr,ctx,constants_only=True))
                        rhs=evaluate_target_high_precision(targets[i],ctx,precision=700,index=i)
                        if mp.isfinite(lhs) and mp.isfinite(rhs):
                            scales[i]=max(scales[i],abs(lhs),abs(rhs));counts[i]+=1
                    except Exception: pass
            except Exception: pass
        return dict(constraints=list(spec.constraints),targets=list(targets),
            scales=[mp.nstr(v,710) for v in scales],finite_counts=counts,
            rule='max(1,finite |lhs|,finite |rhs|) over saved first ordinary search candidates; never reference solution')

def make_reference(item,bundle,evaluator,folder):
    if item['selection'] is None:
        return dict(status='reference_unavailable',reason='今回の単一通常solveで最終検証通過図なし')
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
            relative_error=num(relative,50))
        if not mp.isfinite(answer) or error>mp.mpf('1e-300') or relative>mp.mpf('1e-300'):
            return result|dict(status='reference_unavailable',reason='目標値と独立参照値の300桁一致を確認できず')
    return result|dict(status='ok')

import sys
s4=sys.modules[__name__]
