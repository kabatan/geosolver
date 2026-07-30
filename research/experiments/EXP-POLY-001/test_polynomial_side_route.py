from __future__ import annotations

import unittest

from polynomial_side_route import (
    PolynomialLimits,
    allocate_symbolic_portfolio,
    detect_polynomial_plan,
    run_symbolic_side_route,
)


def problem(constraints, variables=("x", "y"), construction=()):
    return {
        "task": "solve",
        "variables": {"names": list(variables)},
        "construction": list(construction),
        "constraints": list(constraints),
        "guards": [],
    }


POLYNOMIAL = problem(
    ({"def": "x**2", "value": 1}, {"def": "y", "value": "x"})
)


class PolynomialSideRouteTests(unittest.TestCase):
    def test_strict_polynomial_detection(self):
        plan = detect_polynomial_plan(POLYNOMIAL)
        self.assertTrue(plan.applicable)
        self.assertEqual(plan.maximum_total_degree, 2)
        self.assertEqual(plan.total_terms, 4)

    def test_nonpolynomial_opaque_and_branch_fall_back(self):
        nonpoly = problem(({"def": "sin(x)", "value": 0}, {"def": "y", "value": 0}))
        opaque = problem(
            ({"def": "A", "value": 0}, {"def": "y", "value": 0}),
            construction=({"name": "A", "expr": "Point(x, 0)"},),
        )
        branch = problem(({"def": "x if x > 0 else -x", "value": 1}, {"def": "y", "value": 0}))
        for formulation in (nonpoly, opaque, branch):
            self.assertFalse(detect_polynomial_plan(formulation).applicable)

    def test_float_literal_is_rejected_but_exact_integer_division_is_allowed(self):
        floating = problem(({"def": "x + 0.5", "value": 1}, {"def": "y", "value": 0}))
        rational = problem(({"def": "x / 2", "value": 1}, {"def": "y", "value": "x"}))
        self.assertEqual(detect_polynomial_plan(floating).reason, "noninteger_literal")
        self.assertTrue(detect_polynomial_plan(rational).applicable)

    def test_degree_dimension_and_coefficient_caps(self):
        high_degree = problem(({"def": "x**5", "value": 0}, {"def": "y", "value": 0}))
        high_dimension = problem(
            tuple({"def": name, "value": 0} for name in ("a", "b", "c", "d")),
            variables=("a", "b", "c", "d"),
        )
        large_coefficient = problem(
            ({"def": f"{1 << 80}*x", "value": 1}, {"def": "y", "value": 0})
        )
        self.assertEqual(detect_polynomial_plan(high_degree).reason, "degree_cap")
        self.assertEqual(detect_polynomial_plan(high_dimension).reason, "dimension_cap")
        self.assertEqual(detect_polynomial_plan(large_coefficient).reason, "coefficient_bits_cap")

    def test_term_cap_falls_back(self):
        monomials = (
            "1", "x", "y", "z", "x**2", "x*y", "x*z", "y**2", "y*z", "z**2",
            "x**3", "x**2*y", "x**2*z", "x*y**2", "x*y*z", "x*z**2", "y**3",
        )
        too_many_terms = problem(
            (
                {"def": "+".join(monomials), "value": 0},
                {"def": "y", "value": 0},
                {"def": "z", "value": 0},
            ),
            variables=("x", "y", "z"),
        )
        self.assertEqual(
            detect_polynomial_plan(too_many_terms).reason,
            "terms_per_equation_cap",
        )

    def test_baseline_quota_is_at_least_half(self):
        allocation = allocate_symbolic_portfolio(9, baseline_quota=0.5)
        self.assertEqual(allocation.baseline_starts, 5)
        self.assertEqual(allocation.symbolic_slots, 4)
        with self.assertRaises(ValueError):
            allocate_symbolic_portfolio(9, baseline_quota=0.49)

    def test_nonapplicable_route_never_calls_verifier(self):
        nonpoly = problem(({"def": "sin(x)", "value": 0}, {"def": "y", "value": 0}))
        result = run_symbolic_side_route(
            nonpoly,
            lambda _point: self.fail("baseline-only route must not verify symbolic output"),
            total_starts=8,
        )
        self.assertEqual(result.status, "baseline_only")
        self.assertEqual(result.proposals, ())
        self.assertEqual(result.verifier_calls, 0)

    def test_candidates_return_through_canonical_verifier(self):
        observed = []

        def verifier(point):
            observed.append(tuple(point))
            return point[0] > 0.0

        result = run_symbolic_side_route(
            POLYNOMIAL,
            verifier,
            total_starts=8,
            timeout_seconds=1.0,
        )
        self.assertEqual(result.status, "complete")
        self.assertEqual(len(result.proposals), 2)
        self.assertEqual(result.verifier_calls, 2)
        self.assertEqual(len(observed), 2)
        self.assertEqual(result.verified, ((1.0, 1.0),))

    def test_tiny_wall_cap_falls_back_without_verification(self):
        result = run_symbolic_side_route(
            POLYNOMIAL,
            lambda _point: self.fail("timed-out route must not verify"),
            total_starts=8,
            timeout_seconds=0.000001,
        )
        self.assertEqual(result.status, "symbolic_timeout")
        self.assertEqual(result.proposals, ())
        self.assertEqual(result.verifier_calls, 0)

    def test_positive_dimensional_and_solution_cap_emit_nothing(self):
        positive_dimensional = problem(
            ({"def": "x", "value": 0}, {"def": "2*x", "value": 0})
        )
        positive = run_symbolic_side_route(
            positive_dimensional,
            lambda _point: self.fail("positive-dimensional route must not verify"),
            total_starts=8,
            timeout_seconds=1.0,
        )
        self.assertEqual(positive.status, "positive_dimensional")
        self.assertEqual(positive.proposals, ())

        capped = run_symbolic_side_route(
            POLYNOMIAL,
            lambda _point: self.fail("solution-overflow route must not verify"),
            total_starts=8,
            timeout_seconds=1.0,
            limits=PolynomialLimits(maximum_solutions=1),
        )
        self.assertEqual(capped.status, "solution_cap")
        self.assertEqual(capped.proposals, ())


if __name__ == "__main__":
    unittest.main()
