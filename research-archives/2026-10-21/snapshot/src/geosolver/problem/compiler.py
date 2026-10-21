"""One-pass AST compilation for public ``GeometryProblem`` documents."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Literal

from geosolver.problem.dsl_spec import DslSymbolSpec, symbols_by_name
from geosolver.problem.expression_source import annotate_source, source_expression
from geosolver.problem.models import GeometryProblem, PredicateCondition, RelationCondition


class ProblemCompileError(ValueError):
    def __init__(self, code: str, path: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.path = path


@dataclass(frozen=True)
class CompiledExpression:
    source: str
    tree: ast.Expression
    original_source: str = ""
    numeric_tokens: tuple[str, ...] = ()
    call_site_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompiledRelation:
    left: CompiledExpression
    operator: Literal["=", "!=", "<", "<=", ">", ">="]
    right: CompiledExpression
    right_literal: int | float | None = None


@dataclass(frozen=True)
class CompiledPredicate:
    expression: CompiledExpression


CompiledCondition = CompiledRelation | CompiledPredicate


@dataclass(frozen=True)
class CompiledConstruction:
    name: str
    expression: CompiledExpression


@dataclass(frozen=True)
class CompiledProblem:
    identifier: str
    variables: tuple[str, ...]
    constructions: tuple[CompiledConstruction, ...]
    conditions: tuple[CompiledCondition, ...]
    target: CompiledExpression


class _MacroExpander(ast.NodeTransformer):
    def visit_Call(self, node: ast.Call) -> ast.AST:
        node = self.generic_visit(node)
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            return node
        if node.func.id == "Ratio" and len(node.args) == 4 and not node.keywords:
            numerator = ast.Call(
                func=ast.Name(id="Distance", ctx=ast.Load()),
                args=[node.args[0], node.args[1]],
                keywords=[],
            )
            denominator = ast.Call(
                func=ast.Name(id="Distance", ctx=ast.Load()),
                args=[node.args[2], node.args[3]],
                keywords=[],
            )
            return ast.copy_location(ast.BinOp(numerator, ast.Div(), denominator), node)
        if node.func.id == "TangentAtPoint" and len(node.args) == 2 and not node.keywords:
            return ast.copy_location(
                ast.Call(
                    func=ast.Name(id="Polar", ctx=ast.Load()),
                    args=list(node.args),
                    keywords=[],
                ),
                node,
            )
        return node


def _parse(expression: str, path: str) -> CompiledExpression:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as error:
        raise ProblemCompileError("expression_syntax", path, str(error)) from error
    annotate_source(tree, expression)
    expanded = _MacroExpander().visit(tree)
    ast.fix_missing_locations(expanded)
    assert isinstance(expanded, ast.Expression)
    source = source_expression(expanded.body)
    # Reparse generated syntax so offsets always refer to the accompanying text.
    tree = ast.parse(source, mode="eval")
    annotate_source(tree, source)
    return CompiledExpression(
        source=source,
        tree=tree,
        original_source=expression,
        numeric_tokens=tuple(
            n.numeric_lexeme
            for n in ast.walk(tree)
            if getattr(n, "numeric_lexeme", None) is not None
        ),
        call_site_ids=tuple(n.call_site_id for n in ast.walk(tree) if isinstance(n, ast.Call)),
    )


def _root_symbol(expression: CompiledExpression) -> DslSymbolSpec | None:
    body = expression.tree.body
    if not isinstance(body, ast.Call) or not isinstance(body.func, ast.Name):
        return None
    return symbols_by_name().get(body.func.id)


def _require_position(expression: CompiledExpression, position: str, path: str) -> None:
    symbol = _root_symbol(expression)
    if symbol is not None and position not in symbol.positions:
        raise ProblemCompileError(
            "invalid_expression_position",
            path,
            f"{symbol.name} cannot be used as a {position} expression",
        )


def _is_boolean_expression(expression: CompiledExpression) -> bool:
    body = expression.tree.body
    if isinstance(body, ast.Compare | ast.BoolOp):
        return True
    if isinstance(body, ast.UnaryOp) and isinstance(body.op, ast.Not):
        return True
    symbol = _root_symbol(expression)
    return symbol is not None and symbol.semantic_kind == "boolean"


def predicate_guard_source(expression: CompiledExpression) -> str:
    """Lower Python boolean syntax to explicit DSL logical nodes.

    In particular a chain such as ``0 < x < 1`` becomes two independent
    comparisons.  This avoids the old string splitter interpreting ``x < 1``
    as part of the right-hand scalar expression.
    """

    def lower(node: ast.AST) -> str:
        if isinstance(node, ast.Compare):
            clauses: list[str] = []
            left = node.left
            for operator, right in zip(node.ops, node.comparators, strict=True):
                comparison = ast.Compare(left=left, ops=[operator], comparators=[right])
                clauses.append(source_expression(comparison))
                left = right
            return clauses[0] if len(clauses) == 1 else f"And({', '.join(clauses)})"
        if isinstance(node, ast.BoolOp):
            name = "And" if isinstance(node.op, ast.And) else "Or"
            return f"{name}({', '.join(lower(value) for value in node.values)})"
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return f"Not({lower(node.operand)})"
        return source_expression(node)

    return lower(expression.tree.body)


def compile_problem(problem: GeometryProblem) -> CompiledProblem:
    constructions: list[CompiledConstruction] = []
    for index, item in enumerate(problem.constructions):
        path = f"constructions[{index}].expression"
        expression = _parse(item.expression, path)
        _require_position(expression, "construction", path)
        constructions.append(CompiledConstruction(name=item.name, expression=expression))

    conditions: list[CompiledCondition] = []
    for index, condition in enumerate(problem.conditions):
        path = f"conditions[{index}]"
        if isinstance(condition, RelationCondition):
            left = _parse(condition.left, f"{path}.left")
            right = _parse(str(condition.right), f"{path}.right")
            conditions.append(
                CompiledRelation(
                    left=left,
                    operator=condition.operator,
                    right=right,
                    right_literal=(
                        condition.right if not isinstance(condition.right, str) else None
                    ),
                )
            )
            continue
        if isinstance(condition, PredicateCondition):
            expression = _parse(condition.predicate, f"{path}.predicate")
            if not _is_boolean_expression(expression):
                raise ProblemCompileError(
                    "predicate_not_boolean",
                    f"{path}.predicate",
                    "predicate conditions are boolean guards; use left = 0 for residual functions",
                )
            conditions.append(CompiledPredicate(expression=expression))

    target = _parse(problem.target, "target")
    _require_position(target, "target", "target")
    return CompiledProblem(
        identifier=problem.id,
        variables=tuple(problem.variables),
        constructions=tuple(constructions),
        conditions=tuple(conditions),
        target=target,
    )
