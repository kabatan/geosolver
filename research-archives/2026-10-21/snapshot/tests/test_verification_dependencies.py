from mpmath import mp

from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.evaluation.verification_domains import DomainVerifier
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle


def evaluator(extra=()):
    return build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x", "y", "z"]},
                "construction": [
                    {"name": "O", "expr": "Point(0,0)"},
                    {"name": "P", "expr": "Point(x,0)"},
                    {"name": "Q", "expr": "Point(y,0)"},
                    {"name": "R", "expr": "Midpoint(P,Q)"},
                    *extra,
                ],
                "constraints": ["x-2", "y-3", "z-4"],
                "guards": ["x>0", "y>0", "z>0"],
                "answer": "Distance(O,P)",
            }
        )
    )


def test_coordinate_dependencies_include_transitive_construction_leaves():
    plan = evaluator().evaluation_store.plan
    assert plan.variable_dependencies(("Distance(O,P)",)) == frozenset({0})
    assert plan.variable_dependencies(("Distance(O,R)",)) == frozenset({0, 1})
    assert plan.variable_dependencies(("Distance(O,R)+z",)) == frozenset({0, 1, 2})
    assert plan.variable_dependencies(("Distance(O,O)",)) == frozenset()


def test_independent_coordinates_need_no_finite_difference(monkeypatch):
    from geosolver.engine.standard.evaluation import verification_domains

    differentiate = verification_domains.differentiate
    columns = []

    def recorded(function, point, index, *args, **kwargs):
        columns.append(index)
        return differentiate(function, point, index, *args, **kwargs)

    monkeypatch.setattr(verification_domains, "differentiate", recorded)
    with mp.workdps(120), high_precision_mode():
        point = tuple(map(mp.mpf, (2, 3, 4)))
        error = mp.mpf("1e-30")
        domain = DomainVerifier(evaluator(), point, (error,) * 3, (mp.mpf(10),) * 3, 120)
        value, uncertainty = domain.measure(domain.scalar("Distance(O,P)"), "distance")
        assert value == 2
        assert error <= uncertainty < 2 * error
        assert columns == [0]


def test_scalar_slice_keeps_unrelated_construction_out_of_difference_evaluations():
    ev = evaluator()
    with mp.workdps(120), high_precision_mode():
        point = tuple(map(mp.mpf, (2, 3, 4)))
        domain = DomainVerifier(ev, point, (mp.mpf("1e-30"),) * 3, (mp.mpf(10),) * 3, 120)
        value, calls, trace, margins = domain.expression_snapshot(point, "Distance(O,P)")
        assert value == 2 and not trace
        snapshots = tuple(ev.evaluation_store.snapshots.values())
        assert len(snapshots) == 1
        assert set(snapshots[0].completed) == {"O", "P"}


def test_final_verification_still_rejects_unrelated_invalid_construction():
    ev = evaluator(extra=({"name": "bad", "expr": "Circle(O,0)"},))
    with mp.workdps(180):
        result = verify_final_candidate(evaluator=ev, values=tuple(map(mp.mpf, (2, 3, 4))))
    assert not result.verified
