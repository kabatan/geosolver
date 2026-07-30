#!/usr/bin/env python3
"""Generated-only S0 for the strict polynomial side route."""

from __future__ import annotations

import json

from polynomial_side_route import PolynomialLimits, detect_polynomial_plan, run_symbolic_side_route


def formulation(constraints, variables=("x", "y"), construction=()):
    return {
        "task": "solve",
        "variables": {"names": list(variables)},
        "construction": list(construction),
        "constraints": list(constraints),
        "guards": [],
    }


def main() -> None:
    polynomial = formulation(
        ({"def": "x**2", "value": 1}, {"def": "y", "value": "x"})
    )
    verifier_calls = []

    def canonical(point):
        verifier_calls.append(tuple(point))
        x, y = point
        return abs(x * x - 1.0) <= 1.0e-10 and abs(y - x) <= 1.0e-10 and x > 0.0

    solved = run_symbolic_side_route(
        polynomial,
        canonical,
        total_starts=16,
        baseline_quota=0.75,
        timeout_seconds=1.0,
    )
    nonpolynomial = detect_polynomial_plan(
        formulation(({"def": "sin(x)", "value": 0}, {"def": "y", "value": 0}))
    )
    opaque = detect_polynomial_plan(
        formulation(
            ({"def": "A", "value": 0}, {"def": "y", "value": 0}),
            construction=({"name": "A", "expr": "Point(x, 0)"},),
        )
    )
    branch = detect_polynomial_plan(
        formulation(({"def": "x if x > 0 else -x", "value": 1}, {"def": "y", "value": 0}))
    )
    degree_cap = detect_polynomial_plan(
        formulation(({"def": "x**5", "value": 1}, {"def": "y", "value": 0}))
    )
    dimension_cap = detect_polynomial_plan(
        formulation(
            tuple({"def": name, "value": 0} for name in ("a", "b", "c", "d")),
            variables=("a", "b", "c", "d"),
        )
    )
    monomials = (
        "1", "x", "y", "z", "x**2", "x*y", "x*z", "y**2", "y*z", "z**2",
        "x**3", "x**2*y", "x**2*z", "x*y**2", "x*y*z", "x*z**2", "y**3",
    )
    term_cap = detect_polynomial_plan(
        formulation(
            (
                {"def": "+".join(monomials), "value": 0},
                {"def": "y", "value": 0},
                {"def": "z", "value": 0},
            ),
            variables=("x", "y", "z"),
        )
    )
    positive_dimensional = run_symbolic_side_route(
        formulation(({"def": "x", "value": 0}, {"def": "2*x", "value": 0})),
        lambda _point: False,
        total_starts=16,
        timeout_seconds=1.0,
    )
    solution_cap = run_symbolic_side_route(
        polynomial,
        lambda _point: False,
        total_starts=16,
        timeout_seconds=1.0,
        limits=PolynomialLimits(maximum_solutions=1),
    )
    timeout = run_symbolic_side_route(
        polynomial,
        lambda _point: True,
        total_starts=16,
        timeout_seconds=0.000001,
    )
    result = {
        "schema_version": "geotarget.exp-poly-001-s0/v1",
        "generated_only": True,
        "truth_materialized": False,
        "polynomial": {
            "applicable": solved.plan.applicable,
            "status": solved.status,
            "proposal_count": len(solved.proposals),
            "verified_count": len(solved.verified),
            "verifier_calls": solved.verifier_calls,
            "guard_filtered_count": len(solved.proposals) - len(solved.verified),
            "baseline_starts": solved.allocation.baseline_starts,
            "symbolic_slots": solved.allocation.symbolic_slots,
        },
        "fallbacks": {
            "nonpolynomial": nonpolynomial.reason,
            "opaque": opaque.reason,
            "branch": branch.reason,
            "degree_cap": degree_cap.reason,
            "dimension_cap": dimension_cap.reason,
            "term_cap": term_cap.reason,
            "positive_dimensional": positive_dimensional.status,
            "positive_dimensional_verified_count": len(positive_dimensional.verified),
            "solution_cap": solution_cap.status,
            "solution_cap_verified_count": len(solution_cap.verified),
            "timeout": timeout.status,
            "timeout_verified_count": len(timeout.verified),
        },
        "authority": {
            "symbolic_result_is_proposal_only": True,
            "canonical_verifier_bypassed": False,
            "canonical_verifier_observed_points": len(verifier_calls),
        },
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
