#!/usr/bin/env python3
"""Synthetic exact-replay adversary and Repair A for low-height transport."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
import json
import math
import random
from statistics import mean
from typing import Callable, Sequence

import sympy as sp
from sympy.polys.polyerrors import CoercionFailed, PolynomialError

from candidate import RunResult, System, _low_height_values, run


SEED = 20260731
SCENARIOS = 28
SCORE_PROPOSALS = 4
X, Y, Z = sp.symbols("x y z", real=True)
VARIABLES = (X, Y)
TRANSFORMS = {
    "identity": ((sp.Integer(1), sp.Integer(0)), (sp.Integer(0), sp.Integer(1))),
    "row-permutation": ((sp.Integer(0), sp.Integer(1)), (sp.Integer(1), sp.Integer(0))),
    "extreme-row-scale": (
        (sp.Integer(10) ** 12, sp.Integer(0)),
        (sp.Integer(0), sp.Rational(1, 10**12)),
    ),
    "rational-row-rotation": (
        (sp.Rational(3, 5), -sp.Rational(4, 5)),
        (sp.Rational(4, 5), sp.Rational(3, 5)),
    ),
}
PRIMARY = ("affine", "curved", "singular-cusp")


@dataclass(frozen=True)
class ExactSystem:
    float_system: System
    polynomials: tuple[sp.Expr, ...] | None
    guards: tuple[sp.Relational, ...]
    initial: tuple[float, float]


def _transform(polynomials: Sequence[sp.Expr], matrix) -> tuple[sp.Expr, ...]:
    return tuple(
        sp.expand(sum(row[index] * polynomials[index] for index in range(2)))
        for row in matrix
    )


def _float_system(polynomials, guards, bounds) -> System:
    residual_function = sp.lambdify((X, Y), polynomials, "math")

    def residual(point):
        values = residual_function(point[0], point[1])
        return tuple(float(value) for value in values)

    def guard(point):
        substitutions = {X: point[0], Y: point[1]}
        return all(bool(relation.subs(substitutions)) for relation in guards)

    return System(residual=residual, guard=guard, bounds=bounds)


def _make(polynomials, guards, bounds, initial, matrix) -> ExactSystem:
    transformed = _transform(polynomials, matrix)
    return ExactSystem(
        float_system=_float_system(transformed, guards, bounds),
        polynomials=transformed,
        guards=tuple(guards),
        initial=initial,
    )


def _affine(rng, matrix):
    constant = sp.Rational(rng.randint(-3, 3), rng.randint(1, 5))
    parameter = rng.uniform(-0.7, 0.7) + math.sqrt(2.0) * 1.0e-3
    initial = (float(constant) - 2.0 * parameter + rng.uniform(-1e-5, 1e-5), parameter)
    base = X + 2 * Y - constant
    return _make(
        (base, 2 * base),
        (X > sp.Rational(-19, 10), X < sp.Rational(19, 10), Y > sp.Rational(-9, 10), Y < sp.Rational(9, 10)),
        ((-1.9, 1.9), (-0.9, 0.9)),
        initial,
        matrix,
    )


def _curved(rng, matrix):
    theta = rng.uniform(0.45, 1.05)
    initial = (math.cos(theta) * (1.0 + rng.uniform(-1e-5, 1e-5)), math.sin(theta))
    base = X**2 + Y**2 - 1
    return _make(
        (base, 2 * base),
        (X > sp.Rational(1, 20), X < sp.Rational(49, 50), Y > sp.Rational(1, 20), Y < sp.Rational(49, 50)),
        ((0.05, 0.98), (0.05, 0.98)),
        initial,
        matrix,
    )


def _cusp(rng, matrix):
    parameter = rng.uniform(0.09, 0.28)
    initial = (parameter**2 + rng.uniform(-1e-7, 1e-7), parameter**3)
    base = Y**2 - X**3
    return _make(
        (base, 3 * base),
        (X > sp.Rational(1, 250), X < sp.Rational(9, 100), Y > 0, Y < sp.Rational(1, 25)),
        ((0.004, 0.09), (1e-7, 0.04)),
        initial,
        matrix,
    )


def _nearly_full_rank(rng, matrix):
    constant = sp.Rational(rng.randint(-2, 2), rng.randint(1, 5))
    root = sp.Rational(rng.randint(-3, 3), rng.randint(1, 7))
    epsilon = sp.Rational(1, 10 ** rng.randint(11, 14))
    first = X + Y - constant
    second = first + epsilon * (X - root)
    initial = (float(root) + rng.uniform(-1e-6, 1e-6), float(constant - root))
    return _make(
        (first, second),
        (X > -2, X < 2, Y > -2, Y < 2),
        ((-2.0, 2.0), (-2.0, 2.0)),
        initial,
        matrix,
    )


def _precision_rank_change(rng, matrix):
    epsilon = sp.Rational(1, 10 ** rng.randint(10, 14))
    first = Y - X**2
    second = first + epsilon * X
    initial_x = rng.uniform(-1e-4, 1e-4)
    initial = (initial_x, initial_x**2)
    return _make(
        (first, second),
        (X > sp.Rational(-1, 2), X < sp.Rational(1, 2), Y > sp.Rational(-1, 10), Y < sp.Rational(1, 2)),
        ((-0.5, 0.5), (-0.1, 0.5)),
        initial,
        matrix,
    )


def _irrational_parameter(rng, matrix):
    parameter = rng.uniform(0.08, 0.65) + math.pi * 1e-4
    initial = (parameter, math.sqrt(2.0) * parameter)
    base = Y**2 - 2 * X**2
    return _make(
        (base, 2 * base),
        (X > sp.Rational(1, 20), X < sp.Rational(7, 10), Y > 0, Y < 1),
        ((0.05, 0.7), (0.01, 1.0)),
        initial,
        matrix,
    )


def _guard_boundary(rng, matrix):
    lower = sp.Rational(rng.randint(8, 12), 20)
    upper = lower + sp.Rational(1, 8)
    parameter = float(lower) + rng.uniform(0.01, float(upper - lower) - 0.01)
    initial = (parameter, 1.0 - parameter)
    base = X + Y - 1
    return _make(
        (base, 5 * base),
        (X > lower, X < upper, Y > 0),
        ((float(lower), float(upper)), (0.0, 1.0)),
        initial,
        matrix,
    )


def _multiple_branches(rng, matrix):
    parameter = rng.uniform(0.08, 0.75)
    sign = -1 if rng.random() < 0.5 else 1
    initial = (parameter, sign * math.sqrt(parameter))
    base = Y**2 - X
    branch_guard = Y < 0 if sign < 0 else Y > 0
    return _make(
        (base, 2 * base),
        (X > sp.Rational(1, 20), X < sp.Rational(4, 5), branch_guard),
        ((0.05, 0.8), (-1.0, 1.0)),
        initial,
        matrix,
    )


def _nonpolynomial(rng, matrix):
    constant = sp.Rational(rng.randint(-2, 2), rng.randint(1, 5))
    parameter = rng.uniform(-0.5, 0.5)
    initial = (parameter, float(constant) - math.sin(parameter))
    base = sp.sin(X) + Y - constant
    transformed = _transform((base, 2 * base), matrix)
    return ExactSystem(
        float_system=_float_system(transformed, (), ((-1.0, 1.0), (-2.0, 2.0))),
        polynomials=None,
        guards=(),
        initial=initial,
    )


FAMILIES: dict[str, Callable] = {
    "affine": _affine,
    "curved": _curved,
    "singular-cusp": _cusp,
    "nearly-dependent-full-rank": _nearly_full_rank,
    "precision-rank-change": _precision_rank_change,
    "irrational-free-parameter": _irrational_parameter,
    "guard-boundary": _guard_boundary,
    "multiple-branches": _multiple_branches,
    "unsupported-nonpolynomial": _nonpolynomial,
}


def _approx_descriptor(value: float):
    rational = Fraction(value).limit_denominator(4096)
    if abs(value - float(rational)) <= 1e-9:
        return sp.Rational(rational.numerator, rational.denominator)
    square = Fraction(value * value).limit_denominator(200_000)
    if abs(value * value - float(square)) <= 1e-9:
        root = sp.sqrt(sp.Rational(square.numerator, square.denominator))
        return root if value >= 0 else -root
    return None


@lru_cache(maxsize=512)
def _minpoly(expression: sp.Expr) -> sp.Poly:
    return sp.Poly(sp.minpoly(expression, Z), Z, domain=sp.QQ)


def _exact_guard(system: ExactSystem, values: tuple[sp.Expr, sp.Expr]) -> bool:
    substitutions = dict(zip(VARIABLES, values, strict=True))
    try:
        return all(bool(relation.subs(substitutions)) for relation in system.guards)
    except TypeError:
        return False


def _exact_replay(system: ExactSystem, values: tuple[sp.Expr, sp.Expr]) -> bool:
    if system.polynomials is None or not _exact_guard(system, values):
        return False
    substitutions = dict(zip(VARIABLES, values, strict=True))
    if not all(sp.expand(polynomial.subs(substitutions)) == 0 for polynomial in system.polynomials):
        return False
    for value in values:
        polynomial = _minpoly(value)
        if polynomial.degree() < 1 or sp.gcd(polynomial, polynomial.diff()).degree() != 0:
            return False
    return True


def _pre_replay_claim(system: ExactSystem, point) -> tuple[bool, bool]:
    values = (_approx_descriptor(point[0]), _approx_descriptor(point[1]))
    claimed = all(value is not None for value in values)
    exact = claimed and _exact_replay(system, values)  # type: ignore[arg-type]
    return claimed, bool(exact)


def _exact_fiber_lift(
    system: ExactSystem,
    free_coordinate: int,
    point,
) -> tuple[sp.Expr, sp.Expr] | None:
    if system.polynomials is None:
        return None
    free_value = _approx_descriptor(point[free_coordinate])
    if free_value is None or not free_value.is_Rational:
        return None
    dependent = 1 - free_coordinate
    free_symbol = VARIABLES[free_coordinate]
    dependent_symbol = VARIABLES[dependent]
    univariate: list[sp.Poly] = []
    for source in system.polynomials:
        expression = sp.expand(source.subs({free_symbol: free_value}))
        try:
            polynomial = sp.Poly(expression, dependent_symbol, domain=sp.QQ)
        except (PolynomialError, CoercionFailed):
            return None
        if not polynomial.is_zero:
            univariate.append(polynomial)
    if not univariate:
        return None
    common = univariate[0]
    for polynomial in univariate[1:]:
        common = sp.gcd(common, polynomial)
    if common.degree() <= 0:
        return None
    roots = sp.real_roots(common.as_expr())
    if not roots:
        return None
    approximate_dependent = point[dependent]
    root = min(roots, key=lambda value: abs(float(sp.N(value, 40)) - approximate_dependent))
    values = [None, None]
    values[free_coordinate] = free_value
    values[dependent] = root
    answer = (values[0], values[1])
    if not _exact_replay(system, answer):  # type: ignore[arg-type]
        return None
    return answer  # type: ignore[return-value]


def _exact_points_from_raw(
    system: ExactSystem,
    raw: RunResult,
    start: int,
    end: int | None = None,
    limit: int | None = None,
) -> tuple[tuple[sp.Expr, sp.Expr], ...]:
    if raw.free_coordinate is None:
        return ()
    results = []
    seen = set()
    for point in raw.accepted[start:end]:
        lifted = _exact_fiber_lift(system, raw.free_coordinate, point)
        if lifted is None:
            continue
        key = tuple(sp.srepr(value) for value in lifted)
        if key not in seen:
            seen.add(key)
            results.append(lifted)
            if limit is not None and len(results) >= limit:
                break
    return tuple(results)


def _exact_points_from_slices(
    system: ExactSystem,
    free: int,
    limit: int,
) -> tuple[tuple[sp.Expr, sp.Expr], ...]:
    values = _low_height_values(
        system.initial[free], system.float_system.bounds[free]
    )[:limit]
    results = []
    seen = set()
    for value in values:
        point = list(system.initial)
        point[free] = value
        lifted = _exact_fiber_lift(system, free, (point[0], point[1]))
        if lifted is None:
            continue
        key = tuple(sp.srepr(item) for item in lifted)
        if key not in seen:
            seen.add(key)
            results.append(lifted)
    return tuple(results)


def _exact_rank_free_coordinate(system: ExactSystem) -> int | None:
    if system.polynomials is None:
        return None
    jacobian = sp.Matrix(system.polynomials).jacobian(VARIABLES)
    if sp.expand(jacobian.det()) != 0:
        return None
    substitutions = {X: sp.Float(system.initial[0], 60), Y: sp.Float(system.initial[1], 60)}
    rows = []
    for row in range(2):
        gx = sp.N(jacobian[row, 0].subs(substitutions), 50)
        gy = sp.N(jacobian[row, 1].subs(substitutions), 50)
        norm = abs(gx) ** 2 + abs(gy) ** 2
        rows.append((norm, gx, gy))
    norm, gx, gy = max(rows, key=lambda item: item[0])
    if norm == 0:
        return None
    return 0 if abs(gy) >= abs(gx) else 1


def _run_repair(system: ExactSystem, seed: int):
    control = run(system.float_system, system.initial, seed=seed, candidate=False)
    raw = run(system.float_system, system.initial, seed=seed, candidate=True)
    shared_count = raw.shared_baseline_accept_count
    pre_false = 0
    for point in raw.accepted[shared_count:]:
        claimed, exact = _pre_replay_claim(system, point)
        if claimed and not exact:
            pre_false = 1
            break

    shared_exact = _exact_points_from_raw(system, raw, 0, shared_count, limit=1)
    repair_free = _exact_rank_free_coordinate(system)
    side_exact = (
        _exact_points_from_slices(system, repair_free, SCORE_PROPOSALS)
        if repair_free is not None
        else ()
    )
    distinct_free = {
        sp.srepr(point[repair_free])
        for point in side_exact
        if repair_free is not None
    }
    supported_component = len(distinct_free) >= 2
    if not supported_component:
        repaired_points = _exact_points_from_raw(
            system,
            control,
            control.shared_baseline_accept_count,
            control.shared_baseline_accept_count + SCORE_PROPOSALS,
        )
        fallback = True
    else:
        repaired_points = shared_exact + side_exact
        fallback = False
    false_authority = sum(not _exact_replay(system, point) for point in repaired_points)
    control_side = _exact_points_from_raw(
        system,
        control,
        control.shared_baseline_accept_count,
        control.shared_baseline_accept_count + SCORE_PROPOSALS,
    )
    candidate_side = side_exact if not fallback else control_side
    return (
        control,
        raw,
        repaired_points,
        fallback,
        pre_false,
        false_authority,
        len(control_side) / SCORE_PROPOSALS,
        len(candidate_side) / SCORE_PROPOSALS,
    )


def run_campaign() -> dict[str, object]:
    rng = random.Random(SEED)
    rows = {
        family: {"control": [], "candidate": [], "fallback": [], "pre_false": [], "false": []}
        for family in FAMILIES
    }
    fallback_mismatch = 0
    transform_invariance_failure = 0
    trace_count = 0

    for family, generator in FAMILIES.items():
        for scenario in range(SCENARIOS):
            generator_seed = rng.randrange(1 << 30)
            proposal_seed = rng.randrange(1 << 30)
            metamorphic = []
            for _transform_name, matrix in TRANSFORMS.items():
                system = generator(random.Random(generator_seed), matrix)
                (
                    control,
                    raw,
                    repaired,
                    fallback,
                    pre_false,
                    false,
                    control_rate,
                    candidate_rate,
                ) = _run_repair(system, proposal_seed)
                trace_count += 2
                control_success = control_rate
                candidate_success = candidate_rate
                fallback_expected = family in {
                    "nearly-dependent-full-rank",
                    "precision-rank-change",
                    "unsupported-nonpolynomial",
                }
                if fallback_expected and fallback:
                    fallback_mismatch += int(
                        candidate_success != control_success
                        or raw.shared_baseline_signature != control.shared_baseline_signature
                    )
                rows[family]["control"].append(control_success)
                rows[family]["candidate"].append(candidate_success)
                rows[family]["fallback"].append(int(fallback))
                rows[family]["pre_false"].append(pre_false)
                rows[family]["false"].append(false)
                metamorphic.append((candidate_success, fallback, false))
            transform_invariance_failure += int(len(set(metamorphic)) != 1)

    family_results = {}
    primary_gain = 0
    for family, row in rows.items():
        control_rate = mean(row["control"])
        candidate_rate = mean(row["candidate"])
        gain = candidate_rate - control_rate
        primary_gain += int(family in PRIMARY and gain > 0.0)
        family_results[family] = {
            "control_exact_authority_rate": control_rate,
            "candidate_exact_authority_rate": candidate_rate,
            "rate_delta": gain,
            "fallback_rate": mean(row["fallback"]),
            "pre_repair_approximate_false_claim_count": sum(row["pre_false"]),
            "post_repair_exact_false_authority_count": sum(row["false"]),
        }
    false_authority = sum(
        result["post_repair_exact_false_authority_count"]
        for result in family_results.values()
    )
    gate_pass = (
        false_authority == 0
        and fallback_mismatch == 0
        and transform_invariance_failure == 0
        and primary_gain >= 2
    )
    return {
        "schema": "geotarget.nullspace-low-height-exact-adversary/v1",
        "seed": SEED,
        "cpu": 15,
        "synthetic_only": True,
        "instance_count": len(FAMILIES) * SCENARIOS * len(TRANSFORMS),
        "trace_count": trace_count,
        "family_results": family_results,
        "aggregate": {
            "primary_gain_family_count": primary_gain,
            "pre_repair_approximate_false_claim_count": sum(
                result["pre_repair_approximate_false_claim_count"]
                for result in family_results.values()
            ),
            "post_repair_exact_false_authority_count": false_authority,
            "fallback_mismatch_count": fallback_mismatch,
            "transform_invariance_failure_count": transform_invariance_failure,
            "decision": "ADVANCE_REPAIR_A" if gate_pass else "STOP",
        },
    }


if __name__ == "__main__":
    print(json.dumps(run_campaign(), indent=2, sort_keys=True))
