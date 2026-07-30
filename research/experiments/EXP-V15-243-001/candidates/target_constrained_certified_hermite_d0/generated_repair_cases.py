"""Anonymous generated source strata for Repair A."""

from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
from typing import Any, Mapping

import sympy as sp


def descriptor(coefficients: list[int], left: str, right: str, root_index: int) -> dict[str, Any]:
    return {
        "minimal_polynomial_high_to_low": coefficients,
        "selected_real_root_index": root_index,
        "isolating_interval": {
            "left": left,
            "right": right,
            "multiplicity": 1,
            "real_root_index": root_index,
        },
        "proposal_relation_low_to_high": list(reversed(coefficients)),
        "confirmation_relation_low_to_high": list(reversed(coefficients)),
        "target_768": "generated",
        "target_1024": "generated",
    }


POSITIVE: dict[str, tuple[dict[str, Any], dict[str, Any], list[str]]] = {
    "anonymous-stratum-a-degree1-ge-ne": (
        {
            "id": "anonymous-a",
            "task": "solve",
            "variables": {"names": ["x"]},
            "bounds": [["0", "2"]],
            "construction": [],
            "constraints": [{"def": "x", "value": "1"}],
            "guards": ["AssumeNe(x,0)"],
            "answer": "x",
            "post_process": "",
        },
        descriptor([1, -1], "0", "2", 0),
        ["1.0"],
    ),
    "anonymous-stratum-b-degree2-strict": (
        {
            "id": "anonymous-b",
            "task": "solve",
            "variables": {"names": ["x"]},
            "construction": [],
            "constraints": [{"def": "x**2", "value": "2"}],
            "guards": ["AssumeGt(x,0)"],
            "answer": "x",
            "post_process": "",
        },
        descriptor([1, 0, -2], "1", "2", 1),
        ["1.4142135623730951"],
    ),
    "anonymous-stratum-c-degree4-strict": (
        {
            "id": "anonymous-c",
            "task": "solve",
            "variables": {"names": ["x"]},
            "construction": [],
            "constraints": [{"def": "x**4 - 10*x**2 + 9", "value": "0"}],
            "guards": ["AssumeGt(x,0)"],
            "answer": "x",
            "post_process": "",
        },
        descriptor([1, 0, -10, 0, 9], "2", "4", 3),
        ["3.0"],
    ),
}


def renamed(document: Mapping[str, Any]) -> dict[str, Any]:
    out = deepcopy(document)
    out["variables"]["names"] = ["z"]
    for constraint in out["constraints"]:
        constraint["def"] = constraint["def"].replace("x", "z")
        constraint["value"] = str(constraint["value"]).replace("x", "z")
    out["guards"] = [guard.replace("x", "z") for guard in out["guards"]]
    out["answer"] = out["answer"].replace("x", "z")
    return out


def affine_target(
    document: Mapping[str, Any],
    target_descriptor: Mapping[str, Any],
    *,
    scale: int = 2,
    shift: int = 3,
) -> tuple[dict[str, Any], dict[str, Any]]:
    out = deepcopy(document)
    out["answer"] = f"({scale})*({out['answer']}) + ({shift})"
    coefficients = target_descriptor["minimal_polynomial_high_to_low"]
    old = sp.Symbol("old")
    new = sp.Symbol("new")
    polynomial = sum(
        coefficient * old ** (len(coefficients) - index - 1)
        for index, coefficient in enumerate(coefficients)
    )
    transformed = sp.Poly(
        sp.expand(scale ** (len(coefficients) - 1) * polynomial.subs(old, (new - shift) / scale)),
        new,
        domain=sp.QQ,
    )
    denominator_lcm = sp.ilcm(*[int(value.q) for value in transformed.all_coeffs()])
    integer_coefficients = [int(value * denominator_lcm) for value in transformed.all_coeffs()]
    content = abs(integer_coefficients[0])
    for value in integer_coefficients[1:]:
        content = int(sp.igcd(content, abs(value)))
    integer_coefficients = [value // max(1, content) for value in integer_coefficients]
    if integer_coefficients[0] < 0:
        integer_coefficients = [-value for value in integer_coefficients]
    isolator = target_descriptor["isolating_interval"]
    left = scale * Fraction(isolator["left"]) + shift
    right = scale * Fraction(isolator["right"]) + shift
    return out, descriptor(
        integer_coefficients,
        str(left),
        str(right),
        int(target_descriptor["selected_real_root_index"]),
    )


NEGATIVE: dict[str, tuple[dict[str, Any], dict[str, Any], list[str], str]] = {
    "wrong-sign-strict-guard": (
        deepcopy(POSITIVE["anonymous-stratum-b-degree2-strict"][0]),
        descriptor([1, 0, -2], "-2", "-1", 0),
        ["-1.4142135623730951"],
        "no-root-satisfies-strict-guards",
    ),
    "descriptor-source-mismatch": (
        deepcopy(POSITIVE["anonymous-stratum-a-degree1-ge-ne"][0]),
        descriptor([1, -2], "3/2", "5/2", 0),
        ["1.0"],
        "inconsistent-target-fibre",
    ),
    "strict-boundary-zero": (
        {
            "id": "anonymous-boundary",
            "task": "solve",
            "variables": {"names": ["x"]},
            "construction": [],
            "constraints": [{"def": "x", "value": "0"}],
            "guards": ["AssumeGt(x,0)"],
            "answer": "x",
            "post_process": "",
        },
        descriptor([1, 0], "-1", "1", 0),
        ["0.0"],
        "no-root-satisfies-strict-guards",
    ),
    "definedness-ledger-unsupported": (
        {
            "id": "anonymous-definedness",
            "task": "solve",
            "variables": {"names": ["x"]},
            "construction": [],
            "constraints": [{"def": "x", "value": "1"}],
            "guards": [],
            "answer": "sqrt(x+3)",
            "post_process": "",
        },
        descriptor([1, -2], "1", "3", 0),
        ["1.0"],
        "definedness-replay-not-supported-by-thin-seam",
    ),
    "boolean-selector-unsupported": (
        {
            "id": "anonymous-selector",
            "task": "solve",
            "variables": {"names": []},
            "construction": [
                {"name": "O", "expr": "Point(0,0)"},
                {"name": "C", "expr": "Circle(O,1)"},
                {"name": "E", "expr": "Point(1,0)"},
                {"name": "L", "expr": "Line(Point(-2,0),Point(2,0))"},
                {"name": "Q", "expr": "Intersect(L,C,exclude=E)"},
            ],
            "constraints": [{"def": "Q.y", "value": "0"}],
            "guards": [],
            "answer": "Q.x",
            "post_process": "",
        },
        descriptor([1, 1], "-2", "0", 0),
        [],
        "boolean-selector-replay-not-supported",
    ),
    "phase-sheet-unsupported": (
        {
            "id": "anonymous-phase",
            "task": "solve",
            "variables": {"names": ["theta"]},
            "construction": [],
            "constraints": [{"def": "cos(theta)", "value": "1"}],
            "guards": ["Bound(theta,(0,1),inclusive=True)"],
            "answer": "cos(theta)",
            "post_process": "",
        },
        descriptor([1, -1], "0", "2", 0),
        ["0.0"],
        "phase-sheet-replay-not-supported",
    ),
}


__all__ = ["NEGATIVE", "POSITIVE", "affine_target", "descriptor", "renamed"]
