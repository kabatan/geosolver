"""One normal frozen refinement or one PSLQ condition; immutable receipts."""
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time
import traceback
from datetime import datetime, timezone

OUT=Path(__file__).resolve().parent
MAN=json.loads((OUT/'pre-run-hashes.json').read_text())
sys.dont_write_bytecode=True
sys.path.insert(0,MAN['frozen_source'])
from s2_common import canonical, references, save, now

class BudgetStop(BaseException):
    pass

def refine(item, folder):
    from mpmath import mp
    from geosolver.problem.models import GeometryProblem
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    from geosolver.engine.standard.contracts.candidate_record import FloatCandidate
    from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
    from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
    import geosolver.engine.standard.refinement.mpmath_refiner as mod
    bundle=load_problem_bundle(GeometryProblem.model_validate(item['dsl']).engine_document())
    evaluator=build_ir_evaluator(bundle)
    records=[]; samples=[]
    started=time.monotonic(); deadline=started+600
    def alarm(signum,frame):
        raise BudgetStop('180-second stage or 600-second total refinement limit')
    signal.signal(signal.SIGALRM,alarm)
    def timer(seconds):
        remaining=deadline-time.monotonic()
        if remaining<=0: raise BudgetStop('600-second refinement limit')
        signal.setitimer(signal.ITIMER_REAL,min(seconds,remaining))
    def sample(point,dps,label,answer=None):
        with mp.workdps(int(dps)),high_precision_mode():
            hard=evaluator.evaluate_hp_hard_feasibility(point,precision=int(dps),include_margins=True)
            ev=evaluator.evaluate_hp_residual(point,precision=int(dps))
            residual=mp.sqrt(mp.fsum(v*v for v in ev.residual_vector))
            if answer is None:
                answer=evaluator.evaluate_answer_hp(point,precision=int(dps)).answer_hp
            good=bool(hard.hard_feasible) and mp.isfinite(residual) and residual<=mod.RefinerConfig().target_for_dps(int(dps)) and answer is not None and mp.isfinite(answer)
            entry=dict(label=label,working_dps=int(dps),hard_feasible=bool(hard.hard_feasible),
                       original_residual_norm=mp.nstr(residual,35),eligible=bool(good),
                       coordinates=[mp.nstr(v,500) for v in point],
                       value=None if answer is None else mp.nstr(answer,500))
            samples.append(entry)
    def observe(label,dps,call,extract):
        timer(180); t=time.monotonic()
        row=dict(index=len(records)+1,label=label,working_dps=int(dps),started_seconds=t-started)
        records.append(row)
        try:
            result=call()
            row['completed']=True
            row['seconds']=time.monotonic()-t
            # Restore total timer before the extra observational evaluation.
            timer(600)
            extracted=extract(result)
            if extracted is not None:
                point,answer=extracted
                sample(point,dps,f'{row["index"]}:{label}',answer)
            return result
        except BaseException as e:
            row.update(completed=False,exception=repr(e),seconds=time.monotonic()-t)
            raise
        finally:
            save(folder/'stages.json',dict(stages=records,samples=samples))
    original_closure=mod._run_findroot_closure
    def closure(**kwargs):
        return observe('findroot',kwargs['dps'],lambda:original_closure(**kwargs),
                       lambda r:None if r is None else (r[0],None))
    class ObservedRefiner(mod.MpmathRefiner):
        def _run_stage(self,**kwargs):
            parent=super()._run_stage
            return observe('LM_integer' if kwargs.get('integer_closures') else 'LM',kwargs['dps'],
                           lambda:parent(**kwargs),lambda r:(r[1],None))
        def _direct_accept_candidate(self,**kwargs):
            parent=super()._direct_accept_candidate
            dps=max(self.config.direct_accept_dps,max(self.config.schedule_dps))
            return observe('direct_probe',dps,lambda:parent(**kwargs),
                           lambda r:None if r is None else (r.x_hp,r.answer_hp))
    candidate=FloatCandidate(x_float=tuple(float(v) for v in item['coordinates']),score=0.,
        residual_norm_float=float(item['witness']['residual_norm']),guard_ok=True,
        evaluation_status=EvaluationStatus.OK,origin_seed=0,origin_start_point_index=0,
        candidate_id=int(item['witness']['candidate_id']),hard_feasible=bool(item['witness']['hard_feasible']),
        initial_point_decimal=tuple(item['coordinates']))
    stopped='completed'; phase_history=[]
    mod._run_findroot_closure=closure
    try:
        timer(600)
        batch=ObservedRefiner().refine_candidates(bundle=bundle,evaluator=evaluator,candidates=(candidate,),deadline_monotonic=deadline)
        for i,c in enumerate(batch.candidates):
            sample(c.x_hp,c.answer_precision_dps,f'final:{i}',c.answer_hp)
            phase_history.append(dict(status=c.refinement_status,history=c.phase_history,answer_dps=c.answer_precision_dps))
    except BudgetStop as e:
        stopped=str(e)
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        mod._run_findroot_closure=original_closure
        duration=time.monotonic()-started
        save(folder/'stages.json',dict(stages=records,samples=samples,refinement_seconds=duration,stop_reason=stopped,phase_history=phase_history))
    ref,truth,description=references(item)
    with mp.workdps(700):
        for s in samples:
            if not s['eligible']: continue
            error=abs(mp.mpf(s['value'])-ref)/max(1,abs(ref))
            s['relative_error']=mp.nstr(error,45)
            s['achieved_digits']=500 if error==0 else min(500,max(0,int(mp.floor(-mp.log10(error)))))
        eligible=[s for s in samples if s.get('achieved_digits',0)>0]
        best=max(eligible,key=lambda s:s['achieved_digits']) if eligible else None
        result=dict(status='ok' if best else 'refinement_unavailable',achieved_digits=best['achieved_digits'] if best else 0,
            refinement_seconds=duration,stage_count=len(records),stop_reason=stopped,phase_history=phase_history,
            reference_value=mp.nstr(ref,700),reference_description=description,reference_source=item['reference_source'],
            true_polynomial=truth,true_max_coefficient=max(abs(c) for c in truth),
            reason='' if best else 'normal frozen refinement produced no eligible measured value')
        if best:
            result.update({k:best[k] for k in ['value','relative_error','original_residual_norm','hard_feasible','coordinates','working_dps']})
            result['selected_sample']=best['label']
    save(folder/'stages.json',dict(stages=records,samples=samples,refinement_seconds=duration,stop_reason=stopped,phase_history=phase_history))
    return result

def identify(item,condition):
    from mpmath import mp
    from pslq_wrapper import identify as pslq
    r=json.loads((OUT/'raw'/item['key']/'refined.json').read_text())
    arm,arg=condition.split('_'); achieved=r.get('achieved_digits',0)
    digits=achieved if arg=='max' or arm=='b' else int(arg)
    bound=10**8 if arm=='a' else int(arg)
    base=dict(condition=condition,arm=arm,digits=digits,max_coeff=bound,achieved_digits=achieved,
              true_polynomial=r.get('true_polynomial'),true_max_coefficient=r.get('true_max_coefficient'))
    if achieved<digits or digits==0 or r['status']!='ok':
        return base|dict(outcome='到達不可',seconds=None,polynomial=None,reason=r.get('reason',r['status']),missing_reason=r.get('exception',''))
    with mp.workdps(700):
        text=mp.nstr(mp.mpf(r['value']),digits)
        error=abs(mp.mpf(text)-mp.mpf(r['reference_value']))/max(1,abs(mp.mpf(r['reference_value'])))
    with mp.workdps(digits+40):
        value=mp.mpf(text); start=time.monotonic()
        cs=pslq(value,digits,bound); elapsed=time.monotonic()-start
    outcome='棄却' if cs is None else ('正しい式' if canonical(cs)==r['true_polynomial'] else '誤った式')
    return base|dict(outcome=outcome,seconds=elapsed,polynomial=cs,input_value=text,
        rounded_input_relative_error=mp.nstr(error,30),returned_max_coefficient=None if cs is None else max(abs(c) for c in cs),
        returned_coeff_exceeds_bound=False if cs is None else max(abs(c) for c in cs)>bound,
        bound_strictly_exceeds_truth=bound>r['true_max_coefficient'])

if __name__=='__main__':
    phase,key,cpu=sys.argv[1:4]
    os.sched_setaffinity(0,{int(cpu)})
    resource.setrlimit(resource.RLIMIT_AS,(3<<30,3<<30))
    resource.setrlimit(resource.RLIMIT_CPU,(600,601) if phase=='refine' else (180,181))
    from geosolver.runtime.integrity import source_tree_hash
    assert source_tree_hash()==MAN['source_hash']
    path=OUT/'inputs'/(key+'.json')
    assert hashlib.sha256(path.read_bytes()).hexdigest()==MAN['files'][str(path)]
    item=json.loads(path.read_text()); folder=OUT/'raw'/key; folder.mkdir(parents=True,exist_ok=True)
    name='refined' if phase=='refine' else sys.argv[4]
    with (folder/(name+'.started.json')).open('x') as f:
        json.dump(dict(utc=now(),pid=os.getpid(),cpu=int(cpu),loadavg=os.getloadavg(),phase=phase),f)
    start=time.monotonic(); result=dict(key=key,phase=phase,started_utc=now(),cpu=int(cpu),loadavg_start=os.getloadavg())
    try:
        if phase!='refine':
            signal.signal(signal.SIGALRM,lambda *a:(_ for _ in ()).throw(TimeoutError('180-second PSLQ limit')))
            signal.setitimer(signal.ITIMER_REAL,180)
        result.update(refine(item,folder) if phase=='refine' else identify(item,name))
    except Exception as e:
        result.update(status='error',outcome='欠測',achieved_digits=0,exception=repr(e),traceback=traceback.format_exc())
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
    result.update(wall_seconds=time.monotonic()-start,finished_utc=now(),loadavg_end=os.getloadavg(),
        max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,source_hash=source_tree_hash())
    save(folder/(name+'.json'),result)
