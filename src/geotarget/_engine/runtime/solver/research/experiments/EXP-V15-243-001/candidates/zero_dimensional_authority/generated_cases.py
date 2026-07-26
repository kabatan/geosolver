"""Small zero-dimensional source families for fail-closed tests."""

from __future__ import annotations

import json
from typing import Mapping


def source_bytes(
    answer: str,
    *,
    constraints: tuple[object, ...] = (),
    guards: tuple[str, ...] = (),
    variable_names: tuple[str, ...] = (),
) -> bytes:
    document: Mapping[str, object] = {
        "id": "GENERATED_ZERO_DIMENSIONAL",
        "task": "solve",
        "variables": {"names": list(variable_names)},
        "construction": [
            {"name": "A", "expr": "Point(0, 0)"},
            {"name": "B", "expr": "Point(3, 4)"},
        ],
        "constraints": list(constraints),
        "guards": list(guards),
        "answer": answer,
        "post_process": "",
    }
    return json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def generated_family() -> dict[str, bytes]:
    family = {
        "constant_rational_positive": source_bytes("7/3"),
        "rational_geometry_positive": source_bytes("Distance(A, B)**2"),
        "algebraic_geometry_positive": source_bytes("sqrt(Distance(A, B))"),
        "exact_conditions_positive": source_bytes(
            "Distance(A, B)**2",
            constraints=(
                {"def": "Distance(A, B)**2", "value": 25},
            ),
            guards=(
                "AssumeEq(Distance(A, B)**2, 25)",
                "AssumeGt(1, 0)",
                "Bound(1, (0, 2))",
            ),
        ),
        "extreme_numeric_guards_positive": source_bytes(
            "Distance(A, B)**2",
            guards=(
                "AssumeNe(0, 1e-1000)",
                "AssumeEq(1e1000, 10**1000)",
                "AssumeEq(5e-324, 5 / 10**324)",
                "AssumeLt(-1e-1000, 0)",
                "Bound(1e-1000, (0, 1e-999), inclusive=False)",
                "Bound(1e-1000, (1e-1000, 1e-999), inclusive=True)",
                "AssumeEq((1e-1000 + 2e-1000) * 1e1000, 3)",
            ),
        ),
        "nested_boolean_guards_positive": source_bytes(
            "Distance(A, B)**2",
            guards=(
                "Assume(And(AssumeEq(1e-1000, 1/10**1000), "
                "Or(AssumeEq(0, 1), Not(AssumeEq(0, 1)))))",
                "And(AssumeEq(0, 0), Not(AssumeEq(0, 1)))",
                "Assume((1e-1000 == 1/10**1000) and not (0 == 1))",
            ),
        ),
        "invalid_guard_near_miss": source_bytes(
            "Distance(A, B)**2", guards=("AssumeGt(1, 2)",)
        ),
        "near_unsatisfied_constraint": source_bytes(
            "Distance(A, B)**2",
            constraints=({"def": "0", "value": "1e-300"},),
        ),
        "near_unsatisfied_guard": source_bytes(
            "Distance(A, B)**2", guards=("AssumeEq(0, 1e-300)",)
        ),
        "underflow_guard_near_miss": source_bytes(
            "Distance(A, B)**2", guards=("AssumeEq(0, 1e-1000)",)
        ),
        "extreme_open_bound_near_miss": source_bytes(
            "Distance(A, B)**2",
            guards=(
                "Bound(1e-1000, (1e-1000, 1e-999), inclusive=False)",
            ),
        ),
        "nested_boolean_false_near_miss": source_bytes(
            "Distance(A, B)**2",
            guards=(
                "Assume(And(AssumeEq(0, 0), "
                "Or(AssumeEq(0, 1), Not(AssumeEq(0, 0)))))",
            ),
        ),
        "nested_boolean_unknown_under_not_near_miss": source_bytes(
            "Distance(A, B)**2",
            guards=("Assume(Not(Xor(True, False)))",),
        ),
        "unproved_geometry_guard": source_bytes(
            "Distance(A, B)**2", guards=("AssumeAcute(A, A, B)",)
        ),
        "transcendental_near_miss": source_bytes("pi"),
        "near_transcendental_shift_near_miss": source_bytes(
            "pi + 1/10**80"
        ),
        "algebraic_argument_sine_near_miss": source_bytes("sin(1)"),
        "inverse_trig_near_miss": source_bytes("acos(0)"),
        "unsupported_target_near_miss": source_bytes(
            "UnsupportedTargetFunction(1)"
        ),
        "positive_dimension_near_miss": source_bytes(
            "Distance(A, B)**2", variable_names=("x",)
        ),
    }
    unsafe_parametric = {
        "id": "GENERATED_ZERO_DIMENSIONAL",
        "task": "solve",
        "variables": {"names": []},
        "construction": [
            {"name": "O", "expr": "Point(0, 0)"},
            {"name": "C", "expr": "Circle(O, 1)"},
            {"name": "P", "expr": "PointOnCircle(C, sqrt(2))"},
        ],
        "constraints": [],
        "guards": [],
        "answer": "P.x",
        "post_process": "",
    }
    family["irrational_circle_phase_near_miss"] = json.dumps(
        unsafe_parametric,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return family


__all__ = ["generated_family", "source_bytes"]
