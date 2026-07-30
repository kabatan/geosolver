#!/usr/bin/env python3
"""Independent exact adversary for QVS Repair A; synthetic QQ sources only."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import random
from statistics import mean
from typing import Callable

import sympy as sp

import candidate as original
from candidate_repair_a import Source, solve


SEED = 20260731 + 17
SCENARIOS = 20
DEFAULT_SCENARIOS = 20
TRANSFORMS = (
    "identity",
    "variable-permutation",
    "residual-permutation-scale",
    "factor-expand",
)
PRIMARY = ("primary-n2", "primary-n3", "primary-n4")


@dataclass(frozen=True)
class Case:
    source: Source
    expected_fallback: bool


def _q(rng: random.Random, low=-4, high=4) -> sp.Rational:
    return sp.Rational(rng.randint(low, high), rng.randint(1, 7))


def _primary_n2(rng: random.Random) -> Case:
    x, y = sp.symbols("x y", real=True)
    r = sp.Integer(rng.choice((2, 3, 5, 6, 7)))
    q = _q(rng)
    source = Source(
        (x, y),
        (x**2 - r, y - x - q),
        (x > 0,),
        (),
        3 * x + y,
        {x: math.sqrt(int(r)), y: math.sqrt(int(r)) + float(q)},
    )
    return Case(source, False)


def _nested_chain(rng: random.Random, n: int) -> Source:
    variables = sp.symbols(f"x0:{n}", real=True)
    r = sp.Integer(rng.choice((2, 3, 5, 6)))
    equations = [variables[0] ** 2 - r]
    endpoint = {variables[0]: math.sqrt(int(r))}
    guards = [variables[0] > 0]
    previous = sp.sqrt(r)
    for index in range(1, n):
        shift = sp.Integer(rng.randint(2, 5))
        equations.append(variables[index] ** 2 - variables[index - 1] - shift)
        previous = sp.sqrt(previous + shift)
        endpoint[variables[index]] = float(sp.N(previous, 30))
        guards.append(variables[index] > 0)
    target = sum((index + 1) * variable for index, variable in enumerate(variables))
    return Source(tuple(variables), tuple(equations), tuple(guards), (), target, endpoint)


def _primary_n3(rng: random.Random) -> Case:
    return Case(_dimension_chain(rng, 3), False)


def _primary_n4(rng: random.Random) -> Case:
    return Case(_dimension_chain(rng, 4), False)


def _dimension_chain(rng: random.Random, n: int) -> Source:
    variables = sp.symbols(f"d0:{n}", real=True)
    total = sp.Integer(rng.choice((2, 3, 5, 6)))
    equations = [variables[0] ** 2 - total]
    endpoint = {variables[0]: math.sqrt(int(total))}
    guards = [variables[0] > 0]
    for index in range(1, n):
        shift = sp.Integer(rng.randint(2, 7))
        equations.append(variables[index] ** 2 - variables[index - 1] ** 2 - shift)
        total += shift
        endpoint[variables[index]] = math.sqrt(int(total))
        guards.append(variables[index] > 0)
    return Source(
        tuple(variables), tuple(equations), tuple(guards), (),
        variables[-1], endpoint,
    )


def _leading_zero_split(rng: random.Random) -> Case:
    x, z, y, w = sp.symbols("x z y w", real=True)
    root = sp.Integer(rng.randint(1, 4))
    # x has one graph neighbour while z participates in a three-cycle, forcing
    # elimination of x while its quadratic leading coefficient is unresolved.
    equations = (
        z * x**2 + x - root,
        z + y,
        y + w,
        w + z,
    )
    source = Source(
        (x, z, y, w),
        equations,
        (x > 0,),
        (),
        x + 2 * z + y,
        {x: float(root), z: 0.0, y: 0.0, w: 0.0},
    )
    return Case(source, False)


def _nested_radicals(rng: random.Random) -> Case:
    return Case(_nested_chain(rng, 4), False)


def _repeated_roots(rng: random.Random) -> Case:
    n = rng.choice((2, 3, 4, 6))
    variables = sp.symbols(f"r0:{n}", real=True)
    roots = [rng.randint(-4, 4) for _ in variables]
    equations = tuple((variable - root) ** 2 for variable, root in zip(variables, roots, strict=True))
    target = sum((2**index) * variable for index, variable in enumerate(variables))
    source = Source(
        tuple(variables), equations, (), (), target,
        {variable: float(root) for variable, root in zip(variables, roots, strict=True)},
    )
    return Case(source, False)


def _discriminant_zero(rng: random.Random) -> Case:
    x, y = sp.symbols("x y", real=True)
    root = _q(rng)
    offset = _q(rng)
    source = Source(
        (x, y),
        ((x - y - offset) ** 2, y - root),
        (),
        (),
        2 * x - y,
        {x: float(root + offset), y: float(root)},
    )
    return Case(source, False)


def _denominator_sign(rng: random.Random) -> Case:
    x, y = sp.symbols("x y", real=True)
    r = sp.Integer(rng.choice((2, 3, 5, 6, 7)))
    offset = sp.Integer(1)
    denominator = x + offset
    negative = -sp.sqrt(r)
    source = Source(
        (x, y),
        (x**2 - r, denominator * y - 1),
        (denominator < 0, y < 0),
        (denominator,),
        x - y,
        {x: float(negative), y: float(1 / (negative + offset))},
    )
    return Case(source, False)


def _strict_boundary(rng: random.Random) -> Case:
    x = sp.symbols("x", real=True)
    upper = sp.Integer(rng.randint(1, 7))
    source = Source(
        (x,),
        (x * (x - upper),),
        (x > 0, x < upper),
        (),
        x,
        {x: float(upper) / 2},
    )
    return Case(source, True)


def _branch_cap(rng: random.Random, n: int, expected_fallback: bool) -> Case:
    variables = sp.symbols(f"b0:{n}", real=True)
    magnitudes = [rng.randint(1, 4) for _ in variables]
    equations = tuple(
        variable**2 - magnitude**2
        for variable, magnitude in zip(variables, magnitudes, strict=True)
    )
    target = sum((5**index) * variable for index, variable in enumerate(variables))
    source = Source(
        tuple(variables), equations, (), (), target,
        {variable: float(magnitude) for variable, magnitude in zip(variables, magnitudes, strict=True)},
        branch_cap=64,
    )
    return Case(source, expected_fallback)


def _branch_cap_before(rng: random.Random) -> Case:
    return _branch_cap(rng, 5, False)


def _branch_cap_over(rng: random.Random) -> Case:
    return _branch_cap(rng, 6, True)


def _elimination_ties(rng: random.Random) -> Case:
    x, y, z = sp.symbols("x y z", real=True)
    rx = sp.Integer(rng.choice((2, 3, 5)))
    ry = sp.Integer(rng.choice((6, 7, 10)))
    source = Source(
        (x, y, z),
        (x**2 - rx, y**2 - ry, z - x - y),
        (x > 0, y > 0),
        (),
        z + x - 2 * y,
        {x: math.sqrt(int(rx)), y: math.sqrt(int(ry)), z: math.sqrt(int(rx)) + math.sqrt(int(ry))},
    )
    return Case(source, False)


def _coefficient_swell(rng: random.Random) -> Case:
    x0, x1, x2, x3 = sp.symbols("x0:4", real=True)
    primes = rng.sample((101, 103, 107, 109, 113, 127, 131, 137), 8)
    p0, p1, p2, p3, p4, p5, p6, p7 = map(sp.Integer, primes)
    equations = (
        p0 * x0**2 - p1,
        p2 * x1 - p3 * x0 - 1,
        p4 * x2**2 - p5 * x1 - 1,
        p6 * x3 - p7 * x2 - 1,
    )
    x0v = sp.sqrt(p1 / p0)
    x1v = (p3 * x0v + 1) / p2
    x2v = sp.sqrt((p5 * x1v + 1) / p4)
    x3v = (p7 * x2v + 1) / p6
    source = Source(
        (x0, x1, x2, x3), equations, (x0 > 0, x2 > 0), (),
        x0 + 2 * x1 + 3 * x2 + 4 * x3,
        {x0: float(x0v), x1: float(x1v), x2: float(x2v), x3: float(x3v)},
    )
    return Case(source, False)


FAMILIES: dict[str, Callable[[random.Random], Case]] = {
    "primary-n2": _primary_n2,
    "primary-n3": _primary_n3,
    "primary-n4": _primary_n4,
    "leading-zero-case-split": _leading_zero_split,
    "nested-radicals": _nested_radicals,
    "repeated-roots": _repeated_roots,
    "discriminant-zero": _discriminant_zero,
    "denominator-sign": _denominator_sign,
    "strict-boundary": _strict_boundary,
    "branch-cap-before": _branch_cap_before,
    "branch-cap-over": _branch_cap_over,
    "elimination-order-ties": _elimination_ties,
    "coefficient-swell": _coefficient_swell,
}

HEAVY_FAMILIES = {
    "primary-n4",
    "nested-radicals",
    "coefficient-swell",
    "elimination-order-ties",
}


def _scenario_count(family: str) -> int:
    if SCENARIOS != DEFAULT_SCENARIOS:
        return SCENARIOS
    return 4 if family in HEAVY_FAMILIES else 28


def _transform(source: Source, name: str) -> Source:
    if name == "identity":
        return source
    if name == "variable-permutation":
        fresh = sp.symbols(f"v0:{len(source.variables)}", real=True)
        mapping = dict(zip(source.variables, reversed(fresh), strict=True))
        return Source(
            tuple(mapping[v] for v in source.variables),
            tuple(e.xreplace(mapping) for e in source.equations),
            tuple(g.xreplace(mapping) for g in source.guards),
            tuple(d.xreplace(mapping) for d in source.denominators),
            source.target.xreplace(mapping),
            {mapping[v]: value for v, value in source.endpoint.items()},
            source.branch_cap,
        )
    if name == "residual-permutation-scale":
        equations = tuple(
            sp.Rational((-1) ** index * (index + 2), index + 1) * equation
            for index, equation in enumerate(reversed(source.equations))
        )
        return Source(
            source.variables, equations, tuple(reversed(source.guards)),
            tuple(reversed(source.denominators)), source.target,
            source.endpoint, source.branch_cap,
        )
    if name == "factor-expand":
        equations = tuple(
            sp.factor(expression) if index % 2 else sp.expand(expression)
            for index, expression in enumerate(source.equations)
        )
        return Source(
            source.variables, equations, source.guards,
            tuple(sp.factor(d) for d in source.denominators),
            sp.expand(source.target), source.endpoint, source.branch_cap,
        )
    raise ValueError(name)


def _exact_zero(expression: sp.Expr) -> bool:
    value = sp.factor(sp.cancel(sp.together(expression)))
    if value == 0 or value.is_zero is True:
        return True
    answer = value.equals(0)
    return answer is True


def _exact_sign(expression: sp.Expr) -> int | None:
    value = sp.simplify(sp.cancel(sp.together(expression)))
    if _exact_zero(value):
        return 0
    if value.is_positive is True:
        return 1
    if value.is_negative is True:
        return -1
    try:
        root = sp.polys.numberfields.to_number_field(value).to_root()
    except (NotImplementedError, TypeError, ValueError):
        return None
    if root.is_positive is True:
        return 1
    if root.is_negative is True:
        return -1
    if root.is_zero is True:
        return 0
    return None


def _exact_relation(relation: sp.Relational) -> bool:
    if relation is sp.true:
        return True
    if relation is sp.false:
        return False
    difference = sp.simplify(relation.lhs - relation.rhs)
    sign = _exact_sign(difference)
    if sign is None:
        return False
    if isinstance(relation, sp.Equality):
        return sign == 0
    if isinstance(relation, sp.Unequality):
        return sign != 0
    if isinstance(relation, sp.StrictGreaterThan):
        return sign > 0
    if isinstance(relation, sp.GreaterThan):
        return sign >= 0
    if isinstance(relation, sp.StrictLessThan):
        return sign < 0
    if isinstance(relation, sp.LessThan):
        return sign <= 0
    return False


def _descriptor(value: sp.Expr):
    target = sp.Symbol("oracle_target")
    polynomial = sp.Poly(sp.minpoly(value, target), target, domain=sp.QQ).sqf_part().monic()
    denominator = sp.ilcm(*(coefficient.q for coefficient in polynomial.all_coeffs()))
    coefficients = tuple(int(coefficient * denominator) for coefficient in polynomial.all_coeffs())
    common = math.gcd(*(abs(coefficient) for coefficient in coefficients if coefficient))
    coefficients = tuple(coefficient // common for coefficient in coefficients)
    if coefficients[0] < 0:
        coefficients = tuple(-coefficient for coefficient in coefficients)
    roots = sp.real_roots(sp.Poly.from_list(coefficients, gens=target).as_expr())
    distances = [abs(sp.N(root - value, 100)) for root in roots]
    ordinal = min(range(len(roots)), key=lambda index: distances[index])
    if distances[ordinal] != 0 and not _exact_zero(roots[ordinal] - value):
        raise ValueError("descriptor-root-mismatch")
    return coefficients, ordinal


def _groebner_oracle(source: Source, result) -> tuple[int, tuple]:
    false = 0
    descriptors = []
    try:
        basis = sp.groebner(source.equations, *source.variables, order="lex", domain=sp.QQ)
    except Exception:
        return len(result.configurations) or 1, ()
    for equation in source.equations:
        _quotients, remainder = basis.reduce(sp.expand(equation))
        if not _exact_zero(remainder):
            return len(result.configurations) or 1, ()

    seen = set()
    for configuration in result.configurations:
        values = configuration.values
        valid = set(values) == set(source.variables)
        valid &= all(
            _exact_zero(polynomial.as_expr().subs(values))
            for polynomial in basis.polys
        )
        valid &= all(
            not _exact_zero(denominator.subs(values))
            for denominator in source.denominators
        )
        valid &= all(_exact_relation(guard.subs(values)) for guard in source.guards)
        target_value = sp.simplify(source.target.subs(values))
        valid &= _exact_zero(target_value - configuration.target_value)
        try:
            descriptor = _descriptor(target_value)
        except (ValueError, NotImplementedError):
            valid = False
            descriptor = None
        reported = (
            configuration.target_descriptor.coefficients_high_to_low,
            configuration.target_descriptor.real_root_index,
        )
        valid &= descriptor == reported
        if reported in seen:
            valid = False
        seen.add(reported)
        false += int(not valid)
        if valid:
            descriptors.append(reported)
    return false, tuple(sorted(descriptors))


def _baseline(source: Source, seed: int):
    rng = random.Random(seed)
    successes = []
    for _ in range(100):
        values = {
            variable: sp.Rational(rng.randint(-9, 9), rng.randint(1, 9))
            for variable in source.variables
        }
        if all(_exact_zero(equation.subs(values)) for equation in source.equations):
            if all(not _exact_zero(d.subs(values)) for d in source.denominators):
                if all(_exact_relation(g.subs(values)) for g in source.guards):
                    successes.append(values)
    return successes


def _signature(assignments) -> str:
    payload = json.dumps(
        [sorted((str(k), sp.srepr(v)) for k, v in row.items()) for row in assignments],
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _pre_repair_counterexamples() -> dict[str, object]:
    x = sp.symbols("x", real=True)
    duplicate = original.solve(Source((x,), ((x - 1) ** 2,), (), (), x, {x: 1.0}))
    variables = sp.symbols("q0:6", real=True)
    cap = original.solve(Source(
        tuple(variables), tuple((variable - index) ** 2 for index, variable in enumerate(variables, 1)),
        (), (), sum(variables), {variable: float(index) for index, variable in enumerate(variables, 1)},
    ))
    return {
        "duplicate_root_configuration_count": len(duplicate.configurations),
        "duplicate_root_branch_states": duplicate.branch_states_generated,
        "repeated_n6_status": cap.status,
        "repeated_n6_branch_states": cap.branch_states_generated,
    }


def run_campaign() -> dict[str, object]:
    rng = random.Random(SEED)
    rows = {name: {"control": [], "candidate": [], "fallback": [], "false": []} for name in FAMILIES}
    fallback_mismatch = 0
    baseline_mismatch = 0
    metamorphic_failure = 0
    max_branch_states = 0

    for family, generator in FAMILIES.items():
        for _scenario in range(_scenario_count(family)):
            source_seed = rng.randrange(1 << 30)
            baseline_seed = rng.randrange(1 << 30)
            variants = []
            for transform in TRANSFORMS:
                case = generator(random.Random(source_seed))
                source = _transform(case.source, transform)
                baseline = _baseline(source, baseline_seed)
                shared = baseline[:75]
                result = solve(source)
                false, descriptors = _groebner_oracle(source, result)
                max_branch_states = max(max_branch_states, result.branch_states_generated)
                expected_fallback = case.expected_fallback
                fallback_mismatch += int(result.fallback_required != expected_fallback)
                baseline_mismatch += int(_signature(shared) != _signature(baseline[:75]))
                control = int(bool(baseline))
                candidate = control if result.fallback_required else int(bool(shared) or bool(descriptors))
                rows[family]["control"].append(control)
                rows[family]["candidate"].append(candidate)
                rows[family]["fallback"].append(int(result.fallback_required))
                rows[family]["false"].append(false)
                variants.append((result.fallback_required, descriptors, false))
            metamorphic_failure += int(len(set(variants)) != 1)

    family_results = {}
    primary_gain = 0
    false_authority = 0
    for family, row in rows.items():
        control_rate = mean(row["control"])
        candidate_rate = mean(row["candidate"])
        delta = candidate_rate - control_rate
        false_authority += sum(row["false"])
        primary_gain += int(family in PRIMARY and delta > 0)
        family_results[family] = {
            "control_exact_witness_rate": control_rate,
            "candidate_exact_witness_rate": candidate_rate,
            "rate_delta": delta,
            "fallback_rate": mean(row["fallback"]),
            "false_authority_count": sum(row["false"]),
        }

    gate = (
        primary_gain == 3
        and false_authority == 0
        and fallback_mismatch == 0
        and baseline_mismatch == 0
        and metamorphic_failure == 0
    )
    return {
        "schema": "geotarget.qvs-repair-a-exact-adversary/v1",
        "seed": SEED,
        "cpu": 14,
        "synthetic_only": True,
        "instance_count": sum(_scenario_count(family) for family in FAMILIES) * len(TRANSFORMS),
        "trace_count": sum(_scenario_count(family) for family in FAMILIES) * len(TRANSFORMS) * 2,
        "pre_repair_counterexamples": _pre_repair_counterexamples(),
        "family_results": family_results,
        "aggregate": {
            "primary_gain_family_count": primary_gain,
            "false_authority_count": false_authority,
            "fallback_mismatch_count": fallback_mismatch,
            "shared_baseline_mismatch_count": baseline_mismatch,
            "metamorphic_failure_count": metamorphic_failure,
            "max_branch_states": max_branch_states,
            "baseline_quota": 0.75,
            "side_quota": 0.25,
            "decision": "ADVANCE" if gate else "REPAIR",
        },
    }


if __name__ == "__main__":
    print(json.dumps(run_campaign(), indent=2, sort_keys=True))
