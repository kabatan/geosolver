"""Prove a positive uniform-scale chart preserves the original answer set.

All variables scale by t>0. Typed homogeneous expressions track exact degrees;
zero coordinates and lines through the origin are polymorphic in scale. Every
construction must have an equivariant domain, each equality/inequality must be
homogeneous, and the answer must have degree zero. A directly positive variable
then supplies the representative x=1 of every admissible scale orbit.
"""

import ast
from fractions import Fraction
from functools import lru_cache

from geosolver.engine.standard.problem.zero_test_source import rational_constant
from geosolver.problem.expression_source import annotate_source


def _parse(source):
    return annotate_source(ast.parse(source, mode="eval"), source).body


@lru_cache(maxsize=256)
def positive_scale_chart(variables, constructions, equalities, guards, answer):
    definitions = dict(constructions)
    active = set()
    cache = {}
    scalar = "scalar"

    def same(items, kind=None):
        if kind is not None and any(k != kind for k, _ in items):
            raise ValueError("incompatible geometric kinds")
        degrees = {degree for _, degree in items if degree is not None}
        if len(degrees) > 1:
            raise ValueError("mixed scaling degrees")
        return next(iter(degrees), None)

    def degree(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return scalar, None if rational_constant(node) == 0 else Fraction(0)
        if isinstance(node, ast.Name):
            if node.id in variables:
                return scalar, Fraction(1)
            if node.id in {"pi", "e"}:
                return scalar, Fraction(0)
            if node.id in definitions and node.id not in active:
                if node.id not in cache:
                    active.add(node.id)
                    try:
                        cache[node.id] = degree(_parse(definitions[node.id]))
                    finally:
                        active.remove(node.id)
                return cache[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd | ast.USub):
            return degree(node.operand)
        if isinstance(node, ast.BinOp):
            left, right = degree(node.left), degree(node.right)
            same((left, right), scalar) if isinstance(node.op, ast.Add | ast.Sub) else None
            if left[0] != scalar or right[0] != scalar:
                raise ValueError("non-scalar arithmetic")
            if isinstance(node.op, ast.Add | ast.Sub):
                return scalar, same((left, right))
            if isinstance(node.op, ast.Mult):
                return scalar, None if None in (left[1], right[1]) else left[1] + right[1]
            if isinstance(node.op, ast.Div):
                if right[1] is None:
                    raise ValueError("zero denominator")
                return scalar, None if left[1] is None else left[1] - right[1]
            if isinstance(node.op, ast.Pow):
                exponent = rational_constant(node.right)
                if left[1] is None:
                    if exponent <= 0:
                        raise ValueError("zero nonpositive power")
                    return scalar, None
                return scalar, left[1] * exponent
        if isinstance(node, ast.Attribute):
            kind, value = degree(node.value)
            if node.attr in {"x", "y"} and kind == "point":
                return scalar, value
            if node.attr in {"a", "b", "c"} and kind == "line":
                return scalar, value if node.attr == "c" else Fraction(0)
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            raise ValueError("unsupported homogeneous expression")
        name = node.func.id
        args = node.args
        values = [degree(arg) for arg in args]
        if node.keywords and (
            name != "Intersect" or any(keyword.arg != "exclude" for keyword in node.keywords)
        ):
            raise ValueError("unsupported keyword")
        if name in {"Point", "Vector"} and len(values) == 2:
            if name == "Point":
                return "point", same(values, scalar)
            return "point", same(values, "point")
        if name == "Line":
            if len(values) == 2:
                value = same(values, "point")
                # A line containing the origin maps to itself under any scale.
                return "line", None if any(d is None for _, d in values) else value
            if len(values) == 3:
                normal = same(values[:2], scalar)
                if normal is None or values[2][0] != scalar:
                    raise ValueError("zero line normal")
                return "line", None if values[2][1] is None else values[2][1] - normal
        if name == "Circle" and len(values) == 2:
            if values[0][0] != "point" or values[1][0] != scalar:
                raise ValueError("invalid circle")
            return "circle", same(values)
        if name in {"Circumcircle", "CircleThroughThreePoints", "Incircle"} and len(values) == 3:
            return "circle", same(values, "point")
        if name in {"Circumcenter", "Incenter", "Orthocenter", "Centroid"} and len(values) == 3:
            return "point", same(values, "point")
        if (
            name == "IncircleContactPoint"
            and len(values) == 4
            and values[3][0] == scalar
            and rational_constant(args[3]) in {0, 1, 2}
        ):
            return "point", same(values[:3], "point")
        if name == "Midpoint" and len(values) == 2:
            return "point", same(values, "point")
        if name == "PointOnSegment" and len(values) == 3 and values[2][1] in (None, 0):
            return "point", same(values[:2], "point")
        if name in {"Center", "Radius"} and len(values) == 1 and values[0][0] == "circle":
            return ("point" if name == "Center" else scalar), values[0][1]
        if name in {"Intersect", "IntersectLines"} and len(values) == 2:
            if any(k not in {"line", "circle"} for k, _ in values):
                raise ValueError("unsupported intersection")
            value = same(values)
            for keyword in node.keywords:
                same((degree(keyword.value), ("point", value)), "point")
            return "point", value
        if (
            name in {"ParallelLine", "PerpendicularLine", "FootOfPerpendicular", "Reflect"}
            and len(values) == 2
        ):
            kinds = tuple(k for k, _ in values)
            supported = (
                kinds in {("point", "point"), ("point", "line")}
                if name == "Reflect"
                else sorted(kinds) == ["line", "point"]
            )
            if not supported:
                raise ValueError("unsupported incidence construction")
            return ("line" if name.endswith("Line") else "point"), same(values)
        if name == "PerpendicularBisector" and len(values) == 2:
            return "line", same(values, "point")
        if name == "Distance" and len(values) == 2:
            if sorted(k for k, _ in values) not in (["line", "point"], ["point", "point"]):
                raise ValueError("unsupported distance")
            return scalar, same(values)
        if name == "Dot" and len(values) == 2:
            value = same(values)
            if all(k == "line" for k, _ in values):
                return scalar, Fraction(0)
            same(values, "point")
            return scalar, None if value is None else 2 * value
        if (name == "Collinear" and len(values) == 3) or (name == "Area" and len(values) >= 3):
            value = same(values, "point")
            return scalar, None if value is None else 2 * value
        if name == "AreConcyclic" and len(values) == 4:
            # The public primitive is Distance(D,circumcenter(A,B,C))-R,
            # not the algebraic four-point determinant.
            return scalar, same(values, "point")
        if name in {"Parallel", "Perpendicular"} and len(values) == 2:
            same(values, "line")
            return scalar, Fraction(0)
        if name == "OnLine" and len(values) == 3:
            value = same(values, "point")
            return scalar, None if value is None else 2 * value
        if name == "OnLine" and len(values) == 2:
            if tuple(k for k, _ in values) != ("point", "line"):
                raise ValueError("invalid line incidence")
            return scalar, same(values)
        if name == "OnCircle" and len(values) == 2:
            if tuple(k for k, _ in values) != ("point", "circle"):
                raise ValueError("invalid circle incidence")
            return scalar, same(values)
        if name == "OnSegment" and len(values) == 3:
            return scalar, same(values, "point")
        if name == "IsTangent" and len(values) == 2:
            if sorted(k for k, _ in values) not in (["circle", "line"], ["circle", "circle"]):
                raise ValueError("invalid tangent objects")
            return scalar, same(values)
        if name in {"Abs", "abs", "sqrt"} and len(values) == 1 and values[0][0] == scalar:
            value = values[0][1]
            return scalar, value / 2 if name == "sqrt" and value is not None else value
        if (
            name in {"sin", "cos", "tan"}
            and len(values) == 1
            and values[0] in {(scalar, None), (scalar, Fraction(0))}
        ):
            return scalar, Fraction(0)
        if (
            name in {"AssumeGt", "AssumeGe", "AssumeLt", "AssumeLe", "AssumeNe", "AssumeEq"}
            and len(values) == 2
        ):
            same(values, scalar)
            return "boolean", Fraction(0)
        raise ValueError("unsupported homogeneous primitive")

    try:
        for name in definitions:
            degree(ast.Name(id=name))
        for left, right in equalities:
            same(
                tuple(degree(_parse(str(source))) for source in (left, right)),
                scalar,
            )
        for source in guards:
            if degree(_parse(source))[0] != "boolean":
                return None
        if degree(_parse(answer)) != (scalar, Fraction(0)):
            return None
        for source in guards:
            node = _parse(source)
            if not isinstance(node, ast.Call) or len(node.args) != 2:
                continue
            first, second = node.args
            if node.func.id == "AssumeLt":
                first, second = second, first
            elif node.func.id != "AssumeGt":
                continue
            if (
                isinstance(first, ast.Name)
                and first.id in variables
                and isinstance(second, ast.Constant)
                and rational_constant(second) == 0
            ):
                return first.id
        return None
    except (ValueError, TypeError, SyntaxError, ArithmeticError, RecursionError):
        return None
