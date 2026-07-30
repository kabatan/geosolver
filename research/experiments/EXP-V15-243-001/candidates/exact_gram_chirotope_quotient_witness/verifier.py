"""Independent exact verifier and untouched source replay for Gram D0."""

from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path
from typing import Any, Mapping

import sympy as sp


SOURCE_SCHEMA = "geotarget.exact-gram-chirotope-source/v1"
CERTIFICATE_SCHEMA = "geotarget.exact-gram-chirotope-certificate/v1"


class VerificationFailure(ValueError):
    pass


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise VerificationFailure(reason)


def _exact(text: object) -> sp.Expr:
    _require(isinstance(text, str), "non-string exact expression")
    expression = sp.sympify(text)
    _require(not expression.free_symbols and not expression.atoms(sp.Float), "inexact certificate expression")
    return sp.simplify(expression)


def _sign(value: sp.Expr) -> int:
    value = sp.simplify(value)
    if value == 0:
        return 0
    if value.is_positive is True:
        return 1
    if value.is_negative is True:
        return -1
    raise VerificationFailure("undecidable exact sign")


def _area(coordinates, triple) -> sp.Expr:
    a, b, c = (coordinates[index] for index in triple)
    return sp.simplify((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))


def verify_source(*, source: Path, source_sha256: str, certificate: Mapping[str, Any]) -> dict[str, Any]:
    raw = source.read_bytes()
    _require(hashlib.sha256(raw).hexdigest() == source_sha256, "source digest mismatch")
    document = json.loads(raw)
    _require(isinstance(document, Mapping) and document.get("schema") == SOURCE_SCHEMA, "source schema")
    _require(certificate.get("schema") == CERTIFICATE_SCHEMA, "certificate schema")
    _require(certificate.get("authority_pass") is True, "certificate nonauthority")
    _require(certificate.get("source_sha256") == source_sha256, "certificate source binding")
    _require(certificate.get("truth_used") is False, "truth contamination")
    _require(certificate.get("untouched_source_guard_branch_target_replay_required") is True, "replay bypass")
    for escape in ("absolute_coordinate_guards", "bounds", "raw_scalar_uses", "non_invariant_operations"):
        _require(not document.get(escape), f"source escape {escape}")

    points = document.get("points")
    _require(isinstance(points, list) and len(set(points)) == len(points) and len(points) >= 3, "points")
    index = {point: ordinal for ordinal, point in enumerate(points)}
    distance = sp.zeros(len(points))
    seen = set()
    for item in document.get("squared_distance_equalities", ()):
        pair = item.get("points") if isinstance(item, Mapping) else None
        _require(isinstance(pair, list) and len(pair) == 2 and all(p in index for p in pair), "distance pair")
        i, j = sorted((index[pair[0]], index[pair[1]]))
        _require((i, j) not in seen, "duplicate distance")
        seen.add((i, j))
        value = _exact(str(item.get("value")))
        _require(value.is_Rational is True and value >= 0, "non-QQ distance")
        _require((i != j and value > 0) or (i == j and value == 0), "hollow EDM")
        distance[i, j] = distance[j, i] = value
    _require(len(seen) == len(points) * (len(points) + 1) // 2, "incomplete EDM")
    certificate_distance = sp.Matrix([[_exact(value) for value in row] for row in certificate.get("distance_matrix", ())])
    _require(certificate_distance == distance and distance == distance.T, "distance matrix mismatch")

    gram = sp.Matrix(
        [[sp.simplify((distance[0, i] + distance[0, j] - distance[i, j]) / 2) for j in range(1, len(points))] for i in range(1, len(points))]
    )
    certificate_gram = sp.Matrix([[_exact(value) for value in row] for row in certificate.get("gram_matrix", ())])
    _require(certificate_gram == gram, "Gram mismatch")
    for size in range(1, gram.rows + 1):
        for subset in itertools.combinations(range(gram.rows), size):
            _require(_sign(gram.extract(subset, subset).det()) >= 0, "Gram not PSD")
    rank = int(gram.rank())
    _require(rank <= 2 and certificate.get("gram_rank") == rank, "rank exceeds two")
    _require(certificate.get("all_3x3_gram_minors_zero") is True, "minor ledger")

    raw_coordinates = certificate.get("qqbar_realization")
    _require(isinstance(raw_coordinates, list) and len(raw_coordinates) == len(points), "realization length")
    coordinates = []
    for pair in raw_coordinates:
        _require(isinstance(pair, list) and len(pair) == 2, "realization pair")
        coordinates.append((_exact(pair[0]), _exact(pair[1])))
    for i in range(len(points)):
        for j in range(len(points)):
            squared = sp.simplify(
                (coordinates[i][0] - coordinates[j][0]) ** 2
                + (coordinates[i][1] - coordinates[j][1]) ** 2
            )
            _require(squared == distance[i, j], "realization EDM replay")

    exact_signs = {}
    for guard in document.get("orientation_guards", ()):
        triple = tuple(index[point] for point in guard["triple"])
        sign = _sign(_area(coordinates, triple))
        declared = 1 if guard["relation"] == "positive" else -1
        _require(sign == declared, "orientation source replay")
        exact_signs[triple] = sign
    _require(any(sign != 0 for sign in exact_signs.values()), "mirror ambiguity")
    for selector in document.get("selector_ledger", ()):
        triple = tuple(index[point] for point in selector["triple"])
        sign = exact_signs.get(triple, _sign(_area(coordinates, triple)))
        expected = sign > 0 if selector["true_when"] == "positive" else sign < 0
        _require(selector["bit"] is expected, "selector branch replay")

    target = document.get("raw_target")
    target_points = tuple(index[point] for point in target["points"])
    operation = target["op"]
    if operation == "squared_distance":
        value = distance[target_points[0], target_points[1]]
    elif operation == "distance":
        value = sp.sqrt(distance[target_points[0], target_points[1]])
    elif operation in {"signed_double_area", "absolute_double_area"}:
        value = _area(coordinates, target_points)
        if operation == "absolute_double_area":
            value = sp.Abs(value)
    elif operation == "dot":
        a, b, c, d = target_points
        value = sp.simplify(
            (coordinates[b][0] - coordinates[a][0]) * (coordinates[d][0] - coordinates[c][0])
            + (coordinates[b][1] - coordinates[a][1]) * (coordinates[d][1] - coordinates[c][1])
        )
    else:
        raise VerificationFailure("raw target operator escape")
    _require(sp.simplify(value - _exact(certificate.get("raw_target_exact"))) == 0, "raw target replay")
    return {
        "schema": "geotarget.exact-gram-chirotope-independent-verification/v1",
        "verified": True,
        "source_sha256": source_sha256,
        "edm_symmetry_hollow": True,
        "gram_psd_rank_le_2": True,
        "chirotope_selector_replay": True,
        "raw_target_replay": True,
    }


__all__ = ["VerificationFailure", "verify_source"]
