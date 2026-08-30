"""Exact evaluation of closed scalar arithmetic, without evaluating Python code."""

import ast
import operator
import re
from functools import lru_cache

import sympy as sp


@lru_cache(maxsize=1024)
def exact_constant(expression: str):
    operations = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
    }
    functions = {
        "sqrt": sp.sqrt,
        "sin": sp.sin,
        "cos": sp.cos,
        "tan": sp.tan,
        "abs": sp.Abs,
        "Abs": sp.Abs,
    }

    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return sp.Rational(ast.get_source_segment(expression, node))
        if isinstance(node, ast.Name) and node.id == "pi":
            return sp.pi
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd | ast.USub):
            return visit(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        if isinstance(node, ast.BinOp) and type(node.op) in operations:
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 10000:
                raise ValueError("constant exponent too large")
            return operations[type(node.op)](left, right)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in functions
            and len(node.args) == 1
            and not node.keywords
        ):
            return functions[node.func.id](visit(node.args[0]))
        raise ValueError("not closed scalar arithmetic")

    try:
        return visit(ast.parse(expression, mode="eval").body)
    except (ValueError, TypeError, SyntaxError, ZeroDivisionError):
        return None


@lru_cache(maxsize=1024)
def normalized_difference(left: str, right: str) -> str:
    """Cancel common arithmetic terms before rounding; geometry calls stay opaque.

    This does not rewrite the search problem or infer geometric identities.
    In particular, C+x = C+x+1 reduces to -1 even when C exceeds HP precision.
    """
    atoms = {}
    operations = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
    }

    def visit(node, source):
        text = ast.get_source_segment(source, node)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return sp.Rational(text)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd | ast.USub):
            return visit(node.operand, source) * (-1 if isinstance(node.op, ast.USub) else 1)
        if isinstance(node, ast.BinOp) and type(node.op) in operations:
            a, b = visit(node.left, source), visit(node.right, source)
            if not isinstance(node.op, ast.Pow) or not b.is_number or abs(b) <= 10000:
                return operations[type(node.op)](a, b)
        if text not in atoms:
            atoms[text] = sp.Symbol(f"_atom{len(atoms)}")
        return atoms[text]

    try:
        expression = visit(ast.parse(left, mode="eval").body, left) - visit(
            ast.parse(right, mode="eval").body, right
        )
        sources = {str(symbol): f"({text})" for text, symbol in atoms.items()}
        return re.sub(r"\b_atom\d+\b", lambda match: sources[match.group()], str(expression))
    except (ValueError, TypeError, SyntaxError, ZeroDivisionError):
        return f"({left})-({right})"
