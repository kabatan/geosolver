"""Read-only use of frozen GeoSolver and its existing probe's scoring criteria."""
import math
import sys
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0,str(ROOT/'jssa/difficulty'))
from probe_basins import (ANS_RTOL, RES_TOL, answer_float, load_case, reference_values,
    GeometryProblem, load_problem_bundle, build_ir_evaluator, infer_problem_bounds,
    ExternalPipelineConfig, smb)

IDS = ['AIME-2006-I-01','AIME-2025-I-06','AIME-2025-II-06',
       'HMMT-2010-FEB-GEO-02','HMMT-2014-FEB-GEO-08','JMO-2008-PRE-02']

def context(cid, seed=211025):
    case = load_case(cid)
    bundle = load_problem_bundle(GeometryProblem.model_validate(case['dsl']).engine_document())
    evaluator = build_ir_evaluator(bundle)
    bounds = infer_problem_bounds(bundle)
    config = ExternalPipelineConfig.production_baseline_tier(
        seed=seed,total_time_budget_sec=180.0).search
    return dict(id=cid,bundle=bundle,evaluator=evaluator,bounds=bounds,config=config,
                refs=reference_values(case['answer']),telemetry=smb._SearchTelemetry())

def classify(ctx, cand):
    if cand is None:
        return {'cls':'error'}
    rec = dict(x=list(cand.x_float),res=cand.residual_norm_float,
               guard_ok=bool(cand.guard_ok),hard_feasible=cand.hard_feasible,
               hard_violation_tags=list(cand.hard_violation_tags))
    if 'out_of_bounds' in tuple(cand.hard_violation_tags):
        rec['cls']='left_box'
    elif not math.isfinite(cand.residual_norm_float):
        rec.update(cls='error',error='nonfinite')
    elif cand.residual_norm_float > RES_TOL:
        rec['cls']='stuck'
    elif not (bool(cand.guard_ok) and cand.hard_feasible is not False):
        rec['cls']='wrong_branch'
    else:
        value=answer_float(ctx['evaluator'],cand.x_float)
        rec['ans']=value
        matches=[j for j,r in enumerate(ctx['refs']) if value is not None and
                 abs(value-r)<=ANS_RTOL*max(1.0,abs(r))]
        rec['cls']='hit' if matches else 'wrong_answer'
        if matches:
            rec['ref']=matches[0]
    return rec

def score_point(ctx, x):
    cand=smb._build_candidate(evaluator=ctx['evaluator'],config=ctx['config'],
        bounds=ctx['bounds'],values=np.array(x,dtype=float),origin_seed=0,
        family_code=smb._LM_FAMILY_CODE,origin_start_point_index=0,
        telemetry=ctx['telemetry'])
    return classify(ctx,cand)

def finite_json(x):
    if isinstance(x,dict): return {k:finite_json(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)): return [finite_json(v) for v in x]
    if isinstance(x,float) and not math.isfinite(x): return None
    return x
