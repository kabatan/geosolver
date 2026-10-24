"""One full external-pipeline call, <=10 s process. Persist routing only."""
import collections
import hashlib
import json
import os
import signal
import sys
import time
from pathlib import Path

OUT = Path(__file__).resolve().parent
ARM, CASE = sys.argv[1:3]
DEST = OUT / 'smoke' / f'{ARM}.{CASE}.json'
receipt = dict(arm=ARM,case_id=CASE,calls={},thresholds={},boxes=[],nomad_params=[],
               nomad_penalties={},invalid_notifications={},phase='imports')


def save():
    DEST.write_text(json.dumps(receipt,indent=2) + '\n')


def watchdog(signum, frame):
    receipt['process_state'] = 'watchdog'
    save()
    os._exit(124)


def main():
    signal.signal(signal.SIGALRM,watchdog)
    signal.setitimer(signal.ITIMER_REAL,9)
    from mpmath import mp
    from geosolver.runtime.ablation import active_ablations
    from geosolver.runtime.integrity import verify_engine_lock
    from geosolver.problem.models import GeometryProblem
    from geosolver.engine.standard.orchestration.run_external_pipeline import run_external_pipeline
    from geosolver.engine.standard.contracts.external_pipeline_config import ExternalPipelineConfig
    from geosolver.runtime.deadline import runtime_session
    ok, source_hash = verify_engine_lock()
    assert ok, source_hash
    receipt.update(active=active_ablations(),source_hash=source_hash,lock_valid=ok)
    task = next(t for t in json.loads((OUT / 'inputs.json').read_text()) if t['case_id']==CASE)
    path=Path(task['path'])
    assert hashlib.sha256(path.read_bytes()).hexdigest()==task['sha256']
    doc = GeometryProblem.model_validate_json(path.read_text()).engine_document()
    calls=collections.Counter()
    floor_fns = {'_evaluate_line_distinct_check','_evaluate_triangle_check','_evaluate_intersection_exclude_check'}
    wanted = {'run_external_pipeline','run_search','run_refinement','run_rescue_search',
              'assemble_exact_results','search_bounds','search_box_domains','dependencies',
              '_evaluate','build_params','_expand_bounds',*floor_fns}

    def trace(frame,event,arg):
        filename=frame.f_code.co_filename
        if '/geosolver/' not in filename:
            return None
        name=frame.f_code.co_name
        if event=='call':
            if name in wanted:
                calls[name]+=1
            # Trace only selected frames; do not inspect answer/residual/coordinates.
            return trace if name in wanted else None
        if event=='return':
            loc=frame.f_locals
            if name in floor_fns and 'threshold' in loc:
                receipt['thresholds'].setdefault(name,[])
                v=str(loc['threshold'])
                if v not in receipt['thresholds'][name]:
                    receipt['thresholds'][name].append(v)
            if name in {'search_bounds','_expand_bounds'} and isinstance(arg,list):
                row=dict(function=name,values=arg)
                if row not in receipt['boxes']:
                    receipt['boxes'].append(row)
            if name=='build_params' and isinstance(arg,list) and 'nomad_config.py' in filename:
                if arg not in receipt['nomad_params']:
                    receipt['nomad_params'].append(arg)
            if name=='_evaluate' and 'nomad_blackbox_adapter.py' in filename:
                # Difference between sent score and stored score is never persisted as a residual.
                if 'penalty' in loc:
                    is_off='NO_NOMAD_GUARD_PENALTY' in receipt['active']
                    key='zero' if not loc['penalty'] else ('removed' if is_off else 'applied')
                    receipt['nomad_penalties'][key]=receipt['nomad_penalties'].get(key,0)+1
                elif loc.get('self') is not None and loc['self'].records:
                    key=str(arg)
                    receipt['invalid_notifications'][key]=receipt['invalid_notifications'].get(key,0)+1
        return trace

    receipt['phase']='full_pipeline'
    started=time.monotonic()
    deadline=started+3
    # Same reduced smoke budget in all arms; no algorithm is replaced or bypassed.
    config=ExternalPipelineConfig.production_baseline_tier(seed=0,total_time_budget_sec=3)
    sys.settrace(trace)
    try:
        with mp.workdps(180),runtime_session(deadline):
            run_external_pipeline(doc,seed=0,pipeline_config=config,deadline_monotonic=deadline)
        receipt['process_state']='returned'
    except TimeoutError:
        receipt['process_state']='deadline'
    finally:
        sys.settrace(None)
        receipt['calls']=dict(calls)
        receipt['pipeline_wall_seconds']=time.monotonic()-started
        save()
    signal.setitimer(signal.ITIMER_REAL,0)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        receipt.update(process_state='exception',exception_type=type(error).__name__)
        save()
        raise
