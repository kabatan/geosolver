"""Q41 stage-2 measurement; never modifies or imports the shared solver tree."""
from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
import signal
import time
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
CLEAN = Path('/tmp/q41-clean')
RAW = Path('/tmp/q41-stage2')
FROZEN = '60db4b679b04167175c51c479c87c22fa663fda0'
PREDICTION_COMMIT = '795565c2'
PYTHON = '/home/kabatan/work/solver/.venv/bin/python'
ARMS = tuple(json.loads((OUT / 'rules.json').read_text())['arms'])
SEEDS = (410251, 410252, 410253)


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def json_value(value):
    if hasattr(value, '_mpf_'):
        from mpmath import mp
        return mp.nstr(value, 90)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): json_value(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_value(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if hasattr(value, 'item'):
        return json_value(value.item())
    return value


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f'.tmp-{os.getpid()}')
    tmp.write_text(json.dumps(json_value(value), ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)


def append(path, value):
    with Path(path).open('a') as f:
        f.write(json.dumps(json_value(value), ensure_ascii=False, separators=(',', ':')) + '\n')
        f.flush()


class MeasurementDeadline(BaseException):
    pass


@contextlib.contextmanager
def limit(seconds):
    def expire(_signum, _frame):
        raise MeasurementDeadline()
    previous = signal.signal(signal.SIGALRM, expire)
    old_timer = signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
        if old_timer[0]:
            signal.setitimer(signal.ITIMER_REAL, *old_timer)


def assert_identity():
    import geosolver
    from geosolver.runtime.integrity import source_tree_hash
    assert Path(geosolver.__file__).resolve().is_relative_to(CLEAN / 'src')
    lock = json.loads((OUT / 'prediction.lock.json').read_text())
    for name, expected in lock['files'].items():
        assert digest(OUT / name) == expected, name
    source_hash = source_tree_hash()
    assert source_hash == json.loads((CLEAN / 'src/geosolver/engine-lock.json').read_text())['source_tree_hash']
    assert source_hash.startswith('sha256:d8fd9bb8')
    return source_hash


def load_case(cid, arm):
    from geosolver.problem.models import GeometryProblem
    from geosolver.problem.validation import validate
    from geosolver.problem.ir.parser import load_ir
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    problem = GeometryProblem.model_validate_json((OUT / 'dsl' / cid / f'{arm}.json').read_text())
    validation = validate(problem)
    if not validation.valid:
        raise ValueError(str(validation.issues))
    document = problem.engine_document()
    original_spec = load_ir(document)
    bundle = load_problem_bundle(document)
    # Check original DSL equalities, without added consequence rows, rescaling,
    # smoothing, exact-answer equations, or any position correction.
    targets = tuple(original_spec.v or [0] * len(original_spec.constraints))
    judge_spec = replace(bundle.spec, constraints=original_spec.constraints,
                         v=list(targets), m=None)
    judge_bundle = replace(bundle, spec=judge_spec, targets=targets)
    return problem, bundle, build_ir_evaluator(bundle), build_ir_evaluator(judge_bundle)


def check_point(evaluator, coordinates, *, budget=1.0):
    """Fixed common criterion: binary64, then 17 decimal digits at 80 dps."""
    from mpmath import mp
    from geosolver.engine.standard.evaluation.snapshots import numerical_snapshot
    from geosolver.problem.ir.compiler import safe_eval_expr_hp
    from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
    result = {'success': False, 'reason': 'evaluation_exception', 'float': None, 'hp': None}
    started = time.monotonic()
    try:
        with limit(budget):
            x = tuple(float(v) for v in coordinates)
            decimal = tuple(format(v, '.17g') for v in x)
            result['evaluated_coordinates_decimal17'] = decimal
            f = evaluator.evaluate_float_residual(x)
            g, violations = evaluator.evaluate_guard(x)
            hard = evaluator.evaluate_float_hard_feasibility(x)
            b = evaluator.bundle
            with mp.workprec(53):
                snapshot = numerical_snapshot(b.spec, b.var_names, x, b.base_context, arithmetic='float')
                context = snapshot.for_expressions([b.spec.answer_expr])
                target = float(safe_eval_expr_hp(b.spec.answer_expr, context))
            ok_float = f.is_finite and f.residual_norm_float <= 1e-8 and g and hard.hard_feasible and math.isfinite(target)
            result['float'] = {'norm': f.residual_norm_float, 'residuals': f.residual_vector,
                               'guard_ok': g, 'guard_violations': violations,
                               'hard_ok': hard.hard_feasible, 'hard_tags': hard.failure_tags,
                               'target_finite': math.isfinite(target)}
            if not ok_float:
                result['reason'] = 'float_rejected'
                return result
            with mp.workdps(80), high_precision_mode():
                y = tuple(mp.mpf(v) for v in decimal)
                h = evaluator.evaluate_hp_residual(y, precision=80)
                hg, hv = evaluator.evaluate_guard(y)
                hh = evaluator.evaluate_hp_hard_feasibility(y, precision=80)
                a = evaluator.evaluate_answer_hp(y, precision=80)
                ok_hp = bool(h.is_finite and h.residual_norm_hp <= mp.mpf('1e-8')
                             and hg and hh.hard_feasible and a.answer_hp is not None
                             and mp.isfinite(a.answer_hp))
                result['hp'] = {'norm': str(h.residual_norm_hp),
                                'guard_ok': hg, 'guard_violations': hv,
                                'hard_ok': hh.hard_feasible, 'hard_tags': hh.failure_tags,
                                'target_finite': a.answer_hp is not None and bool(mp.isfinite(a.answer_hp))}
            result.update(success=ok_hp, reason='pass' if ok_hp else 'hp_rejected')
    except MeasurementDeadline:
        result['reason'] = 'verification_timeout'
    except Exception as error:
        result['error'] = f'{type(error).__name__}: {error}'
    finally:
        result['seconds'] = time.monotonic() - started
    return result


def order(cid, seed, arm, k=None):
    text = f'Q41/order/v1|{cid}|{seed}|{arm}'
    if k is not None:
        text += f'|{k}'
    return hashlib.sha256(text.encode()).hexdigest()


def environment():
    env = os.environ.copy()
    env.update(PYTHONPATH=f'{CLEAN / "src"}:{OUT}', PYTHONDONTWRITEBYTECODE='1',
               PYTHONNOUSERSITE='1', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
               MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1', TMPDIR=str(RAW / 'tmp'))
    return env
