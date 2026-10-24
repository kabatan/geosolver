"""One problem: at most one ordinary solve, one reference closure, static Jacobians."""
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time
import traceback

sys.dont_write_bytecode=True
OUT=Path(__file__).resolve().parent
M=json.loads((OUT/'pre-run-hashes.json').read_text())
sys.path.insert(0,M['frozen_source'])
from select_targets import save,sha
from mpmath import mp
import s4_helpers as s4
from reference import make_reference
from measure import measure
from geosolver.engine.standard.precision.type_guards.boundary_float_to_mpf import boundary_float_to_mpf,BoundaryOrigin


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


def sigma_kind(value):
    v=mp.mpf(value)
    return '特異' if v<mp.mpf('1e-60') else ('非特異' if v>mp.mpf('1e-10') else '不定')

def run(key,cpu):
    started=time.monotonic()
    os.sched_setaffinity(0,{int(cpu)})
    os.environ.update(M['threads'])
    resource.setrlimit(resource.RLIMIT_FSIZE,(2_999_999,2_999_999))
    task=next(t for t in M['items'] if t['case_id']==key)
    folder=OUT/'results'/key;folder.mkdir(parents=True,exist_ok=True)
    with (folder/'started.json').open('x') as f: json.dump(dict(started=time.time(),cpu=cpu,pid=os.getpid()),f)
    result=dict(case_id=key,status='reference_unavailable',type='参照解なし',prediction='',reason='')
    def timeout_handler(*_): raise TimeoutError('per-problem 600-second limit')
    signal.signal(signal.SIGALRM,timeout_handler);signal.alarm(598)
    try:
        assert s4.source_tree_hash()==M['source_hash']
        assert sha(Path(task['input']))==M['files'][task['input']]
        item=json.loads(Path(task['input']).read_text())
        if item['selection'] is None:
            item['selection']=fresh_solve(item,folder)
        else:
            save(folder/'diagram-selection.json',item['selection'])
        if item['selection'] is None:
            result['reason']='凍結版通常solve(seed 0)の1回実行で最終検証通過図なし'
            return
        bundle=s4.load_problem_bundle(s4.GeometryProblem.model_validate(item['dsl']).engine_document())
        evaluator=s4.build_ir_evaluator(bundle)
        if not item['reference_expressions']:
            result['reason']='独立参照式なし: '+str(item.get('reference_parse_error'))
            return
        ref=make_reference(item,bundle,evaluator,folder)
        save(folder/'reference.json',ref)
        if ref['status']!='ok':
            result['reason']=ref['reason'];return
        result.update(reference_status='ok',reference_absolute_digits=ref['absolute_digits'],type='不定',status='measurement_unavailable')
        starts=item['selection'].get('initial_points',[])
        # float-boundary conversion is outside high_precision_mode, as in S4.12.
        with mp.workdps(700):
            points=[[boundary_float_to_mpf(v,origin=BoundaryOrigin.INITIAL_POINT) for v in p] for p in starts]
        assert points, 'no preserved initial search coordinates for S4 fixed divisors'
        scales=fixed_scales(item,bundle,points);save(folder/'scales.json',scales)
        details,rows=measure(s4,item,ref,scales,{key:points},dict(case_id=key,reference=str(folder/'reference.json')))
        save(folder/'sigma-details.json',details)
        judgments={}
        with mp.workdps(200):
            for method in ['T1','T2']:
                condition=details['conditions'][method]
                sigmas=[s['singular_values'][0] for s in condition['samples']]
                states=[sigma_kind(s) for s in sigmas]
                judgments[method]=states[0] if len(set(states))==1 else '不定'
                result.update({method+'_sigma':sigmas[0],method+'_sigma_check':sigmas[1],
                    method+'_judgment':judgments[method],method+'_spectra_agree':condition['agreement']})
        pair=judgments['T1'],judgments['T2']
        kind={('特異','非特異'):'P',('非特異','非特異'):'N',('特異','特異'):'B'}.get(pair,'不定')
        result.update(status='ok',type=kind,prediction={'P':'U1: T2がT1より40桁以上良い','N':'U2: T1とT2が20桁以内','B':'U3: T2が300桁未満'}.get(kind,''),
                      reason='' if kind!='不定' else '両幅の閾値判定が不定、または登録のP/N/Bに該当しない組合せ')
    except BaseException as e:
        result.update(reason=repr(e),traceback=traceback.format_exc())
    finally:
        signal.alarm(0)
        result['elapsed_seconds']=time.monotonic()-started
        save(folder/'result.json',result)
        print(key,result['type'],result['reason'],flush=True)

if __name__=='__main__': run(*sys.argv[1:3])
