from types import SimpleNamespace

from mpmath import mp

# Import the public interpreter first; the current standard-engine package
# exposes eager compatibility imports that otherwise make direct low-level
# module imports order-dependent during test collection.
from geosolver.engine.standard.refinement.mpmath_refiner import (
    IntegerConstraintClosure,
    _exact_answer_from_integer_closures,
    _extract_isinteger_inner_expression,
)
from geosolver.geometry.mp.mp_number_constraints import mp_is_prime


def _bundle(answer_expr: str) -> SimpleNamespace:
    return SimpleNamespace(
        var_names=("u", "v"),
        spec=SimpleNamespace(answer_expr=answer_expr),
    )


def _closures() -> tuple[IntegerConstraintClosure, ...]:
    return (
        IntegerConstraintClosure(
            constraint_index=0,
            inner_expression="u",
            target_integer=mp.mpf(11),
        ),
        IntegerConstraintClosure(
            constraint_index=1,
            inner_expression="v",
            target_integer=mp.mpf(10),
        ),
    )


def test_integer_closure_supplies_exact_arithmetic_answer() -> None:
    answer = _exact_answer_from_integer_closures(
        bundle=_bundle("u + v"),
        closures=_closures(),
    )

    assert answer == 21


def test_integer_closure_keeps_rational_answer_at_high_precision() -> None:
    answer = _exact_answer_from_integer_closures(
        bundle=_bundle("u / 3"),
        closures=_closures(),
    )

    with mp.workdps(100):
        assert abs(answer - mp.mpf(11) / 3) < mp.mpf("1e-90")


def test_integer_closure_does_not_hint_geometry_expression() -> None:
    answer = _exact_answer_from_integer_closures(
        bundle=_bundle("Distance(Point(u, v), Point(0, 0))"),
        closures=_closures(),
    )

    assert answer is None


def test_prime_constraints_use_integer_projection_and_unbounded_exact_test() -> None:
    assert _extract_isinteger_inner_expression("IsPrime(n)") == "n"
    with mp.workdps(180):
        assert mp_is_prime(mp.mpf(1009)) == 0
        assert mp_is_prime(mp.mpf(1009) + mp.mpf("1e-80")) != 0
        assert mp_is_prime(mp.mpf(1001)) != 0
