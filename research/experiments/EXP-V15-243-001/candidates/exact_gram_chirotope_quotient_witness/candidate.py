"""D0 exact Gram/EDM + chirotope quotient witness (generated/source-only)."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib
import itertools
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import sympy as sp


SCHEMA = "geotarget.exact-gram-chirotope-source/v1"
CERTIFICATE_SCHEMA = "geotarget.exact-gram-chirotope-certificate/v1"
ORIENTATION_MARGIN = Decimal("1e-8")
MAX_POINTS = 8


class WitnessFailure(ValueError):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _fail(reason: str) -> None:
    raise WitnessFailure(reason)


def _qq(value: object, label: str) -> sp.Rational:
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        _fail(f"nonexact-{label}")
    try:
        result = sp.Rational(value)
    except (TypeError, ValueError, ZeroDivisionError):
        _fail(f"nonrational-{label}")
    return result


def _sign(value: sp.Expr, label: str) -> int:
    simplified = sp.simplify(value)
    if simplified == 0:
        return 0
    if simplified.is_positive is True:
        return 1
    if simplified.is_negative is True:
        return -1
    _fail(f"undecidable-exact-sign:{label}")


def _matrix_strings(matrix: sp.Matrix) -> list[list[str]]:
    return [[str(sp.simplify(matrix[row, col])) for col in range(matrix.cols)] for row in range(matrix.rows)]


def _parse_source(document: Mapping[str, Any]) -> dict[str, Any]:
    if document.get("schema") != SCHEMA:
        _fail("source-schema-mismatch")
    for escape in (
        "absolute_coordinate_guards",
        "bounds",
        "raw_scalar_uses",
        "non_invariant_operations",
    ):
        if document.get(escape):
            _fail(f"source-escape:{escape}")
    points = document.get("points")
    if (
        not isinstance(points, list)
        or not 3 <= len(points) <= MAX_POINTS
        or any(not isinstance(point, str) or not point for point in points)
        or len(set(points)) != len(points)
    ):
        _fail("invalid-point-ledger")
    index = {point: ordinal for ordinal, point in enumerate(points)}
    raw_distances = document.get("squared_distance_equalities")
    if not isinstance(raw_distances, list):
        _fail("missing-squared-distance-ledger")
    distances: dict[tuple[int, int], sp.Rational] = {}
    for item in raw_distances:
        pair = item.get("points") if isinstance(item, Mapping) else None
        if not isinstance(pair, list) or len(pair) != 2 or any(point not in index for point in pair):
            _fail("malformed-distance-entry")
        i, j = sorted((index[pair[0]], index[pair[1]]))
        value = _qq(item.get("value"), "squared-distance")
        if (i, j) in distances:
            _fail("duplicate-distance-entry")
        if value < 0 or (i == j and value != 0) or (i != j and value == 0):
            _fail("invalid-hollow-edm-entry")
        distances[i, j] = value
    expected = {(i, j) for i in range(len(points)) for j in range(i, len(points))}
    if set(distances) != expected:
        _fail("incomplete-edm")
    matrix = sp.zeros(len(points))
    for (i, j), value in distances.items():
        matrix[i, j] = matrix[j, i] = value

    orientations = []
    raw_orientations = document.get("orientation_guards")
    if not isinstance(raw_orientations, list) or not raw_orientations:
        _fail("mirror-ambiguity-no-orientation-choice")
    for item in raw_orientations:
        triple = item.get("triple") if isinstance(item, Mapping) else None
        relation = item.get("relation") if isinstance(item, Mapping) else None
        approximation = item.get("approximate_double_area") if isinstance(item, Mapping) else None
        if (
            not isinstance(triple, list)
            or len(triple) != 3
            or len(set(triple)) != 3
            or any(point not in index for point in triple)
            or relation not in {"positive", "negative"}
            or not isinstance(approximation, str)
        ):
            _fail("malformed-orientation-guard")
        try:
            approximate = Decimal(approximation)
        except InvalidOperation:
            _fail("invalid-orientation-approximation")
        expected_sign = 1 if relation == "positive" else -1
        if not approximate.is_finite() or abs(approximate) <= ORIENTATION_MARGIN:
            _fail("near-zero-orientation")
        if (approximate > 0) != (expected_sign > 0):
            _fail("orientation-proposal-sign-mismatch")
        orientations.append((tuple(index[point] for point in triple), expected_sign, approximation))

    selectors = []
    for item in document.get("selector_ledger", ()):
        triple = item.get("triple") if isinstance(item, Mapping) else None
        if (
            not isinstance(item, Mapping)
            or not isinstance(item.get("name"), str)
            or not isinstance(triple, list)
            or len(triple) != 3
            or len(set(triple)) != 3
            or any(point not in index for point in triple)
            or not isinstance(item.get("bit"), bool)
            or item.get("true_when") not in {"positive", "negative"}
        ):
            _fail("malformed-selector-ledger")
        selectors.append(
            {
                "name": item["name"],
                "triple": tuple(index[point] for point in triple),
                "bit": item["bit"],
                "true_when": item["true_when"],
            }
        )
    target = document.get("raw_target")
    if not isinstance(target, Mapping) or target.get("op") not in {
        "distance", "squared_distance", "signed_double_area", "absolute_double_area", "dot"
    }:
        _fail("raw-target-outside-invariant-whitelist")
    target_points = target.get("points")
    required = 3 if "area" in target["op"] else (4 if target["op"] == "dot" else 2)
    if (
        not isinstance(target_points, list)
        or len(target_points) != required
        or any(point not in index for point in target_points)
    ):
        _fail("malformed-raw-target")
    return {
        "points": tuple(points),
        "distance_matrix": matrix,
        "orientations": orientations,
        "selectors": selectors,
        "target": {"op": target["op"], "points": tuple(index[p] for p in target_points)},
    }


def _dot_from_edm(distance: sp.Matrix, a: int, b: int, c: int) -> sp.Expr:
    """(p_b-p_a) dot (p_c-p_a)."""
    return sp.simplify((distance[a, b] + distance[a, c] - distance[b, c]) / 2)


def _realize(parsed: Mapping[str, Any]) -> tuple[list[tuple[sp.Expr, sp.Expr]], tuple[int, int, int]]:
    distance = parsed["distance_matrix"]
    # The first exact nonzero chirotope declaration fixes the mirror sheet and
    # supplies a non-collinear affine basis.
    for triple, declared_sign, _approximation in parsed["orientations"]:
        a, b, c = triple
        uu = distance[a, b]
        vv = distance[a, c]
        uv = _dot_from_edm(distance, a, b, c)
        determinant = sp.simplify(uu * vv - uv**2)
        if _sign(determinant, "orientation-basis-minor") <= 0:
            continue
        ux = sp.sqrt(uu)
        cx = sp.simplify(uv / ux)
        cy = sp.simplify(declared_sign * sp.sqrt(determinant / uu))
        coordinates = []
        for point in range(distance.rows):
            up = _dot_from_edm(distance, a, b, point)
            vp = _dot_from_edm(distance, a, c, point)
            x = sp.simplify(up / ux)
            y = sp.simplify((vp - cx * x) / cy)
            coordinates.append((x, y))
        return coordinates, triple
    _fail("mirror-ambiguity-or-collinear-orientation-basis")


def _double_area(coordinates: Sequence[tuple[sp.Expr, sp.Expr]], triple: Sequence[int]) -> sp.Expr:
    a, b, c = (coordinates[index] for index in triple)
    return sp.simplify((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))


def _target_value(parsed: Mapping[str, Any], coordinates: Sequence[tuple[sp.Expr, sp.Expr]]) -> sp.Expr:
    operation = parsed["target"]["op"]
    indices = parsed["target"]["points"]
    distance = parsed["distance_matrix"]
    if operation == "squared_distance":
        return distance[indices[0], indices[1]]
    if operation == "distance":
        return sp.sqrt(distance[indices[0], indices[1]])
    if operation in {"signed_double_area", "absolute_double_area"}:
        value = _double_area(coordinates, indices)
        return sp.Abs(value) if operation == "absolute_double_area" else value
    a, b, c, d = indices
    va = (coordinates[b][0] - coordinates[a][0], coordinates[b][1] - coordinates[a][1])
    vb = (coordinates[d][0] - coordinates[c][0], coordinates[d][1] - coordinates[c][1])
    return sp.simplify(va[0] * vb[0] + va[1] * vb[1])


def certify_source(*, source: Path, source_sha256: str) -> dict[str, Any]:
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != source_sha256:
        _fail("untouched-source-digest-mismatch")
    document = json.loads(raw)
    if not isinstance(document, Mapping):
        _fail("source-not-object")
    parsed = _parse_source(document)
    distance = parsed["distance_matrix"]
    if distance != distance.T or any(distance[i, i] != 0 for i in range(distance.rows)):
        _fail("edm-not-symmetric-hollow")
    gram = sp.Matrix(
        [
            [sp.simplify((distance[0, i] + distance[0, j] - distance[i, j]) / 2) for j in range(1, distance.rows)]
            for i in range(1, distance.rows)
        ]
    )
    principal_minors = []
    for size in range(1, gram.rows + 1):
        for subset in itertools.combinations(range(gram.rows), size):
            determinant = sp.simplify(gram.extract(subset, subset).det())
            if _sign(determinant, "gram-principal-minor") < 0:
                _fail("gram-not-psd")
            principal_minors.append({"subset": list(subset), "determinant": str(determinant)})
    rank = int(gram.rank())
    if rank > 2:
        _fail("rank3-or-higher-gram")
    coordinates, basis = _realize(parsed)
    for i in range(distance.rows):
        for j in range(distance.cols):
            actual = sp.simplify(
                (coordinates[i][0] - coordinates[j][0]) ** 2
                + (coordinates[i][1] - coordinates[j][1]) ** 2
            )
            if actual != distance[i, j]:
                _fail("qqbar-realization-edm-mismatch")
    orientation_ledger = []
    signs = {}
    for triple, declared_sign, approximation in parsed["orientations"]:
        exact_area = _double_area(coordinates, triple)
        exact_sign = _sign(exact_area, "orientation")
        if exact_sign != declared_sign:
            _fail("exact-chirotope-source-guard-mismatch")
        signs[tuple(triple)] = exact_sign
        orientation_ledger.append(
            {"triple": list(triple), "exact_double_area": str(exact_area), "sign": exact_sign, "proposal": approximation}
        )
    selector_ledger = []
    for selector in parsed["selectors"]:
        triple = selector["triple"]
        exact_sign = signs.get(triple)
        if exact_sign is None:
            exact_sign = _sign(_double_area(coordinates, triple), "selector-orientation")
        expected = exact_sign > 0 if selector["true_when"] == "positive" else exact_sign < 0
        if selector["bit"] is not expected:
            _fail("selector-bit-chirotope-mismatch")
        selector_ledger.append({**selector, "triple": list(triple), "exact_sign": exact_sign})
    target = sp.simplify(_target_value(parsed, coordinates))
    return {
        "schema": CERTIFICATE_SCHEMA,
        "status": "EXACT_GRAM_CHIROTOPE_AUTHORITY_READY",
        "authority_pass": True,
        "source_sha256": source_sha256,
        "truth_used": False,
        "coordinate_exactification": "ONE_QQBAR_REALIZATION_AFTER_INVARIANT_AUTHORITY",
        "distance_matrix": _matrix_strings(distance),
        "gram_matrix": _matrix_strings(gram),
        "gram_rank": rank,
        "principal_minors": principal_minors,
        "all_3x3_gram_minors_zero": rank <= 2,
        "basis_orientation_triple": list(basis),
        "qqbar_realization": [[str(sp.simplify(x)), str(sp.simplify(y))] for x, y in coordinates],
        "orientation_ledger": orientation_ledger,
        "selector_ledger": selector_ledger,
        "raw_target_exact": str(target),
        "untouched_source_guard_branch_target_replay_required": True,
    }


def attempt_source(*, source: Path, source_sha256: str) -> dict[str, Any]:
    try:
        return certify_source(source=source, source_sha256=source_sha256)
    except Exception as error:  # noqa: BLE001 - D0 authority boundary
        reason = getattr(error, "reason", None) or str(error) or f"unsupported:{type(error).__name__}"
        return {
            "schema": CERTIFICATE_SCHEMA,
            "status": "EXACT_GRAM_CHIROTOPE_NOT_PROVED",
            "authority_pass": False,
            "source_sha256": source_sha256,
            "failure_reason": reason,
            "partial_certificate_discarded": True,
            "truth_used": False,
        }


__all__ = ["CERTIFICATE_SCHEMA", "SCHEMA", "WitnessFailure", "attempt_source", "certify_source"]
