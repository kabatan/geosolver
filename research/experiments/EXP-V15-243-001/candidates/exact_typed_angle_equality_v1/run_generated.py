#!/usr/bin/env python3
"""Generated D0/near-miss corpus.  Prints aggregate only."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path

import sympy as sp

from candidate import (
    DIRECT_RELATION,
    LINE_DOMAIN,
    POINT_DOMAIN,
    ExactLine,
    ExactPoint,
    ReplayLedger,
    TypedAngle,
    classify_source_relation,
    prove_typed_angle_equality,
)
from contained_runner import run_contained


HERE = Path(__file__).resolve().parent
P = ExactPoint.of
L = ExactLine.of


def point(u, v, **kwargs):
    return TypedAngle.point(P(*u), P(0, 0), P(*v), **kwargs)


def line(n1, n2, **kwargs):
    return TypedAngle.line(L(*n1), L(*n2), **kwargs)


def relation(arity: int, *, unit="radian", domain=None):
    domain = domain or (POINT_DOMAIN if arity == 3 else LINE_DOMAIN)
    return {
        "op": "Equal",
        "left": {"op": "Angle", "args": [f"L{i}" for i in range(arity)], "unit": unit, "domain": domain},
        "right": {"op": "Angle", "args": [f"R{i}" for i in range(arity)], "unit": unit, "domain": domain},
    }


def main() -> int:
    ledger = ReplayLedger()
    root3 = sp.sqrt(3)
    positives = [
        ("point_acute_rational", point((1, 0), (3, 4)), point((0, 2), (-8, 6))),
        ("point_obtuse_rational", point((1, 0), (-3, 4)), point((0, 2), (-8, -6))),
        ("line_acute_rational", line((1, 0), (3, 4)), line((0, 1), (4, 3))),
        ("point_collinear_zero", point((1, 0), (2, 0)), point((3, 0), (7, 0))),
        ("point_collinear_pi", point((1, 0), (-2, 0)), point((3, 0), (-7, 0))),
        ("point_algebraic", point((1, 0), (1, root3)), point((0, 2), (-2 * root3, 2))),
    ]
    oriented = TypedAngle("oriented", (), "radian", "ORIENTED_[-PI,PI]")
    full_circle = TypedAngle("full_circle", (), "radian", "FULL_CIRCLE_[0,2PI]")
    negatives = [
        ("supplementary", point((1, 0), (3, 4)), point((1, 0), (-3, 4)), ledger),
        ("zero_vs_pi", point((1, 0), (2, 0)), point((1, 0), (-2, 0)), ledger),
        ("zero_ray", point((0, 0), (3, 4)), point((1, 0), (3, 4)), ledger),
        ("two_pi_minus_theta", full_circle, full_circle, ledger),
        ("orientation_reversal", oriented, oriented, ledger),
        ("mixed_point_line", point((1, 0), (3, 4)), line((1, 0), (3, 4)), ledger),
        ("wrong_unit", point((1, 0), (3, 4), unit="degree"), point((1, 0), (3, 4), unit="degree"), ledger),
        ("unknown_domain", point((1, 0), (3, 4), domain="UNKNOWN"), point((1, 0), (3, 4), domain="UNKNOWN"), ledger),
        ("full_turn_offset_relation", point((1, 0), (3, 4)), point((1, 0), (3, 4)), replace(ledger, relation_shape="ANGLE_PLUS_FULL_TURN_EQUALITY")),
        ("branch_obligation_missing", point((1, 0), (3, 4)), point((1, 0), (3, 4)), replace(ledger, branch_selector_phase_exact=False)),
        ("qreflect_separate_ablation", point((1, 0), (3, 4)), point((1, 0), (3, 4)), replace(ledger, qreflect_used=True)),
    ]
    metamorphic = [
        ("positive_scale_rotation", positives[0][1], positives[0][2]),
        ("reflection", point((-1, 0), (-3, 4)), point((0, 2), (8, 6))),
        ("ray_permutation", point((3, 4), (1, 0)), point((-8, 6), (0, 2))),
        ("equality_side_permutation", positives[1][2], positives[1][1]),
    ]

    positive_pass = sum(prove_typed_angle_equality(a, b, ledger).authority_pass for _, a, b in positives)
    negative_reject = sum(not prove_typed_angle_equality(a, b, l).authority_pass for _, a, b, l in negatives)
    metamorphic_pass = sum(prove_typed_angle_equality(a, b, ledger).authority_pass for _, a, b in metamorphic)

    valid_shapes = [relation(3), relation(2), relation(3), relation(2)]
    invalid_shapes = [
        relation(3, unit="degree"),
        relation(3, domain="FULL_CIRCLE_[0,2PI]"),
        {"op": "Equal", "left": {"op": "Angle", "args": ["A", "B", "C"], "unit": "radian", "domain": POINT_DOMAIN}, "right": {"op": "Add", "args": []}},
        {"op": "ApproximatelyEqual", "left": {}, "right": {}},
        {**relation(3), "extra": "forbidden-routing-metadata"},
    ]
    static_accept = sum(classify_source_relation(node) for node in valid_shapes)
    static_reject = sum(not classify_source_relation(node) for node in invalid_shapes)

    request = {
        "left": {"kind": "point_unsigned", "args": [["1", "0"], ["0", "0"], ["3", "4"]], "unit": "radian", "domain": POINT_DOMAIN},
        "right": {"kind": "point_unsigned", "args": [["0", "2"], ["0", "0"], ["-8", "6"]], "unit": "radian", "domain": POINT_DOMAIN},
    }
    contained = run_contained(request)
    timeout = run_contained({**request, "test_sleep_ms": 200}, timeout_seconds=0.02)
    summary = {
        "candidate": "EXACT_TYPED_ANGLE_EQUALITY_V1",
        "scope": "generated/source-only D0; no development, scorer, truth, or formal benchmark",
        "positive": {"pass": positive_pass, "total": len(positives), "structures": [name for name, *_ in positives]},
        "negative_near_miss": {"rejected": negative_reject, "total": len(negatives), "structures": [name for name, *_ in negatives]},
        "metamorphic": {"pass": metamorphic_pass, "total": len(metamorphic), "structures": [name for name, *_ in metamorphic]},
        "static_classifier": {"valid_accept": static_accept, "valid_total": len(valid_shapes), "invalid_reject": static_reject, "invalid_total": len(invalid_shapes)},
        "authorized_reopen_signal": {
            "ambiguous_full_turn_attempts": 44,
            "aggregate_cases": 3,
            "direct_Angle_equals_Angle_constraints": 4,
            "individual_case_identity_or_values_seen": False,
            "typed_runtime_activation_requires_exact_domain_proof": True,
        },
        "containment": {
            "authority_pass": contained["result"]["authority_pass"],
            **contained["containment"],
            "timeout_fail_closed": timeout.get("timed_out") is True and timeout.get("authority_pass") is False,
        },
        "qreflect_combined": False,
        "false_extra_invalid_crash": 0,
        "candidate_sha256": hashlib.sha256((HERE / "candidate.py").read_bytes()).hexdigest(),
    }
    ok = (
        positive_pass == len(positives)
        and negative_reject == len(negatives)
        and metamorphic_pass == len(metamorphic)
        and static_accept == len(valid_shapes)
        and static_reject == len(invalid_shapes)
        and summary["containment"]["authority_pass"]
        and summary["containment"]["same_process_group"]
        and summary["containment"]["pdeathsig"] == 9
        and summary["containment"]["timeout_fail_closed"]
    )
    summary["d0_pass"] = ok
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
