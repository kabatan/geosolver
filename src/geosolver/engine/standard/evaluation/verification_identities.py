"""Structural zero certificates for equality leaves and closed boundaries.

This proves only equality of zero loci of explicit scalar expressions, not
existence or elimination of general constraint systems.
"""

import ast
from functools import lru_cache

from geosolver.problem.expression_source import annotate_source, source_expression
from geosolver.problem.ir.compiler import safe_eval_expr_hp


def active_source(source, context):
    node = annotate_source(ast.parse(source, mode="eval"), source).body
    while isinstance(node, ast.IfExp):
        condition = safe_eval_expr_hp(source_expression(node.test), context)
        node = node.body if condition else node.orelse
    # min of nonnegative distances is zero iff a selected minimum is zero.
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "min"
        and not node.keywords
        and node.args
        and all(
            isinstance(a, ast.Call)
            and isinstance(a.func, ast.Name)
            and a.func.id in {"Distance", "abs", "Abs"}
            for a in node.args
        )
    ):
        node = min(node.args, key=lambda a: safe_eval_expr_hp(source_expression(a), context))
    return source_expression(node)


@lru_cache(maxsize=4096)
def zero_signature(source, constructions):
    from geosolver.runtime.symbolic import request

    return request("zero_signature", (source, constructions))


def signatures(sources, constructions, context):
    return {
        signature
        for source in sources
        if (signature := zero_signature(active_source(source, context), constructions)) is not None
    }
