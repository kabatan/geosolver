#!/usr/bin/env python3
"""Synthetic-only D0 for bounded real-radical SOS target identities."""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import os
from pathlib import Path
import random
import time

import sympy as sp

from candidate import Certificate, Source, solve


SEED = int(os.environ.get("SEED", "731904"))
SCENARIOS = int(os.environ.get("SCENARIOS", "32"))


@dataclass(frozen=True)
class Family:
    name: str
    source: Source
    certificate: Certificate
    expected_identity: bool
    expected_join: bool
    primary_recovery: bool = False


def rat(rng, nonzero=False):
    while True:
        value = sp.Rational(rng.randint(-7, 7), rng.randint(1, 7))
        if not nonzero or value:
            return value


def cert(generators, cofactors, monomials, diagonal, m=1):
    return Certificate(
        tuple(map(sp.sympify, generators)), tuple(map(sp.sympify, cofactors)), m,
        tuple(map(sp.sympify, monomials)),
        sp.ImmutableMatrix(sp.diag(*diagonal)),
    )


def families(rng):
    x, y, z = sp.symbols("x y z")
    q = rat(rng)

    g1 = x**2 + y**2
    positive_direct_failure = Family(
        "sos_only_x2_y2",
        Source((x, y), (g1,), q + x, q, True, True, True),
        cert((g1,), (1,), (y,), (1,)),
        True, True, True,
    )

    scale = rat(rng, nonzero=True)
    u, v = x + y, x - y
    g_rotated = sp.expand(scale * (u**2 + v**2))
    positive_rotated = Family(
        "rotated_scaled",
        Source((x, y), (g_rotated,), q + u, q, True, True, True),
        Certificate(
            (g_rotated,), (sp.cancel(1 / scale),), 1, (x, y),
            sp.ImmutableMatrix([[1, -1], [-1, 1]]),
        ),
        True, True, True,
    )

    g2 = y**2 + z**2
    positive_chain = Family(
        "two_generator_chain",
        Source((x, y, z), (g1, g2), q + x, q, True, True, True),
        cert((g1, g2), (1, 1), (y, z), (2, 1)),
        True, True, True,
    )

    complex_g = x**2 + 1
    complex_only = Family(
        "complex_only_no_existence_join",
        Source((x,), (complex_g,), x, sp.Rational(0), True, False, True),
        cert((complex_g,), (1,), (sp.Integer(1),), (1,)),
        True, False,
    )

    unit = Family(
        "unit_ideal",
        Source((x,), (sp.Integer(1),), x, sp.Rational(0), True, True, True),
        cert((sp.Integer(1),), (x**2 + 1,), (sp.Integer(1),), (1,)),
        False, False,
    )

    wrong_q = Family(
        "wrong_q",
        replace(positive_direct_failure.source, target_q=q + 1),
        positive_direct_failure.certificate,
        False, False,
    )

    omitted = Family(
        "omitted_generator",
        positive_chain.source,
        cert((g1,), (1,), (y, z), (2, 1)),
        False, False,
    )

    tampered = Family(
        "tampered_gram",
        positive_direct_failure.source,
        replace(positive_direct_failure.certificate, gram=sp.ImmutableMatrix([[-1]])),
        False, False,
    )

    inequality = Family(
        "inequality_or_guard_in_generator_lane",
        replace(positive_direct_failure.source, equality_only=False),
        positive_direct_failure.certificate,
        False, False,
    )

    opaque = Family(
        "opaque_transcendental",
        Source((x,), (sp.sin(x),), x, sp.Rational(0), True, True, True),
        cert((sp.sin(x),), (x,), (sp.Integer(1),), (1,)),
        False, False,
    )
    return (
        positive_direct_failure, positive_rotated, positive_chain,
        complex_only, unit, wrong_q, omitted, tampered, inequality, opaque,
    )


def rename_variables(family, serial):
    fresh = sp.symbols(" ".join(f"r{serial}_{i}" for i in range(len(family.source.variables))))
    if len(family.source.variables) == 1:
        fresh = (fresh,)
    mapping = dict(zip(family.source.variables, reversed(fresh), strict=True))
    source = replace(
        family.source,
        variables=tuple(reversed(fresh)),
        equality_generators=tuple(g.xreplace(mapping) for g in family.source.equality_generators),
        raw_target=family.source.raw_target.xreplace(mapping),
    )
    certificate = replace(
        family.certificate,
        generators=tuple(g.xreplace(mapping) for g in family.certificate.generators),
        cofactors=tuple(a.xreplace(mapping) for a in family.certificate.cofactors),
        sos_monomials=tuple(v.xreplace(mapping) for v in family.certificate.sos_monomials),
    )
    return replace(family, source=source, certificate=certificate)


def permute_scale_equations(family, rng):
    source_indices = tuple(reversed(range(len(family.source.equality_generators))))
    scales = tuple(rat(rng, nonzero=True) for _ in source_indices)
    source_generators = tuple(
        scales[j] * family.source.equality_generators[index]
        for j, index in enumerate(source_indices)
    )
    if len(family.certificate.generators) == len(family.source.equality_generators):
        certificate_generators = source_generators
        cofactors = tuple(
            family.certificate.cofactors[index] / scales[j]
            for j, index in enumerate(source_indices)
        )
    else:
        certificate_generators = family.certificate.generators
        cofactors = family.certificate.cofactors
    return replace(
        family,
        source=replace(family.source, equality_generators=source_generators),
        certificate=replace(
            family.certificate,
            generators=certificate_generators,
            cofactors=cofactors,
        ),
    )


def affine_target(family, rng):
    alpha = rat(rng, nonzero=True)
    beta = rat(rng)
    exponent = 2 * family.certificate.m
    return replace(
        family,
        source=replace(
            family.source,
            raw_target=sp.expand(alpha * family.source.raw_target + beta),
            target_q=sp.expand(alpha * family.source.target_q + beta),
        ),
        certificate=replace(
            family.certificate,
            cofactors=tuple(sp.expand(alpha**exponent * a) for a in family.certificate.cofactors),
            gram=sp.ImmutableMatrix(alpha**exponent * sp.Matrix(family.certificate.gram)),
        ),
    )


def signature(result):
    return (
        result.identity_ready, result.join_ready, result.authority_emitted,
        result.status, result.direct_membership, result.square_membership,
        result.join_required,
    )


def run_campaign():
    rng = random.Random(SEED)
    counts = {}
    failures = []
    metamorphic_failures = 0
    false_authority = 0
    negative_join = 0
    total = 0
    started = time.perf_counter()

    for scenario in range(SCENARIOS):
        for family in families(rng):
            variants = (
                ("identity", family),
                ("variable_permutation", rename_variables(family, scenario)),
                ("equation_permutation_row_scaling", permute_scale_equations(family, rng)),
                ("affine_target", affine_target(family, rng)),
            )
            baseline_signature = None
            for transform, variant in variants:
                result = solve(variant.source, variant.certificate)
                total += 1
                false_authority += int(result.authority_emitted)
                if not variant.expected_join:
                    negative_join += int(result.join_ready)
                record = counts.setdefault(variant.name, {
                    "trials": 0, "identity_ready": 0, "join_ready": 0,
                    "direct_membership": 0, "square_membership": 0,
                    "authority_emitted": 0,
                })
                record["trials"] += 1
                for field in (
                    "identity_ready", "join_ready", "direct_membership",
                    "square_membership", "authority_emitted",
                ):
                    record[field] += int(getattr(result, field))
                expected = (variant.expected_identity, variant.expected_join, False)
                observed = (result.identity_ready, result.join_ready, result.authority_emitted)
                if observed != expected:
                    failures.append({
                        "scenario": scenario, "family": variant.name,
                        "transform": transform, "expected": expected,
                        "observed": observed, "status": result.status,
                    })
                current_signature = signature(result)
                if baseline_signature is None:
                    baseline_signature = current_signature
                elif current_signature != baseline_signature:
                    metamorphic_failures += 1
                    failures.append({
                        "scenario": scenario, "family": variant.name,
                        "transform": transform, "metamorphic_mismatch": True,
                        "baseline": baseline_signature, "observed": current_signature,
                    })

    primary = {
        name: {
            "join_rate": values["join_ready"] / values["trials"],
            "direct_membership_rate": values["direct_membership"] / values["trials"],
            "square_membership_rate": values["square_membership"] / values["trials"],
        }
        for name, values in counts.items()
        if name in {"sos_only_x2_y2", "rotated_scaled", "two_generator_chain"}
    }
    gate = (
        not failures
        and false_authority == 0
        and negative_join == 0
        and metamorphic_failures == 0
        and len(primary) == 3
        and all(
            values["join_rate"] == 1
            and values["direct_membership_rate"] == 0
            and values["square_membership_rate"] == 0
            for values in primary.values()
        )
        and counts["complex_only_no_existence_join"]["identity_ready"]
        == counts["complex_only_no_existence_join"]["trials"]
        and counts["complex_only_no_existence_join"]["join_ready"] == 0
        and counts["unit_ideal"]["identity_ready"] == 0
    )
    candidate_path = Path(__file__).with_name("candidate.py")
    result = {
        "arm": "REAL_RADICAL_SOS_TARGET_IDENTITY_V1",
        "scope": "synthetic_only_no_formal_no_truth_no_98",
        "seed": SEED,
        "scenarios": SCENARIOS,
        "instances": total,
        "elapsed_seconds": time.perf_counter() - started,
        "mechanism_hash": hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
        "primary_recovery": primary,
        "families": counts,
        "false_authority_count": false_authority,
        "negative_join_count": negative_join,
        "metamorphic_failure_count": metamorphic_failures,
        "failure_count": len(failures),
        "failure_examples": failures[:10],
        "authority_policy": "identity is side-link only; existence and full guard/branch replay remain external obligations",
        "gate": "SYNTHETIC_D0_PASS" if gate else "SYNTHETIC_D0_FAIL",
    }
    return result


def main():
    result = run_campaign()
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["gate"] == "SYNTHETIC_D0_PASS" else 1)


if __name__ == "__main__":
    main()
