"""Truth-free generated polynomial families for the Hermite D0 gate."""

from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
from typing import Any


POSITIVE_CASES: dict[str, dict[str, Any]] = {
    "regular-zero-dimensional-degree2": {
        "variables": ["x", "t"],
        "target_variable": "t",
        "equations": ["x**2 - 2"],
        "target": "x",
        "polynomial": "t**2 - 2",
        "interval": ["1", "2"],
        "guards": ["x"],
    },
    "nonradical-singular-degree1": {
        "variables": ["x", "y", "t"],
        "target_variable": "t",
        "equations": ["x - 1", "(y - 1)**2"],
        "target": "x",
        "polynomial": "t - 1",
        "interval": ["1/2", "3/2"],
        "guards": ["x", "y"],
    },
    "positive-dimensional-overall-finite-target-fibre-degree4": {
        "variables": ["x", "y", "t"],
        "target_variable": "t",
        "equations": ["y - x**2"],
        "target": "x",
        "polynomial": "(t**2 - 1)*(t**2 - 4)",
        "interval": ["3/2", "5/2"],
        "guards": ["x", "y"],
    },
}


NEGATIVE_CASES: dict[str, tuple[dict[str, Any], str]] = {
    "near-miss-no-root-in-interval": (
        {**POSITIVE_CASES["regular-zero-dimensional-degree2"], "interval": ["2", "3"]},
        "isolating-interval-not-single-real-root",
    ),
    "strict-guard-wrong-sign": (
        {**POSITIVE_CASES["regular-zero-dimensional-degree2"], "interval": ["-2", "-1"], "guards": ["x"]},
        "no-root-satisfies-strict-guards",
    ),
    "strict-guard-boundary": (
        {**POSITIVE_CASES["nonradical-singular-degree1"], "guards": ["x - 1", "y"]},
        "no-root-satisfies-strict-guards",
    ),
    "nonsquarefree-target-polynomial": (
        {**POSITIVE_CASES["nonradical-singular-degree1"], "polynomial": "(t - 1)**2"},
        "target-polynomial-not-square-free",
    ),
    "positive-dimensional-target-fibre": (
        {
            "variables": ["x", "y", "t"],
            "target_variable": "t",
            "equations": ["x**2 - 1"],
            "target": "x",
            "polynomial": "t - 1",
            "interval": ["1/2", "3/2"],
            "guards": ["x"],
        },
        "target-fibre-not-zero-dimensional",
    ),
    "inconsistent-target-fibre": (
        {**POSITIVE_CASES["regular-zero-dimensional-degree2"], "polynomial": "t - 1", "interval": ["1/2", "3/2"]},
        "inconsistent-target-fibre",
    ),
}


def permuted(problem: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(problem)
    out["variables"] = list(reversed(out["variables"]))
    out["equations"] = list(reversed(out["equations"]))
    out["guards"] = list(reversed(out["guards"]))
    return out


def affine_target(problem: dict[str, Any], scale: int = -2, shift: int = 3) -> dict[str, Any]:
    """Apply u=scale*tau+shift, retaining the input target variable's name."""

    out = deepcopy(problem)
    old_target = out["target"]
    old_polynomial = out["polynomial"]
    target_variable = out["target_variable"]
    # Multiplying by scale**degree is unnecessary: any nonzero QQ scalar
    # defines the same zero set, and SymPy accepts the substituted rational
    # polynomial directly.
    out["target"] = f"({scale})*({old_target}) + ({shift})"
    out["polynomial"] = f"({old_polynomial.replace(target_variable, f'(({target_variable} - ({shift}))/({scale}))')})"
    left, right = (Fraction(value) for value in out["interval"])
    transformed_values = [scale * left + shift, scale * right + shift]
    if scale < 0:
        transformed_values.reverse()
    out["interval"] = [str(value) for value in transformed_values]
    return out


__all__ = ["NEGATIVE_CASES", "POSITIVE_CASES", "affine_target", "permuted"]
