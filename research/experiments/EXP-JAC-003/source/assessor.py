"""Independent JAC003 Gold and analytic-Jacobian assessor.

This module deliberately does not import ``generator``.  Descriptor tables,
seed arithmetic, graph parameters and derivative formulas are repeated here as
an independent control.  The duplication is an experiment-safety boundary, not
shared production code.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from collections.abc import Sequence
from typing import Any


SCHEMA_VERSION = "exp-jac-003-assessor-truth/v1"
NAMESPACE = "jac3-v1"
START_COUNT = 32

TRIG_ROWS = (
    (2, 2, 0.02), (3, 2, 0.02), (2, 3, 0.02), (3, 3, 0.02),
    (2, 4, 0.02), (3, 4, 0.02), (2, 2, 0.2), (3, 2, 0.2),
    (2, 3, 0.2), (3, 3, 0.2), (2, 4, 0.2), (3, 4, 0.2),
    (2, 2, 0.02), (3, 3, 0.02), (2, 4, 0.2), (3, 2, 0.2),
)
RATIONAL_ROWS = (
    (7, 2, 1.0, "balanced"), (13, 3, 10.0, "skewed"),
    (23, 5, 1.0, "balanced"), (7, 3, 10.0, "skewed"),
    (13, 5, 1.0, "skewed"), (23, 2, 10.0, "balanced"),
    (7, 5, 10.0, "balanced"), (13, 2, 1.0, "skewed"),
    (23, 3, 10.0, "skewed"), (7, 2, 1.0, "skewed"),
    (13, 3, 10.0, "balanced"), (23, 5, 1.0, "skewed"),
    (7, 3, 10.0, "balanced"), (13, 5, 1.0, "balanced"),
    (23, 2, 10.0, "skewed"), (23, 3, 1.0, "balanced"),
)
HEX_ROWS = (
    (1, "axial", 0.05), (1, "alternating", 0.05),
    (2, "axial", 0.05), (2, "alternating", 0.05),
    (3, "axial", 0.05), (3, "alternating", 0.05),
    (1, "axial", 5.0), (1, "alternating", 5.0),
    (2, "axial", 5.0), (2, "alternating", 5.0),
    (3, "axial", 5.0), (3, "alternating", 5.0),
    (1, "alternating", 0.05), (2, "axial", 5.0),
    (3, "alternating", 5.0), (3, "axial", 0.05),
)
DENSE_ROWS = (
    (5, 0.65, 0.0, "smooth-switch"), (9, 0.85, 1.0e-8, "piecewise"),
    (15, 1.0, 0.03, "smooth-switch"), (5, 0.85, 0.03, "piecewise"),
    (9, 1.0, 0.0, "smooth-switch"), (15, 0.65, 1.0e-8, "piecewise"),
    (5, 1.0, 1.0e-8, "piecewise"), (9, 0.65, 0.03, "smooth-switch"),
    (15, 0.85, 0.0, "piecewise"), (5, 0.65, 0.03, "smooth-switch"),
    (9, 0.85, 0.0, "piecewise"), (15, 1.0, 1.0e-8, "smooth-switch"),
    (5, 0.85, 0.0, "smooth-switch"), (9, 1.0, 0.03, "piecewise"),
    (15, 0.65, 0.03, "smooth-switch"), (15, 0.85, 1.0e-8, "piecewise"),
)


def _digest(text: str) -> bytes:
    return hashlib.sha256(text.encode("utf-8")).digest()


def _unit(text: str) -> float:
    return int.from_bytes(_digest(text)[:8], "big") / 2**64


def _signed(text: str) -> float:
    return 2.0 * _unit(text) - 1.0


def _opaque_id(ordinal: int, index: int) -> str:
    return hashlib.sha256(
        f"{NAMESPACE}/case/{ordinal}/{index}".encode("utf-8")
    ).hexdigest()[:24]


def _configuration(ordinal: int, index: int, size: int) -> list[float]:
    return [
        0.55 * _signed(f"{NAMESPACE}/offset/{ordinal}/{index}/{column}")
        for column in range(size)
    ]


def _permutation(ordinal: int, index: int, size: int, tag: str) -> list[int]:
    return sorted(
        range(size),
        key=lambda value: (_digest(f"{NAMESPACE}/{tag}/{ordinal}/{index}/{value}"), value),
    )


def _rational_edges(index: int, size: int, width: int, overlap: str) -> list[list[int]]:
    result = []
    for row in range(size):
        if overlap == "balanced":
            order = sorted(
                range(size),
                key=lambda column: (
                    _digest(f"{NAMESPACE}/rational-edge/2/{index}/{row}/{column}"),
                    column,
                ),
            )
        else:
            hubs = list(range(min(max(width - 1, 1), size)))
            order = hubs + sorted(
                (column for column in range(size) if column not in hubs),
                key=lambda column: (
                    _digest(f"{NAMESPACE}/rational-skew/2/{index}/{row}/{column}"),
                    column,
                ),
            )
        result.append(sorted(order[:width]))
    return result


def _hex_coordinates(rings: int) -> list[tuple[int, int]]:
    return sorted(
        (q, r)
        for q in range(-rings, rings + 1)
        for r in range(-rings, rings + 1)
        if max(abs(q), abs(r), abs(q + r)) <= rings
    )


def _dense_matrix(index: int, size: int, density: float, tag: str) -> list[list[float]]:
    result = []
    for row in range(size):
        values = []
        for column in range(size):
            keep = row == column or _unit(
                f"{NAMESPACE}/{tag}-keep/4/{index}/{row}/{column}"
            ) <= density
            values.append(
                0.35 * _signed(
                    f"{NAMESPACE}/{tag}-value/4/{index}/{row}/{column}"
                ) / math.sqrt(size)
                if keep else 0.0
            )
        result.append(values)
    return result


def _trig_private(index: int) -> tuple[str, dict[str, Any], list[float], dict[str, Any]]:
    branching, depth, amplitude = TRIG_ROWS[index]
    size = (branching ** (depth + 1) - 1) // (branching - 1)
    permutation = _permutation(1, index, size, "trig-permutation")
    children: list[list[int]] = [[] for _ in range(size)]
    for logical in range(size):
        first = branching * logical + 1
        children[permutation[logical]] = [
            permutation[child]
            for child in range(first, min(first + branching, size))
        ]
    configuration = _configuration(1, index, size)
    program = {
        "kind": "sin-cos-tree-v1",
        "offsets": [-value for value in configuration],
        "children": children,
        "amplitude": amplitude,
    }
    factors = {"branching_factor": branching, "depth": depth, "trig_amplitude": amplitude}
    return "JAC3-TRIG-TREE", factors, configuration, program


def _rational_private(index: int) -> tuple[str, dict[str, Any], list[float], dict[str, Any]]:
    size, width, margin, overlap = RATIONAL_ROWS[index]
    configuration = _configuration(2, index, size)
    program = {
        "kind": "safe-rational-hypergraph-v1",
        "offsets": [-value for value in configuration],
        "edges": _rational_edges(index, size, width, overlap),
        "margin": margin,
        "alpha": 0.12 / width,
    }
    factors = {
        "dimension": size,
        "hyperedge_width": width,
        "denominator_margin": margin,
        "overlap": overlap,
    }
    return "JAC3-RATIONAL-HYPERGRAPH", factors, configuration, program


def _hex_private(index: int) -> tuple[str, dict[str, Any], list[float], dict[str, Any]]:
    rings, stencil, curvature = HEX_ROWS[index]
    coordinates = _hex_coordinates(rings)
    size = len(coordinates)
    coordinate_index = {coordinate: position for position, coordinate in enumerate(coordinates)}
    permutation = _permutation(3, index, size, "hex-permutation")
    directions = ((1, 0), (0, 1), (-1, 1), (-1, 0), (0, -1), (1, -1))
    neighbours: list[list[int]] = [[] for _ in range(size)]
    for logical, (q, r) in enumerate(coordinates):
        chosen = directions if stencil == "axial" else directions[((q - r) & 1)::2]
        neighbours[permutation[logical]] = sorted(
            permutation[coordinate_index[(q + dq, r + dr)]]
            for dq, dr in chosen
            if (q + dq, r + dr) in coordinate_index
        )
    configuration = _configuration(3, index, size)
    program = {
        "kind": "hex-ring-atan-v1",
        "offsets": [-value for value in configuration],
        "neighbours": neighbours,
        "curvature": curvature,
        "alpha": 0.055,
    }
    factors = {"ring_count": rings, "stencil": stencil, "curvature": curvature}
    return "JAC3-HEX-RING-STENCIL", factors, configuration, program


def _dense_private(index: int) -> tuple[str, dict[str, Any], list[float], dict[str, Any]]:
    size, density, boundary, chart = DENSE_ROWS[index]
    configuration = _configuration(4, index, size)
    configuration[0] = -0.75 + boundary
    matrix = _dense_matrix(index, size, density, "dense")
    alternate = _dense_matrix(index, size, density, "dense-alt")
    weights = [
        _signed(f"{NAMESPACE}/chart-weight/4/{index}/{column}") / math.sqrt(size)
        for column in range(size)
    ]
    chart_offset = boundary if index % 2 == 0 else -boundary
    threshold = sum(
        weight * value for weight, value in zip(weights, configuration, strict=True)
    ) - chart_offset
    program = {
        "kind": "dense-chart-v1",
        "offsets": [-value for value in configuration],
        "matrix": matrix,
        "alternate_matrix": alternate,
        "chart": chart,
        "chart_weights": weights,
        "chart_threshold": threshold,
        "smooth_gain": 0.08,
    }
    factors = {
        "dimension": size,
        "density": density,
        "boundary_distance": boundary,
        "branch_chart": chart,
    }
    return "JAC3-DENSE-BRANCH-CONTROL", factors, configuration, program


PRIVATE_BUILDERS = (_trig_private, _rational_private, _hex_private, _dense_private)


def _residual(program: dict[str, Any], point: Sequence[float]) -> list[float]:
    delta = [value + offset for value, offset in zip(point, program["offsets"], strict=True)]
    kind = program["kind"]
    if kind == "sin-cos-tree-v1":
        amplitude = program["amplitude"]
        result = []
        for row, children in enumerate(program["children"]):
            if children:
                total = sum(delta[column] for column in children)
                correction = math.sin(total) + 0.5 * (1.0 - math.cos(delta[children[0]]))
            else:
                correction = 0.0
            result.append(delta[row] + amplitude * correction)
        return result
    if kind == "safe-rational-hypergraph-v1":
        margin = program["margin"]
        alpha = program["alpha"]
        return [
            delta[row] + alpha * sum(
                delta[column] / (margin + delta[column] ** 2)
                for column in edge
            )
            for row, edge in enumerate(program["edges"])
        ]
    if kind == "hex-ring-atan-v1":
        curvature = program["curvature"]
        alpha = program["alpha"]
        return [
            delta[row] + alpha * sum(
                math.atan(curvature * delta[column]) / curvature
                for column in neighbours
            )
            for row, neighbours in enumerate(program["neighbours"])
        ]
    if kind == "dense-chart-v1":
        chart_value = sum(
            weight * value
            for weight, value in zip(program["chart_weights"], point, strict=True)
        ) - program["chart_threshold"]
        if program["chart"] == "piecewise":
            matrix = program["matrix"] if chart_value >= 0.0 else program["alternate_matrix"]
            return [
                delta[row] + sum(value * delta[column] for column, value in enumerate(matrix[row]))
                for row in range(len(delta))
            ]
        gain = program["smooth_gain"]
        return [
            delta[row] + gain * math.tanh(
                sum(value * delta[column] for column, value in enumerate(program["matrix"][row]))
            )
            for row in range(len(delta))
        ]
    raise ValueError(f"unknown assessor model {kind!r}")


def _jacobian(program: dict[str, Any], point: Sequence[float]) -> list[list[float]]:
    size = len(point)
    delta = [value + offset for value, offset in zip(point, program["offsets"], strict=True)]
    result = [[0.0] * size for _ in range(size)]
    for row in range(size):
        result[row][row] = 1.0
    kind = program["kind"]
    if kind == "sin-cos-tree-v1":
        amplitude = program["amplitude"]
        for row, children in enumerate(program["children"]):
            if not children:
                continue
            total = sum(delta[column] for column in children)
            common = amplitude * math.cos(total)
            for column in children:
                result[row][column] += common
            result[row][children[0]] += 0.5 * amplitude * math.sin(delta[children[0]])
        return result
    if kind == "safe-rational-hypergraph-v1":
        margin = program["margin"]
        alpha = program["alpha"]
        for row, edge in enumerate(program["edges"]):
            for column in edge:
                value = delta[column]
                result[row][column] += alpha * (margin - value * value) / (margin + value * value) ** 2
        return result
    if kind == "hex-ring-atan-v1":
        curvature = program["curvature"]
        alpha = program["alpha"]
        for row, neighbours in enumerate(program["neighbours"]):
            for column in neighbours:
                result[row][column] += alpha / (1.0 + (curvature * delta[column]) ** 2)
        return result
    if kind == "dense-chart-v1":
        chart_value = sum(
            weight * value
            for weight, value in zip(program["chart_weights"], point, strict=True)
        ) - program["chart_threshold"]
        if program["chart"] == "piecewise":
            matrix = program["matrix"] if chart_value >= 0.0 else program["alternate_matrix"]
            for row in range(size):
                for column in range(size):
                    result[row][column] += matrix[row][column]
            return result
        gain = program["smooth_gain"]
        for row in range(size):
            projected = sum(
                value * delta[column]
                for column, value in enumerate(program["matrix"][row])
            )
            multiplier = gain * (1.0 - math.tanh(projected) ** 2)
            for column, value in enumerate(program["matrix"][row]):
                result[row][column] += multiplier * value
        return result
    raise ValueError(f"unknown assessor model {kind!r}")


def _sparse_entries(matrix: Sequence[Sequence[float]]) -> list[list[float | int]]:
    return [
        [row, column, value]
        for row, values in enumerate(matrix)
        for column, value in enumerate(values)
        if value != 0.0
    ]


def _canonical_sha(document: Any) -> str:
    payload = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validate_coverage(rows: list[tuple[str, dict[str, Any]]]) -> None:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for family, factors in rows:
        grouped.setdefault(family, []).append(factors)
    if set(grouped) != {
        "JAC3-TRIG-TREE", "JAC3-RATIONAL-HYPERGRAPH",
        "JAC3-HEX-RING-STENCIL", "JAC3-DENSE-BRANCH-CONTROL",
    } or any(len(values) != 16 for values in grouped.values()):
        raise ValueError("family allocation drift")
    trig = grouped["JAC3-TRIG-TREE"]
    if min(Counter((row["branching_factor"], row["depth"]) for row in trig).values()) < 2:
        raise ValueError("trig branching/depth pair under-covered")
    rational = grouped["JAC3-RATIONAL-HYPERGRAPH"]
    for key in ("dimension", "hyperedge_width"):
        if min(Counter(row[key] for row in rational).values()) < 4:
            raise ValueError(f"rational {key} under-covered")
    hex_rows = grouped["JAC3-HEX-RING-STENCIL"]
    if min(Counter((row["ring_count"], row["stencil"]) for row in hex_rows).values()) < 2:
        raise ValueError("hex ring/stencil pair under-covered")
    dense = grouped["JAC3-DENSE-BRANCH-CONTROL"]
    for key in ("dimension", "density", "boundary_distance", "branch_chart"):
        if min(Counter(row[key] for row in dense).values()) < 4:
            raise ValueError(f"dense {key} under-covered")


def build_assessor_document(candidate_document: dict[str, Any]) -> dict[str, Any]:
    candidate_cases = {
        case["opaque_case_id"]: case for case in candidate_document["cases"]
    }
    if len(candidate_cases) != 64:
        raise ValueError("candidate opaque IDs are not exactly 64 unique values")
    assessments = []
    coverage_rows: list[tuple[str, dict[str, Any]]] = []
    for ordinal, builder in enumerate(PRIVATE_BUILDERS, start=1):
        for index in range(16):
            opaque_id = _opaque_id(ordinal, index)
            candidate = candidate_cases.get(opaque_id)
            if candidate is None:
                raise ValueError("candidate/assessor join mismatch")
            family, factors, configuration, program = builder(index)
            if candidate["oracle_program"] != program:
                raise ValueError(f"independent program mismatch for {opaque_id}")
            starts = candidate["starts"]
            if len(starts) != START_COUNT:
                raise ValueError("start-count drift")
            jacobian_traces = [
                {
                    "start_index": start_index,
                    "shape": [len(configuration), len(configuration)],
                    "entries": _sparse_entries(_jacobian(program, point)),
                }
                for start_index, point in enumerate(starts)
            ]
            root_residual = _residual(program, configuration)
            chart_value = None
            branch_label = None
            if program["kind"] == "dense-chart-v1":
                chart_value = sum(
                    weight * value
                    for weight, value in zip(
                        program["chart_weights"], configuration, strict=True
                    )
                ) - program["chart_threshold"]
                branch_label = "nonnegative" if chart_value >= 0.0 else "negative"
            assessments.append({
                "opaque_case_id": opaque_id,
                "family_id": family,
                "factors": factors,
                "instance_seed": 2_730_000 + 100 * ordinal + index,
                "start_seed": 2_830_000 + 100 * ordinal + index,
                "gold_configuration": configuration,
                "gold_target": configuration[-1],
                "gold_branch_label": branch_label,
                "gold_branch_margin": chart_value,
                "known_root_residual_infinity": max(abs(value) for value in root_residual),
                "candidate_program_sha256": _canonical_sha(program),
                "analytic_jacobian_traces": jacobian_traces,
            })
            coverage_rows.append((family, factors))
    _validate_coverage(coverage_rows)
    assessments.sort(key=lambda value: value["opaque_case_id"])
    return {
        "schema_version": SCHEMA_VERSION,
        "namespace": NAMESPACE,
        "case_count": len(assessments),
        "starts_per_case": START_COUNT,
        "assessments": assessments,
    }


if __name__ == "__main__":
    raise SystemExit("assessor.py is a library; invoke materialize_development.py once")
