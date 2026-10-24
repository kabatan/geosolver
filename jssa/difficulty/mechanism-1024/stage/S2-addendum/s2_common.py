"""One registered refinement or PSLQ condition; never search or retry."""
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import time
import traceback
from datetime import datetime, timezone

OUT = Path(__file__).resolve().parent
MAN = json.loads((OUT / 'pre-run-hashes.json').read_text())
sys.dont_write_bytecode = True
sys.path.insert(0, MAN['frozen_source'])


def now():
    return datetime.now(timezone.utc).isoformat()


def save(path, value):
    text = json.dumps(value, ensure_ascii=False, indent=2, default=str, allow_nan=False) + '\n'
    assert len(text.encode()) < 3_000_000
    path.write_text(text)


def canonical(cs):
    from functools import reduce
    from math import gcd
    cs = [int(c) for c in cs]
    while cs and cs[0] == 0:
        cs.pop(0)
    g = reduce(gcd, cs, 0)
    cs = [c // abs(g) for c in cs]
    return cs if cs[0] > 0 else [-c for c in cs]


def references(item):
    """Independent existing exact answer; never supplies a refinement start."""
    import sympy as sp
    from mpmath import mp
    x = sp.Symbol('x')
    polys = [canonical(p) for p in item['reference_polynomials']]
    with mp.workdps(700):
        if 'reference_expression' in item:
            expr = sp.sympify(item['reference_expression'])
            assert canonical(sp.Poly(sp.minimal_polynomial(expr, x), x).all_coeffs()) == polys[0]
            return mp.mpf(str(sp.N(expr, 700))), polys[0], str(expr)
        saved = mp.mpf(item['saved_answer'])
        choices = []
        for cs in polys:
            for ri, root in enumerate(sp.real_roots(sp.Poly.from_list(cs, x))):
                val = mp.mpf(str(sp.N(root, 700)))
                choices.append((abs(val - saved), val, cs, f'real_root_index={ri}; {root}'))
        _, val, cs, desc = min(choices, key=lambda c: c[0])
        return val, cs, desc


def refine(item):
    from functools import partial
    from mpmath import mp
    from geosolver.problem.models import GeometryProblem
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    from geosolver.engine.standard.refinement.mpmath_refiner import (
        MpmathRefiner, _run_findroot_closure, _convert_problem_bounds)
    from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
    bundle = load_problem_bundle(GeometryProblem.model_validate(item['dsl']).engine_document())
    evaluator = build_ir_evaluator(bundle)
    refiner = MpmathRefiner()
    deadline = time.monotonic() + 180
    with mp.workdps(620), high_precision_mode():
        point = [mp.mpf(s) for s in item['coordinates']]
        t = time.monotonic()
        if point:
            closed = _run_findroot_closure(
                evaluator=evaluator, start_point=point, bounds=_convert_problem_bounds(bundle),
                dps=620, target_residual=mp.mpf('1e-580'), solver_tolerance=mp.mpf('1e-1160'),
                max_steps=1240, deadline_monotonic=deadline,
                residual_fn=partial(refiner._residual_vector_for_stage, bundle, evaluator, smooth_zero_constraints=True),
                one_sided_at_cusp=any('Angle(' in str(c) for c in bundle.spec.constraints))
            if closed is None:
                return dict(status='refinement_unavailable', achieved_digits=0, refinement_seconds=time.monotonic()-t,
                            reason='single frozen closure did not certify target residual')
            point, residual = closed
        else:
            ev = evaluator.evaluate_hp_residual(point, precision=620)
            residual = mp.sqrt(mp.fsum(v*v for v in ev.residual_vector))
        hard = evaluator.evaluate_hp_hard_feasibility(point, precision=620, include_margins=True)
        ev = evaluator.evaluate_answer_hp(point, precision=620)
        duration = time.monotonic() - t
        result = dict(refinement_seconds=duration, original_residual_norm=mp.nstr(residual, 35),
                      hard_feasible=bool(hard.hard_feasible), hard_failure_tags=list(hard.hard_failure_tags) if hasattr(hard, 'hard_failure_tags') else [],
                      evaluation_status=ev.evaluation_status.value,
                      coordinates=[mp.nstr(v, 620) for v in point],
                      method='frozen_findroot_closure' if point else 'frozen_DSL_direct_evaluation')
        if not hard.hard_feasible or ev.answer_hp is None or not mp.isfinite(ev.answer_hp) or residual > mp.mpf('1e-580'):
            return result | dict(status='refinement_unavailable', achieved_digits=0, reason='hard/residual/answer gate failed')
        value_text = mp.nstr(ev.answer_hp, 620)
    ref, truth, description = references(item)
    with mp.workdps(700):
        value = mp.mpf(value_text)
        error = abs(value-ref) / max(1, abs(ref))
        digits = 620 if error == 0 else min(620, max(0, int(mp.floor(-mp.log10(error)))))
        result.update(status='ok', value=value_text, reference_value=mp.nstr(ref, 700),
                      reference_description=description, reference_source=item['reference_source'],
                      true_polynomial=truth, true_max_coefficient=max(abs(c) for c in truth),
                      relative_error=mp.nstr(error, 45), achieved_digits=digits)
    return result


def identify(item, condition):
    from mpmath import mp
    from pslq_wrapper import identify as pslq
    refined = json.loads((OUT / 'raw' / item['key'] / 'refined.json').read_text())
    arm, arg = condition.split('_')
    achieved = refined.get('achieved_digits', 0)
    digits = int(arg) if arm == 'a' else achieved
    bound = 10**8 if arm == 'a' else int(arg)
    base = dict(condition=condition, arm=arm, digits=digits, max_coeff=bound, achieved_digits=achieved,
                true_polynomial=refined.get('true_polynomial'), true_max_coefficient=refined.get('true_max_coefficient'))
    if achieved < digits or digits == 0 or refined['status'] != 'ok':
        return base | dict(outcome='到達不可', seconds=None, polynomial=None,
                           missing_reason=refined.get('exception', ''), reason=refined.get('reason', refined['status']))
    with mp.workdps(700):
        input_text = mp.nstr(mp.mpf(refined['value']), digits)
        input_error = abs(mp.mpf(input_text)-mp.mpf(refined['reference_value'])) / max(1, abs(mp.mpf(refined['reference_value'])))
    with mp.workdps(digits+40):
        value = mp.mpf(input_text)
        start = time.monotonic()
        cs = pslq(value, digits, bound)
        elapsed = time.monotonic() - start
    outcome = '棄却' if cs is None else ('正しい式' if canonical(cs) == refined['true_polynomial'] else '誤った式')
    return base | dict(outcome=outcome, seconds=elapsed, polynomial=cs, input_value=input_text,
                       rounded_input_relative_error=mp.nstr(input_error, 30),
                       returned_max_coefficient=None if cs is None else max(abs(c) for c in cs),
                       returned_coeff_exceeds_bound=False if cs is None else max(abs(c) for c in cs) > bound,
                       bound_strictly_exceeds_truth=bound > refined['true_max_coefficient'])


if __name__ == '__main__':
    phase, key, cpu = sys.argv[1:4]
    os.sched_setaffinity(0, {int(cpu)})
    resource.setrlimit(resource.RLIMIT_AS, (3 << 30, 3 << 30))
    resource.setrlimit(resource.RLIMIT_CPU, (180, 181))
    from geosolver.runtime.integrity import source_tree_hash
    assert source_tree_hash() == MAN['source_hash']
    path = OUT / 'inputs' / (key + '.json')
    assert hashlib.sha256(path.read_bytes()).hexdigest() == MAN['files'][str(path)]
    item = json.loads(path.read_text())
    folder = OUT / 'raw' / key
    folder.mkdir(parents=True, exist_ok=True)
    name = 'refined' if phase == 'refine' else sys.argv[4]
    # Exclusive attempt receipt prevents both accidental retries and overwrites.
    with (folder / (name + '.started.json')).open('x') as f:
        json.dump(dict(utc=now(), pid=os.getpid(), cpu=int(cpu), loadavg=os.getloadavg(), phase=phase), f)
    start = time.monotonic()
    result = dict(key=key, phase=phase, started_utc=now(), cpu=int(cpu), loadavg_start=os.getloadavg())
    try:
        result.update(refine(item) if phase == 'refine' else identify(item, name))
    except Exception as e:
        result.update(status='error', outcome='欠測', achieved_digits=0, exception=repr(e), traceback=traceback.format_exc())
    result.update(wall_seconds=time.monotonic()-start, finished_utc=now(), loadavg_end=os.getloadavg(),
                  max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, source_hash=source_tree_hash())
    save(folder / (name + '.json'), result)
