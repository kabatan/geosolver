"""Truth-blind compiler from the legacy expression DSL to a compact DAG.

The compiler preserves source construction order and never evaluates a
numeric endpoint.  Numeric source literals are normalized to exact rational
strings; all geometry and algebra are evaluated by the FLINT qqbar worker.
"""

from __future__ import annotations

import ast
import json
from fractions import Fraction
from typing import Any, Mapping


class DagCompileError(ValueError):
    """The source expression is outside the bounded replay subset."""


_BINARY = {
    ast.Add: "add",
    ast.Sub: "sub",
    ast.Mult: "mul",
    ast.Div: "div",
    ast.Pow: "pow",
}
_UNARY = {ast.USub: "neg", ast.UAdd: "pos", ast.Not: "not"}
_COMPARE = {
    ast.Eq: "eq",
    ast.NotEq: "ne",
    ast.Lt: "lt",
    ast.LtE: "le",
    ast.Gt: "gt",
    ast.GtE: "ge",
}


def _fraction_text(source: str) -> str:
    cleaned = source.replace("_", "").strip()
    try:
        value = Fraction(cleaned)
    except (ValueError, ZeroDivisionError) as error:
        raise DagCompileError(f"numeric literal is not an exact rational: {source}") from error
    return f"{value.numerator}/{value.denominator}"


class DagBuilder:
    """Compile expressions while hash-consing identical source subexpressions."""

    def __init__(self) -> None:
        self.nodes: list[dict[str, Any]] = []
        self._cache: dict[str, int] = {}

    def add(self, node: Mapping[str, Any]) -> int:
        document = dict(node)
        key = json.dumps(document, sort_keys=True, separators=(",", ":"))
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        index = len(self.nodes)
        self.nodes.append(document)
        self._cache[key] = index
        return index

    def compile(self, source: str, context: Mapping[str, int]) -> int:
        try:
            tree = ast.parse(source, mode="eval")
        except SyntaxError as error:
            raise DagCompileError(f"invalid source expression: {source}") from error
        return self._visit(tree.body, source, context)

    def _visit(self, node: ast.AST, source: str, context: Mapping[str, int]) -> int:
        if isinstance(node, ast.Name):
            if node.id in context:
                return context[node.id]
            if node.id == "pi":
                return self.add({"op": "pi"})
            raise DagCompileError(f"unknown source name: {node.id}")

        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool):
                return self.add({"op": "bool", "value": node.value})
            if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                segment = ast.get_source_segment(source, node)
                if segment is None:
                    segment = repr(node.value)
                return self.add({"op": "rational", "value": _fraction_text(segment)})
            if isinstance(node.value, str):
                return self.add({"op": "string", "value": node.value})
            raise DagCompileError(f"unsupported literal: {node.value!r}")

        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
            return self.add(
                {
                    "op": _BINARY[type(node.op)],
                    "args": [
                        self._visit(node.left, source, context),
                        self._visit(node.right, source, context),
                    ],
                }
            )

        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
            return self.add(
                {
                    "op": _UNARY[type(node.op)],
                    "args": [self._visit(node.operand, source, context)],
                }
            )

        if isinstance(node, ast.Compare):
            if len(node.ops) != 1 or len(node.comparators) != 1:
                raise DagCompileError("comparison chains are outside the bounded subset")
            operation = _COMPARE.get(type(node.ops[0]))
            if operation is None:
                raise DagCompileError("unsupported comparison operation")
            return self.add(
                {
                    "op": operation,
                    "args": [
                        self._visit(node.left, source, context),
                        self._visit(node.comparators[0], source, context),
                    ],
                }
            )

        if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
            operation = "and" if isinstance(node.op, ast.And) else "or"
            return self.add(
                {
                    "op": operation,
                    "args": [self._visit(item, source, context) for item in node.values],
                }
            )

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise DagCompileError("only direct DSL function calls are permitted")
            arguments = [self._visit(item, source, context) for item in node.args]
            keywords: dict[str, int] = {}
            for item in node.keywords:
                if item.arg is None:
                    raise DagCompileError("dictionary keyword expansion is forbidden")
                if item.arg in keywords:
                    raise DagCompileError(f"duplicate keyword: {item.arg}")
                keywords[item.arg] = self._visit(item.value, source, context)
            return self.add(
                {
                    "op": "call",
                    "name": node.func.id,
                    "args": arguments,
                    "kwargs": dict(sorted(keywords.items())),
                }
            )

        raise DagCompileError(f"unsupported AST node: {type(node).__name__}")


def _expression(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return repr(value)
    raise DagCompileError(f"source scalar is not an expression: {value!r}")


def compile_document(
    document: Mapping[str, Any],
    *,
    coordinate_descriptors: list[Mapping[str, Any]],
    target_descriptor: Mapping[str, Any],
) -> dict[str, Any]:
    """Compile one untouched source document and supplied exact descriptors."""

    variables = document.get("variables")
    names = variables.get("names") if isinstance(variables, Mapping) else None
    if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
        raise DagCompileError("source variable names are malformed")
    if len(names) != len(coordinate_descriptors):
        raise DagCompileError("coordinate descriptor count differs from source dimension")

    builder = DagBuilder()
    context: dict[str, int] = {}
    for index, name in enumerate(names):
        context[name] = builder.add({"op": "coordinate", "index": index})

    construction_roots = []
    construction = document.get("construction", [])
    if not isinstance(construction, list):
        raise DagCompileError("source construction is not an array")
    for item in construction:
        if not isinstance(item, Mapping):
            raise DagCompileError("source construction entry is not an object")
        name, expression = item.get("name"), item.get("expr")
        if not isinstance(name, str) or not isinstance(expression, str):
            raise DagCompileError("source construction entry is incomplete")
        if name in context:
            raise DagCompileError(f"source name is redefined: {name}")
        root = builder.compile(expression, context)
        context[name] = root
        construction_roots.append(root)

    relation_roots = []
    constraints = document.get("constraints", [])
    if not isinstance(constraints, list):
        raise DagCompileError("source constraints are not an array")
    for item in constraints:
        if not isinstance(item, Mapping) or not isinstance(item.get("def"), str):
            raise DagCompileError("source constraint entry is incomplete")
        left = builder.compile(item["def"], context)
        right = builder.compile(_expression(item.get("value")), context)
        relation_roots.append(builder.add({"op": "sub", "args": [left, right]}))

    guard_roots = []
    guards = document.get("guards", []) or []
    if not isinstance(guards, list) or not all(isinstance(item, str) for item in guards):
        raise DagCompileError("source guards are malformed")
    for expression in guards:
        guard_roots.append(builder.compile(expression, context))

    bound_roots = []
    bounds = document.get("bounds")
    if bounds is not None:
        if not isinstance(bounds, list) or len(bounds) != len(names):
            raise DagCompileError("source bounds differ from source dimension")
        for index, pair in enumerate(bounds):
            if not isinstance(pair, list) or len(pair) != 2:
                raise DagCompileError("source bound pair is malformed")
            lower = builder.compile(_expression(pair[0]), context)
            upper = builder.compile(_expression(pair[1]), context)
            coordinate = context[names[index]]
            lower_ok = builder.add({"op": "le", "args": [lower, coordinate]})
            upper_ok = builder.add({"op": "le", "args": [coordinate, upper]})
            bound_roots.append(builder.add({"op": "and", "args": [lower_ok, upper_ok]}))

    answer = document.get("answer")
    if not isinstance(answer, str):
        raise DagCompileError("source answer expression is missing")
    answer_root = builder.compile(answer, context)

    return {
        "schema_version": "geotarget.qqbar-straight-line-job/v1",
        "truth_used": False,
        "post_process_used": False,
        "completeness_claim_permitted": False,
        "coordinate_descriptors": coordinate_descriptors,
        "target_descriptor": target_descriptor,
        "nodes": builder.nodes,
        "construction_roots": construction_roots,
        "relation_roots": relation_roots,
        "guard_roots": guard_roots,
        "bound_roots": bound_roots,
        "answer_root": answer_root,
    }
