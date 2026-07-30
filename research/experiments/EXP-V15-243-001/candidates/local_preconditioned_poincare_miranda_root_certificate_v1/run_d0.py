#!/usr/bin/env python3
"""Fixed synthetic D0/adversary for local preconditioned Poincare--Miranda."""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import random
from statistics import mean
from typing import Callable

import sympy as sp

from candidate import Source, bernstein_range, solve


SEED = 20260731 + 41
SCENARIOS = 32
TRANSFORMS = ("identity", "variable-permutation", "equation-scale-permutation", "rational-affine")
POSITIVE = ("singular-odd-x3", "coupled-singular-odd", "regular-rotated")


@dataclass(frozen=True)
class Case:
    source: Source
    positive: bool
    family: str


def _q(rng, low=-2, high=2):
    return sp.Rational(rng.randint(low, high), rng.randint(1, 4))


def _halfwidth(rng):
    return rng.choice((sp.Rational(1, 2), sp.Rational(1), sp.Rational(3, 2), sp.Rational(2)))


def _cover(variables, centers):
    radius = sum((variable - center) ** 2 for variable, center in zip(variables, centers, strict=True))
    return (
        (sp.Integer(10) - radius,),
        tuple(sp.Integer(5) + variable - center for variable, center in zip(variables, centers, strict=True)),
        tuple(sp.Integer(5) - variable + center for variable, center in zip(variables, centers, strict=True)),
        (sp.Integer(9) - radius,),
    )


def _source_from_active(rng, family, active, variables, centers, box, A, *, omitted=(), omitted_coefficients=()):
    guards, branches, defined, principal = _cover(variables, centers)
    equations = tuple(active) + tuple(omitted)
    epsilon = sp.Rational(1, 256)
    target_constant = _q(rng)
    target_cofactors = tuple(epsilon * (index + 1) for index in range(len(active))) + tuple(sp.Rational(0) for _ in omitted)
    target = target_constant + sum(c * f for c, f in zip(target_cofactors, equations, strict=True))
    source = Source(
        tuple(variables), equations, box, tuple(range(len(active))), tuple(omitted_coefficients),
        sp.ImmutableMatrix(A), tuple(1 for _ in variables),
        guards, branches, defined, principal, True,
        sp.expand(target), target_constant, target_cofactors,
        (target_constant - 2, target_constant + 2), True, 1,
    )
    return Case(source, True, family)


def _singular_odd(rng):
    x = sp.Symbol("x", real=True)
    center = _q(rng)
    half = _halfwidth(rng)
    dx = x - center
    return _source_from_active(
        rng, "singular-odd-x3", (dx**3,), (x,), (center,), {x: (center - half, center + half)},
        sp.Matrix([[1]]),
    )


def _coupled_singular(rng):
    x, y = sp.symbols("x y", real=True)
    centers = (_q(rng), _q(rng))
    half = _halfwidth(rng)
    z = sp.Matrix(((x - centers[0]) ** 3, (y - centers[1]) ** 3))
    rotation = sp.Matrix([[1, 1], [1, -2]])
    active = tuple(rotation * z)
    box = {x: (centers[0] - half, centers[0] + half), y: (centers[1] - half, centers[1] + half)}
    return _source_from_active(rng, "coupled-singular-odd", active, (x, y), centers, box, rotation.inv())


def _regular_rotated(rng):
    x, y = sp.symbols("x y", real=True)
    centers = (_q(rng), _q(rng))
    half = _halfwidth(rng)
    z = sp.Matrix((x - centers[0], y - centers[1]))
    rotation = sp.Matrix([[1, 2], [-2, 1]])
    active = tuple(rotation * z)
    omitted = (active[0] - active[1],)
    box = {x: (centers[0] - half, centers[0] + half), y: (centers[1] - half, centers[1] + half)}
    return _source_from_active(
        rng, "regular-rotated", active, (x, y), centers, box, rotation.inv(),
        omitted=omitted, omitted_coefficients=((sp.Rational(1), sp.Rational(-1)),),
    )


def _replace_active(case, active, A=None, orientations=None):
    source = case.source
    equations = tuple(active) + source.equations[len(source.active_indices):]
    epsilon = sp.Rational(1, 256)
    target_cofactors = tuple(epsilon * (index + 1) for index in range(len(active))) + tuple(
        sp.Rational(0) for _ in equations[len(active):]
    )
    target = source.target_constant + sum(c * f for c, f in zip(target_cofactors, equations, strict=True))
    return Case(replace(
        source, equations=equations,
        preconditioner=source.preconditioner if A is None else sp.ImmutableMatrix(A),
        orientations=source.orientations if orientations is None else tuple(orientations),
        target_expression=sp.expand(target), target_cofactors=target_cofactors,
    ), False, case.family)


def _even_touch(rng):
    case = _singular_odd(rng)
    x = case.source.variables[0]
    lower, upper = case.source.box[x]
    center = (lower + upper) / 2
    return _replace_active(case, ((x - center) ** 2,))


def _face_zero(rng):
    case = _singular_odd(rng)
    x = case.source.variables[0]
    lower, upper = case.source.box[x]
    center = (lower + upper) / 2
    half = (upper - lower) / 2
    return _replace_active(case, ((x - center) * (x - center + half),))


def _wrong_orientation(rng):
    case = _singular_odd(rng)
    return Case(replace(case.source, orientations=(-1,)), False, "wrong-orientation")


def _singular_A(rng):
    case = _coupled_singular(rng)
    return Case(replace(case.source, preconditioner=sp.ImmutableMatrix.zeros(2)), False, "singular-A")


def _guard_boundary(rng):
    case = _singular_odd(rng)
    x = case.source.variables[0]
    lower, _upper = case.source.box[x]
    return Case(replace(case.source, guards_positive=case.source.guards_positive + (x - lower,)), False, "guard-boundary")


def _omitted_not_consequence(rng):
    case = _regular_rotated(rng)
    equations = case.source.equations[:-1] + (case.source.equations[-1] + 1,)
    return Case(replace(case.source, equations=equations), False, "omitted-not-consequence")


def _discontinuous_branch(rng):
    case = _singular_odd(rng)
    x = case.source.variables[0]
    branch = sp.Piecewise((sp.Integer(1), x >= 0), (sp.Integer(2), True))
    return Case(replace(case.source, branch_positive=(branch,)), False, "discontinuous-branch")


def _cofactor_mutation(rng):
    case = _singular_odd(rng)
    mutated = tuple(2 * value for value in case.source.target_cofactors)
    return Case(replace(case.source, target_cofactors=mutated), False, "cofactor-mutation")


FAMILIES: dict[str, Callable[[random.Random], Case]] = {
    "singular-odd-x3": _singular_odd,
    "coupled-singular-odd": _coupled_singular,
    "regular-rotated": _regular_rotated,
    "negative-even-touch": _even_touch,
    "negative-face-zero": _face_zero,
    "negative-wrong-orientation": _wrong_orientation,
    "negative-singular-A": _singular_A,
    "negative-guard-boundary": _guard_boundary,
    "negative-omitted-not-consequence": _omitted_not_consequence,
    "negative-discontinuous-branch": _discontinuous_branch,
    "negative-cofactor-mutation": _cofactor_mutation,
}


def _substitute_source(source, mapping, variables, box, orientations=None):
    return Source(
        tuple(variables), tuple(e.xreplace(mapping) for e in source.equations), box,
        source.active_indices, source.omitted_consequences, source.preconditioner,
        source.orientations if orientations is None else tuple(orientations),
        tuple(e.xreplace(mapping) for e in source.guards_positive),
        tuple(e.xreplace(mapping) for e in source.branch_positive),
        tuple(e.xreplace(mapping) for e in source.defined_positive),
        tuple(e.xreplace(mapping) for e in source.principal_positive),
        source.cover_reversible, source.target_expression.xreplace(mapping),
        source.target_constant, source.target_cofactors, source.target_isolator,
        source.typed_square, source.proposal_rounds,
    )


def _transform(case, name):
    source = case.source
    n = len(source.variables)
    if name == "identity":
        return case
    if name == "variable-permutation":
        fresh = sp.symbols(f"v0:{n}", real=True)
        mapping = dict(zip(source.variables, reversed(fresh), strict=True))
        box = {mapping[v]: source.box[v] for v in source.variables}
        transformed = _substitute_source(source, mapping, tuple(mapping[v] for v in source.variables), box)
        return Case(transformed, case.positive, case.family)
    if name == "equation-scale-permutation":
        permutation = tuple(reversed(range(n)))
        scales = tuple(sp.Rational((-1) ** j * (j + 2), j + 1) for j in range(n))
        old_active = source.equations[:n]
        new_active = tuple(scales[j] * old_active[permutation[j]] for j in range(n))
        omitted = source.equations[n:]
        new_omitted = []
        new_consequences = []
        for equation, coefficients in zip(omitted, source.omitted_consequences, strict=True):
            new_omitted.append(equation)
            new_consequences.append(tuple(coefficients[permutation[j]] / scales[j] for j in range(n)))
        A = sp.Matrix(source.preconditioner)
        new_A = sp.zeros(n)
        for j in range(n):
            new_A[:, j] = A[:, permutation[j]] / scales[j]
        active_target = source.target_cofactors[:n]
        new_target = tuple(active_target[permutation[j]] / scales[j] for j in range(n)) + source.target_cofactors[n:]
        transformed = replace(
            source, equations=new_active + tuple(new_omitted),
            omitted_consequences=tuple(new_consequences), preconditioner=sp.ImmutableMatrix(new_A),
            target_cofactors=new_target,
        )
        return Case(transformed, case.positive, case.family)
    if name == "rational-affine":
        fresh = sp.symbols(f"u0:{n}", real=True)
        scales = tuple(sp.Rational(-1 if index % 2 == 0 else 2) for index in range(n))
        shifts = tuple(sp.Rational(index + 1, 3) for index in range(n))
        mapping = {v: scale * u + shift for v, u, scale, shift in zip(source.variables, fresh, scales, shifts, strict=True)}
        box = {}
        for v, u, scale, shift in zip(source.variables, fresh, scales, shifts, strict=True):
            endpoints = tuple((bound - shift) / scale for bound in source.box[v])
            box[u] = (min(endpoints), max(endpoints))
        orientations = tuple(o * (1 if scale > 0 else -1) for o, scale in zip(source.orientations, scales, strict=True))
        transformed = _substitute_source(source, mapping, fresh, box, orientations)
        return Case(transformed, case.positive, case.family)
    raise ValueError(name)


def _hash_source(source):
    payload = "|".join(sp.srepr(e) for e in source.equations).encode()
    return hashlib.sha256(payload).hexdigest()


def _hash_box(source):
    payload = "|".join(f"{v}:{source.box[v]}" for v in source.variables).encode()
    return hashlib.sha256(payload).hexdigest()


def _krawczyk_regular_ablation(source):
    active = tuple(source.equations[index] for index in source.active_indices)
    determinant = sp.factor(sp.Matrix(active).jacobian(source.variables).det())
    lower, upper, _height = bernstein_range(determinant, source.variables, source.box)
    return not (lower <= 0 <= upper)


def run_campaign():
    rng = random.Random(SEED)
    rows = {family: {"pm": [], "krawczyk": [], "false": []} for family in FAMILIES}
    metamorphic_failures = 0
    max_height = 0
    subdivisions = 0
    proposal_failures = 0
    singular_det_pm_success = 0
    source_hashes = set()
    local_box_hashes = set()

    for family, generator in FAMILIES.items():
        for _scenario in range(SCENARIOS):
            scenario_seed = rng.randrange(1 << 30)
            base = generator(random.Random(scenario_seed))
            if base.positive:
                source_hashes.add(_hash_source(base.source))
                local_box_hashes.add(_hash_box(base.source))
            variants = []
            for transform in TRANSFORMS:
                case = _transform(generator(random.Random(scenario_seed)), transform)
                result = solve(case.source)
                krawczyk = _krawczyk_regular_ablation(case.source) if case.positive else False
                false = int(result.emitted != case.positive)
                rows[family]["pm"].append(int(result.emitted))
                rows[family]["krawczyk"].append(int(krawczyk))
                rows[family]["false"].append(false)
                max_height = max(max_height, result.max_face_coefficient_height)
                subdivisions += result.subdivisions
                proposal_failures += int(result.proposal_rounds != 1)
                singular_det_pm_success += int(result.emitted and result.det_j_interval_contains_zero)
                variants.append((result.emitted, result.descriptor, result.det_j_interval_contains_zero, false))
            metamorphic_failures += int(len(set(variants)) != 1)

    family_results = {}
    pm_positive = 0
    pm_gain = 0
    negative_emit = 0
    false_authority = 0
    for family, row in rows.items():
        pm_rate = mean(row["pm"])
        k_rate = mean(row["krawczyk"])
        false_authority += sum(row["false"])
        if family in POSITIVE:
            pm_positive += int(pm_rate == 1)
            pm_gain += int(pm_rate > k_rate)
        else:
            negative_emit += sum(row["pm"])
        family_results[family] = {
            "pm_emit_rate": pm_rate,
            "krawczyk_regular_emit_rate": k_rate,
            "rate_delta": pm_rate - k_rate,
            "false_authority_count": sum(row["false"]),
        }

    gate = (
        pm_positive == 3 and pm_gain >= 2 and negative_emit == 0
        and false_authority == 0 and metamorphic_failures == 0
        and proposal_failures == 0 and subdivisions == 0
        and len(local_box_hashes) >= 4 and len(source_hashes) >= 2
        and singular_det_pm_success >= 1 and max_height <= 4096
    )
    return {
        "schema": "geotarget.local-preconditioned-poincare-miranda-d0/v1",
        "seed": SEED,
        "cpu": 14,
        "synthetic_only": True,
        "instance_count": len(FAMILIES) * SCENARIOS * len(TRANSFORMS),
        "trace_count": len(FAMILIES) * SCENARIOS * len(TRANSFORMS) * 2,
        "family_results": family_results,
        "aggregate": {
            "pm_positive_family_count": pm_positive,
            "pm_gain_over_krawczyk_family_count": pm_gain,
            "negative_emit_count": negative_emit,
            "false_authority_count": false_authority,
            "metamorphic_failure_count": metamorphic_failures,
            "proposal_round_failure_count": proposal_failures,
            "subdivision_count": subdivisions,
            "max_face_coefficient_height": max_height,
            "local_box_hash_count": len(local_box_hashes),
            "source_hash_count": len(source_hashes),
            "singular_det_interval_pm_success_count": singular_det_pm_success,
            "decision": "ADVANCE" if gate else "STOP",
        },
    }


if __name__ == "__main__":
    print(json.dumps(run_campaign(), indent=2, sort_keys=True))
