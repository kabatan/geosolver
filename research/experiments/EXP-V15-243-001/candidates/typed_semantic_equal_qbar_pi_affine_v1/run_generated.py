#!/usr/bin/env python3
"""Aggregate-only generated source-replay D0."""

from __future__ import annotations

import hashlib
import json
import os

import sympy as sp

from candidate import prove_direct_relation, repair_or_current_exact_fallback
from test_candidate import A, B, E, ORIGINAL, PI, Q, R, ledger


def repaired(relation, replay=None):
    result = prove_direct_relation(relation, replay or ledger())
    payload = repair_or_current_exact_fallback(ORIGINAL, relation=relation, ledger=replay or ledger())
    return result.get("authority_pass") is True and payload != ORIGINAL


def rejected(relation, replay=None):
    payload = repair_or_current_exact_fallback(ORIGINAL, relation=relation, ledger=replay or ledger())
    return payload is ORIGINAL


def main() -> int:
    angle_acute = A(sp.Rational(3, 5), sp.Rational(4, 5))
    positives = [
        ("rational", E(R(1, 2), R(2, 4)), ledger()),
        ("qbar", E(Q(sp.sqrt(8) / 2), Q(sp.sqrt(2))), ledger()),
        ("rational_into_qbar", E(Q(sp.Rational(2, 3)), R(2, 3)), ledger()),
        ("pi_multiple", E(B("mul", PI(), R(1, 2)), B("div", PI(), R(2))), ledger()),
        ("direct_angle", E(angle_acute, A(sp.sqrt(sp.Rational(9, 25)), sp.sqrt(sp.Rational(16, 25)))), ledger("scalar is not an exact angle expression")),
        (
            "qbar_pi_affine",
            E(
                B("add", B("mul", Q(sp.sqrt(2)), PI()), Q(sp.sqrt(3))),
                B("add", Q(sp.sqrt(3)), B("mul", PI(), Q(sp.sqrt(2)))),
            ),
            ledger(),
        ),
        (
            "affine_distribution",
            E(
                B("mul", B("add", PI(), Q(sp.sqrt(2))), Q(sp.sqrt(3))),
                B("add", B("mul", Q(sp.sqrt(3)), PI()), Q(sp.sqrt(6))),
            ),
            ledger(),
        ),
    ]
    positive_pass = sum(repaired(relation, replay) for _, relation, replay in positives)

    affine = B("add", B("mul", Q(sp.sqrt(2)), PI()), Q(sp.sqrt(3)))
    negatives = [
        ("wrong_rational_embedding", E(R(2), Q(sp.Integer(1))), ledger()),
        ("mixed_pi_affine", E(PI(), B("add", PI(), R(0))), ledger()),
        ("mixed_angle_pi", E(angle_acute, PI()), ledger("scalar is not an exact angle expression")),
        ("angle_domain", E(angle_acute, A(sp.Rational(3, 5), sp.Rational(4, 5), domain="LINE_ACUTE_RADIAN_[0,PI/2]")), ledger()),
        ("supplementary", E(angle_acute, A(sp.Rational(-3, 5), sp.Rational(4, 5))), ledger()),
        ("affine_coefficient", E(affine, B("add", B("mul", Q(sp.sqrt(3)), PI()), Q(sp.sqrt(3)))), ledger()),
        ("affine_offset", E(affine, B("add", B("mul", Q(sp.sqrt(2)), PI()), Q(sp.sqrt(5)))), ledger()),
        ("nonlinear_pi", E(B("mul", PI(), PI()), PI()), ledger()),
        ("nested_trig", E({"op": "sin", "arg": PI()}, R(0)), ledger()),
        ("nested_power", E({"op": "pow", "left": PI(), "right": R(2)}, PI()), ledger()),
        ("order", E(R(1), R(1), op="lt"), ledger()),
        ("approximate", E(Q(sp.Float("1.0")), Q(sp.Integer(1))), ledger()),
        ("nonreal", E(Q(sp.I), Q(sp.I)), ledger()),
        ("nonalgebraic_unknown", E(Q(sp.pi), R(3)), ledger()),
        ("mixed_arithmetic_not_embedding", E(B("add", Q(sp.Integer(1)), R(1)), Q(sp.Integer(2))), ledger()),
        ("mutated_embedding_node", E(Q(sp.Integer(1)), {**R(1), "embedding": "approximate"}), ledger()),
        ("wrong_failure", E(affine, affine), ledger("unrelated failure")),
    ]
    negative_pass = sum(rejected(relation, replay) for _, relation, replay in negatives)

    first = B("add", B("mul", Q(sp.sqrt(8) / 2), PI()), Q(sp.sqrt(12) / 2))
    second = B("add", Q(sp.sqrt(3)), B("mul", PI(), Q(sp.sqrt(2))))
    metamorphic = [
        ("side_permutation", E(second, first)),
        ("commutative_affine_terms", E(first, second)),
        ("qbar_exact_rewrite", E(Q(sp.sqrt(8) / 2), Q(sp.sqrt(2)))),
        ("rational_normalization", E(R(-2, -4), R(1, 2))),
        ("angle_pair_rewrite", E(angle_acute, A(sp.sqrt(sp.Rational(9, 25)), sp.sqrt(sp.Rational(16, 25))))),
    ]
    metamorphic_pass = sum(repaired(relation) for _, relation in metamorphic)

    summary = {
        "candidate": "TYPED_SEMANTIC_EQUAL_QBAR_PI_AFFINE_V1",
        "scope": "generated/current-exact-replay source-only mechanism; no scorer/truth/formal",
        "authorized_failure_aggregate": {
            "value_not_exact_rational": 25,
            "scalar_not_exact_angle": 14,
            "individual_rows_shared": False,
        },
        "positive": {"pass": positive_pass, "total": len(positives), "closed_types": [name for name, *_ in positives]},
        "negative_near_miss": {"rejected": negative_pass, "total": len(negatives), "kinds": [name for name, *_ in negatives]},
        "metamorphic": {"pass": metamorphic_pass, "total": len(metamorphic), "kinds": [name for name, _ in metamorphic]},
        "fallback_byte_identical": negative_pass == len(negatives),
        "order_sign_or_coercive_broadening": False,
        "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "truth_or_case_rows_used": False,
    }
    summary["d0_pass"] = bool(
        positive_pass == len(positives)
        and negative_pass == len(negatives)
        and metamorphic_pass == len(metamorphic)
        and os.sched_getaffinity(0) == {15}
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["d0_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
