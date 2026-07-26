"""Compile IR expression strings into prefix ExpressionSpec nodes."""

from __future__ import annotations

import ast
from typing import Any

from geosolver.ir.compiler import ALLOWED_AST_NODES, validate_expr_safety
from geosolver.ir.compiler_validation import ensure_allowed_ast_nodes, parse_eval_tree

from .schema import ExpressionSpec, UnsupportedReason, UnsupportedReasonCode, literal_expression

_BIN_OPS: dict[type[ast.operator], str] = {
    ast.Add: "add",
    ast.Sub: "sub",
    ast.Mult: "mul",
    ast.Div: "div",
    ast.FloorDiv: "floordiv",
    ast.Mod: "mod",
    ast.Pow: "pow",
}

_UNARY_OPS: dict[type[ast.unaryop], str] = {
    ast.UAdd: "pos",
    ast.USub: "neg",
    ast.Not: "not",
}

_COMPARE_OPS: dict[type[ast.cmpop], str] = {
    ast.Eq: "eq",
    ast.NotEq: "ne",
    ast.Lt: "lt",
    ast.LtE: "le",
    ast.Gt: "gt",
    ast.GtE: "ge",
}


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _compile_node(
    node: ast.AST,
    *,
    variables: set[str],
    expression_id: str,
    unsupported: list[UnsupportedReason],
) -> ExpressionSpec:
    if isinstance(node, ast.Expression):
        return _compile_node(
            node.body,
            variables=variables,
            expression_id=expression_id,
            unsupported=unsupported,
        )
    if isinstance(node, ast.Constant):
        return literal_expression(node.value)
    if isinstance(node, ast.Name):
        return ExpressionSpec(op="var" if node.id in variables else "symbol", value=node.id)
    if isinstance(node, ast.BinOp):
        op = _BIN_OPS.get(type(node.op))
        if op is None:
            unsupported.append(
                UnsupportedReason(
                    code=UnsupportedReasonCode.AST_UNSUPPORTED,
                    expression_id=expression_id,
                    detail=f"unsupported binary operator {type(node.op).__name__}",
                )
            )
            op = "unsupported_binop"
        return ExpressionSpec(
            op=op,
            args=(
                _compile_node(
                    node.left,
                    variables=variables,
                    expression_id=expression_id,
                    unsupported=unsupported,
                ),
                _compile_node(
                    node.right,
                    variables=variables,
                    expression_id=expression_id,
                    unsupported=unsupported,
                ),
            ),
        )
    if isinstance(node, ast.UnaryOp):
        op = _UNARY_OPS.get(type(node.op), "unsupported_unary")
        return ExpressionSpec(
            op=op,
            args=(
                _compile_node(
                    node.operand,
                    variables=variables,
                    expression_id=expression_id,
                    unsupported=unsupported,
                ),
            ),
        )
    if isinstance(node, ast.Call):
        if node.keywords:
            unsupported.append(
                UnsupportedReason(
                    code=UnsupportedReasonCode.KEYWORD_UNSUPPORTED,
                    expression_id=expression_id,
                    detail="keyword arguments are not kernel-compiled",
                )
            )
        name = _call_name(node.func)
        if not name:
            unsupported.append(
                UnsupportedReason(
                    code=UnsupportedReasonCode.CALL_UNSUPPORTED,
                    expression_id=expression_id,
                    detail="call target is not a simple name",
                )
            )
            name = "unsupported_call"
        return ExpressionSpec(
            op=name.lower(),
            args=tuple(
                _compile_node(
                    arg,
                    variables=variables,
                    expression_id=expression_id,
                    unsupported=unsupported,
                )
                for arg in node.args
            ),
            value=name,
        )
    if isinstance(node, ast.Compare):
        if len(node.ops) != 1 or len(node.comparators) != 1:
            unsupported.append(
                UnsupportedReason(
                    code=UnsupportedReasonCode.COMPARISON_UNSUPPORTED,
                    expression_id=expression_id,
                    detail="chained comparisons are not kernel-compiled",
                )
            )
        op = _COMPARE_OPS.get(type(node.ops[0]), "unsupported_compare")
        return ExpressionSpec(
            op=op,
            args=(
                _compile_node(
                    node.left,
                    variables=variables,
                    expression_id=expression_id,
                    unsupported=unsupported,
                ),
                _compile_node(
                    node.comparators[0],
                    variables=variables,
                    expression_id=expression_id,
                    unsupported=unsupported,
                ),
            ),
        )
    if isinstance(node, ast.BoolOp):
        unsupported.append(
            UnsupportedReason(
                code=UnsupportedReasonCode.BOOLEAN_UNSUPPORTED,
                expression_id=expression_id,
                detail="boolean expressions are not kernel-compiled",
            )
        )
        op = "and" if isinstance(node.op, ast.And) else "or"
        return ExpressionSpec(
            op=op,
            args=tuple(
                _compile_node(
                    value,
                    variables=variables,
                    expression_id=expression_id,
                    unsupported=unsupported,
                )
                for value in node.values
            ),
        )
    if isinstance(node, ast.Attribute):
        unsupported.append(
            UnsupportedReason(
                code=UnsupportedReasonCode.ATTRIBUTE_UNSUPPORTED,
                expression_id=expression_id,
                detail="attribute expressions are not kernel-compiled",
            )
        )
        return ExpressionSpec(op="attribute", value=ast.unparse(node))
    if isinstance(node, ast.Subscript):
        unsupported.append(
            UnsupportedReason(
                code=UnsupportedReasonCode.SUBSCRIPT_UNSUPPORTED,
                expression_id=expression_id,
                detail="subscript expressions are not kernel-compiled",
            )
        )
        return ExpressionSpec(op="subscript", value=ast.unparse(node))
    if isinstance(node, (ast.Tuple, ast.List)):
        return ExpressionSpec(
            op="tuple" if isinstance(node, ast.Tuple) else "list",
            args=tuple(
                _compile_node(
                    value,
                    variables=variables,
                    expression_id=expression_id,
                    unsupported=unsupported,
                )
                for value in node.elts
            ),
        )
    unsupported.append(
        UnsupportedReason(
            code=UnsupportedReasonCode.AST_UNSUPPORTED,
            expression_id=expression_id,
            detail=f"unsupported AST node {type(node).__name__}",
        )
    )
    return ExpressionSpec(op="unsupported_ast", value=type(node).__name__)


def compile_expression(
    expr: str,
    *,
    variables: set[str] | None = None,
    expression_id: str = "expr",
) -> tuple[ExpressionSpec, tuple[UnsupportedReason, ...]]:
    """Compile an IR expression string into a prefix expression.

    Syntax/security failures are schema errors and raise. Unsupported but safe
    constructs are represented as UnsupportedReason values.
    """

    if not isinstance(expr, str) or not expr.strip():
        raise ValueError(f"{expression_id}: expression must be a non-empty string")
    validate_expr_safety(expr, where=expression_id)
    tree = parse_eval_tree(expr)
    ensure_allowed_ast_nodes(tree, expr=expr, allowed_nodes=ALLOWED_AST_NODES)
    unsupported: list[UnsupportedReason] = []
    compiled = _compile_node(
        tree,
        variables=set() if variables is None else set(variables),
        expression_id=expression_id,
        unsupported=unsupported,
    )
    return compiled, tuple(unsupported)


def compile_value_expression(
    value: Any,
    *,
    variables: set[str],
    expression_id: str,
) -> tuple[ExpressionSpec, tuple[UnsupportedReason, ...]]:
    if isinstance(value, (bool, int, float)):
        return literal_expression(value), ()
    if isinstance(value, str):
        return compile_expression(value, variables=variables, expression_id=expression_id)
    return literal_expression(value), ()
