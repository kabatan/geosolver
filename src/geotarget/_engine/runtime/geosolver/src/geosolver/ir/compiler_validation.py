"""Validation helpers extracted from IR compiler."""

from __future__ import annotations

import ast
from typing import List, Set, Type

from geosolver.ir.errors import IRCompileError


def parse_eval_tree(expr: str) -> ast.AST:
    try:
        return ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise IRCompileError(f"構文エラー: {e}", expr=expr, cause=e) from e


def ensure_allowed_ast_nodes(tree: ast.AST, *, expr: str, allowed_nodes: Set[Type]) -> None:
    for node in ast.walk(tree):
        node_type = type(node)
        if node_type not in allowed_nodes:
            raise IRCompileError(
                f"許可されていないAST ノード: {node_type.__name__}", expr=expr
            )


def collect_name_nodes(tree: ast.AST) -> List[str]:
    names: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.append(node.id)
    return names