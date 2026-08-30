"""Lossless numeric tokens for AST rewrites (including macro-generated nodes)."""

from __future__ import annotations

import ast
import copy
import hashlib
import re


def annotate_source(tree: ast.AST, source: str) -> ast.AST:
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            node.numeric_lexeme = ast.get_source_segment(source, node)
        if isinstance(node, ast.Call):
            location = f"{source}\0{node.lineno}:{node.col_offset}:{node.end_col_offset}"
            node.call_site_id = hashlib.sha256(location.encode()).hexdigest()[:24]
    return tree


def source_expression(node: ast.AST, source: str | None = None) -> str:
    """Unparse syntax, never the rounded float stored by Python's parser."""
    tree = copy.deepcopy(node)
    if source is not None:
        annotate_source(tree, source)
    names = {item.id for item in ast.walk(tree) if isinstance(item, ast.Name)}
    replacements = {}

    class Tokens(ast.NodeTransformer):
        def visit_Constant(self, item):
            token = getattr(item, "numeric_lexeme", None)
            if token is None:
                return item
            name = f"_numeric_token_{len(replacements)}"
            while name in names:
                name += "_"
            names.add(name)
            replacements[name] = token
            return ast.copy_location(ast.Name(id=name, ctx=ast.Load()), item)

    rendered = ast.unparse(Tokens().visit(tree))
    return re.sub(r"\b_numeric_token_\d+_*\b", lambda m: replacements.get(m[0], m[0]), rendered)
