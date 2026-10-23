"""Replay the archived post-LM closure, then independently verify the same point."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument('variant', choices=('stage8-scalar-budget-source', 'stage9-noadaptive-source'))
args = parser.parse_args()
out = Path(__file__).resolve().parent
state = json.loads((out / 'replay-environment.json').read_text())
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(state['sources'][args.variant]) / 'src'))
for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[key] = '1'
os.environ['MPMATH_NOGMPY'] = '1'
os.sched_setaffinity(0, {state['cpu']})

from mpmath import mp
from geosolver import GeometryProblem
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate
from geosolver.engine.standard.refinement.mpmath_refiner import MpmathRefiner
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.runtime.deadline import deadline_scope
from geosolver.runtime.integrity import engine_identity_hashes

bundle = load_problem_bundle(GeometryProblem.model_validate(
    json.loads((out / 'inputs/zero-distance-precision.json').read_text())).engine_document())
evaluator = build_ir_evaluator(bundle)
refiner = MpmathRefiner()
rows = []
for epsilon in ('1e-40', '1e-60'):
    started = time.monotonic()
    with mp.workdps(120), high_precision_mode():
        start = [mp.mpf(2) + mp.mpf(epsilon), mp.sqrt(2) + mp.mpf(epsilon)]
        initial_serialized = [mp.nstr(v, 125) for v in start]
        with deadline_scope(time.monotonic() + 20):
            point, history, status, dps = refiner._apply_post_lm_closure_polish(
                bundle=bundle, evaluator=evaluator, bounds=((None, None), (None, None)),
                point=start, phase_history=('120:fixed_diagnostic_start',),
                stage_status='target_reached', answer_dps=120,
                deadline_monotonic=time.monotonic()+20,
            )
    evaluations = []
    for precision in (250, 500):
        with mp.workdps(precision), high_precision_mode():
            residual = evaluator.evaluate_hp_residual(point, precision=precision)
            hard = evaluator.evaluate_hp_hard_feasibility(point, precision=precision)
            evaluations.append(dict(dps=precision, residual=str(residual.residual_norm_hp),
                                    hard_feasible=bool(hard.hard_feasible)))
    with mp.workdps(600), high_precision_mode():
        error = abs(point[0]+point[1]-(2+mp.sqrt(2)))
        serial = [mp.nstr(v, 605) for v in point]
        target_digits = str(-mp.log10(error)) if error else 'inf'
        with deadline_scope(time.monotonic()+20):
            verification = verify_final_candidate(evaluator=evaluator, values=tuple(point))
        with deadline_scope(time.monotonic()+20):
            verification_high = verify_final_candidate(
                evaluator=evaluator, values=tuple(point), precision_schedule=(350, 500))
    rows.append(dict(epsilon=epsilon, initial_values=initial_serialized,
                     closure_status=status, closure_dps=dps,
                     phase_history=list(history), values_before_verification=serial,
                     target_error_digits_before_verification=target_digits,
                     same_point_evaluation=evaluations,
                     final_verified=verification.verified, final_status=verification.status,
                     final_precision=verification.precision_dps,
                     final_failure_tags=list(verification.hard_failure_tags),
                     final_evidence=verification.evidence,
                     high_verified=verification_high.verified, high_status=verification_high.status,
                     high_precision=verification_high.precision_dps,
                     high_failure_tags=list(verification_high.hard_failure_tags),
                     high_evidence=verification_high.evidence,
                     seconds=time.monotonic()-started))
payload = dict(variant=args.variant, engine=engine_identity_hashes(), rows=rows,
               scope='Fixed post-LM starts, archived native closure and verifier; not a complete solve')
target = out / ('stability-local--'+args.variant+'.json')
target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str)+'\n')
for row in rows:
    print(json.dumps({k: row[k] for k in ('epsilon', 'closure_dps', 'final_verified', 'final_status',
                                        'final_precision', 'high_verified', 'high_status', 'high_precision',
                                        'seconds')}))
