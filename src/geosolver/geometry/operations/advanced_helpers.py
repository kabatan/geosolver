"""Shared math helpers for advanced geometry operations."""

from __future__ import annotations

from typing import Any


def compute_polar_coeffs(cx: Any, cy: Any, radius: Any, px: Any, py: Any) -> tuple[Any, Any, Any]:
    a_coeff = px - cx
    b_coeff = py - cy
    c_coeff = -cx * a_coeff - cy * b_coeff - radius**2
    return a_coeff, b_coeff, c_coeff


def compute_pole_point(
    line_a: Any,
    line_b: Any,
    line_c: Any,
    cx: Any,
    cy: Any,
    radius: Any,
    tolerance: Any,
) -> tuple[Any, Any] | None:
    denom = line_a * cx + line_b * cy + line_c
    if abs(denom) < tolerance:
        return None
    k_value = -(radius**2) / denom
    return cx + k_value * line_a, cy + k_value * line_b


def compute_radical_axis_coeffs(
    x1: Any,
    y1: Any,
    r1: Any,
    x2: Any,
    y2: Any,
    r2: Any,
) -> tuple[Any, Any, Any]:
    a_coeff = 2 * (x2 - x1)
    b_coeff = 2 * (y2 - y1)
    sq1 = x1**2 + y1**2 - r1**2
    sq2 = x2**2 + y2**2 - r2**2
    c_coeff = sq1 - sq2
    return a_coeff, b_coeff, c_coeff
