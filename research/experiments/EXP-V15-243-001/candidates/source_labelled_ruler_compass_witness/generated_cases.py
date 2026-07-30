"""Anonymous circle-circle, line-circle, and line-line D0 sources."""

from __future__ import annotations

from copy import deepcopy


def _guard(triple, positive=True, approximation="1.0"):
    return {
        "triple": list(triple),
        "relation": "positive" if positive else "negative",
        "approximate_double_area": approximation if positive else "-" + approximation,
    }


POSITIVES = {
    "anonymous-circle-circle": {
        "schema": "geotarget.source-labelled-ruler-compass/v1",
        "anchors": {"A": ["0", "0"], "B": ["4", "0"]},
        "steps": [
            {
                "point": "C",
                "loci": [
                    {"kind": "circle", "center": "A", "radius_squared": "9"},
                    {"kind": "circle", "center": "B", "radius_squared": "9"},
                ],
                "endpoint_hint": [2.0, 2.2],
            }
        ],
        "orientation_guards": [_guard(("A", "B", "C"), True, "8.9")],
        "selector_ledger": [
            {"name": "upper", "triple": ["A", "B", "C"], "bit": True, "true_when": "positive"}
        ],
        "raw_target": {"op": "distance", "points": ["A", "C"]},
    },
    "anonymous-line-circle": {
        "schema": "geotarget.source-labelled-ruler-compass/v1",
        "anchors": {"A": ["0", "0"], "B": ["4", "0"], "D": ["0", "1"]},
        "steps": [
            {
                "point": "C",
                "loci": [
                    {"kind": "line", "through": ["A", "D"]},
                    {"kind": "circle", "center": "B", "radius_squared": "25"},
                ],
                "endpoint_hint": [0.0, 3.0],
            }
        ],
        "orientation_guards": [_guard(("A", "B", "C"), True, "12.0")],
        "selector_ledger": [
            {"name": "upper", "triple": ["A", "B", "C"], "bit": True, "true_when": "positive"}
        ],
        "raw_target": {"op": "squared_distance", "points": ["A", "C"]},
    },
    "anonymous-line-line": {
        "schema": "geotarget.source-labelled-ruler-compass/v1",
        "anchors": {"A": ["0", "0"], "B": ["2", "2"], "C": ["0", "2"], "D": ["2", "0"]},
        "steps": [
            {
                "point": "X",
                "loci": [
                    {"kind": "line", "through": ["A", "B"]},
                    {"kind": "line", "through": ["C", "D"]},
                ],
                "endpoint_hint": [1.0, 1.0],
            }
        ],
        "orientation_guards": [_guard(("A", "C", "X"), False, "2.0")],
        "selector_ledger": [
            {"name": "right", "triple": ["A", "C", "X"], "bit": False, "true_when": "positive"}
        ],
        "raw_target": {"op": "distance", "points": ["A", "X"]},
    },
}


def reversed_endpoint_hints(document):
    result = deepcopy(document)
    for step in result["steps"]:
        hint = step.get("endpoint_hint", [0.0, 0.0])
        step["endpoint_hint"] = [-float(hint[0]), -float(hint[1])]
    return result


def branch_cap_source():
    source = deepcopy(POSITIVES["anonymous-circle-circle"])
    source["steps"] = []
    for index in range(6):
        source["steps"].append(
            {
                "point": f"C{index}",
                "loci": [
                    {"kind": "circle", "center": "A", "radius_squared": "9"},
                    {"kind": "circle", "center": "B", "radius_squared": "9"},
                ],
                "endpoint_hint": [2.0, 2.0],
            }
        )
    source["orientation_guards"] = [_guard(("A", "B", "C0"), True, "8.9")]
    source["selector_ledger"] = []
    source["raw_target"] = {"op": "distance", "points": ["A", "C0"]}
    return source


def near_zero_source():
    source = deepcopy(POSITIVES["anonymous-circle-circle"])
    source["orientation_guards"][0]["approximate_double_area"] = "1e-12"
    return source


NEGATIVES = {
    "branch-cap": branch_cap_source(),
    "near-zero-orientation": near_zero_source(),
    "operation-escape": {**deepcopy(POSITIVES["anonymous-line-circle"]), "non_ruler_compass_operations": ["Angle"]},
}


__all__ = ["NEGATIVES", "POSITIVES", "reversed_endpoint_hints"]
