"""Exact elementary Cartesian arithmetic and conservative zero relations.

Lines retain homogeneous coefficients internally. Scalar measurements apply
normalization explicitly; only zero-equality relaxations remove normalization.
"""

import ast
import operator

import sympy as sp

from geosolver.problem.scalar_geometry import ScalarGeometry

CARTESIAN_CALLS = {
    "Angle",
    "sin",
    "cos",
    "tan",
    "Point",
    "Midpoint",
    "Vector",
    "Distance",
    "OnLine",
    "sqrt",
    "abs",
    "Abs",
    "Line",
    "Circle",
    "Area",
    "Dot",
    "Collinear",
    "Perpendicular",
    "Parallel",
    "Intersect",
    "IntersectLines",
    "Circumcenter",
    "Circumcircle",
    "Center",
    "Radius",
    "FootOfPerpendicular",
    "PointOnSegment",
    "Centroid",
    "Orthocenter",
    "Reflect",
    "ParallelLine",
    "PerpendicularLine",
    "PerpendicularBisector",
    "OnCircle",
    "OnSegment",
    "IsTangent",
    "CircleThroughThreePoints",
    "AreConcyclic",
}


def squared_distance(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b, strict=True))


class CartesianPolynomials(ScalarGeometry):
    def resolve(self, node):
        while isinstance(node, ast.Name) and node.id in self.definitions:
            self.visits += 1
            if self.visits > 1000:
                raise ValueError("Cartesian expression too large")
            node = self.parse(self.definitions[node.id])
        return node

    def line(self, node):
        node = self.resolve(node)
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            raise ValueError("unsupported exact line")
        name, args = node.func.id, node.args
        if name == "Line":
            if len(args) == 3:
                return tuple(self.scalar(a) for a in args)
            if len(args) == 2:
                a, b = (self.point(arg) for arg in args)
                return a[1] - b[1], b[0] - a[0], a[0] * b[1] - b[0] * a[1]
        if name in {"PerpendicularLine", "ParallelLine"} and len(args) == 2:
            try:
                a, b, _ = self.line(args[0])
                p = self.point(args[1])
            except ValueError:
                a, b, _ = self.line(args[1])
                p = self.point(args[0])
            if name == "PerpendicularLine":
                a, b = b, -a
            return a, b, -a * p[0] - b * p[1]
        if name == "PerpendicularBisector" and len(args) == 2:
            p, q = (self.point(a) for a in args)
            a, b = q[0] - p[0], q[1] - p[1]
            return a, b, -(a * (p[0] + q[0]) + b * (p[1] + q[1])) / 2
        raise ValueError("unsupported exact line")

    @staticmethod
    def intersection(first, second):
        a, b, c = first
        d, e, f = second
        determinant = a * e - b * d
        return (b * f - c * e) / determinant, (c * d - a * f) / determinant

    def circumcenter(self, args):
        a, b, c = (self.point(arg) for arg in args)
        bx, by, cx, cy = b[0] - a[0], b[1] - a[1], c[0] - a[0], c[1] - a[1]
        denominator = 2 * (bx * cy - by * cx)
        bs, cs = bx * bx + by * by, cx * cx + cy * cy
        return a[0] + (bs * cy - cs * by) / denominator, a[1] + (cs * bx - bs * cx) / denominator

    def circle(self, node):
        node = self.resolve(node)
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            raise ValueError("unsupported exact circle")
        name, args = node.func.id, node.args
        if name == "Circle" and len(args) == 2:
            return self.point(args[0]), self.scalar(args[1]) ** 2
        if name in {"Circumcircle", "CircleThroughThreePoints"} and len(args) == 3:
            center = self.circumcenter(args)
            return center, squared_distance(center, self.point(args[0]))
        raise ValueError("unsupported exact circle")

    def point(self, node):
        node = self.resolve(node)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            name, args = node.func.id, node.args
            if name in {"Intersect", "IntersectLines"} and len(args) == 2:
                return self.intersection(*(self.line(a) for a in args))
            if name == "Circumcenter" and len(args) == 3:
                return self.circumcenter(args)
            if name == "Center" and len(args) == 1:
                return self.circle(args[0])[0]
            if name == "Centroid" and len(args) == 3:
                points = [self.point(a) for a in args]
                return tuple(sum(p[i] for p in points) / 3 for i in range(2))
            if name == "Orthocenter" and len(args) == 3:
                points = [self.point(a) for a in args]
                center = self.circumcenter(args)
                return tuple(sum(p[i] for p in points) - 2 * center[i] for i in range(2))
            if name == "PointOnSegment" and len(args) == 3:
                a, b = (self.point(arg) for arg in args[:2])
                t = self.scalar(args[2])
                return tuple(x + t * (y - x) for x, y in zip(a, b, strict=True))
            if name == "FootOfPerpendicular" and len(args) == 2:
                try:
                    a, b, c = self.line(args[0])
                    p = self.point(args[1])
                except ValueError:
                    a, b, c = self.line(args[1])
                    p = self.point(args[0])
                shift = (a * p[0] + b * p[1] + c) / (a * a + b * b)
                return p[0] - a * shift, p[1] - b * shift
            if name == "Reflect" and len(args) == 2:
                p = self.point(args[0])
                try:
                    a, b, c = self.line(args[1])
                except ValueError:
                    center = self.point(args[1])
                    return tuple(2 * q - v for q, v in zip(center, p, strict=True))
                shift = 2 * (a * p[0] + b * p[1] + c) / (a * a + b * b)
                return p[0] - a * shift, p[1] - b * shift
        return super().point(node)

    def scalar(self, node):
        if isinstance(node, ast.Attribute) and node.attr in {"a", "b", "c"}:
            a, b, c = self.line(node.value)
            return (a, b, c)["abc".index(node.attr)] / sp.sqrt(a * a + b * b)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            name, args = node.func.id, node.args
            if name == "Angle":
                if len(args) == 3:
                    a, b, c = (self.point(arg) for arg in args)
                    first = tuple(x - y for x, y in zip(a, b, strict=True))
                    second = tuple(x - y for x, y in zip(c, b, strict=True))
                    dot = sum(x * y for x, y in zip(first, second, strict=True))
                    norm = sp.sqrt(sum(x * x for x in first) * sum(x * x for x in second))
                elif len(args) == 2:
                    a, b, _ = self.line(args[0])
                    c, d, _ = self.line(args[1])
                    dot = sp.Abs(a * c + b * d)
                    norm = sp.sqrt((a * a + b * b) * (c * c + d * d))
                else:
                    raise ValueError("unsupported angle arity")
                # On the original nondegenerate domain atan2(|cross|,dot)
                # equals acos(dot/norm); line angles additionally use |dot|.
                # Undefined rays are never admitted by the final verifier.
                return sp.acos(dot / norm)
            if name == "Distance" and len(args) == 2:
                try:
                    p, q = (self.point(arg) for arg in args)
                except ValueError:
                    p = self.point(args[0])
                    a, b, c = self.line(args[1])
                    return sp.Abs(a * p[0] + b * p[1] + c) / sp.sqrt(a * a + b * b)
                return sp.sqrt(squared_distance(p, q))
            if name == "Area" and len(args) >= 3:
                points = [self.point(a) for a in args]
                return (
                    sp.Abs(
                        sum(
                            p[0] * q[1] - p[1] * q[0]
                            for p, q in zip(points, points[1:] + points[:1], strict=True)
                        )
                    )
                    / 2
                )
            if name == "Dot" and len(args) == 2:
                try:
                    p, q = (self.point(a) for a in args)
                except ValueError:
                    a, b, _ = self.line(args[0])
                    c, d, _ = self.line(args[1])
                    return (a * c + b * d) / sp.sqrt((a * a + b * b) * (c * c + d * d))
                return sum(x * y for x, y in zip(p, q, strict=True))
            if name in {"Parallel", "Perpendicular"} and len(args) == 2:
                a, b, _ = self.line(args[0])
                c, d, _ = self.line(args[1])
                numerator = a * d - b * c if name == "Parallel" else a * c + b * d
                return numerator / sp.sqrt((a * a + b * b) * (c * c + d * d))
            if name == "OnLine" and len(args) == 2:
                p = self.point(args[0])
                a, b, c = self.line(args[1])
                return sp.Abs(a * p[0] + b * p[1] + c) / sp.sqrt(a * a + b * b)
            if name == "Collinear" and len(args) == 3:
                p, a, b = (self.point(arg) for arg in args)
                return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
            if name == "Radius" and len(args) == 1:
                return sp.sqrt(self.circle(args[0])[1])
        return super().scalar(node)

    def zero_relation(self, node):
        """Necessary polynomial equalities for original zero-valued predicates."""
        node = self.resolve(node)
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            return None
        name, args = node.func.id, node.args
        if name in {"OnSegment", "Collinear"} and len(args) == 3:
            p, a, b = (self.point(arg) for arg in args)
            return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
        if name in {"Perpendicular", "Parallel"} and len(args) == 2:
            a, b, _ = self.line(args[0])
            c, d, _ = self.line(args[1])
            return a * d - b * c if name == "Parallel" else a * c + b * d
        if name == "OnLine" and len(args) == 2:
            p = self.point(args[0])
            a, b, c = self.line(args[1])
            return a * p[0] + b * p[1] + c
        if name == "OnCircle" and len(args) == 2:
            p = self.point(args[0])
            center, radius_squared = self.circle(args[1])
            return squared_distance(p, center) - radius_squared
        if name == "AreConcyclic" and len(args) == 4:
            center = self.circumcenter(args[:3])
            return squared_distance(center, self.point(args[3])) - squared_distance(
                center, self.point(args[0])
            )
        if name == "IsTangent" and len(args) == 2:
            try:
                a, b, c = self.line(args[0])
                center, rs = self.circle(args[1])
            except ValueError:
                try:
                    a, b, c = self.line(args[1])
                    center, rs = self.circle(args[0])
                except ValueError:
                    p, ps = self.circle(args[0])
                    q, qs = self.circle(args[1])
                    return (squared_distance(p, q) - ps - qs) ** 2 - 4 * ps * qs
            return (a * center[0] + b * center[1] + c) ** 2 - rs * (a * a + b * b)
        return None


def exact_guard_value(source, geometry, substitutions):
    """Return a proved boolean, or None when the original guard is unsupported.

    Unknown is never interpreted as false. This is only an exclusion proof for
    polynomial relaxation roots, never an admission gate or a replacement for
    the original high-precision domain and guard verification.
    """
    relations = {
        ast.Eq: sp.Eq,
        ast.NotEq: sp.Ne,
        ast.Lt: sp.Lt,
        ast.LtE: sp.Le,
        ast.Gt: sp.Gt,
        ast.GtE: sp.Ge,
    }
    assumptions = {
        "AssumeEq": sp.Eq,
        "AssumeNe": sp.Ne,
        "AssumeLt": sp.Lt,
        "AssumeLe": sp.Le,
        "AssumeGt": sp.Gt,
        "AssumeGe": sp.Ge,
    }

    def boolean(expression):
        if expression is sp.true:
            return True
        if expression is sp.false:
            return False
        return None

    def conjunction(values):
        if False in values:
            return False
        return True if all(value is True for value in values) else None

    def disjunction(values):
        if True in values:
            return True
        return False if all(value is False for value in values) else None

    scalar_visits = 0

    def scalar(node):
        # Exclusion proofs deliberately use only concrete arithmetic. Geometry
        # reductions may discard construction validity, and must never turn an
        # undefined original primitive into a proved false guard. Evaluate each
        # operation after substitution so cancellation cannot conceal a pole.
        nonlocal scalar_visits
        scalar_visits += 1
        if scalar_visits > 1000:
            raise ValueError("guard arithmetic too large")
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            value = geometry.scalar(node)
        elif isinstance(node, ast.Name):
            if node.id in geometry.definitions:
                return scalar(geometry.parse(geometry.definitions[node.id]))
            value = substitutions.get(sp.Symbol(node.id, real=True))
            if value is None:
                raise ValueError("unknown original guard scalar")
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub | ast.UAdd):
            value = (-1 if isinstance(node.op, ast.USub) else 1) * scalar(node.operand)
        elif isinstance(node, ast.BinOp):
            a, b = scalar(node.left), scalar(node.right)
            operations = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul}
            if type(node.op) in operations:
                value = operations[type(node.op)](a, b)
            elif isinstance(node.op, ast.Div) and b.is_zero is False:
                value = a / b
            elif isinstance(node.op, ast.Pow) and b.is_Integer and abs(b) <= 1000:
                if b < 0 and a.is_zero is not False:
                    raise ValueError("undefined original guard power")
                value = a**b
            else:
                raise ValueError("unsupported original guard arithmetic")
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and len(node.args) == 1
            and not node.keywords
        ):
            argument = scalar(node.args[0])
            if node.func.id in {"abs", "Abs"}:
                value = sp.Abs(argument)
            elif node.func.id == "sqrt" and argument.is_nonnegative is True:
                value = sp.sqrt(argument)
            else:
                raise ValueError("unsupported original guard function")
        else:
            raise ValueError("unsupported original guard scalar")
        if value.is_real is not True or value.is_finite is not True:
            raise ValueError("undefined original guard expression")
        return value

    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) is bool:
            return node.value
        if isinstance(node, ast.Compare):
            operands = [node.left, *node.comparators]
            values = []
            for left, right, operation in zip(operands[:-1], operands[1:], node.ops, strict=True):
                relation = relations.get(type(operation))
                if relation is None:
                    return None
                values.append(boolean(relation(scalar(left), scalar(right))))
            return conjunction(values)
        if isinstance(node, ast.BoolOp):
            values = [visit(child) for child in node.values]
            return conjunction(values) if isinstance(node.op, ast.And) else disjunction(values)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            value = visit(node.operand)
            return None if value is None else not value
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
            name = node.func.id
            if name == "Assume" and len(node.args) == 1:
                return visit(node.args[0])
            if name in assumptions and len(node.args) == 2:
                return boolean(assumptions[name](*(scalar(a) for a in node.args)))
            if name in {"And", "Or"}:
                values = [visit(child) for child in node.args]
                return conjunction(values) if name == "And" else disjunction(values)
        return None

    try:
        return visit(geometry.parse(source))
    except (ValueError, TypeError, ArithmeticError):
        return None
