#!/usr/bin/env python3
"""One-use source-only eligibility scan after HP-rung racing was held."""

from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


KNOWN_CALLS = frozenset(
    {
        "Angle", "AngleBisector", "Arc", "Area", "Assume", "AssumeAcute",
        "AssumeEq", "AssumeGe", "AssumeGt", "AssumeLe", "AssumeLt",
        "AssumeNe", "AssumeObtuse", "AssumeRight", "Bound", "Center",
        "Centroid", "Circle", "CircleThroughPoint", "CircleThroughThreePoints",
        "Circumcenter", "Circumcircle", "ClosestPoint", "Collinear",
        "ContactPoint", "CoordinateA", "CoordinateB", "CoordinateC",
        "CoordinateX", "CoordinateY", "Cross", "Distance", "Dot", "Excenter",
        "Excircle", "FootOfPerpendicular", "Incenter", "Incircle",
        "IncircleContactPoint", "Intersect", "IsTangent", "Line", "MidPoint",
        "Midpoint", "NoSelfIntersection", "Norm", "OnCircle", "OnLine",
        "OnSegment", "Orthocenter", "Parallel", "ParallelLine",
        "ParallelismMeasure", "Perpendicular", "PerpendicularBisector",
        "PerpendicularLine", "Point", "PointOnCircle", "PointOnLine",
        "PointOnSegment", "RadicalAxis", "Radius", "Reflect", "StrictConvex",
        "Vector", "abs", "cos", "max", "min", "sin", "sqrt", "tan",
    }
)
ALLOWED_ATTRIBUTES = frozenset({"a", "b", "c", "center", "radius", "x", "y"})


class OutsideBroadClosure(ValueError):
    pass


def _parse(value: object) -> ast.AST:
    if isinstance(value, str):
        source = value
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        source = repr(value)
    else:
        raise OutsideBroadClosure("expression is not scalar source text")
    try:
        return ast.parse(source, mode="eval").body
    except SyntaxError as error:
        raise OutsideBroadClosure("expression syntax is invalid") from error


def _shape(node: ast.AST, names: Mapping[str, str]) -> str:
    if isinstance(node, ast.Name):
        if node.id == "pi":
            return "PI"
        return names.get(node.id, "UNBOUND_NAME")
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            return "BOOL"
        if isinstance(node.value, (int, float)):
            return "RATIONAL_LITERAL"
        if isinstance(node.value, str):
            return "STRING_OPTION"
        raise OutsideBroadClosure("unsupported literal")
    if isinstance(node, ast.Attribute):
        if node.attr not in ALLOWED_ATTRIBUTES:
            raise OutsideBroadClosure("unsupported source attribute")
        return f"ATTR_{node.attr}({_shape(node.value, names)})"
    if isinstance(node, ast.UnaryOp):
        operation = {
            ast.UAdd: "POS",
            ast.USub: "NEG",
            ast.Not: "NOT",
        }.get(type(node.op))
        if operation is None:
            raise OutsideBroadClosure("unsupported unary operation")
        return f"{operation}({_shape(node.operand, names)})"
    if isinstance(node, ast.BinOp):
        operation = {
            ast.Add: "ADD", ast.Sub: "SUB", ast.Mult: "MUL",
            ast.Div: "DIV", ast.Pow: "POW",
        }.get(type(node.op))
        if operation is None:
            raise OutsideBroadClosure("unsupported binary operation")
        return f"{operation}({_shape(node.left, names)},{_shape(node.right, names)})"
    if isinstance(node, ast.BoolOp):
        operation = "AND" if isinstance(node.op, ast.And) else "OR" if isinstance(node.op, ast.Or) else None
        if operation is None or len(node.values) < 2:
            raise OutsideBroadClosure("unsupported Boolean operation")
        return f"{operation}({','.join(_shape(value, names) for value in node.values)})"
    if isinstance(node, ast.Compare):
        if len(node.ops) != len(node.comparators) or not node.ops:
            raise OutsideBroadClosure("malformed comparison")
        operations = []
        for operation in node.ops:
            name = {
                ast.Eq: "EQ", ast.NotEq: "NE", ast.Lt: "LT",
                ast.LtE: "LE", ast.Gt: "GT", ast.GtE: "GE",
            }.get(type(operation))
            if name is None:
                raise OutsideBroadClosure("unsupported comparison")
            operations.append(name)
        operands = [node.left, *node.comparators]
        return f"CMP_{'_'.join(operations)}({','.join(_shape(value, names) for value in operands)})"
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in KNOWN_CALLS:
            raise OutsideBroadClosure("unknown or dynamic source call")
        if any(keyword.arg is None for keyword in node.keywords):
            raise OutsideBroadClosure("expanded keyword arguments are unsupported")
        arguments = [_shape(value, names) for value in node.args]
        keywords = [
            f"KW_{keyword.arg}({_shape(keyword.value, names)})"
            for keyword in sorted(node.keywords, key=lambda item: str(item.arg))
        ]
        return f"CALL_{node.func.id}({','.join([*arguments, *keywords])})"
    raise OutsideBroadClosure(f"unsupported AST node: {type(node).__name__}")


def _root_species(node: ast.AST) -> str:
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return f"CALL_{node.func.id}"
    if isinstance(node, ast.BinOp):
        return f"BIN_{type(node.op).__name__.upper()}"
    if isinstance(node, ast.UnaryOp):
        return f"UNARY_{type(node.op).__name__.upper()}"
    if isinstance(node, ast.Compare):
        return "COMPARISON"
    if isinstance(node, ast.Name):
        return "DIRECT_NAME"
    if isinstance(node, ast.Attribute):
        return "DIRECT_ATTRIBUTE"
    if isinstance(node, ast.Constant):
        return "DIRECT_LITERAL"
    return type(node).__name__.upper()


def _guard_expressions(value: object) -> list[object]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise OutsideBroadClosure("guards are not a list")
    result: list[object] = []
    for item in value:
        if isinstance(item, (str, int, float)) and not isinstance(item, bool):
            result.append(item)
            continue
        if not isinstance(item, Mapping):
            raise OutsideBroadClosure("guard is malformed")
        selected = [item[key] for key in ("expr", "condition", "def", "value") if key in item]
        if not selected:
            raise OutsideBroadClosure("guard has no source expression")
        result.extend(selected)
    return result


def scan(document: Mapping[str, Any], source_sha256: str) -> dict[str, Any]:
    if document.get("task") != "solve":
        return {"eligible": False, "reason": "NOT_SOLVE", "source_sha256": source_sha256}
    if document.get("post_process") not in (None, ""):
        return {"eligible": False, "reason": "POST_PROCESS", "source_sha256": source_sha256}
    variables = document.get("variables")
    variable_names = variables.get("names") if isinstance(variables, Mapping) else None
    construction = document.get("construction")
    constraints = document.get("constraints")
    if (
        not isinstance(variable_names, list)
        or not variable_names
        or not all(isinstance(name, str) and name for name in variable_names)
        or len(set(variable_names)) != len(variable_names)
        or not isinstance(construction, list)
        or not isinstance(constraints, list)
        or not constraints
    ):
        return {"eligible": False, "reason": "MALFORMED_SOURCE", "source_sha256": source_sha256}
    names: dict[str, str] = {name: "VARIABLE" for name in variable_names}
    construction_shapes: Counter[str] = Counter()
    relation_species: Counter[str] = Counter()
    relation_shapes: Counter[str] = Counter()
    guard_shapes: Counter[str] = Counter()
    try:
        for item in construction:
            if (
                not isinstance(item, Mapping)
                or not isinstance(item.get("name"), str)
                or item["name"] in names
            ):
                raise OutsideBroadClosure("malformed construction")
            shape = _shape(_parse(item.get("expr")), names)
            construction_shapes[shape] += 1
            names[item["name"]] = "CONSTRUCTION"
        for item in constraints:
            if not isinstance(item, Mapping) or "def" not in item or "value" not in item:
                raise OutsideBroadClosure("malformed constraint")
            left, right = _parse(item["def"]), _parse(item["value"])
            left_shape, right_shape = _shape(left, names), _shape(right, names)
            relation_shapes[f"{left_shape}={right_shape}"] += 1
            relation_species[f"{_root_species(left)}={_root_species(right)}"] += 1
        for expression in _guard_expressions(document.get("guards")):
            guard_shapes[_shape(_parse(expression), names)] += 1
        answer_shape = _shape(_parse(document.get("answer")), names)
    except OutsideBroadClosure as error:
        return {
            "eligible": False,
            "reason": "OUTSIDE_BROAD_EXACT_REPLAY_CLOSURE",
            "source_sha256": source_sha256,
            "closed_failure": str(error),
        }
    bounds = document.get("bounds")
    if bounds is not None and not isinstance(bounds, (list, Mapping)):
        return {"eligible": False, "reason": "MALFORMED_BOUNDS", "source_sha256": source_sha256}
    fingerprint_payload = {
        "dimension": len(variable_names),
        "construction_shapes": sorted(construction_shapes.items()),
        "relation_shapes": sorted(relation_shapes.items()),
        "guard_shapes": sorted(guard_shapes.items()),
        "answer_shape": answer_shape,
        "bound_container": "NONE" if bounds is None else type(bounds).__name__,
    }
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "eligible": True,
        "route": "EXACT_DESCRIPTOR_SPECIES_RACING_ELIGIBILITY_ONLY",
        "source_sha256": source_sha256,
        "anonymous_structural_fingerprint_sha256": fingerprint,
        "relation_species_counts": dict(sorted(relation_species.items())),
        "dimension": len(variable_names),
        "constraint_count": len(constraints),
        "guard_count": sum(guard_shapes.values()),
        "activation_requires_safe_endpoint_count_at_least": 2,
        "all_endpoints_receive_low_rung": True,
        "authority_or_descriptor_shared_across_endpoints": False,
        "each_endpoint_requires_own_canonical_replay": True,
        "truth_case_family_target_value_or_prior_outcome_used": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    arguments = parser.parse_args()
    payload = arguments.source.read_bytes()
    observed = hashlib.sha256(payload).hexdigest()
    if observed != arguments.source_sha256:
        raise SystemExit("source SHA-256 mismatch")
    document = json.loads(payload)
    if not isinstance(document, Mapping):
        raise SystemExit("source root is not an object")
    print(json.dumps(scan(document, observed), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
