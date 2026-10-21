"""Generic triangular scale families exercise exact coordinate reconstruction."""

import itertools
import re

import pytest
from mpmath import mp

from geosolver import GeometryProblem
from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.search import algebraic_branches, scale_chart
from geosolver.problem.adapter import to_engine_document
from geosolver.runtime.deadline import runtime_session
from geosolver.runtime.symbolic import OptionalSymbolicTimeout


def _family(names=("s", "a", "b", "c"), unit=1):
    replacement = dict(zip(("s", "a", "b", "c"), names, strict=True))

    def rename(source):
        return re.sub(r"\b(s|a|b|c)\b", lambda m: replacement[m[0]], source)

    equalities = [("a+b", "3*s"), ("a*b", "s*s"), ("c", "a+2*b")]
    problem = GeometryProblem.model_validate(
        {
            "id": "generated-triangular-scale",
            "variables": list(names),
            "constructions": [],
            "conditions": [
                {
                    "left": rename(f"{unit}*({left})"),
                    "operator": "=",
                    "right": rename(f"{unit}*({right})"),
                }
                for left, right in equalities
            ]
            + [{"left": names[0], "operator": ">", "right": "0"}],
            "target": rename("a/s"),
        }
    )
    return load_problem_bundle(to_engine_document(problem))


@pytest.mark.parametrize("names", [("s", "a", "b", "c"), ("scale", "u", "v", "w")])
@pytest.mark.parametrize("unit", [1, 11])
@pytest.mark.parametrize("order", list(itertools.permutations(range(3))))
def test_triangular_reconstruction_preserves_all_irrational_scale_shapes(names, unit, order):
    bundle = _family(names, unit)
    active = [names[i + 1] for i in order]
    data = algebraic_branches.discover_polynomial_branches(
        {
            "variables": active,
            "construction": [(names[0], "1")],
            "constraints": bundle.spec.constraints,
            "targets": bundle.targets,
            "guards": bundle.spec.guards,
            "report_work": True,
        }
    )
    assert data["work_telemetry"]["stop_reason"] is None
    branches = data["result"]
    assert branches is not None and len(branches["points"]) == 2
    evaluator = build_ir_evaluator(bundle)
    with mp.workdps(180):
        answers = []
        for point in branches["points"]:
            values = {names[0]: mp.mpf(7)} | {
                name: 7 * mp.mpf(value) for name, value in zip(active, point, strict=True)
            }
            result = verify_final_candidate(
                evaluator=evaluator, values=tuple(values[name] for name in names)
            )
            assert result.verified
            answers.append(result.answer_hp)
        assert sorted(answers) == pytest.approx(
            [(3 - mp.sqrt(5)) / 2, (3 + mp.sqrt(5)) / 2], rel=mp.mpf("1e-150")
        )


def test_inner_timeout_retains_interrupted_phase_and_declines(monkeypatch):
    from geosolver.engine.standard.search.cartesian_polynomials import CartesianPolynomials

    def interrupt(*args):
        raise algebraic_branches.AlgebraicWorkLimit("generated interruption")

    monkeypatch.setattr(CartesianPolynomials, "scalar", interrupt)
    data = algebraic_branches.discover_polynomial_branches(
        {
            "variables": ["a"],
            "construction": [],
            "constraints": ["a"],
            "targets": ["1"],
            "report_work": True,
        }
    )
    assert data["result"] is None
    work = data["work_telemetry"]
    assert work["stop_reason"] == "inner_cpu_timeout"
    assert work["interrupted_phase"] == "polynomial_conversion"
    assert all(v >= 0 for values in work["phases"].values() for v in values.values())


def test_outer_timeout_keeps_fallback_and_has_distinct_counter(monkeypatch):
    bundle = _family()

    def interrupt(*args, **kwargs):
        raise OptionalSymbolicTimeout("generated outer interruption")

    monkeypatch.setattr(scale_chart, "request", interrupt)
    with runtime_session(None) as telemetry:
        assert (
            scale_chart.search_positive_scale_chart(
                bundle=bundle, evaluator=build_ir_evaluator(bundle)
            )
            is None
        )
    assert telemetry.counters["positive_scale_chart_outer_wall_timeout"] == 1


def test_inner_timeout_counter_includes_phase_without_admitting_candidates(monkeypatch):
    bundle = _family()
    monkeypatch.setattr(
        scale_chart,
        "request",
        lambda *args, **kwargs: {
            "result": None,
            "work_telemetry": {
                "stop_reason": "inner_cpu_timeout",
                "interrupted_phase": "branch_boxes",
                "phases": {"branch_boxes": {"wall_seconds": 0.1, "cpu_seconds": 0.09}},
            },
        },
    )
    with runtime_session(None) as telemetry:
        assert (
            scale_chart.search_positive_scale_chart(
                bundle=bundle, evaluator=build_ir_evaluator(bundle)
            )
            is None
        )
    assert telemetry.counters["positive_scale_chart_stop_inner_cpu_timeout"] == 1
    assert telemetry.counters["positive_scale_chart_interrupted_branch_boxes"] == 1
    assert telemetry.counters["positive_scale_chart_branch_boxes_wall_microseconds"] == 100000
    assert telemetry.counters["positive_scale_chart_branch_boxes_cpu_microseconds"] == 90000


def test_cpu_work_budget_does_not_charge_scheduler_or_idle_time():
    import signal
    import time

    if not hasattr(signal, "ITIMER_PROF"):
        pytest.skip("process CPU timer unavailable")
    with algebraic_branches._bounded_symbolic_work(0.02) as supported:
        assert supported
        time.sleep(0.06)
    started = time.process_time()
    with (
        pytest.raises(algebraic_branches.AlgebraicWorkLimit),
        algebraic_branches._bounded_symbolic_work(0.02),
    ):
        while time.process_time() - started < 1:
            pass
    assert time.process_time() - started < 0.2


def test_cpu_work_timer_leaves_an_independent_wall_timer_active():
    import signal
    import time

    if not hasattr(signal, "ITIMER_PROF"):
        pytest.skip("process CPU timer unavailable")
    alarms = []
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    try:
        signal.signal(signal.SIGALRM, lambda *_: alarms.append(True))
        signal.setitimer(signal.ITIMER_REAL, 0.02)
        with algebraic_branches._bounded_symbolic_work(0.5):
            time.sleep(0.06)
        assert alarms == [True]
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        signal.setitimer(signal.ITIMER_REAL, *previous_timer)


def test_optional_work_does_not_replace_an_enclosing_cpu_timer():
    import signal

    if not hasattr(signal, "ITIMER_PROF"):
        pytest.skip("process CPU timer unavailable")
    previous_handler = signal.getsignal(signal.SIGPROF)
    previous_timer = signal.getitimer(signal.ITIMER_PROF)

    def handler(*_):
        pass

    try:
        signal.signal(signal.SIGPROF, handler)
        signal.setitimer(signal.ITIMER_PROF, 1)
        with algebraic_branches._bounded_symbolic_work(0.5) as supported:
            assert not supported
            assert signal.getsignal(signal.SIGPROF) is handler
            remaining = signal.getitimer(signal.ITIMER_PROF)[0]
            assert 0 < remaining <= 1.01
    finally:
        signal.setitimer(signal.ITIMER_PROF, 0)
        signal.signal(signal.SIGPROF, previous_handler)
        signal.setitimer(signal.ITIMER_PROF, *previous_timer)
