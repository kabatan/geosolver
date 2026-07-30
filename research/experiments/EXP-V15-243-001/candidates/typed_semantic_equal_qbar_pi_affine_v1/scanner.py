#!/usr/bin/env python3
"""One-use aggregate scanner for the two authorized failure classes.

It reads only variable names, construction expressions, and source
constraints.  It never reads answer/target/result/descriptor/truth fields and
emits only an eligible count plus one anonymous structural hash.
"""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping
from collections import Counter


FAILURES = frozenset(
    ("value is not exact rational", "scalar is not an exact angle expression")
)
MAX_AFFINE_NODES = 12


@dataclass(frozen=True)
class StaticType:
    tag: str
    nodes: int
    shape: str


UNKNOWN = StaticType("UNKNOWN", 0, "UNKNOWN")
ALGEBRAIC = frozenset(("RATIONAL", "QBAR"))
PI_BEARING = frozenset(("PI_MULTIPLE", "PI_AFFINE"))


POINT_CALLS = frozenset(
    (
        "Point",
        "Intersect",
        "Midpoint",
        "MidPoint",
        "FootOfPerpendicular",
        "ClosestPoint",
        "ContactPoint",
        "Center",
        "Circumcenter",
        "Orthocenter",
        "Incenter",
        "Excenter",
        "PointOnLine",
        "PointOnCircle",
        "Centroid",
        "IncircleContactPoint",
    )
)
LINE_CALLS = frozenset(("Line", "PerpendicularBisector", "RadicalAxis"))
CIRCLE_CALLS = frozenset(
    (
        "Circle",
        "Circumcircle",
        "CircleThroughPoint",
        "CircleThroughThreePoints",
        "Incircle",
        "Excircle",
    )
)
QBAR_CALLS = frozenset(
    (
        "Distance",
        "Radius",
        "Area",
        "Dot",
        "Cross",
        "Norm",
        "Parallel",
        "ParallelismMeasure",
        "CoordinateX",
        "CoordinateY",
        "CoordinateA",
        "CoordinateB",
        "CoordinateC",
        "OnLine",
        "Collinear",
        "IsTangent",
    )
)


def _combine_shape(operation: str, left: StaticType, right: StaticType) -> str:
    return f"{operation}({left.shape},{right.shape})"


def _algebra(left: StaticType, right: StaticType, operation: str) -> StaticType:
    nodes = left.nodes + right.nodes + 1
    shape = _combine_shape(operation, left, right)
    if left.tag == "UNKNOWN" or right.tag == "UNKNOWN":
        return UNKNOWN
    if left.tag.startswith("ANGLE") or right.tag.startswith("ANGLE"):
        return UNKNOWN
    if operation in ("ADD", "SUB"):
        if left.tag in PI_BEARING or right.tag in PI_BEARING:
            return StaticType("PI_AFFINE", nodes, shape) if nodes <= MAX_AFFINE_NODES else UNKNOWN
        if left.tag in ALGEBRAIC and right.tag in ALGEBRAIC:
            tag = "RATIONAL" if left.tag == right.tag == "RATIONAL" else "QBAR"
            return StaticType(tag, nodes, shape)
        return UNKNOWN
    if operation == "MUL":
        if left.tag in PI_BEARING and right.tag in PI_BEARING:
            return UNKNOWN
        if left.tag in PI_BEARING or right.tag in PI_BEARING:
            scalar = right if left.tag in PI_BEARING else left
            pi_value = left if left.tag in PI_BEARING else right
            if scalar.tag not in ALGEBRAIC or nodes > MAX_AFFINE_NODES:
                return UNKNOWN
            tag = (
                "PI_MULTIPLE"
                if pi_value.tag == "PI_MULTIPLE" and scalar.tag == "RATIONAL"
                else "PI_AFFINE"
            )
            return StaticType(tag, nodes, shape)
        if left.tag in ALGEBRAIC and right.tag in ALGEBRAIC:
            tag = "RATIONAL" if left.tag == right.tag == "RATIONAL" else "QBAR"
            return StaticType(tag, nodes, shape)
        return UNKNOWN
    if operation == "DIV":
        if right.tag not in ALGEBRAIC:
            return UNKNOWN
        if left.tag in PI_BEARING:
            if nodes > MAX_AFFINE_NODES:
                return UNKNOWN
            tag = (
                "PI_MULTIPLE"
                if left.tag == "PI_MULTIPLE" and right.tag == "RATIONAL"
                else "PI_AFFINE"
            )
            return StaticType(tag, nodes, shape)
        if left.tag in ALGEBRAIC:
            tag = "RATIONAL" if left.tag == right.tag == "RATIONAL" else "QBAR"
            return StaticType(tag, nodes, shape)
    return UNKNOWN


def _infer(node: ast.AST, environment: Mapping[str, StaticType]) -> StaticType:
    if isinstance(node, ast.Name):
        if node.id == "pi":
            return StaticType("PI_MULTIPLE", 1, "PI")
        value = environment.get(node.id, UNKNOWN)
        return StaticType(value.tag, 1, f"NAME_{value.tag}") if value.tag != "UNKNOWN" else UNKNOWN
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            try:
                Fraction(str(node.value))
            except (ValueError, ZeroDivisionError):
                return UNKNOWN
            return StaticType("RATIONAL", 1, "R")
        return UNKNOWN
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _infer(node.operand, environment)
        if value.tag in ALGEBRAIC | PI_BEARING:
            return StaticType(value.tag, value.nodes + 1, f"NEG({value.shape})")
        return UNKNOWN
    if isinstance(node, ast.BinOp):
        left, right = _infer(node.left, environment), _infer(node.right, environment)
        if isinstance(node.op, ast.Add):
            return _algebra(left, right, "ADD")
        if isinstance(node.op, ast.Sub):
            return _algebra(left, right, "SUB")
        if isinstance(node.op, ast.Mult):
            return _algebra(left, right, "MUL")
        if isinstance(node.op, ast.Div):
            return _algebra(left, right, "DIV")
        # Powers are rejected even when algebraic: this scanner is only for
        # the direct bounded repair, not a general expression compiler.
        return UNKNOWN
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        name = node.func.id
        arguments = [_infer(item, environment) for item in node.args]
        if any(value.tag == "UNKNOWN" for value in arguments):
            return UNKNOWN
        if name == "Angle" and not node.keywords:
            if len(arguments) == 3 and all(value.tag == "POINT" for value in arguments):
                return StaticType("ANGLE_POINT", 1, "ANGLE_POINT")
            if len(arguments) == 2 and all(value.tag == "LINE" for value in arguments):
                return StaticType("ANGLE_LINE", 1, "ANGLE_LINE")
            return UNKNOWN
        if name in POINT_CALLS:
            return StaticType("POINT", 1, f"CALL_{name}")
        if name in LINE_CALLS:
            return StaticType("LINE", 1, f"CALL_{name}")
        if name in CIRCLE_CALLS:
            return StaticType("CIRCLE", 1, f"CALL_{name}")
        if name == "Arc":
            return StaticType("ARC", 1, "CALL_Arc")
        if name == "Vector":
            return StaticType("POINT", 1, "CALL_Vector")
        if name in QBAR_CALLS:
            return StaticType("QBAR", 1, f"CALL_{name}")
        # sin/cos/tan/min/max and every other nested call are outside this
        # equality-only scanner regardless of their possible runtime value.
    return UNKNOWN


def _parse_expression(value: Any) -> ast.AST | None:
    if isinstance(value, str):
        source = value
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        source = repr(value)
    else:
        return None
    try:
        return ast.parse(source, mode="eval").body
    except SyntaxError:
        return None


def _eligible_for_failure(tag: str, failure: str) -> bool:
    if failure == "value is not exact rational":
        return tag == "PI_AFFINE"
    return tag in ("ANGLE_POINT", "ANGLE_LINE", "PI_AFFINE")


def _eligible_relation(left: str, right: str, failure: str) -> bool:
    if {left, right} == {"QBAR", "RATIONAL"}:
        return True
    return left == right and _eligible_for_failure(left, failure)


def _pi_degree(node: ast.AST) -> int:
    """Capped syntactic degree; 2 means nonlinear or nested transcendental."""
    if isinstance(node, ast.Name):
        return 1 if node.id == "pi" else 0
    if isinstance(node, ast.Constant):
        return 0
    if isinstance(node, ast.UnaryOp):
        return _pi_degree(node.operand)
    if isinstance(node, ast.BinOp):
        left, right = _pi_degree(node.left), _pi_degree(node.right)
        if isinstance(node.op, (ast.Add, ast.Sub)):
            return min(2, max(left, right))
        if isinstance(node.op, ast.Mult):
            return min(2, left + right)
        if isinstance(node.op, ast.Div):
            return 2 if right else left
        return 2 if left or right else 0
    if isinstance(node, ast.Call):
        return 2 if any(_pi_degree(item) for item in node.args) else 0
    return 2


def _root_shape(node: ast.AST, inferred: StaticType) -> str:
    if isinstance(node, ast.Name):
        return "PI_LITERAL" if node.id == "pi" else "TYPED_NAME"
    if isinstance(node, ast.Constant):
        return "RATIONAL_LITERAL"
    if isinstance(node, ast.UnaryOp):
        return "UNARY_EXACT_SCALAR"
    if isinstance(node, ast.BinOp):
        if _pi_degree(node) >= 2:
            return "NONLINEAR_PI"
        operation = {
            ast.Add: "ADD",
            ast.Sub: "SUB",
            ast.Mult: "MUL",
            ast.Div: "DIV",
            ast.Pow: "POWER",
        }.get(type(node.op), "UNKNOWN_BINARY")
        return f"{operation}_{inferred.tag}"
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        name = node.func.id
        if name == "Angle":
            return "DIRECT_ANGLE_CALL"
        if name in QBAR_CALLS:
            return "DIRECT_QBAR_CALL"
        if name in POINT_CALLS | LINE_CALLS | CIRCLE_CALLS | {"Arc", "Vector"}:
            return "DIRECT_GEOMETRY_OBJECT_CALL"
        if name in {"sin", "cos", "tan", "min", "max"}:
            return "NESTED_SPECIAL_CALL"
        return "UNKNOWN_CALL"
    if isinstance(node, ast.Compare):
        return "NESTED_COMPARISON"
    return "UNKNOWN_SYNTAX"


def _ineligible_reason(
    left_ast: ast.AST,
    right_ast: ast.AST,
    left: StaticType,
    right: StaticType,
    failure: str,
) -> str:
    if _pi_degree(left_ast) >= 2 or _pi_degree(right_ast) >= 2:
        return "NONLINEAR_OR_NESTED_PI"
    if (
        (_pi_degree(left_ast) == 1 and sum(1 for _ in ast.walk(left_ast)) > MAX_AFFINE_NODES)
        or (_pi_degree(right_ast) == 1 and sum(1 for _ in ast.walk(right_ast)) > MAX_AFFINE_NODES)
    ):
        return "AFFINE_BOUND_EXCEEDED"
    if left.tag == "UNKNOWN" or right.tag == "UNKNOWN":
        return "UNKNOWN_OR_UNSUPPORTED_TYPE"
    if left.tag != right.tag:
        return "MIXED_CLOSED_TYPES"
    if left.tag in {"POINT", "LINE", "CIRCLE", "ARC"}:
        return "NONSCALAR_DIRECT_EQUALITY"
    if not _eligible_for_failure(left.tag, failure):
        return "CLOSED_TYPE_OUTSIDE_FAILURE_ROUTE"
    return "OTHER_CLOSED_PRECONDITION"


def scan(document: Mapping[str, Any], failure: str) -> dict[str, Any]:
    if failure not in FAILURES:
        raise ValueError("unauthorized failure class")
    variables = document.get("variables")
    names = variables.get("names") if isinstance(variables, Mapping) else None
    construction = document.get("construction")
    constraints = document.get("constraints")
    if (
        not isinstance(names, list)
        or not all(isinstance(name, str) for name in names)
        or not isinstance(construction, list)
        or not isinstance(constraints, list)
    ):
        raise ValueError("malformed source-only document")
    environment: dict[str, StaticType] = {
        name: StaticType("QBAR", 1, "VARIABLE_QBAR") for name in names
    }
    for item in construction:
        if not isinstance(item, Mapping) or not isinstance(item.get("name"), str):
            raise ValueError("malformed construction")
        expression = _parse_expression(item.get("expr"))
        inferred = _infer(expression, environment) if expression is not None else UNKNOWN
        if item["name"] in environment:
            raise ValueError("source name redefinition")
        environment[item["name"]] = inferred

    signatures: list[str] = []
    reason_counts: Counter[str] = Counter()
    shape_counts: Counter[str] = Counter()
    for item in constraints:
        if not isinstance(item, Mapping):
            continue
        left_ast = _parse_expression(item.get("def"))
        right_ast = _parse_expression(item.get("value"))
        if left_ast is None or right_ast is None:
            continue
        left, right = _infer(left_ast, environment), _infer(right_ast, environment)
        left_shape = _root_shape(left_ast, left)
        right_shape = _root_shape(right_ast, right)
        closed_shape = f"{left.tag}_EQ_{right.tag}__{left_shape}_TO_{right_shape}"
        if not _eligible_relation(left.tag, right.tag, failure):
            reason_counts[
                _ineligible_reason(left_ast, right_ast, left, right, failure)
            ] += 1
            shape_counts[closed_shape] += 1
            continue
        signature = hashlib.sha256(
            f"{failure}|{left.tag}|{left.shape}|{right.shape}".encode()
        ).hexdigest()
        signatures.append(signature)
    combined = hashlib.sha256(
        json.dumps(sorted(signatures), separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "eligible_relation_count": len(signatures),
        "anonymous_structural_signature_sha256": combined,
        "ineligibility_reason_counts": dict(sorted(reason_counts.items())),
        "closed_operator_type_shape_counts": dict(sorted(shape_counts.items())),
    }


def eligible_relation_indices(document: Mapping[str, Any], failure: str) -> list[int]:
    """Internal connector seam. Indices never cross the candidate boundary."""
    if failure not in FAILURES:
        raise ValueError("unauthorized failure class")
    variables = document.get("variables")
    names = variables.get("names") if isinstance(variables, Mapping) else None
    construction = document.get("construction")
    constraints = document.get("constraints")
    if (
        not isinstance(names, list)
        or not all(isinstance(name, str) for name in names)
        or not isinstance(construction, list)
        or not isinstance(constraints, list)
    ):
        raise ValueError("malformed source-only document")
    environment: dict[str, StaticType] = {
        name: StaticType("QBAR", 1, "VARIABLE_QBAR") for name in names
    }
    for item in construction:
        if not isinstance(item, Mapping) or not isinstance(item.get("name"), str):
            raise ValueError("malformed construction")
        expression = _parse_expression(item.get("expr"))
        inferred = _infer(expression, environment) if expression is not None else UNKNOWN
        if item["name"] in environment:
            raise ValueError("source name redefinition")
        environment[item["name"]] = inferred
    eligible: list[int] = []
    for index, item in enumerate(constraints):
        if not isinstance(item, Mapping):
            continue
        left_ast = _parse_expression(item.get("def"))
        right_ast = _parse_expression(item.get("value"))
        if left_ast is None or right_ast is None:
            continue
        left, right = _infer(left_ast, environment), _infer(right_ast, environment)
        if _eligible_relation(left.tag, right.tag, failure):
            eligible.append(index)
    return eligible


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--failure-class", choices=sorted(FAILURES), required=True)
    arguments = parser.parse_args()
    payload = arguments.source.read_bytes()
    if hashlib.sha256(payload).hexdigest() != arguments.source_sha256:
        raise SystemExit("source hash mismatch")
    document = json.loads(payload)
    if not isinstance(document, Mapping):
        raise SystemExit("source root is not an object")
    print(json.dumps(scan(document, arguments.failure_class), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
