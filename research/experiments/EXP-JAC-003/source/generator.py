"""Frozen JAC003 development candidate-input generator.

This module has no dependency on prior Jacobian experiments or product solver
code.  It emits only candidate-visible typed graphs, opaque joins, bounds,
scales, budgets and 32 deterministic starts.  Gold and assessment fields are
intentionally absent.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable, Sequence
from typing import Any


SCHEMA_VERSION = "exp-jac-003-candidate-inputs/v1"
GRAPH_VERSION = "exp-jac-003-typed-graph/v1"
NAMESPACE = "jac3-v1"
CASE_COUNT_PER_FAMILY = 16
START_COUNT = 32

TRIG_ROWS: tuple[tuple[int, int, float], ...] = (
    (2, 2, 0.02), (3, 2, 0.02), (2, 3, 0.02), (3, 3, 0.02),
    (2, 4, 0.02), (3, 4, 0.02), (2, 2, 0.2), (3, 2, 0.2),
    (2, 3, 0.2), (3, 3, 0.2), (2, 4, 0.2), (3, 4, 0.2),
    (2, 2, 0.02), (3, 3, 0.02), (2, 4, 0.2), (3, 2, 0.2),
)

RATIONAL_ROWS: tuple[tuple[int, int, float, str], ...] = (
    (7, 2, 1.0, "balanced"), (13, 3, 10.0, "skewed"),
    (23, 5, 1.0, "balanced"), (7, 3, 10.0, "skewed"),
    (13, 5, 1.0, "skewed"), (23, 2, 10.0, "balanced"),
    (7, 5, 10.0, "balanced"), (13, 2, 1.0, "skewed"),
    (23, 3, 10.0, "skewed"), (7, 2, 1.0, "skewed"),
    (13, 3, 10.0, "balanced"), (23, 5, 1.0, "skewed"),
    (7, 3, 10.0, "balanced"), (13, 5, 1.0, "balanced"),
    (23, 2, 10.0, "skewed"), (23, 3, 1.0, "balanced"),
)

HEX_ROWS: tuple[tuple[int, str, float], ...] = (
    (1, "axial", 0.05), (1, "alternating", 0.05),
    (2, "axial", 0.05), (2, "alternating", 0.05),
    (3, "axial", 0.05), (3, "alternating", 0.05),
    (1, "axial", 5.0), (1, "alternating", 5.0),
    (2, "axial", 5.0), (2, "alternating", 5.0),
    (3, "axial", 5.0), (3, "alternating", 5.0),
    (1, "alternating", 0.05), (2, "axial", 5.0),
    (3, "alternating", 5.0), (3, "axial", 0.05),
)

DENSE_ROWS: tuple[tuple[int, float, float, str], ...] = (
    (5, 0.65, 0.0, "smooth-switch"), (9, 0.85, 1.0e-8, "piecewise"),
    (15, 1.0, 0.03, "smooth-switch"), (5, 0.85, 0.03, "piecewise"),
    (9, 1.0, 0.0, "smooth-switch"), (15, 0.65, 1.0e-8, "piecewise"),
    (5, 1.0, 1.0e-8, "piecewise"), (9, 0.65, 0.03, "smooth-switch"),
    (15, 0.85, 0.0, "piecewise"), (5, 0.65, 0.03, "smooth-switch"),
    (9, 0.85, 0.0, "piecewise"), (15, 1.0, 1.0e-8, "smooth-switch"),
    (5, 0.85, 0.0, "smooth-switch"), (9, 1.0, 0.03, "piecewise"),
    (15, 0.65, 0.03, "smooth-switch"), (15, 0.85, 1.0e-8, "piecewise"),
)


def _digest(namespace: str) -> bytes:
    return hashlib.sha256(namespace.encode("utf-8")).digest()


def _unit(namespace: str) -> float:
    return int.from_bytes(_digest(namespace)[:8], "big") / 2**64


def _signed(namespace: str) -> float:
    return 2.0 * _unit(namespace) - 1.0


def opaque_case_id(family_ordinal: int, case_index: int) -> str:
    text = f"{NAMESPACE}/case/{family_ordinal}/{case_index}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


def _root_vector(family_ordinal: int, case_index: int, size: int) -> list[float]:
    return [
        0.55 * _signed(f"{NAMESPACE}/offset/{family_ordinal}/{case_index}/{column}")
        for column in range(size)
    ]


def _permutation(family_ordinal: int, case_index: int, size: int, tag: str) -> list[int]:
    return sorted(
        range(size),
        key=lambda value: (_digest(f"{NAMESPACE}/{tag}/{family_ordinal}/{case_index}/{value}"), value),
    )


def _starts(
    family_ordinal: int,
    case_index: int,
    center: Sequence[float],
    lower: Sequence[float],
    upper: Sequence[float],
) -> list[list[float]]:
    start_seed = 2_830_000 + 100 * family_ordinal + case_index
    starts: list[list[float]] = [list(center)]
    radii = (0.025, 0.08, 0.2, 0.45, 0.7)
    for start_index in range(1, START_COUNT):
        radius = radii[(start_index - 1) % len(radii)]
        raw = [
            _signed(f"{NAMESPACE}/start/{start_seed}/{start_index}/{column}")
            for column in range(len(center))
        ]
        norm = math.sqrt(sum(value * value for value in raw)) or 1.0
        point = []
        for column, value in enumerate(raw):
            candidate = center[column] + radius * math.sqrt(len(center)) * value / norm
            point.append(min(upper[column], max(lower[column], candidate)))
        starts.append(point)
    if len(starts) != START_COUNT:
        raise AssertionError("start-count drift")
    return starts


def _reference_nodes(size: int) -> list[dict[str, Any]]:
    return [
        {
            "kind": "reference",
            "node_id": f"v{column:03d}",
            "value_type": "real",
            "variable_slot": column,
        }
        for column in range(size)
    ]


def _relation_nodes(operation: str, supports: Sequence[Sequence[int]]) -> list[dict[str, Any]]:
    return [
        {
            "kind": "call",
            "node_id": f"r{row:03d}",
            "operation": operation,
            "value_type": "relation",
            "arguments": [f"v{column:03d}" for column in support],
        }
        for row, support in enumerate(supports)
    ]


def _base_case(
    opaque_id: str,
    family_ordinal: int,
    case_index: int,
    size: int,
    supports: Sequence[Sequence[int]],
    operation: str,
    program: dict[str, Any],
    center: Sequence[float],
    lower: Sequence[float],
    upper: Sequence[float],
    *,
    extra_nodes: Iterable[dict[str, Any]] = (),
    domains: Sequence[str] = (),
    branches: Sequence[str] = (),
) -> dict[str, Any]:
    nodes = _reference_nodes(size)
    nodes.extend(_relation_nodes(operation, supports))
    nodes.extend(extra_nodes)
    return {
        "opaque_case_id": opaque_id,
        "typed_graph": {
            "schema_version": GRAPH_VERSION,
            "nodes": nodes,
            "relations": [f"r{row:03d}" for row in range(size)],
            "domains": list(domains),
            "branches": list(branches),
        },
        "oracle_program": program,
        "variable_count": size,
        "residual_count": size,
        "origins": [0.0] * size,
        "scales": [1.0] * size,
        "lower": list(lower),
        "upper": list(upper),
        "starts": _starts(family_ordinal, case_index, center, lower, upper),
        "budgets": {
            "max_iterations": 250,
            "max_evaluations": 2000,
            "observation_wall_seconds": 60,
            "hard_wall_seconds": 180,
        },
    }


def _trig_case(case_index: int) -> dict[str, Any]:
    ordinal = 1
    branching, depth, amplitude = TRIG_ROWS[case_index]
    size = (branching ** (depth + 1) - 1) // (branching - 1)
    permutation = _permutation(ordinal, case_index, size, "trig-permutation")
    children: list[list[int]] = [[] for _ in range(size)]
    for logical in range(size):
        slot = permutation[logical]
        first = branching * logical + 1
        children[slot] = [
            permutation[child]
            for child in range(first, min(first + branching, size))
        ]
    supports = [sorted({row, *children[row]}) for row in range(size)]
    center = _root_vector(ordinal, case_index, size)
    program = {
        "kind": "sin-cos-tree-v1",
        "offsets": [-value for value in center],
        "children": children,
        "amplitude": amplitude,
    }
    return _base_case(
        opaque_case_id(ordinal, case_index), ordinal, case_index, size, supports,
        "jac3.blackbox/sin_cos_relation", program, center,
        [-1.5] * size, [1.5] * size,
    )


def _rational_edges(case_index: int, size: int, width: int, overlap: str) -> list[list[int]]:
    edges: list[list[int]] = []
    for row in range(size):
        if overlap == "balanced":
            ordered = sorted(
                range(size),
                key=lambda column: (
                    _digest(f"{NAMESPACE}/rational-edge/2/{case_index}/{row}/{column}"),
                    column,
                ),
            )
        else:
            hubs = list(range(min(max(width - 1, 1), size)))
            tail = sorted(
                (column for column in range(size) if column not in hubs),
                key=lambda column: (
                    _digest(f"{NAMESPACE}/rational-skew/2/{case_index}/{row}/{column}"),
                    column,
                ),
            )
            ordered = hubs + tail
        selected = sorted(ordered[:width])
        if len(selected) != width or len(set(selected)) != width:
            raise AssertionError("rational hyperedge drift")
        edges.append(selected)
    return edges


def _rational_case(case_index: int) -> dict[str, Any]:
    ordinal = 2
    size, width, margin, overlap = RATIONAL_ROWS[case_index]
    edges = _rational_edges(case_index, size, width, overlap)
    supports = [sorted({row, *edges[row]}) for row in range(size)]
    center = _root_vector(ordinal, case_index, size)
    alpha = 0.12 / width
    program = {
        "kind": "safe-rational-hypergraph-v1",
        "offsets": [-value for value in center],
        "edges": edges,
        "margin": margin,
        "alpha": alpha,
    }
    domain_nodes = [
        {
            "kind": "call",
            "node_id": f"d{row:03d}",
            "operation": "jac3.blackbox/safe_denominator_domain",
            "value_type": "domain",
            "arguments": [f"v{column:03d}" for column in edge],
        }
        for row, edge in enumerate(edges)
    ]
    return _base_case(
        opaque_case_id(ordinal, case_index), ordinal, case_index, size, supports,
        "jac3.blackbox/safe_rational_relation", program, center,
        [-1.5] * size, [1.5] * size,
        extra_nodes=domain_nodes,
        domains=[f"d{row:03d}" for row in range(size)],
    )


def _hex_coordinates(rings: int) -> list[tuple[int, int]]:
    coordinates = []
    for q in range(-rings, rings + 1):
        for r in range(-rings, rings + 1):
            if max(abs(q), abs(r), abs(q + r)) <= rings:
                coordinates.append((q, r))
    return sorted(coordinates)


def _hex_case(case_index: int) -> dict[str, Any]:
    ordinal = 3
    rings, stencil, curvature = HEX_ROWS[case_index]
    coordinates = _hex_coordinates(rings)
    size = len(coordinates)
    coordinate_index = {coordinate: index for index, coordinate in enumerate(coordinates)}
    permutation = _permutation(ordinal, case_index, size, "hex-permutation")
    directions = ((1, 0), (0, 1), (-1, 1), (-1, 0), (0, -1), (1, -1))
    neighbours: list[list[int]] = [[] for _ in range(size)]
    for logical, (q, r) in enumerate(coordinates):
        selected_directions = directions
        if stencil == "alternating":
            parity = (q - r) & 1
            selected_directions = directions[parity::2]
        adjacent = []
        for dq, dr in selected_directions:
            target = (q + dq, r + dr)
            if target in coordinate_index:
                adjacent.append(permutation[coordinate_index[target]])
        neighbours[permutation[logical]] = sorted(adjacent)
    supports = [sorted({row, *neighbours[row]}) for row in range(size)]
    center = _root_vector(ordinal, case_index, size)
    program = {
        "kind": "hex-ring-atan-v1",
        "offsets": [-value for value in center],
        "neighbours": neighbours,
        "curvature": curvature,
        "alpha": 0.055,
    }
    return _base_case(
        opaque_case_id(ordinal, case_index), ordinal, case_index, size, supports,
        "jac3.blackbox/hex_atan_relation", program, center,
        [-1.5] * size, [1.5] * size,
    )


def _dense_matrix(case_index: int, size: int, density: float, tag: str) -> list[list[float]]:
    matrix: list[list[float]] = []
    for row in range(size):
        values = []
        for column in range(size):
            keep = row == column or _unit(
                f"{NAMESPACE}/{tag}-keep/4/{case_index}/{row}/{column}"
            ) <= density
            value = 0.0
            if keep:
                value = 0.35 * _signed(
                    f"{NAMESPACE}/{tag}-value/4/{case_index}/{row}/{column}"
                ) / math.sqrt(size)
            values.append(value)
        matrix.append(values)
    return matrix


def _dense_case(case_index: int) -> dict[str, Any]:
    ordinal = 4
    size, density, boundary_distance, chart = DENSE_ROWS[case_index]
    lower = [-0.75] * size
    upper = [0.75] * size
    center = _root_vector(ordinal, case_index, size)
    center[0] = lower[0] + boundary_distance
    matrix = _dense_matrix(case_index, size, density, "dense")
    alternate = _dense_matrix(case_index, size, density, "dense-alt")
    weights = [
        _signed(f"{NAMESPACE}/chart-weight/4/{case_index}/{column}") / math.sqrt(size)
        for column in range(size)
    ]
    chart_offset = boundary_distance if case_index % 2 == 0 else -boundary_distance
    threshold = sum(weight * value for weight, value in zip(weights, center, strict=True)) - chart_offset
    supports = [
        sorted({
            row,
            *(column for column, value in enumerate(matrix[row]) if value != 0.0),
            *(column for column, value in enumerate(alternate[row]) if value != 0.0),
        })
        for row in range(size)
    ]
    program = {
        "kind": "dense-chart-v1",
        "offsets": [-value for value in center],
        "matrix": matrix,
        "alternate_matrix": alternate,
        "chart": chart,
        "chart_weights": weights,
        "chart_threshold": threshold,
        "smooth_gain": 0.08,
    }
    branch_node = {
        "kind": "call",
        "node_id": "chart000",
        "operation": "jac3.blackbox/stable_chart",
        "value_type": "choice",
        "arguments": [f"v{column:03d}" for column in range(size)],
    }
    return _base_case(
        opaque_case_id(ordinal, case_index), ordinal, case_index, size, supports,
        "jac3.blackbox/dense_chart_relation", program, center,
        lower, upper,
        extra_nodes=(branch_node,),
        branches=("chart000",),
    )


def build_candidate_document() -> dict[str, Any]:
    cases = []
    for builder in (_trig_case, _rational_case, _hex_case, _dense_case):
        cases.extend(builder(index) for index in range(CASE_COUNT_PER_FAMILY))
    cases.sort(key=lambda case: case["opaque_case_id"])
    opaque_ids = [case["opaque_case_id"] for case in cases]
    if len(cases) != 64 or len(set(opaque_ids)) != 64:
        raise AssertionError("development allocation or opaque-ID collision")
    if any(len(case["starts"]) != START_COUNT for case in cases):
        raise AssertionError("start allocation drift")
    return {
        "schema_version": SCHEMA_VERSION,
        "namespace": "opaque-development-v1",
        "case_count": len(cases),
        "starts_per_case": START_COUNT,
        "cases": cases,
    }


if __name__ == "__main__":
    raise SystemExit("generator.py is a library; invoke materialize_development.py once")
