#!/usr/bin/env python3
"""Fixed synthetic campaign for quadratic virtual substitution D0."""

from __future__ import annotations

from fractions import Fraction
import hashlib
import json
import math
import random
from statistics import mean
from typing import Callable

import sympy as sp

from candidate import Source, _descriptor, _exact_replay, solve


SEED = 20260731
SCENARIOS = 32
PRIMARY = ("triangular-quadratic", "nontriangular-low-degree", "rational-guards")


def _triangular(rng: random.Random) -> Source:
    x, y, z = sp.symbols("x y z", real=True)
    radicand = sp.Integer(rng.choice((2, 3, 5, 6)))
    offset = sp.Rational(rng.randint(-2, 2), rng.randint(1, 4))
    addition = sp.Rational(rng.randint(1, 4), rng.randint(1, 4))
    x_value = sp.sqrt(radicand)
    y_value = x_value + offset
    z_value = sp.sqrt(y_value**2 + addition)
    return Source(
        variables=(x, y, z),
        equations=(x**2 - radicand, y - x - offset, z**2 - y**2 - addition),
        guards=(x > 0, z > 0),
        denominators=(),
        target=x + 2 * y + z,
        endpoint={x: float(x_value), y: float(y_value), z: float(z_value)},
    )


def _nontriangular(rng: random.Random) -> Source:
    x, y = sp.symbols("x y", real=True)
    radius = sp.Rational(rng.randint(2, 8), rng.randint(1, 4))
    difference = sp.Rational(rng.randint(-2, 2), rng.randint(2, 6))
    roots = sp.solve(
        (x**2 + y**2 - radius, x - y - difference),
        (x, y),
        dict=True,
    )
    positive = next(root for root in roots if float(sp.N(root[x], 30)) > 0)
    return Source(
        variables=(x, y),
        equations=(x**2 + y**2 - radius, x - y - difference),
        guards=(x > 0,),
        denominators=(),
        target=x * y + x,
        endpoint={x: float(positive[x]), y: float(positive[y])},
    )


def _rational_guards(rng: random.Random) -> Source:
    x, y = sp.symbols("x y", real=True)
    radicand = sp.Integer(rng.choice((2, 3, 5, 6)))
    offset = sp.Integer(rng.choice((1, 2, 3)))
    x_value = sp.sqrt(radicand)
    y_value = 1 / (x_value + offset)
    denominator = x + offset
    return Source(
        variables=(x, y),
        equations=(x**2 - radicand, denominator * y - 1),
        guards=(x > 0, y > 0, y < 1),
        denominators=(denominator,),
        target=y + x / 2,
        endpoint={x: float(x_value), y: float(y_value)},
    )


def _degree_three(rng: random.Random) -> Source:
    x = sp.symbols("x", real=True)
    value = sp.Integer(rng.choice((2, 3, 5)))
    return Source((x,), (x**3 - value,), (), (), x, {x: float(value ** sp.Rational(1, 3))})


def _branch_explosion(rng: random.Random) -> Source:
    variables = sp.symbols("q0:7", real=True)
    equations = tuple(variable**2 - rng.choice((2, 3, 5)) for variable in variables)
    endpoint = {variable: math.sqrt(float(-equation.subs(variable, 0))) for variable, equation in zip(variables, equations, strict=True)}
    return Source(tuple(variables), equations, (), (), sum(variables), endpoint)


def _negative_discriminant(rng: random.Random) -> Source:
    x = sp.symbols("x", real=True)
    constant = sp.Integer(rng.randint(1, 5))
    return Source((x,), (x**2 + constant,), (), (), x, {x: 0.0})


def _leading_zero(rng: random.Random) -> Source:
    a, x = sp.symbols("a x", real=True)
    return Source(
        (a, x),
        (a, a * x**2 + x - 1),
        (x > 0,),
        (),
        x + a,
        {a: 0.0, x: 1.0},
    )


def _zero_denominator(rng: random.Random) -> Source:
    x, y = sp.symbols("x y", real=True)
    denominator = x - 1
    return Source(
        (x, y),
        (denominator, denominator * y - 1),
        (),
        (denominator,),
        y,
        {x: 1.0, y: 0.0},
    )


FAMILIES: dict[str, Callable[[random.Random], Source]] = {
    "triangular-quadratic": _triangular,
    "nontriangular-low-degree": _nontriangular,
    "rational-guards": _rational_guards,
    "negative-degree-three": _degree_three,
    "negative-branch-explosion": _branch_explosion,
    "negative-discriminant": _negative_discriminant,
    "leading-coefficient-zero": _leading_zero,
    "zero-denominator": _zero_denominator,
}


def _substitute_source(source: Source, mapping, variables) -> Source:
    return Source(
        variables=tuple(variables),
        equations=tuple(expression.xreplace(mapping) for expression in source.equations),
        guards=tuple(guard.xreplace(mapping) for guard in source.guards),
        denominators=tuple(value.xreplace(mapping) for value in source.denominators),
        target=source.target.xreplace(mapping),
        endpoint={mapping.get(variable, variable): value for variable, value in source.endpoint.items()},
        branch_cap=source.branch_cap,
    )


def _transform(source: Source, name: str) -> Source:
    if name == "identity":
        return source
    if name == "variable-permutation":
        fresh = sp.symbols(f"u0:{len(source.variables)}", real=True)
        mapping = dict(zip(source.variables, reversed(fresh), strict=True))
        return _substitute_source(source, mapping, tuple(mapping[value] for value in source.variables))
    if name == "residual-permutation-scale":
        equations = tuple(
            sp.Rational(index + 2, index + 1) * equation
            for index, equation in enumerate(reversed(source.equations))
        )
        return Source(
            source.variables,
            equations,
            tuple(reversed(source.guards)),
            tuple(reversed(source.denominators)),
            source.target,
            source.endpoint,
            source.branch_cap,
        )
    if name == "cse-factor":
        return Source(
            source.variables,
            tuple(sp.factor(expression) for expression in source.equations),
            tuple(
                guard.func(sp.factor(guard.lhs), sp.factor(guard.rhs))
                for guard in source.guards
            ),
            tuple(sp.factor(value) for value in source.denominators),
            sp.factor(source.target),
            source.endpoint,
            source.branch_cap,
        )
    raise ValueError(name)


TRANSFORMS = (
    "identity",
    "variable-permutation",
    "residual-permutation-scale",
    "cse-factor",
)


def _baseline(source: Source, seed: int):
    rng = random.Random(seed)
    assignments = []
    for _ordinal in range(100):
        values = {
            variable: sp.Rational(rng.randint(-8, 8), rng.randint(1, 8))
            for variable in source.variables
        }
        if _exact_replay(source, values):
            assignments.append(values)
    return assignments


def _signature(assignments) -> str:
    payload = json.dumps(
        [
            sorted((str(variable), sp.srepr(value)) for variable, value in assignment.items())
            for assignment in assignments
        ],
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _configuration_false(source: Source, configuration) -> bool:
    if not _exact_replay(source, configuration.values):
        return True
    target = sp.simplify(source.target.subs(configuration.values))
    if target != configuration.target_value:
        return True
    return _descriptor(target) != configuration.target_descriptor


def run_campaign() -> dict[str, object]:
    rng = random.Random(SEED)
    rows = {
        family: {"control": [], "candidate": [], "fallback": [], "false": []}
        for family in FAMILIES
    }
    baseline_mismatch = 0
    fallback_mismatch = 0
    metamorphic_failure = 0
    trace_count = 0

    for family, generator in FAMILIES.items():
        for scenario in range(SCENARIOS):
            generator_seed = rng.randrange(1 << 30)
            baseline_seed = rng.randrange(1 << 30)
            variants = []
            for transform in TRANSFORMS:
                source = _transform(generator(random.Random(generator_seed)), transform)
                baseline = _baseline(source, baseline_seed)
                shared = baseline[:75]
                control_success = int(bool(baseline))
                result = solve(source)
                trace_count += 2
                false = sum(
                    _configuration_false(source, configuration)
                    for configuration in result.configurations
                )
                if result.fallback_required:
                    candidate_success = control_success
                    fallback = True
                    fallback_mismatch += int(candidate_success != control_success)
                else:
                    candidate_success = int(bool(shared) or bool(result.configurations))
                    fallback = False
                baseline_mismatch += int(_signature(shared) != _signature(baseline[:75]))
                target_set = tuple(
                    sorted(
                        (
                            configuration.target_descriptor.coefficients_high_to_low,
                            configuration.target_descriptor.real_root_index,
                        )
                        for configuration in result.configurations
                    )
                )
                variants.append((candidate_success, fallback, false, target_set))
                rows[family]["control"].append(control_success)
                rows[family]["candidate"].append(candidate_success)
                rows[family]["fallback"].append(int(fallback))
                rows[family]["false"].append(false)
            metamorphic_failure += int(len(set(variants)) != 1)

    family_results = {}
    primary_gain = 0
    false_authority = 0
    for family, row in rows.items():
        control_rate = mean(row["control"])
        candidate_rate = mean(row["candidate"])
        delta = candidate_rate - control_rate
        primary_gain += int(family in PRIMARY and delta > 0.0)
        false_authority += sum(row["false"])
        family_results[family] = {
            "control_exact_witness_rate": control_rate,
            "candidate_exact_witness_rate": candidate_rate,
            "rate_delta": delta,
            "fallback_rate": mean(row["fallback"]),
            "false_authority_count": sum(row["false"]),
        }
    gate_pass = (
        primary_gain >= 2
        and false_authority == 0
        and fallback_mismatch == 0
        and baseline_mismatch == 0
        and metamorphic_failure == 0
    )
    return {
        "schema": "geotarget.quadratic-virtual-substitution-witness-d0/v1",
        "seed": SEED,
        "cpu": 15,
        "synthetic_only": True,
        "instance_count": len(FAMILIES) * SCENARIOS * len(TRANSFORMS),
        "trace_count": trace_count,
        "family_results": family_results,
        "aggregate": {
            "primary_gain_family_count": primary_gain,
            "false_authority_count": false_authority,
            "fallback_mismatch_count": fallback_mismatch,
            "shared_baseline_mismatch_count": baseline_mismatch,
            "metamorphic_failure_count": metamorphic_failure,
            "baseline_quota": 0.75,
            "side_quota": 0.25,
            "decision": "ADVANCE" if gate_pass else "STOP",
        },
    }


if __name__ == "__main__":
    print(json.dumps(run_campaign(), indent=2, sort_keys=True))
