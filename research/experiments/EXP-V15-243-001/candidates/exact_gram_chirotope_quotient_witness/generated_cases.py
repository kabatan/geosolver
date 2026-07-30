"""Three anonymous invariant families and adversarial/metamorphic variants."""

from __future__ import annotations

from copy import deepcopy
import itertools
from typing import Any, Mapping

import sympy as sp


def _area(coordinates: Mapping[str, tuple[sp.Expr, sp.Expr]], triple: tuple[str, str, str]) -> sp.Expr:
    a, b, c = (coordinates[name] for name in triple)
    return sp.simplify((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))


def source_from_coordinates(
    coordinates: Mapping[str, tuple[sp.Expr, sp.Expr]],
    *,
    point_order: list[str] | None = None,
    orientation_triples: list[tuple[str, str, str]] | None = None,
    target: dict[str, Any] | None = None,
) -> dict[str, Any]:
    points = list(coordinates) if point_order is None else point_order
    triples = orientation_triples or [tuple(points[:3])]
    distances = []
    for i, j in itertools.combinations_with_replacement(range(len(points)), 2):
        a, b = coordinates[points[i]], coordinates[points[j]]
        value = sp.simplify((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)
        if value.is_Rational is not True:
            raise ValueError("generated squared distance must be rational")
        distances.append({"points": [points[i], points[j]], "value": str(value)})
    guards = []
    for triple in triples:
        value = _area(coordinates, triple)
        if value == 0:
            raise ValueError("generated orientation basis is collinear")
        guards.append(
            {
                "triple": list(triple),
                "relation": "positive" if value.is_positive else "negative",
                "approximate_double_area": str(float(sp.N(value, 30))),
            }
        )
    first = guards[0]
    return {
        "schema": "geotarget.exact-gram-chirotope-source/v1",
        "points": points,
        "squared_distance_equalities": distances,
        "orientation_guards": guards,
        "selector_ledger": [
            {
                "name": "anonymous-side-choice",
                "triple": list(triples[0]),
                "bit": first["relation"] == "positive",
                "true_when": "positive",
            }
        ],
        "raw_target": target or {"op": "distance", "points": points[:2]},
    }


COORDINATES = {
    "anonymous-rational-triangle": {
        "A": (sp.Integer(0), sp.Integer(0)),
        "B": (sp.Integer(3), sp.Integer(0)),
        "C": (sp.Integer(0), sp.Integer(4)),
    },
    "anonymous-rectangle-four-points": {
        "A": (sp.Integer(0), sp.Integer(0)),
        "B": (sp.Integer(2), sp.Integer(0)),
        "C": (sp.Integer(2), sp.Integer(1)),
        "D": (sp.Integer(0), sp.Integer(1)),
    },
    "anonymous-radical-realization": {
        "A": (sp.Integer(0), sp.Integer(0)),
        "B": (sp.sqrt(2), sp.Integer(0)),
        "C": (sp.Integer(0), sp.sqrt(3)),
    },
}

POSITIVES = {
    "anonymous-rational-triangle": source_from_coordinates(COORDINATES["anonymous-rational-triangle"]),
    "anonymous-rectangle-four-points": source_from_coordinates(
        COORDINATES["anonymous-rectangle-four-points"],
        orientation_triples=[("A", "B", "C"), ("A", "C", "D")],
        target={"op": "absolute_double_area", "points": ["A", "B", "C"]},
    ),
    "anonymous-radical-realization": source_from_coordinates(
        COORDINATES["anonymous-radical-realization"],
        target={"op": "distance", "points": ["A", "B"]},
    ),
}


def permuted(name: str) -> dict[str, Any]:
    coordinates = COORDINATES[name]
    order = list(reversed(coordinates))
    source = POSITIVES[name]
    triples = [tuple(item["triple"]) for item in source["orientation_guards"]]
    return source_from_coordinates(
        coordinates,
        point_order=order,
        orientation_triples=triples,
        target=deepcopy(source["raw_target"]),
    )


def rotated(name: str) -> dict[str, Any]:
    coordinates = {point: (-y, x) for point, (x, y) in COORDINATES[name].items()}
    source = POSITIVES[name]
    return source_from_coordinates(
        coordinates,
        orientation_triples=[tuple(item["triple"]) for item in source["orientation_guards"]],
        target=deepcopy(source["raw_target"]),
    )


def reflected(name: str) -> dict[str, Any]:
    coordinates = {point: (-x, y) for point, (x, y) in COORDINATES[name].items()}
    source = POSITIVES[name]
    return source_from_coordinates(
        coordinates,
        orientation_triples=[tuple(item["triple"]) for item in source["orientation_guards"]],
        target=deepcopy(source["raw_target"]),
    )


def rank3_source() -> dict[str, Any]:
    coordinates = {
        "A": (0, 0, 0), "B": (1, 0, 0), "C": (0, 1, 0), "D": (0, 0, 1)
    }
    points = list(coordinates)
    distances = []
    for i, j in itertools.combinations_with_replacement(range(4), 2):
        value = sum((coordinates[points[i]][axis] - coordinates[points[j]][axis]) ** 2 for axis in range(3))
        distances.append({"points": [points[i], points[j]], "value": str(value)})
    return {
        "schema": "geotarget.exact-gram-chirotope-source/v1",
        "points": points,
        "squared_distance_equalities": distances,
        "orientation_guards": [
            {"triple": ["A", "B", "C"], "relation": "positive", "approximate_double_area": "1.0"}
        ],
        "selector_ledger": [],
        "raw_target": {"op": "distance", "points": ["A", "D"]},
    }


def mirror_ambiguous_source() -> dict[str, Any]:
    source = deepcopy(POSITIVES["anonymous-rational-triangle"])
    source["orientation_guards"] = []
    source["selector_ledger"] = []
    return source


def near_zero_orientation_source() -> dict[str, Any]:
    source = deepcopy(POSITIVES["anonymous-radical-realization"])
    source["orientation_guards"][0]["approximate_double_area"] = "1e-12"
    return source


def absolute_coordinate_guard_source() -> dict[str, Any]:
    source = deepcopy(POSITIVES["anonymous-rectangle-four-points"])
    source["absolute_coordinate_guards"] = ["A.x > 0"]
    return source


NEGATIVES = {
    "rank3-gram": rank3_source(),
    "same-edm-mirror-ambiguity": mirror_ambiguous_source(),
    "near-zero-orientation": near_zero_orientation_source(),
    "absolute-coordinate-guard": absolute_coordinate_guard_source(),
}


__all__ = ["NEGATIVES", "POSITIVES", "permuted", "reflected", "rotated"]
