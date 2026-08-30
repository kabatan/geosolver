"""Small exact arithmetic model for construction identities, not a solver.

Only elementary Cartesian arithmetic is supported. Unsupported constructions
are not guessed or evaluated via Python. All numeric tokens stay rational.
"""

import ast
import hashlib
import operator

import sympy as sp

from geosolver.problem.expression_source import annotate_source, source_expression


class ScalarGeometry:
    def __init__(self, constructions, *, allow_opaque=False):
        self.definitions = constructions
        self.points = {}
        self.visits = 0
        self.allow_opaque = allow_opaque

    def parse(self, source):
        return annotate_source(ast.parse(source, mode="eval"), source).body

    def point(self, node):
        self.visits += 1
        if self.visits > 1000:
            raise ValueError("identity expression too large")
        if isinstance(node, ast.Name) and node.id in self.definitions:
            if node.id not in self.points:
                self.points[node.id] = self.point(self.parse(self.definitions[node.id]))
            return self.points[node.id]
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            name = node.func.id
            if name == "Point" and len(node.args) == 2:
                return tuple(self.scalar(a) for a in node.args)
            if name in {"Vector", "Midpoint"} and len(node.args) == 2:
                a, b = (self.point(p) for p in node.args)
                return tuple(
                    y - x if name == "Vector" else (x + y) / 2 for x, y in zip(a, b, strict=True)
                )
        raise ValueError("unsupported exact point construction")

    def scalar(self, node):
        self.visits += 1
        if self.visits > 1000:
            raise ValueError("identity expression too large")
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return sp.Rational(source_expression(node))
        if isinstance(node, ast.Name):
            if node.id == "pi":
                return sp.pi
            if node.id in self.definitions:
                return self.scalar(self.parse(self.definitions[node.id]))
            return sp.Symbol(node.id, real=True)
        if isinstance(node, ast.Attribute) and node.attr in {"x", "y"}:
            return self.point(node.value)[node.attr == "y"]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub | ast.UAdd):
            return (-1 if isinstance(node.op, ast.USub) else 1) * self.scalar(node.operand)
        if isinstance(node, ast.BinOp):
            operations = {
                ast.Add: operator.add,
                ast.Sub: operator.sub,
                ast.Mult: operator.mul,
                ast.Div: operator.truediv,
                ast.Pow: operator.pow,
            }
            if type(node.op) in operations:
                a, b = self.scalar(node.left), self.scalar(node.right)
                if isinstance(node.op, ast.Pow) and (not b.is_number or abs(b) > 1000):
                    raise ValueError("identity exponent too large")
                return operations[type(node.op)](a, b)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            functions = {
                "sqrt": sp.sqrt,
                "sin": sp.sin,
                "cos": sp.cos,
                "tan": sp.tan,
                "abs": sp.Abs,
                "Abs": sp.Abs,
            }
            if node.func.id in functions and len(node.args) == 1 and not node.keywords:
                return functions[node.func.id](self.scalar(node.args[0]))
            if node.func.id == "OnLine" and len(node.args) == 3:
                p, a, b = (self.point(arg) for arg in node.args)
                return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
            if node.func.id == "Distance" and len(node.args) == 2:
                p, line = node.args
                if isinstance(line, ast.Name) and line.id in self.definitions:
                    line = self.parse(self.definitions[line.id])
                if (
                    isinstance(line, ast.Call)
                    and isinstance(line.func, ast.Name)
                    and line.func.id == "Line"
                    and len(line.args) == 2
                ):
                    p = self.point(p)
                    a, b = (self.point(arg) for arg in line.args)
                    return sp.Abs(
                        (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
                    ) / sp.sqrt((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2)
        if self.allow_opaque and isinstance(node, ast.Call | ast.Attribute):
            digest = hashlib.sha256(source_expression(node).encode()).hexdigest()
            return sp.Symbol("opaque_" + digest, real=True)
        raise ValueError("unsupported exact scalar expression")
