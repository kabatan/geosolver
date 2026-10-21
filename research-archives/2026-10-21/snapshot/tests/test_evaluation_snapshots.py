"""Artificial fixtures only: never read the held-out GMB comparison inputs."""

from dataclasses import replace

import pytest
from mpmath import mp

from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.evaluation.selection_trace import capture_selection_trace
from geosolver.engine.standard.evaluation.snapshots import (
    evaluation_session,
    numerical_snapshot,
)
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.problem.evaluation_trace import capture_calls


def circle_evaluator(*, extra=()):
    return build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["t"]},
                "construction": [
                    {"name": "O", "expr": "Point(0,0)"},
                    {"name": "omega", "expr": "Circle(O,2)"},
                    {"name": "P", "expr": "PointOnCircle(omega,t)"},
                    {"name": "A", "expr": "Point(-3,0)"},
                    {"name": "B", "expr": "Point(3,0)"},
                    {"name": "Q", "expr": "Intersect(Line(A,B),omega,n=1)"},
                    *extra,
                ],
                "constraints": ["Distance(P,O)-2"],
                "guards": ["t>0"],
                "answer": "Distance(P,Q)",
            }
        )
    )


def test_float_residual_is_numeric_lazy_and_reuses_constructions():
    ev = circle_evaluator()
    assert ev.evaluate_float_residual([0.173]).is_finite
    store = ev.evaluation_store
    ordinary = next(s for k, s in store.snapshots.items() if k[0] == "float")
    assert set(ordinary.completed) == {"O", "omega", "P"}
    assert isinstance(ordinary.completed["P"].x, mp.mpf)
    assert ordinary.precision_bits == 53
    assert ev.evaluate_float_hard_feasibility([0.173], include_margins=False).hard_feasible
    before = store.construction_evaluations
    assert ev.evaluate_guard([0.173])[0]
    assert ev.evaluate_float_residual([0.173]).is_finite
    assert store.construction_evaluations == before
    assert set(ordinary.completed) == {"O", "omega", "P", "A", "B", "Q"}


def test_unneeded_invalid_construction_is_still_a_hard_rejection():
    ev = circle_evaluator(extra=({"name": "bad", "expr": "Circle(O,0)"},))
    assert ev.evaluate_float_residual([0.173]).is_finite
    assert not ev.evaluate_float_hard_feasibility([0.173]).hard_feasible


def test_guard_preparation_is_not_repeated(monkeypatch):
    ev = circle_evaluator()
    from geosolver.engine.standard.evaluation import guard_penalty

    def forbidden(*_args):
        raise AssertionError("guards were compiled during evaluation")

    monkeypatch.setattr(guard_penalty, "compile_guards", forbidden)
    for t in (0.17, 0.28):
        assert ev.evaluate_float_hard_feasibility([t]).hard_feasible
        assert ev.evaluate_guard([t])[0]
    with mp.workdps(120), high_precision_mode():
        assert ev.evaluate_hp_hard_feasibility([mp.mpf("0.17")], precision=120).hard_feasible


def test_cached_constructions_replay_identical_branch_and_call_evidence():
    ev = circle_evaluator()
    with evaluation_session(ev), mp.workdps(120), high_precision_mode():
        snap = numerical_snapshot(
            ev.bundle.spec, ev.bundle.var_names, [mp.mpf("0.17")], ev.bundle.base_context
        )
        with capture_calls() as calls1, capture_selection_trace() as trace1:
            snap.for_expressions(["Distance(P,Q)"])
        before = ev.evaluation_store.construction_evaluations
        with capture_calls() as calls2, capture_selection_trace() as trace2:
            snap.for_expressions(["Distance(P,Q)"])
        assert ev.evaluation_store.construction_evaluations == before
        assert calls1 == calls2 and trace1 == trace2
        assert trace1 and trace1[0].call_site_id.startswith("Q:")


def test_cache_never_merges_close_coordinates_or_precisions():
    ev = circle_evaluator()
    with mp.workdps(180):
        first = mp.mpf("0.17")
        close = first + mp.mpf("1e-150")
    with evaluation_session(ev), high_precision_mode():
        with mp.workdps(80):
            a = numerical_snapshot(
                ev.bundle.spec, ev.bundle.var_names, [first], ev.bundle.base_context
            )
            b = numerical_snapshot(
                ev.bundle.spec, ev.bundle.var_names, [close], ev.bundle.base_context
            )
            assert a is not b
        with mp.workdps(180):
            c = numerical_snapshot(
                ev.bundle.spec, ev.bundle.var_names, [first], ev.bundle.base_context
            )
            assert c is not a
            with pytest.raises(RuntimeError, match="different precision"):
                a.for_expressions(["P.x"])


def test_hp_equation_slices_can_share_a_construction_plan():
    ev = circle_evaluator()
    spec = replace(ev.bundle.spec, constraints=["P.x"], v=[0])
    child = build_ir_evaluator(
        replace(ev.bundle, spec=spec, targets=(0,)), evaluation_store=ev.evaluation_store
    )
    with mp.workdps(120), high_precision_mode():
        point = [mp.mpf("0.17")]
        assert ev.evaluate_hp_residual(point, precision=120).is_finite
        before = ev.evaluation_store.construction_evaluations
        assert child.evaluate_hp_residual(point, precision=120).is_finite
        assert ev.evaluation_store.construction_evaluations == before


def test_guard_cache_replays_inline_selector_evidence():
    ev = circle_evaluator()
    spec = replace(ev.bundle.spec, guards=["Intersect(Line(A,B),omega,n=1).x<0"])
    ev = build_ir_evaluator(replace(ev.bundle, spec=spec))
    with capture_calls() as calls1, capture_selection_trace() as trace1:
        first = ev.evaluate_guard([0.173])
    with capture_calls() as calls2, capture_selection_trace() as trace2:
        second = ev.evaluate_guard([0.173])
    assert first == second
    assert trace1 and trace1 == trace2
    assert calls1 == calls2


def test_failed_construction_is_not_retried_at_identical_coordinates():
    ev = circle_evaluator(extra=({"name": "bad", "expr": "Circle(O,0)"},))
    assert not ev.evaluate_float_hard_feasibility([0.17]).hard_feasible
    before = ev.evaluation_store.construction_evaluations
    assert not ev.evaluate_float_hard_feasibility([0.17]).hard_feasible
    assert ev.evaluation_store.construction_evaluations == before


def test_snapshot_capacity_is_bounded_and_eviction_preserves_values():
    ev = circle_evaluator()
    ev.evaluation_store.capacity = 2
    first = ev.evaluate_float_residual([0.173]).residual_vector
    for t in (0.19, 0.21, 0.23):
        ev.evaluate_float_residual([t])
    assert len(ev.evaluation_store.snapshots) == 2
    assert ev.evaluate_float_residual([0.173]).residual_vector == first


def test_constants_are_reused_at_different_points_but_not_across_precisions():
    ev = circle_evaluator()
    ev.evaluate_float_residual([0.173])
    before = ev.evaluation_store.construction_evaluations
    ev.evaluate_float_residual([0.271])
    # O and omega are constant; P depends on the coordinate.
    assert ev.evaluation_store.construction_evaluations - before == 1
    with mp.workprec(53), high_precision_mode(), evaluation_session(ev):
        first = numerical_snapshot(
            ev.bundle.spec, ev.bundle.var_names, [mp.mpf("0.173")], ev.bundle.base_context
        )
        before = ev.evaluation_store.construction_evaluations
        first.for_expressions(["P.x"])
        # Same bits, but HP and float arithmetic have separate constant caches.
        assert ev.evaluation_store.construction_evaluations - before == 3
    with mp.workdps(120), high_precision_mode():
        before = ev.evaluation_store.construction_evaluations
        assert ev.evaluate_hp_residual([mp.mpf("0.173")], precision=120).is_finite
        assert ev.evaluation_store.construction_evaluations - before == 3
        before = ev.evaluation_store.construction_evaluations
        assert ev.evaluate_hp_residual([mp.mpf("0.271")], precision=120).is_finite
        assert ev.evaluation_store.construction_evaluations - before == 1


def test_constant_cache_replays_complete_evidence_at_new_coordinates():
    ev = circle_evaluator()
    with mp.workdps(120), high_precision_mode(), evaluation_session(ev):

        def sample(t):
            snap = numerical_snapshot(
                ev.bundle.spec, ev.bundle.var_names, [mp.mpf(t)], ev.bundle.base_context
            )
            with capture_calls() as calls, capture_selection_trace() as trace:
                snap.for_expressions(["Q.x"])
            return snap.context["Q"], calls, trace

        value1, calls1, trace1 = sample("0.173")
        before = ev.evaluation_store.construction_evaluations
        value2, calls2, trace2 = sample("0.271")
        assert ev.evaluation_store.construction_evaluations == before
        assert value1 == value2 and calls1 == calls2 and trace1 == trace2
        assert trace1


def test_cached_failure_does_not_accumulate_tracebacks():
    ev = circle_evaluator(extra=({"name": "bad", "expr": "Circle(O,0)"},))
    with mp.workdps(80), evaluation_session(ev):
        snap = numerical_snapshot(
            ev.bundle.spec, ev.bundle.var_names, [mp.mpf("0.173")], ev.bundle.base_context
        )
        lengths = []
        for _ in range(12):
            try:
                snap.for_expressions(["bad"])
            except Exception as error:
                length, traceback = 0, error.__traceback__
                while traceback is not None:
                    length += 1
                    traceback = traceback.tb_next
                lengths.append(length)
        assert len(lengths) == 12 and len(set(lengths)) == 1
