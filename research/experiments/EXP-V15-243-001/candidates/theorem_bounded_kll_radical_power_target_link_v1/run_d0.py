#!/usr/bin/env python3
"""Fixed synthetic D0/adversary for bounded radical-power target links."""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
import math
import random
from statistics import mean
from typing import Callable

import sympy as sp

from candidate import KLL_BITS, Proposal, RegularRootBox, Source, T, solve


SEED = 20260731 + 29
SCENARIOS = 32
TRANSFORMS = ("identity", "variable-permutation", "scale-permutation", "factor-expand")
POSITIVE = ("x2-minus-r", "squared-generator-radical-only", "coupled2d-identity-omitted")


@dataclass(frozen=True)
class Case:
    source: Source
    positive: bool
    radical_only: bool = False


def _interval_for_sqrt(r: int):
    lower = math.isqrt(r)
    return sp.Rational(lower), sp.Rational(lower + 1)


def _base(rng: random.Random):
    x = sp.Symbol("x", real=True)
    r = rng.choice((2, 3, 5, 6, 7, 10))
    f = x**2 - r
    interval = _interval_for_sqrt(r)
    box = RegularRootBox((x,), (f,), (x > 0,), {x: sp.sqrt(r)}, {x: interval})
    return x, sp.Integer(r), f, interval, box


def _positive_direct(rng: random.Random) -> Case:
    x, r, f, interval, box = _base(rng)
    proposal = Proposal(T**2 - r, x, (f,), (sp.Integer(1),), 1, interval)
    return Case(Source(box, proposal), True)


def _positive_radical_only(rng: random.Random) -> Case:
    _x, _r, f, _interval, box = _base(rng)
    proposal = Proposal(T, f, (f**2,), (sp.Integer(1),), 2, (sp.Rational(-1), sp.Rational(1)))
    return Case(Source(box, proposal), True, True)


def _positive_coupled(rng: random.Random) -> Case:
    x, y = sp.symbols("x y", real=True)
    r = sp.Integer(rng.choice((2, 3, 5, 6, 7, 10)))
    f1 = x**2 - r
    f2 = y - x - 1
    xv = sp.sqrt(r)
    yv = xv + 1
    x_interval = _interval_for_sqrt(int(r))
    y_interval = (x_interval[0] + 1, x_interval[1] + 1)
    box = RegularRootBox(
        (x, y), (f1, f2), (x > 0, y > 0),
        {x: xv, y: yv}, {x: x_interval, y: y_interval},
    )
    h = x + y
    polynomial = T**2 - 2 * T + 1 - 4 * r
    approximate = float(sp.N(1 + 2 * xv, 30))
    lower = math.floor(approximate)
    interval = (sp.Rational(lower), sp.Rational(lower + 1))
    proposal = Proposal(
        polynomial, h, (f1, f2), (sp.Integer(4), 4 * x + f2), 1,
        interval, identity_omitted_from_proposal=True,
    )
    return Case(Source(box, proposal), True)


def _wrong_polynomial(rng: random.Random) -> Case:
    case = _positive_direct(rng)
    proposal = case.source.proposal
    polynomial = sp.expand(proposal.polynomial - 1)
    return Case(Source(case.source.root_box, replace(proposal, polynomial=polynomial)), False)


def _fourth_power_only(rng: random.Random) -> Case:
    _x, _r, f, _interval, box = _base(rng)
    proposal = Proposal(T, f, (f**4,), (sp.Integer(1),), 4, (sp.Rational(-1), sp.Rational(1)))
    return Case(Source(box, proposal), False)


def _reducible(rng: random.Random) -> Case:
    x, r, f, interval, box = _base(rng)
    polynomial = (T**2 - r) * (T - 1)
    proposal = Proposal(polynomial, x, (f,), (x - 1,), 1, interval)
    return Case(Source(box, proposal), False)


def _two_root_interval(rng: random.Random) -> Case:
    x, r, f, _interval, box = _base(rng)
    bound = math.isqrt(int(r)) + 2
    proposal = Proposal(T**2 - r, x, (f,), (sp.Integer(1),), 1, (-sp.Rational(bound), sp.Rational(bound)))
    return Case(Source(box, proposal), False)


def _discriminant_zero(rng: random.Random) -> Case:
    _x, _r, f, _interval, box = _base(rng)
    proposal = Proposal((T - 1) ** 2, sp.Integer(1), (f,), (sp.Integer(0),), 1, (sp.Rational(0), sp.Rational(2)))
    return Case(Source(box, proposal), False)


def _incomplete_root_box(rng: random.Random) -> Case:
    case = _positive_direct(rng)
    box = replace(case.source.root_box, complete=False)
    return Case(Source(box, case.source.proposal), False)


def _mutated_cofactor(rng: random.Random) -> Case:
    case = _positive_direct(rng)
    proposal = replace(case.source.proposal, cofactors=(sp.Integer(2),))
    return Case(Source(case.source.root_box, proposal), False)


FAMILIES: dict[str, Callable[[random.Random], Case]] = {
    "x2-minus-r": _positive_direct,
    "squared-generator-radical-only": _positive_radical_only,
    "coupled2d-identity-omitted": _positive_coupled,
    "negative-wrong-polynomial": _wrong_polynomial,
    "negative-fourth-power-only": _fourth_power_only,
    "negative-reducible": _reducible,
    "negative-two-root-interval": _two_root_interval,
    "negative-discriminant-zero": _discriminant_zero,
    "negative-incomplete-root-box": _incomplete_root_box,
    "negative-mutated-cofactor": _mutated_cofactor,
}


def _transform(case: Case, name: str) -> Case:
    source = case.source
    box = source.root_box
    proposal = source.proposal
    if name == "identity":
        return case
    if name == "variable-permutation":
        fresh = sp.symbols(f"v0:{len(box.variables)}", real=True)
        mapping = dict(zip(box.variables, reversed(fresh), strict=True))
        new_box = RegularRootBox(
            tuple(mapping[v] for v in box.variables),
            tuple(e.xreplace(mapping) for e in box.equations),
            tuple(g.xreplace(mapping) for g in box.guards),
            {mapping[v]: value.xreplace(mapping) for v, value in box.witness.items()},
            {mapping[v]: interval for v, interval in box.intervals.items()},
            box.complete,
        )
        new_proposal = Proposal(
            proposal.polynomial,
            proposal.target_expression.xreplace(mapping),
            tuple(g.xreplace(mapping) for g in proposal.generators),
            tuple(c.xreplace(mapping) for c in proposal.cofactors),
            proposal.link_power,
            proposal.target_interval,
            proposal.identity_omitted_from_proposal,
        )
        return Case(Source(new_box, new_proposal), case.positive, case.radical_only)
    if name == "scale-permutation":
        equation_scales = [sp.Rational(index + 2, index + 1) for index in range(len(box.equations))]
        equations = tuple(scale * equation for scale, equation in zip(equation_scales, reversed(box.equations), strict=True))
        pairs = list(reversed(list(zip(proposal.generators, proposal.cofactors, strict=True))))
        generators = []
        cofactors = []
        for index, (generator, cofactor) in enumerate(pairs):
            scale = sp.Rational((-1) ** index * (index + 3), index + 2)
            generators.append(scale * generator)
            cofactors.append(cofactor / scale)
        new_box = replace(box, equations=equations, guards=tuple(reversed(box.guards)))
        new_proposal = replace(proposal, generators=tuple(generators), cofactors=tuple(cofactors))
        return Case(Source(new_box, new_proposal), case.positive, case.radical_only)
    if name == "factor-expand":
        new_box = replace(box, equations=tuple(sp.factor(sp.expand(e)) for e in box.equations))
        new_proposal = replace(
            proposal,
            polynomial=sp.expand(proposal.polynomial),
            target_expression=sp.expand(proposal.target_expression),
            generators=tuple(sp.factor(sp.expand(g)) for g in proposal.generators),
            cofactors=tuple(sp.expand(c) for c in proposal.cofactors),
        )
        return Case(Source(new_box, new_proposal), case.positive, case.radical_only)
    raise ValueError(name)


def _zero(expression):
    value = sp.factor(sp.cancel(sp.together(expression)))
    return value == 0 or value.is_zero is True or value.equals(0) is True


def _oracle(source: Source, allow_radical_power: bool):
    box = source.root_box
    proposal = source.proposal
    if not box.complete or len(box.equations) != len(box.variables):
        return None
    if set(box.variables) != set(box.witness) or set(box.variables) != set(box.intervals):
        return None
    if any(not _zero(e.subs(box.witness)) for e in box.equations):
        return None
    if any(sp.simplify(g.subs(box.witness)) is not sp.true for g in box.guards):
        return None
    if _zero(sp.Matrix(box.equations).jacobian(box.variables).det().subs(box.witness)):
        return None
    try:
        polynomial = sp.Poly(proposal.polynomial, T, domain=sp.QQ)
    except Exception:
        return None
    denominator = sp.ilcm(*(c.q for c in polynomial.all_coeffs()))
    coefficients = tuple(int(c * denominator) for c in polynomial.all_coeffs())
    common = math.gcd(*(abs(c) for c in coefficients if c))
    coefficients = tuple(c // common for c in coefficients)
    if coefficients[0] < 0:
        coefficients = tuple(-c for c in coefficients)
    if not 1 <= polynomial.degree() <= 4 or max(map(abs, coefficients)) > 2**20:
        return None
    if not polynomial.is_irreducible or sp.gcd(polynomial, polynomial.diff()).degree() != 0:
        return None
    allowed = (1, 2) if allow_radical_power else (1,)
    if proposal.link_power not in allowed or len(proposal.generators) != len(proposal.cofactors):
        return None
    relation = sp.expand(polynomial.as_expr().subs(T, proposal.target_expression))
    claimed = sp.expand(sum(c * g for c, g in zip(proposal.cofactors, proposal.generators, strict=True)))
    if not _zero(relation**proposal.link_power - claimed):
        return None
    if any(not _zero(g.subs(box.witness)) for g in proposal.generators):
        return None
    target = sp.simplify(proposal.target_expression.subs(box.witness))
    if not _zero(polynomial.as_expr().subs(T, target)):
        return None
    lower, upper = proposal.target_interval
    if sp.simplify(target > lower) is not sp.true or sp.simplify(target < upper) is not sp.true:
        return None
    if polynomial.count_roots(lower, upper) != 1:
        return None
    ordinal = 0
    selected = 0
    for (left, right), multiplicity in polynomial.intervals(eps=sp.Rational(1, 10**30)):
        if right <= lower:
            ordinal += multiplicity
        elif left >= upper:
            continue
        elif lower <= left and right <= upper:
            selected += multiplicity
        else:
            return None
    return (coefficients, ordinal) if selected == 1 else None


def _family2_ablation_proof():
    case = _positive_radical_only(random.Random(SEED))
    proposal = case.source.proposal
    h = proposal.target_expression
    generator = proposal.generators[0]
    variable = case.source.root_box.variables[0]
    basis = sp.groebner((generator,), variable, order="lex", domain=sp.QQ)
    direct_remainder = basis.reduce(h)[1]
    square_remainder = basis.reduce(sp.expand(h**2))[1]
    return {
        "direct_remainder_nonzero": not _zero(direct_remainder),
        "square_remainder_zero": _zero(square_remainder),
    }


def run_campaign():
    rng = random.Random(SEED)
    rows = {family: {"radical": [], "direct": [], "false": []} for family in FAMILIES}
    metamorphic_failures = 0
    kll_contract_failures = 0

    for family, generator in FAMILIES.items():
        for _scenario in range(SCENARIOS):
            scenario_seed = rng.randrange(1 << 30)
            variants = []
            for transform in TRANSFORMS:
                case = _transform(generator(random.Random(scenario_seed)), transform)
                radical = solve(case.source, allow_radical_power=True)
                direct = solve(case.source, allow_radical_power=False)
                oracle_radical = _oracle(case.source, True)
                oracle_direct = _oracle(case.source, False)
                false = int(radical.emitted != (oracle_radical is not None))
                false += int(direct.emitted != (oracle_direct is not None))
                if radical.emitted:
                    false += int(radical.descriptor != oracle_radical)
                if direct.emitted:
                    false += int(direct.descriptor != oracle_direct)
                kll_contract_failures += int(
                    radical.kll_calls != 1 or direct.kll_calls != 1
                    or radical.kll_bits != KLL_BITS or direct.kll_bits != KLL_BITS
                )
                rows[family]["radical"].append(int(radical.emitted))
                rows[family]["direct"].append(int(direct.emitted))
                rows[family]["false"].append(false)
                variants.append((radical.emitted, radical.descriptor, direct.emitted, direct.descriptor, false))
            metamorphic_failures += int(len(set(variants)) != 1)

    family_results = {}
    positive_gain = 0
    negative_emit = 0
    false_authority = 0
    recovery_families = []
    for family, row in rows.items():
        radical_rate = mean(row["radical"])
        direct_rate = mean(row["direct"])
        false_authority += sum(row["false"])
        if family in POSITIVE:
            positive_gain += int(radical_rate == 1)
            if radical_rate > direct_rate:
                recovery_families.append(family)
        else:
            negative_emit += sum(row["radical"]) + sum(row["direct"])
        family_results[family] = {
            "radical_link_emit_rate": radical_rate,
            "direct_link_emit_rate": direct_rate,
            "rate_delta": radical_rate - direct_rate,
            "false_authority_count": sum(row["false"]),
        }

    ablation = _family2_ablation_proof()
    gate = (
        positive_gain == 3
        and recovery_families == ["squared-generator-radical-only"]
        and negative_emit == 0
        and false_authority == 0
        and metamorphic_failures == 0
        and kll_contract_failures == 0
        and ablation["direct_remainder_nonzero"]
        and ablation["square_remainder_zero"]
    )
    return {
        "schema": "geotarget.theorem-bounded-kll-radical-power-target-link-d0/v1",
        "seed": SEED,
        "cpu": 14,
        "synthetic_only": True,
        "instance_count": len(FAMILIES) * SCENARIOS * len(TRANSFORMS),
        "trace_count": len(FAMILIES) * SCENARIOS * len(TRANSFORMS) * 2,
        "family2_ablation_proof": ablation,
        "family_results": family_results,
        "aggregate": {
            "positive_gain_family_count": positive_gain,
            "radical_only_recovery_families": recovery_families,
            "negative_emit_count": negative_emit,
            "false_authority_count": false_authority,
            "metamorphic_failure_count": metamorphic_failures,
            "kll_contract_failure_count": kll_contract_failures,
            "kll_calls_per_arm": 1,
            "kll_bits": KLL_BITS,
            "fixed_radical_power": 2,
            "decision": "ADVANCE" if gate else "STOP",
        },
    }


if __name__ == "__main__":
    print(json.dumps(run_campaign(), indent=2, sort_keys=True))
