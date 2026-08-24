"""Geometry degeneracy penalization for autosolve candidates."""

from __future__ import annotations

import ast
from collections.abc import Sequence
from typing import Any
from mpmath import mp

DEGENERACY_NEAR_ZERO_EDGE = mp.mpf("1e-12")
DEGENERACY_FLAT_THRESHOLD = mp.mpf("1e-5")
DEGENERACY_EXP_SCALE = mp.mpf("1e4")
DEGENERACY_CLUMP_PENALTY = mp.mpf("10")

def _extract_angle_args(expr: str) -> list[tuple[str, str, str]]:
    """Extracts triplets of point names from Angle(A, B, C) calls in the AST."""
    try:
        tree = ast.parse(expr)
    except SyntaxError:
        return []
    
    triplets = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id != "Angle" or len(node.args) != 3:
            continue
        names: list[str] = []
        for arg in node.args:
            if isinstance(arg, ast.Name):
                names.append(arg.id)
        if len(names) == 3:
            triplets.append((names[0], names[1], names[2]))
    return triplets


def _as_mpf_distance(
    distance_fn: Any,
    lhs: Any,
    rhs: Any,
    *,
    context: str,
) -> Any:
    _ = context
    distance_value = distance_fn(lhs, rhs)
    return mp.mpf(distance_value)


def _extract_angle_triplets(spec: Any) -> list[tuple[str, str, str]]:
    triplets: list[tuple[str, str, str]] = []
    constraints = getattr(spec, "constraints", None)
    if isinstance(constraints, Sequence):
        for expr in constraints:
            if isinstance(expr, str):
                triplets.extend(_extract_angle_args(expr))
    objective_expr = getattr(spec, "objective_expr", None)
    if isinstance(objective_expr, str) and objective_expr:
        triplets.extend(_extract_angle_args(objective_expr))
    answer_expr = getattr(spec, "answer_expr", None)
    if isinstance(answer_expr, str) and answer_expr:
        triplets.extend(_extract_angle_args(answer_expr))
    return triplets


def compute_degeneracy_penalty(
    values: list[Any],
    spec: Any,
    context: dict[str, Any],
    precision: int = 15,
) -> Any:
    """Computes a penalty score for geometrically degenerate configurations.

    Args:
        values: The candidate variable values.
        spec: The IRSpec describing the problem.
        context: The geometry context containing backend/constructed variables.
        precision: Current precision.
        
    Returns:
        A float penalty score >= 0.0. Higher means more degenerate.
    """
    _ = (values, precision)
    penalty = mp.mpf("0")
    if spec is None:
        return penalty

    angle_triplets = _extract_angle_triplets(spec)
    if not angle_triplets:
        return penalty

    try:
        distance_fn = context.get("Distance")
        if not callable(distance_fn):
            return penalty

        for A_name, B_name, C_name in angle_triplets:
            A = context.get(A_name)
            B = context.get(B_name)
            C = context.get(C_name)
            if A is None or B is None or C is None:
                continue

            ab = _as_mpf_distance(distance_fn, A, B, context=f"degeneracy.ab:{A_name}{B_name}")
            bc = _as_mpf_distance(distance_fn, B, C, context=f"degeneracy.bc:{B_name}{C_name}")
            ca = _as_mpf_distance(distance_fn, C, A, context=f"degeneracy.ca:{C_name}{A_name}")

            max_edge = max(ab, bc, ca)
            if max_edge < DEGENERACY_NEAR_ZERO_EDGE:
                penalty += DEGENERACY_CLUMP_PENALTY
                continue

            edges = sorted([ab, bc, ca])
            gap = (edges[0] + edges[1]) - edges[2]
            relative_gap = gap / max_edge
            if relative_gap < DEGENERACY_FLAT_THRESHOLD:
                score = mp.e ** (-DEGENERACY_EXP_SCALE * relative_gap)
                penalty += score
    except Exception:
        pass

    return penalty
