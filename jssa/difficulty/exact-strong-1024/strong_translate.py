"""Input-only extensions of the unchanged exp1 converter (no benchmark imports)."""
import ast
import itertools

import sympy as sp
from algebraize import (Translator, System, Unsupported, Pt, Ln, Circ, Poly,
                        AngleLin, sub, norm2, cross, dot)


class ConversionError(Unsupported):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


class StrongSystem(System):
    def __init__(self):
        super().__init__(mode="fresh")
        self.guards = []
        self.receipts = []
        self.constants = []

    def require(self, expr, source, op="!="):
        expr = self.materialize(sp.sympify(expr))
        num, den = sp.fraction(sp.cancel(expr))
        if expr.has(sp.pi):
            raise ConversionError("NONALGEBRAIC_PI", source)
        try:
            self._check_rational(num)
            self._check_rational(den)
        except Unsupported as exc:
            raise ConversionError("NONALGEBRAIC_CONSTANT", str(exc)) from exc
        self.add_nondeg(den)
        self.guards.append((expr, op, source))
        self.receipts.append({"source": source, "operator": op, "expression": str(expr)})
        if op in ("!=", ">", "<"):
            if num == 0:
                raise ConversionError("INCONSISTENT_NONZERO", source)
            self.add_nondeg(num)

    def sqrt(self, e):
        # Keep denominators that the old sqrt encoding could lose on clearing.
        self.add_nondeg(sp.fraction(sp.together(e))[1])
        s = super().sqrt(e)
        if s.free_symbols:
            self.guards.append((s, ">=", "sqrt:principal_real_root"))
        return s


class StrongTranslator(Translator):
    def __init__(self, dsl):
        super().__init__(dsl, mode="fresh")
        old = self.sys
        self.sys = StrongSystem()
        for attr in ("variables", "dsl_vars", "aux_kinds"):
            setattr(self.sys, attr, getattr(old, attr))
        self.location = "input"
        self.constant_cache = {}

    def require(self, expr, why, op="!="):
        self.sys.require(expr, self.location + ":" + why, op)

    def valid(self, obj, why):
        if isinstance(obj, Ln):
            self.require(norm2(obj.d), why + ":line_direction")
        elif isinstance(obj, Circ):
            self.require(obj.r2, why + ":radius_squared", ">")
            if obj.r is not None:
                self.require(obj.r, why + ":radius", ">")

    def node(self, n):
        # Every construction/measurement consuming or returning a line/circle
        # receives the same validity rule, including nested anonymous objects.
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
            args = [self.node(a) for a in n.args]
            kw = {k.arg: self.node(k.value) for k in n.keywords}
            fn = getattr(self, "f_" + n.func.id, None)
            if fn is None:
                raise ConversionError("UNSUPPORTED_COMMAND", n.func.id)
            name = n.func.id
            for obj in args:
                self.valid(obj, name + ":argument")
            if name in ("Triangle", "Circumcenter", "Circumcircle", "CircleThroughThreePoints",
                        "Orthocenter", "Incenter", "Incircle", "Excenter", "Excircle",
                        "IncircleContactPoint"):
                pts = args[0] if len(args) == 1 and isinstance(args[0], list) else args[:3]
                if len(pts) == 3 and all(isinstance(p, Pt) for p in pts):
                    self.require(cross(sub(pts[1], pts[0]), sub(pts[2], pts[0])), name + ":triangle")
            if name in ("Angle", "AngleBisector"):
                self.require(norm2(sub(args[0], args[1])), name + ":first_ray")
                self.require(norm2(sub(args[2], args[1])), name + ":second_ray")
            if name in ("PointOnSegment", "OnSegment"):
                a, b = args[:2] if name == "PointOnSegment" else args[1:3]
                self.require(norm2(sub(a, b)), name + ":segment")
            if name == "OnLine" and len(args) == 3:
                self.require(norm2(sub(args[1], args[2])), name + ":line")
            if name in ("Intersect", "IntersectLines") and all(isinstance(o, Circ) for o in args[:2]):
                self.require(norm2(sub(args[0].c, args[1].c)), name + ":distinct_centers")
            result = fn(*args, **kw)
            self.valid(result, name + ":result")
            if isinstance(result, sp.Expr):
                self.sys.add_nondeg(sp.fraction(sp.together(result))[1])
            if isinstance(result, Pt):
                for coordinate in (result.x, result.y):
                    self.sys.add_nondeg(sp.fraction(sp.together(coordinate))[1])
            if name in ("Intersect", "IntersectLines") and isinstance(kw.get("exclude"), Pt):
                self.require(norm2(sub(result, kw["exclude"])), name + ":exclude")
            return result
        return super().node(n)

    def algebraic_constant(self, c):
        c = sp.simplify(c)
        if c.is_Rational:
            return c
        if c.free_symbols or c.is_algebraic is not True or c.is_real is not True:
            raise ConversionError("NONALGEBRAIC_CONSTANT", str(c))
        key = sp.srepr(c)
        if key not in self.constant_cache:
            z = sp.Symbol("_constant")
            p = sp.Poly(sp.minimal_polynomial(c, z), z)
            v = self.sys.new_var("k")
            self.sys.add_eq(p.as_expr().subs(z, v))
            self.sys.constants.append({"symbol": str(v), "expression": str(c),
                                       "minimal_polynomial": str(p.as_expr()),
                                       "intended_value_80d": str(sp.N(c, 80))})
            self.constant_cache[key] = v
        return self.constant_cache[key]

    def cos_sin_pi(self, a):
        return self.algebraic_constant(sp.cos(a * sp.pi)), self.algebraic_constant(sp.sin(a * sp.pi))

    def f_Area(self, *args):
        if len(args) == 1 and isinstance(args[0], Circ):
            raise ConversionError("NONALGEBRAIC_PI", "Area(circle) contains pi")
        return super().f_Area(*args)

    def guard_node(self, node):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            name = node.func.id
            if name == "And":
                for n in node.args:
                    self.guard_node(n)
                return
            if name in ("Or", "Not"):
                raise ConversionError("UNSUPPORTED_BOOLEAN_GUARD", ast.unparse(node))
            if name in ("ConvexPolygon", "AssumeConvex", "SimplePolygon"):
                pts = self.node(node.args[0]) if len(node.args) == 1 else [self.node(a) for a in node.args]
                if isinstance(pts, Poly):
                    pts = pts.pts
                for a, b in itertools.combinations(pts, 2):
                    self.require(norm2(sub(a, b)), name + ":distinct_vertices")
                if name != "SimplePolygon":
                    for i in range(len(pts)):
                        a, b, c = (pts[(i+j) % len(pts)] for j in range(3))
                        self.require(cross(sub(b, a), sub(c, b)), name + ":strict_turn")
                return
            if name in ("AcuteTriangle", "ObtuseTriangle"):
                pts = [self.node(a) for a in node.args]
                if len(pts) != 3:
                    raise ConversionError("UNSUPPORTED_GUARD", name)
                self.require(cross(sub(pts[1], pts[0]), sub(pts[2], pts[0])), name + ":triangle")
                if name == "AcuteTriangle":
                    for i in range(3):
                        self.require(dot(sub(pts[(i+1)%3], pts[i]), sub(pts[(i+2)%3], pts[i])), name, ">")
                # Obtuse: an unspecified vertex may have a right angle; do not
                # require all three dot products to be nonzero.
                return
            if name == "Bound":
                if len(node.args) < 2 or not isinstance(node.args[1], (ast.Tuple, ast.List)) or len(node.args[1].elts) != 2:
                    raise ConversionError("UNSUPPORTED_GUARD", "Bound requires a pair of endpoints")
                value = self.node(node.args[0])
                inclusive = True
                for keyword in node.keywords:
                    if keyword.arg == "inclusive":
                        if not isinstance(keyword.value, ast.Constant) or not isinstance(keyword.value.value, bool):
                            raise ConversionError("UNSUPPORTED_GUARD", "Bound inclusive must be boolean literal")
                        inclusive = keyword.value.value
                for side, endpoint in enumerate(node.args[1].elts):
                    if isinstance(endpoint, ast.Constant) and endpoint.value is None:
                        continue
                    bound = self.node(endpoint)
                    op = (">=" if inclusive else ">") if side == 0 else ("<=" if inclusive else "<")
                    self.require(value-bound, "Bound:endpoint", op)
                return
            self.node(node)
            return
        if isinstance(node, ast.Compare):
            values = [self.node(n) for n in [node.left, *node.comparators]]
            names = {ast.Lt: "<", ast.Gt: ">", ast.LtE: "<=", ast.GtE: ">=", ast.Eq: "=", ast.NotEq: "!="}
            for a, op, b in zip(values, node.ops, values[1:]):
                if isinstance(a, AngleLin) or isinstance(b, AngleLin):
                    if not isinstance(op, ast.Eq):
                        raise ConversionError("UNSUPPORTED_ANGLE_GUARD", ast.unparse(node))
                elif isinstance(a, sp.Expr) and isinstance(b, sp.Expr):
                    if not isinstance(op, ast.Eq):
                        self.require(a-b, "predicate_comparison", names[type(op)])
            return
        raise ConversionError("UNSUPPORTED_GUARD", ast.unparse(node))

    def run(self, with_target=True):
        for i, c in enumerate(self.dsl["constructions"]):
            self.location = f"construction[{i}]/{c['name']}"
            value = self.ev(c["expression"])
            if isinstance(value, Pt):
                value = self.sys.fresh_point(value)
            elif isinstance(value, sp.Expr):
                self.sys.add_nondeg(sp.fraction(sp.together(value))[1])
            self.env[c["name"]] = value
        for i, cond in enumerate(self.dsl["conditions"]):
            self.location = f"condition[{i}]"
            if "predicate" in cond:
                node = ast.parse(cond["predicate"], mode="eval").body
                self.guard_node(node)
                self.predicate(cond["predicate"])
            else:
                a, b = self.ev(cond["left"]), self.ev(str(cond["right"]))
                if cond["operator"] == "=":
                    self.equate(a, b)
                elif isinstance(a, sp.Expr) and isinstance(b, sp.Expr):
                    self.require(a-b, "explicit_comparison", cond["operator"])
                else:
                    raise ConversionError("UNSUPPORTED_GUARD_TYPE", str(cond))
        used = set().union(*(e.free_symbols for e in self.sys.eqs)) if self.sys.eqs else set()
        if used & set(self.sys.angle_vars):
            raise ConversionError("MIXED_ANGLE_VARIABLE", "angle also used algebraically")
        self.location = "target"
        t = self.ev(self.dsl["target"])
        if isinstance(t, AngleLin):
            raise ConversionError("ANGLE_TARGET", "angle-valued target")
        self.sys.rationalize(t)
        tv = self.sys.new_var("t")
        self.sys.add_eq(tv-t)
        return self.sys, tv


def translate(dsl):
    try:
        return StrongTranslator(dsl).run()
    except ConversionError:
        raise
    except Unsupported as e:
        text = str(e)
        code = "NONALGEBRAIC_PI" if "pi" in text else "UNSUPPORTED_DSL"
        raise ConversionError(code, text) from e
