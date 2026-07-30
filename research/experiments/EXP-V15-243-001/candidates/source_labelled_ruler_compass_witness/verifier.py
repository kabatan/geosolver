"""Independent branch-complete verifier for source-labelled construction D0."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import sympy as sp


SOURCE_SCHEMA = "geotarget.source-labelled-ruler-compass/v1"
CERT_SCHEMA = "geotarget.source-labelled-ruler-compass-certificate/v1"
BRANCH_CAP = 32
ORIENTATION_MARGIN = Decimal("1e-8")


class VerificationFailure(ValueError):
    pass


def _require(condition: bool, reason: str):
    if not condition:
        raise VerificationFailure(reason)


def _exact(value: object) -> sp.Expr:
    _require(isinstance(value, (str, int)) and not isinstance(value, bool), "nonexact value")
    result = sp.sympify(value)
    _require(not result.free_symbols and not result.atoms(sp.Float) and result.is_real is True, "inexact value")
    return sp.simplify(result)


def _sign(value: sp.Expr) -> int:
    value = sp.simplify(value)
    if value == 0:
        return 0
    if value.is_positive is True:
        return 1
    if value.is_negative is True:
        return -1
    raise VerificationFailure("undecidable sign")


def _area(points, triple) -> sp.Expr:
    a, b, c = (points[name] for name in triple)
    return sp.simplify((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))


def _equation(locus, points, x, y):
    if locus.get("kind") == "circle":
        _require(locus.get("center") in points, "unconstructed circle center")
        cx, cy = points[locus["center"]]
        radius = _exact(locus.get("radius_squared"))
        _require(_sign(radius) > 0, "invalid radius")
        return sp.expand((x - cx) ** 2 + (y - cy) ** 2 - radius)
    _require(locus.get("kind") == "line", "locus escape")
    through = locus.get("through")
    _require(isinstance(through, list) and len(through) == 2 and all(name in points for name in through), "line anchors")
    a, b = (points[name] for name in through)
    _require(a != b, "degenerate line")
    return sp.expand((b[0] - a[0]) * (y - a[1]) - (b[1] - a[1]) * (x - a[0]))


def _intersections(loci, points):
    _require(isinstance(loci, list) and len(loci) == 2, "two loci required")
    x, y = sp.symbols("__verify_x __verify_y", real=True)
    equations = [_equation(locus, points, x, y) for locus in loci]
    result = []
    for solution in sp.solve(equations, (x, y), dict=True):
        if x not in solution or y not in solution:
            continue
        candidate = (sp.simplify(solution[x]), sp.simplify(solution[y]))
        if any(value.free_symbols or value.atoms(sp.Float) or value.is_real is not True for value in candidate):
            continue
        if all(sp.simplify(eq.subs({x: candidate[0], y: candidate[1]})) == 0 for eq in equations):
            if candidate not in result:
                result.append(candidate)
    _require(bool(result), "empty intersection")
    return result


def _accepts(document, points) -> bool:
    signs = {}
    for guard in document.get("orientation_guards", ()):
        sign = _sign(_area(points, guard["triple"]))
        declared = 1 if guard.get("relation") == "positive" else -1
        try:
            approximate = Decimal(guard.get("approximate_double_area"))
        except (InvalidOperation, TypeError):
            raise VerificationFailure("invalid orientation proposal")
        _require(
            approximate.is_finite()
            and abs(approximate) > ORIENTATION_MARGIN
            and (approximate > 0) == (declared > 0),
            "near-zero or sign-mismatched orientation proposal",
        )
        if sign != declared:
            return False
        signs[tuple(guard["triple"])] = sign
    for selector in document.get("selector_ledger", ()):
        triple = tuple(selector["triple"])
        sign = signs.get(triple, _sign(_area(points, triple)))
        expected = sign > 0 if selector.get("true_when") == "positive" else sign < 0
        if selector.get("bit") is not expected:
            return False
    return True


def _target(document, points):
    target = document["raw_target"]
    names = target["points"]
    if target["op"] == "signed_double_area":
        return _area(points, names)
    a, b = (points[name] for name in names)
    squared = sp.simplify((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)
    return squared if target["op"] == "squared_distance" else sp.sqrt(squared)


def _key(points) -> tuple:
    return tuple((name, str(sp.simplify(pair[0])), str(sp.simplify(pair[1]))) for name, pair in sorted(points.items()))


def verify_source(*, source: Path, source_sha256: str, certificate: Mapping[str, Any]) -> dict[str, Any]:
    raw = source.read_bytes()
    _require(hashlib.sha256(raw).hexdigest() == source_sha256, "source digest")
    document = json.loads(raw)
    _require(document.get("schema") == SOURCE_SCHEMA, "source schema")
    _require(certificate.get("schema") == CERT_SCHEMA and certificate.get("authority_pass") is True, "certificate schema")
    _require(certificate.get("source_sha256") == source_sha256, "source binding")
    _require(certificate.get("endpoint_role") == "BRANCH_TRIAL_ORDER_ONLY_NOT_AUTHORITY", "endpoint authority escape")
    _require(certificate.get("branch_cap") == BRANCH_CAP, "branch cap")
    _require(certificate.get("truth_used") is False, "truth contamination")
    anchors = {name: (_exact(pair[0]), _exact(pair[1])) for name, pair in document["anchors"].items()}
    branches = [anchors]
    for step in document["steps"]:
        expanded = []
        for branch in branches:
            for candidate in _intersections(step["loci"], branch):
                expanded.append({**branch, step["point"]: candidate})
        _require(len(expanded) <= BRANCH_CAP, "branch cap exceeded")
        branches = expanded
    accepted = [branch for branch in branches if _accepts(document, branch)]
    _require(bool(accepted), "no accepted branch")
    _require(certificate.get("branches_generated") == len(branches), "branch completeness count")
    _require(certificate.get("branches_examined_exactly") == len(branches), "branches not all replayed")
    _require(certificate.get("branches_accepted") == len(accepted), "accepted count")
    _require(certificate.get("all_branches_exactly_replayed") is True, "replay ledger")
    raw_realizations = certificate.get("accepted_realizations")
    _require(isinstance(raw_realizations, list), "accepted realization ledger")
    certificate_keys = set()
    for item in raw_realizations:
        points = {name: (_exact(pair[0]), _exact(pair[1])) for name, pair in item["points"].items()}
        _require(_accepts(document, points), "certificate branch guard replay")
        _require(sp.simplify(_target(document, points) - _exact(item["raw_target_exact"])) == 0, "branch target replay")
        certificate_keys.add(_key(points))
    _require(certificate_keys == {_key(branch) for branch in accepted}, "accepted branch set mismatch")
    exact_targets = sorted({str(sp.simplify(_target(document, branch))) for branch in accepted})
    _require(certificate.get("raw_target_exact_set") == exact_targets, "target exact set mismatch")
    return {
        "schema": "geotarget.source-labelled-ruler-compass-independent-verification/v1",
        "verified": True,
        "source_sha256": source_sha256,
        "all_branches_exactly_reconstructed_and_replayed": True,
        "endpoint_used_for_authority": False,
        "raw_target_exact_set_verified": True,
    }


__all__ = ["VerificationFailure", "verify_source"]
