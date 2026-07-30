"""Source-labelled exact line/circle construction witness, D0."""

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


class ConstructionFailure(ValueError):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _fail(reason: str):
    raise ConstructionFailure(reason)


def _exact(value: object, label: str) -> sp.Expr:
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        _fail(f"nonexact-{label}")
    expression = sp.sympify(value)
    if expression.free_symbols or expression.atoms(sp.Float) or expression.is_real is not True:
        _fail(f"nonreal-or-inexact-{label}")
    return sp.simplify(expression)


def _sign(value: sp.Expr) -> int:
    value = sp.simplify(value)
    if value == 0:
        return 0
    if value.is_positive is True:
        return 1
    if value.is_negative is True:
        return -1
    _fail("undecidable-exact-sign")


def _area(points, triple) -> sp.Expr:
    a, b, c = (points[name] for name in triple)
    return sp.simplify((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))


def _locus_equation(locus: Mapping[str, Any], points, x, y) -> sp.Expr:
    kind = locus.get("kind")
    if kind == "circle":
        center = locus.get("center")
        if center not in points:
            _fail("circle-center-not-constructed")
        radius_squared = _exact(locus.get("radius_squared"), "radius-squared")
        if _sign(radius_squared) <= 0:
            _fail("nonpositive-radius")
        cx, cy = points[center]
        return sp.expand((x - cx) ** 2 + (y - cy) ** 2 - radius_squared)
    if kind == "line":
        through = locus.get("through")
        if not isinstance(through, list) or len(through) != 2 or any(name not in points for name in through):
            _fail("line-anchor-not-constructed")
        a, b = (points[name] for name in through)
        if a == b:
            _fail("degenerate-line")
        return sp.expand((b[0] - a[0]) * (y - a[1]) - (b[1] - a[1]) * (x - a[0]))
    _fail("non-ruler-compass-locus")


def _intersections(loci, points) -> list[tuple[sp.Expr, sp.Expr]]:
    if not isinstance(loci, list) or len(loci) != 2:
        _fail("step-must-have-two-loci")
    x, y = sp.symbols("__x __y", real=True)
    equations = [_locus_equation(locus, points, x, y) for locus in loci]
    solutions = sp.solve(equations, (x, y), dict=True)
    result = []
    for solution in solutions:
        if x not in solution or y not in solution:
            continue
        candidate = (sp.simplify(solution[x]), sp.simplify(solution[y]))
        if any(value.free_symbols or value.atoms(sp.Float) or value.is_real is not True for value in candidate):
            continue
        if all(sp.simplify(equation.subs({x: candidate[0], y: candidate[1]})) == 0 for equation in equations):
            if candidate not in result:
                result.append(candidate)
    if not result:
        _fail("empty-exact-intersection")
    return result


def _hint_key(candidate, hint) -> float:
    if not isinstance(hint, list) or len(hint) != 2:
        return 0.0
    try:
        hx, hy = float(hint[0]), float(hint[1])
        return (float(sp.N(candidate[0], 20)) - hx) ** 2 + (float(sp.N(candidate[1], 20)) - hy) ** 2
    except (TypeError, ValueError, OverflowError):
        return 0.0


def _target(document, points) -> sp.Expr:
    target = document.get("raw_target")
    if not isinstance(target, Mapping) or target.get("op") not in {"distance", "squared_distance", "signed_double_area"}:
        _fail("raw-target-escape")
    names = target.get("points")
    required = 3 if target["op"] == "signed_double_area" else 2
    if not isinstance(names, list) or len(names) != required or any(name not in points for name in names):
        _fail("malformed-target")
    if target["op"] == "signed_double_area":
        return _area(points, names)
    a, b = (points[name] for name in names)
    squared = sp.simplify((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)
    return squared if target["op"] == "squared_distance" else sp.sqrt(squared)


def _replay(document, points) -> tuple[bool, list[dict[str, Any]]]:
    ledger = []
    signs = {}
    for guard in document.get("orientation_guards", ()):
        triple = guard.get("triple") if isinstance(guard, Mapping) else None
        approximation = guard.get("approximate_double_area") if isinstance(guard, Mapping) else None
        if not isinstance(triple, list) or len(triple) != 3 or any(name not in points for name in triple):
            _fail("malformed-orientation-guard")
        try:
            approximate = Decimal(approximation)
        except (InvalidOperation, TypeError):
            _fail("invalid-orientation-proposal")
        if not approximate.is_finite() or abs(approximate) <= ORIENTATION_MARGIN:
            _fail("near-zero-orientation")
        sign = _sign(_area(points, triple))
        declared = 1 if guard.get("relation") == "positive" else -1 if guard.get("relation") == "negative" else 0
        if declared == 0 or (approximate > 0) != (declared > 0):
            _fail("orientation-proposal-sign-mismatch")
        if sign != declared:
            return False, ledger
        signs[tuple(triple)] = sign
        ledger.append({"kind": "orientation", "triple": triple, "exact_sign": sign})
    for selector in document.get("selector_ledger", ()):
        triple = selector.get("triple") if isinstance(selector, Mapping) else None
        if not isinstance(triple, list) or len(triple) != 3 or any(name not in points for name in triple):
            _fail("malformed-selector")
        sign = signs.get(tuple(triple), _sign(_area(points, triple)))
        expected = sign > 0 if selector.get("true_when") == "positive" else sign < 0
        if not isinstance(selector.get("bit"), bool) or selector["bit"] is not expected:
            return False, ledger
        ledger.append({"kind": "selector", "name": selector.get("name"), "bit": selector["bit"], "exact_sign": sign})
    return True, ledger


def certify_source(*, source: Path, source_sha256: str) -> dict[str, Any]:
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != source_sha256:
        _fail("untouched-source-digest-mismatch")
    document = json.loads(raw)
    if not isinstance(document, Mapping) or document.get("schema") != SOURCE_SCHEMA:
        _fail("source-schema-mismatch")
    if any(document.get(key) for key in ("absolute_coordinate_guards", "bounds", "raw_scalar_uses", "non_ruler_compass_operations")):
        _fail("source-operation-escape")
    raw_anchors = document.get("anchors")
    if not isinstance(raw_anchors, Mapping) or len(raw_anchors) < 2:
        _fail("missing-exact-anchors")
    anchors = {}
    for name, pair in raw_anchors.items():
        if not isinstance(name, str) or not isinstance(pair, list) or len(pair) != 2:
            _fail("malformed-anchor")
        anchors[name] = (_exact(pair[0], "anchor-x"), _exact(pair[1], "anchor-y"))
    steps = document.get("steps")
    if not isinstance(steps, list) or not steps:
        _fail("missing-construction-steps")
    branches = [anchors]
    all_candidates_examined = 0
    for step in steps:
        name = step.get("point") if isinstance(step, Mapping) else None
        if not isinstance(name, str) or any(name in branch for branch in branches):
            _fail("duplicate-or-invalid-step-point")
        expanded = []
        for branch in branches:
            candidates = _intersections(step.get("loci"), branch)
            candidates.sort(key=lambda candidate: _hint_key(candidate, step.get("endpoint_hint")))
            all_candidates_examined += len(candidates)
            for candidate in candidates:
                expanded.append({**branch, name: candidate})
        if len(expanded) > BRANCH_CAP:
            _fail("branch-cap-exceeded")
        branches = expanded
    accepted = []
    rejected = 0
    for branch in branches:
        ok, replay = _replay(document, branch)
        if ok:
            accepted.append((branch, replay, sp.simplify(_target(document, branch))))
        else:
            rejected += 1
    if not accepted:
        _fail("no-branch-passes-exact-replay")
    target_values = sorted({str(value) for _branch, _replay_ledger, value in accepted})
    return {
        "schema": CERT_SCHEMA,
        "status": "SOURCE_LABELLED_RULER_COMPASS_AUTHORITY_READY",
        "authority_pass": True,
        "source_sha256": source_sha256,
        "truth_used": False,
        "endpoint_role": "BRANCH_TRIAL_ORDER_ONLY_NOT_AUTHORITY",
        "branch_cap": BRANCH_CAP,
        "branches_generated": len(branches),
        "branches_examined_exactly": len(branches),
        "intersection_candidates_examined": all_candidates_examined,
        "branches_accepted": len(accepted),
        "branches_rejected_by_exact_replay": rejected,
        "all_branches_exactly_replayed": True,
        "accepted_realizations": [
            {
                "points": {name: [str(x), str(y)] for name, (x, y) in sorted(branch.items())},
                "replay_ledger": replay,
                "raw_target_exact": str(target),
            }
            for branch, replay, target in accepted
        ],
        "raw_target_exact_set": target_values,
        "untouched_source_guard_branch_target_replay": True,
    }


def attempt_source(*, source: Path, source_sha256: str) -> dict[str, Any]:
    try:
        return certify_source(source=source, source_sha256=source_sha256)
    except Exception as error:  # noqa: BLE001
        reason = getattr(error, "reason", None) or str(error) or type(error).__name__
        return {
            "schema": CERT_SCHEMA,
            "status": "SOURCE_LABELLED_RULER_COMPASS_NOT_PROVED",
            "authority_pass": False,
            "source_sha256": source_sha256,
            "failure_reason": reason,
            "partial_artifact_discarded": True,
            "truth_used": False,
        }


__all__ = ["BRANCH_CAP", "CERT_SCHEMA", "SOURCE_SCHEMA", "attempt_source", "certify_source"]
