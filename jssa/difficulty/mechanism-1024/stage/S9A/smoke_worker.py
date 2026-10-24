"""One saved candidate, one refinement stage; emits control flow only."""
import hashlib
import json
import os
import pickle
import signal
import sys
import time
from pathlib import Path

OUT = Path(__file__).resolve().parent
ARM = sys.argv[1]
RECEIPT = OUT / 'smoke' / (ARM + '.json')
M = json.loads((OUT / 'pre-smoke-hashes.json').read_text())
S = json.loads((OUT / 'source-hashes.json').read_text())
C = json.loads((OUT / 'configs.json').read_text())
row = dict(arm=ARM, source_hash=S['source_hash'], case_id=M['case_id'],
           initial_sha256=M['initial_sha256'], candidate_selection='first tuple entry',
           harness='one _run_stage, saved first precision and saved config',
           environment={k: v for k, v in os.environ.items() if k.startswith('GEOSOLVER_ABLATE_')},
           calls={}, lambda_values=[], adaptive_lambda_update_lines=0,
           newton_linear_step_attempts=0, line_search_trial_attempts=0,
           quality_fields_recorded=False)
started = time.monotonic()


def save():
    row['worker_seconds'] = time.monotonic() - started
    temp = RECEIPT.with_suffix('.tmp')
    temp.write_text(json.dumps(row, indent=2) + '\n')
    temp.replace(RECEIPT)


class SmokeWallLimit(BaseException):
    pass


def alarm(*_):
    raise SmokeWallLimit()


signal.signal(signal.SIGALRM, alarm)
signal.setitimer(signal.ITIMER_REAL, 9)
try:
    assert row['environment'] == C['arms'][ARM]
    from mpmath import mp
    from geosolver.runtime.integrity import source_tree_hash, verify_engine_lock
    from geosolver.runtime.ablation import active_ablations
    from geosolver.runtime.deadline import runtime_session
    from geosolver.problem.models import GeometryProblem
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    from geosolver.engine.standard.refinement.mpmath_refiner import MpmathRefiner, _convert_problem_bounds
    from geosolver.engine.standard.precision.type_guards.boundary_float_to_mpf import boundary_float_to_mpf, BoundaryOrigin

    assert source_tree_hash() == S['source_hash']
    assert verify_engine_lock()[0]
    row['active_ablations'] = active_ablations()
    for path, key in [(M['initial_path'], 'initial_sha256'), (M['input_path'], 'input_sha256')]:
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == M[key]
    with Path(M['initial_path']).open('rb') as handle:
        candidates, config = pickle.load(handle)
    candidate = candidates[0]  # Fixed by tuple order, never by numerical performance.
    document = GeometryProblem.model_validate_json(Path(M['input_path']).read_text()).engine_document()
    bundle = load_problem_bundle(document)
    evaluator = build_ir_evaluator(bundle)
    refiner = MpmathRefiner(config)
    bounds = _convert_problem_bounds(bundle)
    dps = int(config.schedule_dps[0])
    row['stage_dps'] = dps
    # Read only source lines in the tracer, never points, residuals or answers.
    refiner_file = Path(sys.modules[MpmathRefiner.__module__].__file__)
    refiner_lines = refiner_file.read_text().splitlines()
    adaptive_lines = {i for i, text in enumerate(refiner_lines, 1)
                      if 'damping = max(damping_min,' in text or 'damping *= damping_scale' in text}
    import mpmath.calculus.optimization as optimization
    opt_file = Path(optimization.__file__)
    opt_lines = opt_file.read_text().splitlines()
    newton_lines = {i for i, text in enumerate(opt_lines, 1) if 's = self.ctx.lu_solve(Jx, fxn)' in text}
    from geosolver.engine.standard.refinement import line_search
    ls_file = Path(line_search.__file__)
    ls_lines = ls_file.read_text().splitlines()
    trial_lines = {i for i, text in enumerate(ls_lines, 1) if 'trial = [value +' in text}
    named = {'_run_stage', 'compute_levenberg_marquardt_step', 'run_line_search',
             '_run_findroot_closure', '_run_rank_aware_findroot', 'findroot',
             '_apply_post_lm_closure_polish', '_direct_accept_candidate'}

    def trace(frame, event, arg):
        name = frame.f_code.co_name
        filename = frame.f_code.co_filename
        if event == 'call':
            if name in named and ('/geosolver/' in filename or filename == str(opt_file)):
                row['calls'][name] = row['calls'].get(name, 0) + 1
                if name == 'compute_levenberg_marquardt_step':
                    value = mp.nstr(frame.f_locals['damping'], 15)
                    if value not in row['lambda_values']:
                        row['lambda_values'].append(value)
                if name == 'findroot':
                    solver = frame.f_locals.get('solver', 'secant')
                    row.setdefault('findroot_requested_solvers', []).append(str(solver))
                save()
            if filename in {str(refiner_file), str(opt_file), str(ls_file)}:
                return trace
            return None
        if event == 'line':
            if filename == str(refiner_file) and frame.f_lineno in adaptive_lines:
                row['adaptive_lambda_update_lines'] += 1
            elif filename == str(opt_file) and name == '__iter__' and frame.f_lineno in newton_lines:
                row['newton_linear_step_attempts'] += 1
            elif filename == str(ls_file) and frame.f_lineno in trial_lines:
                row['line_search_trial_attempts'] += 1
        return trace

    save()
    with mp.workdps(dps):
        point = ([mp.mpf(value) for value in candidate.initial_point_decimal]
                 if candidate.initial_point_decimal and len(candidate.initial_point_decimal) == len(candidate.x_float)
                 else [boundary_float_to_mpf(value, origin=BoundaryOrigin.INITIAL_POINT) for value in candidate.x_float])
        inner_started = time.monotonic()
        deadline = inner_started + C['smoke']['inner_seconds']
        with runtime_session(deadline):
            sys.settrace(trace)
            try:
                refiner._run_stage(bundle=bundle, evaluator=evaluator, start_point=point,
                    bounds=bounds, dps=dps, target_residual=mp.mpf(config.target_for_dps(dps)),
                    preserve_hard_feasibility=bool(candidate.hard_feasible))
            finally:
                sys.settrace(None)
        row['refinement_call_seconds'] = time.monotonic() - inner_started
    row['process_state'] = 'stage_call_returned'
except SmokeWallLimit:
    row['process_state'] = 'worker_wall_limit'
except BaseException as error:
    row['process_state'] = 'exception'
    row['exception_type'] = type(error).__name__
finally:
    sys.settrace(None)
    signal.setitimer(signal.ITIMER_REAL, 0)
    save()
