"""Validation helpers extracted from IR compiler."""

from __future__ import annotations

import ast

from geosolver.problem.ir.errors import IRCompileError


def _normalize_math_caret(expr: str) -> str:
    """Rewrite mathematical ``^`` operators as Python ``**`` operators.

    This must happen before Python parses the expression: Python gives
    BitXor a different precedence from exponentiation (for example,
    ``a^2+b^2``), so changing an already-built AST would be semantically
    wrong.  Quoted string literals are left untouched.
    """
    chars: list[str] = []
    quote: str | None = None
    escaped = False
    for char in expr:
        if quote is not None:
            chars.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            chars.append(char)
        elif char == "^":
            chars.append("**")
        else:
            chars.append(char)
    return "".join(chars)


def parse_eval_tree(expr: str) -> ast.AST:
    try:
        # Normalize before parsing so caret receives exponentiation
        # precedence rather than Python's BitXor precedence.
        return ast.parse(_normalize_math_caret(expr), mode="eval")
    except SyntaxError as e:
        raise IRCompileError(f"構文エラー: {e}", expr=expr, cause=e) from e


def ensure_allowed_ast_nodes(tree: ast.AST, *, expr: str, allowed_nodes: set[type]) -> None:
    for node in ast.walk(tree):
        node_type = type(node)
        if node_type not in allowed_nodes:
            raise IRCompileError(f"許可されていないAST ノード: {node_type.__name__}", expr=expr)


def collect_name_nodes(tree: ast.AST) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.append(node.id)
    return names
