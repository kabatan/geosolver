"""High-precision proposals must not trap lower-precision Newton damping."""

from mpmath import mp

from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.refinement import mpmath_refiner as implementation


def evaluator():
    return build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["u", "v"]},
                "constraints": ["u*u-2", "v*v-3"],
                "answer": "u+v",
            }
        )
    )


def closure(ev, point, **kwargs):
    return implementation._run_findroot_closure(
        evaluator=ev,
        start_point=point,
        bounds=((None, None), (None, None)),
        dps=120,
        target_residual=mp.mpf("1e-80"),
        max_steps=12,
        **kwargs,
    )


def test_original_target_is_checked_before_newton_and_preserves_all_input_bits(monkeypatch):
    ev = evaluator()
    with mp.workdps(240):
        point = [mp.sqrt(2), mp.sqrt(3)]
        original_bits = [x._mpf_ for x in point]

    def forbidden(*args, **kwargs):
        raise AssertionError("an already certified original residual needs no Newton iteration")

    monkeypatch.setattr(mp, "findroot", forbidden)
    result = closure(ev, point)
    assert result is not None
    assert [x._mpf_ for x in result[0]] == original_bits
    assert result[1] <= mp.mpf("1e-80")


def test_unfinished_start_is_rounded_to_newtons_working_precision(monkeypatch):
    ev = evaluator()
    with mp.workdps(240):
        point = [mp.sqrt(2) + mp.mpf("1e-40"), mp.sqrt(3)]
    original = mp.findroot
    calls = []

    def inspect_precision(function, initial, **kwargs):
        calls.append(tuple(x._mpf_[3] for x in initial))
        assert all(x._mpf_[3] <= mp.prec for x in initial)
        return original(function, initial, **kwargs)

    monkeypatch.setattr(mp, "findroot", inspect_precision)
    result = closure(ev, point, solver_tolerance=mp.mpf("1e-160"))
    assert calls and result is not None
    assert result[1] <= mp.mpf("1e-80")


def test_optimizer_residual_cannot_bypass_original_full_residual_certification(monkeypatch):
    ev = evaluator()
    with mp.workdps(240):
        point = [mp.mpf(2), mp.mpf(3)]

    def unchanged(function, initial, **kwargs):
        return mp.matrix(initial)

    monkeypatch.setattr(mp, "findroot", unchanged)
    assert closure(ev, point, residual_fn=lambda p, dps: [mp.mpf(0), mp.mpf(0)]) is None
