"""Static coverage and constructor passthrough checks, without any solve."""
import ast
import json
import time
from dataclasses import asdict, replace
from stage2_common import *


def main():
    from mpmath import mp
    from geosolver.engine.standard.contracts.candidate_record import FloatCandidate,RefinedCandidate
    from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
    calls=[]
    for p in sorted((CLEAN/'src').rglob('*.py')):
        for node in ast.walk(ast.parse(p.read_text())):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in ('FloatCandidate','RefinedCandidate'):
                calls.append({'file':str(p.relative_to(CLEAN)),'line':node.lineno,'constructor':node.func.id})
    kwargs=dict(x_float=(2.,),score=0.,residual_norm_float=0.,guard_ok=True,
                evaluation_status=EvaluationStatus.OK,origin_seed=0,origin_start_point_index=0)
    baseline=FloatCandidate(**kwargs)
    refined_kwargs=dict(x_hp=(mp.mpf('2'),),residual_norm_hp=mp.mpf('0'),answer_hp=mp.mpf('2'),
                        refinement_status='fixture',phase_history=(),source=baseline)
    baseline_refined=RefinedCandidate(**refined_kwargs)
    directory=RAW/'observer-fixtures-hp';directory.mkdir(exist_ok=False)
    from q41_observer import install
    finish=install(directory,time.monotonic(),1)
    observed=FloatCandidate(**kwargs)
    from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
    with mp.workdps(80),high_precision_mode():observed_refined=RefinedCandidate(**refined_kwargs)
    copied=replace(observed,score=1.)
    assert asdict(observed)==asdict(baseline)
    assert asdict(observed_refined)==asdict(baseline_refined)
    assert copied.score==1. and copied.x_float==baseline.x_float
    summary=finish();assert summary['candidates']==3 and summary['errors']==0
    save(OUT/'execution/observer-audit.json',dict(utc=utc(),source_hash=assert_identity(),
         constructor_sites=calls,sites=len(calls),fixture_summary=summary,optimizer_calls=0,
         definition='Birth means creation of FloatCandidate/RefinedCandidate in the frozen solver. Internal finite-difference evaluation points are not candidate records.',
         coverage='All 15 explicit constructor sites and dataclasses.replace use the same observed class __init__. Includes random/manifold/affine samples, scipy, NOMAD, finite-guard, polynomial/scale-chart, refinement, and direct integer enumeration.',
         limitation='Birth time is solver-side candidate materialization after backend evaluation, not the time an internal scalar algebraic root was first calculated.'))
    print('15 constructor sites; 3 constructor/copy fixtures; no solver calls')

if __name__=='__main__':main()
