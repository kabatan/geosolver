"""Recognize zero tests through nonzero rational changes of equation units."""

import ast
from fractions import Fraction

from geosolver.problem.expression_source import annotate_source


def rational_constant(node):
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        if type(node.value) is int:
            return Fraction(node.value)
        token = getattr(node, "numeric_lexeme", None)
        if token is not None:
            return Fraction(token)
        # An unannotated Python float has already lost the original literal.
        # Decline a proof rather than guess that rounded value was intended.
        raise ValueError("missing exact numeric token")
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd | ast.USub):
        value = rational_constant(node.operand)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp):
        left, right = rational_constant(node.left), rational_constant(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
    raise ValueError("not a rational constant")


def zero_test_call(expression):
    """Remove only rational operations preserving the entire residual's zeros."""
    try:
        node = annotate_source(ast.parse(expression, mode="eval"), expression).body
    except (SyntaxError, TypeError):
        return None

    def constant(node):
        try:
            return rational_constant(node)
        except (ValueError, ArithmeticError):
            return None

    while True:
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd | ast.USub):
            node = node.operand
        elif isinstance(node, ast.BinOp):
            left, right = constant(node.left), constant(node.right)
            if isinstance(node.op, ast.Mult):
                if left is not None and left != 0:
                    node = node.right
                elif right is not None and right != 0:
                    node = node.left
                else:
                    return None
            elif isinstance(node.op, ast.Div) and right is not None and right != 0:
                node = node.left
            elif isinstance(node.op, ast.Add | ast.Sub):
                if right == 0:
                    node = node.left
                elif left == 0:
                    node = node.right
                else:
                    return None
            else:
                return None
        else:
            return node if isinstance(node, ast.Call) else None
