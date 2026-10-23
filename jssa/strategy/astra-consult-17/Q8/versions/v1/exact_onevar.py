"""Conservative, exact real answer-set audit for a subset of the public DSL.

No search boxes, numerical stopping tolerances, official answers, or solver
outputs enter the proof. Unsupported or undecidable is NOT treated as false.
SymPy's exact algebraic arithmetic is part of the trusted computing base.
"""
from __future__ import annotations

import ast
import hashlib
import itertools
import json
from dataclasses import dataclass
from functools import lru_cache

import sympy as s
from sympy.solvers.solvers import unrad


class Unsupported(Exception):
    pass


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def clean(e):
    return s.cancel(e)


@dataclass(frozen=True)
class Point:
    x: s.Expr
    y: s.Expr


@dataclass(frozen=True)
class Line:
    p: Point
    d: Point


@dataclass(frozen=True)
class Circle:
    center: Point
    radius: s.Expr


@dataclass(frozen=True)
class Pred:
    formula: tuple


def add(a, b):
    return Point(clean(a.x + b.x), clean(a.y + b.y))


def sub(a, b):
    return Point(clean(a.x - b.x), clean(a.y - b.y))


def mul(a, q):
    return Point(clean(a.x * q), clean(a.y * q))


def dot(a, b):
    return clean(a.x * b.x + a.y * b.y)


def cross(a, b):
    return clean(a.x * b.y - a.y * b.x)


def n2(a):
    return dot(a, a)


def atom(op, e):
    return (op, clean(e))


def both(*f):
    return ("and", *f)


def either(*f):
    return ("or", *f)


def necessary(f):
    """Equalities entailed by a formula, including conservative OR products."""
    if f[0] == "=":
        return [f[1]]
    if f[0] == "and":
        return [e for part in f[1:] for e in necessary(part)]
    if f[0] == "or":
        parts = [necessary(p) for p in f[1:]]
        if parts and all(parts):
            return [s.Mul(*(min(p, key=s.count_ops) for p in parts))]
    return []


class Compiler:
    def __init__(self, dsl):
        if len(dsl["variables"]) != 1:
            raise Unsupported("not one declared real variable")
        self.dsl = dsl
        self.x = s.Symbol(dsl["variables"][0], real=True)
        self.env = {str(self.x): self.x, "pi": s.pi}
        self.domains = []
        self.conditions = []
        self.rewrites = []
        self.location = ""

    def domain(self, op, e, why):
        self.domains.append((self.location + ":" + why, atom(op, e)))

    def div(self, a, b):
        self.domain("!=", b, "denominator")
        return clean(a / b)

    def sqrt(self, a):
        a = clean(a)
        self.domain(">=", a, "sqrt domain")
        return s.sqrt(a)

    def ev(self, text):
        return self.node(ast.parse(str(text).strip(), mode="eval").body)

    def node(self, n):
        if isinstance(n, ast.Constant):
            if n.value is None or isinstance(n.value, (bool, str)):
                return n.value
            if isinstance(n.value, (int, float)):
                return s.Rational(str(n.value))
        if isinstance(n, ast.Name):
            if n.id not in self.env:
                raise Unsupported("name:" + n.id)
            return self.env[n.id]
        if isinstance(n, (ast.Tuple, ast.List)):
            return [self.node(a) for a in n.elts]
        if isinstance(n, ast.Attribute):
            obj = self.node(n.value)
            if isinstance(obj, Point) and n.attr in ("x", "y"):
                return getattr(obj, n.attr)
            if isinstance(obj, Circle) and n.attr in ("center", "radius"):
                return getattr(obj, n.attr)
            # Normalized line coefficients have sign/normalization semantics.
            raise Unsupported("attribute:" + n.attr)
        if isinstance(n, ast.UnaryOp):
            v = self.node(n.operand)
            if isinstance(n.op, ast.USub):
                return mul(v, -1) if isinstance(v, Point) else -v
            if isinstance(n.op, ast.UAdd):
                return v
            if isinstance(n.op, ast.Not) and isinstance(v, Pred):
                return Pred(("not", v.formula))
        if isinstance(n, ast.BinOp):
            a, b = self.node(n.left), self.node(n.right)
            if isinstance(n.op, ast.Add):
                return add(a, b) if isinstance(a, Point) else a + b
            if isinstance(n.op, ast.Sub):
                return sub(a, b) if isinstance(a, Point) else a - b
            if isinstance(n.op, ast.Mult):
                if isinstance(a, Point):
                    return mul(a, b)
                if isinstance(b, Point):
                    return mul(b, a)
                return a * b
            if isinstance(n.op, ast.Div):
                if isinstance(a, Point):
                    return mul(a, self.div(s.S.One, b))
                return self.div(a, b)
            if isinstance(n.op, ast.Pow):
                if b.is_Integer:
                    if b < 0:
                        self.domain("!=", a, "negative power")
                    return a ** b
                if b == s.Rational(1, 2):
                    return self.sqrt(a)
                raise Unsupported("noninteger power")
        if isinstance(n, ast.Compare):
            vals = [self.node(n.left), *(self.node(a) for a in n.comparators)]
            ops = {ast.Eq: "=", ast.NotEq: "!=", ast.Lt: "<", ast.LtE: "<=",
                   ast.Gt: ">", ast.GtE: ">="}
            return Pred(both(*(self.relation(vals[i], ops[type(op)], vals[i + 1])
                               for i, op in enumerate(n.ops))))
        if isinstance(n, ast.BoolOp):
            parts = [self.node(a) for a in n.values]
            if not all(isinstance(a, Pred) for a in parts):
                raise Unsupported("nonpredicate boolean")
            return Pred(("and" if isinstance(n.op, ast.And) else "or",
                         *(p.formula for p in parts)))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
            fn = getattr(self, "f_" + n.func.id, None)
            if fn is None:
                raise Unsupported("function:" + n.func.id)
            return fn(*[self.node(a) for a in n.args],
                      **{k.arg: self.node(k.value) for k in n.keywords})
        raise Unsupported("syntax:" + type(n).__name__)

    def relation(self, a, op, b):
        if isinstance(a, Pred):
            if op == "=" and b == 0:
                return a.formula
            raise Unsupported("predicate residual used outside ==0")
        if isinstance(b, Pred):
            return self.relation(b, op, a)
        if isinstance(a, Point) and isinstance(b, Point) and op == "=":
            return both(atom("=", a.x - b.x), atom("=", a.y - b.y))
        a, b = s.sympify(a), s.sympify(b)
        if a.func == s.acos or b.func == s.acos:
            # acos: [-1,1] -> [0,pi] is one-to-one and decreasing.
            if a.func != s.acos:
                a, b = b, a
                op = {"<": ">", ">": "<", "<=": ">=", ">=": "<=",
                      "=": "=", "!=": "!="}[op]
            if b.func == s.acos:
                ca, cb = a.args[0], b.args[0]
            elif not b.free_symbols and (b >= 0) is s.S.true and (b <= s.pi) is s.S.true:
                ca, cb = a.args[0], s.cos(b)
            else:
                raise Unsupported("angle comparison outside monotone acos range")
            op = {"<": ">", ">": "<", "<=": ">=", ">=": "<=",
                  "=": "=", "!=": "!="}[op]
            self.rewrites.append(self.location + ":acos monotonicity")
            return atom(op, ca - cb)
        e = clean(a - b)
        if e.has(s.acos, s.asin, s.atan, s.atan2):
            raise Unsupported("general angle relation")
        return atom(op, e)

    def run(self):
        for c in self.dsl["constructions"]:
            self.location = "construction:" + c["name"]
            self.env[c["name"]] = self.ev(c["expression"])
        for i, c in enumerate(self.dsl["conditions"]):
            self.location = "condition:" + str(i)
            if "predicate" in c:
                p = self.ev(c["predicate"])
                if not isinstance(p, Pred):
                    raise Unsupported("nonpredicate condition")
                f = p.formula
            else:
                f = self.relation(self.ev(c["left"]), c["operator"], self.ev(c["right"]))
            self.conditions.append((self.location, f))
        self.location = "target"
        target = self.ev(self.dsl["target"])
        if not isinstance(target, s.Expr):
            raise Unsupported("nonscalar target")
        self.target = clean(s.trigsimp(s.expand_trig(target)))
        return self

    def f_Point(self, x, y):
        return Point(clean(x), clean(y))

    def f_Vector(self, a, b):
        return sub(b, a)

    def f_Dot(self, a, b):
        if not isinstance(a, Point) or not isinstance(b, Point):
            raise Unsupported("Dot of line normals")
        return dot(a, b)

    def f_Line(self, a, b, c=None):
        if c is not None:
            nn = a * a + b * b
            self.domain(">", nn, "line normal")
            return Line(Point(self.div(-a * c, nn), self.div(-b * c, nn)), Point(-b, a))
        d = sub(b, a)
        self.domain(">", n2(d), "distinct line points")
        return Line(a, d)

    def f_Midpoint(self, a, b):
        return mul(add(a, b), s.Rational(1, 2))

    def f_Distance(self, a, b):
        if isinstance(b, Line):
            a, b = b, a
        if isinstance(a, Line):
            return self.sqrt(self.div(cross(a.d, sub(b, a.p)) ** 2, n2(a.d)))
        return self.sqrt(n2(sub(a, b)))

    def f_Area(self, *pts):
        if len(pts) == 1 and isinstance(pts[0], Circle):
            return s.pi * pts[0].radius ** 2
        if len(pts) == 1 and isinstance(pts[0], list):
            pts = pts[0]
        if len(pts) < 3 or not all(isinstance(p, Point) for p in pts):
            raise Unsupported("area arguments")
        return s.Abs(clean(sum(cross(pts[i], pts[(i + 1) % len(pts)])
                              for i in range(len(pts))))) / 2

    def f_sqrt(self, a):
        return self.sqrt(a)

    def f_abs(self, a):
        return s.Abs(a)

    def f_Circle(self, p, r):
        self.domain(">", r, "circle radius")
        return Circle(p, r)

    def f_Center(self, c):
        return c.center

    def f_Radius(self, c):
        return c.radius

    def f_Circumcenter(self, a, b, c):
        u, v = sub(b, a), sub(c, a)
        det = 2 * cross(u, v)
        self.domain("!=", det, "noncollinear circumcenter")
        return add(a, Point(self.div(v.y * n2(u) - u.y * n2(v), det),
                            self.div(u.x * n2(v) - v.x * n2(u), det)))

    def f_Circumcircle(self, a, b, c):
        o = self.f_Circumcenter(a, b, c)
        return self.f_Circle(o, self.f_Distance(o, a))

    def f_Intersect(self, a, b, n=None, exclude=None, near=None, far=None):
        if n is not None or near is not None or far is not None:
            raise Unsupported("intersection n/near/far selector")
        if isinstance(a, Circle) and isinstance(b, Line):
            a, b = b, a
        if isinstance(a, Line) and isinstance(b, Line):
            if exclude is not None:
                raise Unsupported("line-line exclude")
            t = self.div(cross(sub(b.p, a.p), b.d), cross(a.d, b.d))
            return add(a.p, mul(a.d, t))
        if exclude is None:
            raise Unsupported("circle intersection without supported exclude")
        if isinstance(a, Line) and isinstance(b, Circle):
            inc = [cross(a.d, sub(exclude, a.p)), n2(sub(exclude, b.center)) - b.radius ** 2]
            if not all(s.simplify(v) == 0 for v in inc):
                raise Unsupported("exclude not identically incident")
            t = self.div(-2 * dot(a.d, sub(exclude, b.center)), n2(a.d))
            q = add(exclude, mul(a.d, t))
        elif isinstance(a, Circle) and isinstance(b, Circle):
            inc = [n2(sub(exclude, c.center)) - c.radius ** 2 for c in (a, b)]
            if not all(s.simplify(v) == 0 for v in inc):
                raise Unsupported("exclude not identically on both circles")
            centerline = self.f_Line(a.center, b.center)
            q = self.f_Reflect(exclude, centerline)
        else:
            raise Unsupported("intersection argument types")
        self.domain(">", n2(sub(q, exclude)), "excluded intersection distinct")
        return q

    def f_FootOfPerpendicular(self, p, line):
        if isinstance(p, Line):
            p, line = line, p
        return add(line.p, mul(line.d, self.div(dot(sub(p, line.p), line.d), n2(line.d))))

    def f_Reflect(self, p, line):
        if isinstance(line, Point):
            return sub(mul(line, 2), p)
        return sub(mul(self.f_FootOfPerpendicular(p, line), 2), p)

    def f_ParallelLine(self, a, b):
        line, p = (a, b) if isinstance(a, Line) else (b, a)
        return Line(p, line.d)

    def f_PerpendicularLine(self, a, b):
        line, p = (a, b) if isinstance(a, Line) else (b, a)
        return Line(p, Point(-line.d.y, line.d.x))

    def f_PointOnLine(self, line, t):
        # Native PointOnLine uses a normalized, canonical line parameter.
        raise Unsupported("PointOnLine parameter normalization")

    def f_PointOnSegment(self, a, b, t):
        return add(a, mul(sub(b, a), t))

    def f_Angle(self, a, b, c):
        u, v = sub(a, b), sub(c, b)
        self.domain(">", n2(u), "angle first ray")
        self.domain(">", n2(v), "angle second ray")
        return s.acos(self.div(dot(u, v), self.sqrt(n2(u) * n2(v))))

    def trig(self, a, name):
        if a.free_symbols and not a.has(s.acos):
            raise Unsupported("free trigonometric variable")
        e = s.trigsimp(s.expand_trig(getattr(s, name)(a)))
        if e.has(s.sin, s.cos, s.tan) and e.free_symbols:
            raise Unsupported("unreduced trigonometric expression")
        return e

    def f_cos(self, a):
        return self.trig(a, "cos")

    def f_sin(self, a):
        return self.trig(a, "sin")

    def f_tan(self, a):
        return self.trig(a, "tan")

    def f_And(self, *args):
        if not all(isinstance(a, Pred) for a in args):
            raise Unsupported("And argument")
        return Pred(both(*(a.formula for a in args)))

    def f_Or(self, *args):
        if not all(isinstance(a, Pred) for a in args):
            raise Unsupported("Or argument")
        return Pred(either(*(a.formula for a in args)))

    def f_Not(self, a):
        return Pred(("not", a.formula))

    def f_Bound(self, x, bounds, inclusive=True):
        lo, hi = bounds
        return Pred(both(*([atom(">=" if inclusive else ">", x - lo)] if lo is not None else []),
                         *([atom("<=" if inclusive else "<", x - hi)] if hi is not None else [])))

    def f_OnLine(self, p, a, b=None):
        line = a if isinstance(a, Line) else self.f_Line(a, b)
        return Pred(atom("=", cross(line.d, sub(p, line.p))))

    def f_OnCircle(self, p, circle):
        return Pred(atom("=", n2(sub(p, circle.center)) - circle.radius ** 2))

    def f_OnSegment(self, p, a, b):
        return Pred(both(atom("=", cross(sub(p, a), sub(b, a))),
                         atom("<=", dot(sub(p, a), sub(p, b)))))

    def f_Collinear(self, a, b, c):
        return Pred(atom("=", cross(sub(b, a), sub(c, a))))

    def f_Parallel(self, a, b):
        return Pred(atom("=", cross(a.d, b.d)))

    def f_Perpendicular(self, a, b):
        return Pred(atom("=", dot(a.d, b.d)))

    def f_IsTangent(self, a, b):
        if isinstance(a, Circle) and isinstance(b, Line):
            a, b = b, a
        if isinstance(a, Line) and isinstance(b, Circle):
            return Pred(atom("=", cross(a.d, sub(b.center, a.p)) ** 2 - b.radius ** 2 * n2(a.d)))
        if isinstance(a, Circle) and isinstance(b, Circle):
            d = n2(sub(a.center, b.center))
            return Pred(both(either(atom("!=", d), atom("!=", a.radius - b.radius)),
                             either(atom("=", d - (a.radius + b.radius) ** 2),
                                    atom("=", d - (a.radius - b.radius) ** 2))))
        raise Unsupported("IsTangent types")

    def f_AngleBisector(self, a, b, c):
        u, v = sub(a, b), sub(c, b)
        nu, nv = self.sqrt(n2(u)), self.sqrt(n2(v))
        self.domain(">", nu, "bisector first ray")
        self.domain(">", nv, "bisector second ray")
        d = add(mul(u, nv), mul(v, nu))
        self.domain(">", n2(d), "bisector nonzero")
        return Line(b, d)

    def f_ConvexPolygon(self, pts):
        if len(pts) < 3:
            raise Unsupported("polygon has fewer than 3 vertices")
        signs = []
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            for j, p in enumerate(pts):
                if j not in (i, (i + 1) % len(pts)):
                    signs.append(cross(sub(b, a), sub(p, a)))
        return Pred(either(both(*(atom(">", z) for z in signs)),
                           both(*(atom("<", z) for z in signs))))


@lru_cache(maxsize=8192)
def exact_sign(e):
    """0 and strict signs are decided algebraically; never by evalf tolerance."""
    e = s.cancel(s.simplify(e))
    if e == 0:
        return 0
    if e.has(s.nan, s.zoo, s.oo, -s.oo) or e.free_symbols:
        raise Unsupported("undefined/nonconstant sign expression")
    if e.is_real is False:
        raise Unsupported("nonreal sign expression")
    if e.is_positive is True:
        return 1
    if e.is_negative is True:
        return -1
    a = s.to_number_field(e)
    if all(q == 0 for q in a.coeffs()):
        return 0
    r = a.to_root(radicals=False)
    if r.is_positive is True:
        return 1
    if r.is_negative is True:
        return -1
    raise Unsupported("algebraic sign unresolved")


def eval_formula(f, x, root):
    if f[0] in ("and", "or"):
        undecided = False
        for p in f[1:]:
            try:
                v = eval_formula(p, x, root)
            except Unsupported:
                undecided = True
                continue
            if f[0] == "and" and not v:
                return False
            if f[0] == "or" and v:
                return True
        if undecided:
            raise Unsupported("Boolean formula unresolved")
        return f[0] == "and"
    if f[0] == "not":
        return not eval_formula(f[1], x, root)
    sg = exact_sign(f[1].subs(x, root))
    return {"=": sg == 0, "!=": sg != 0, ">": sg > 0, ">=": sg >= 0,
            "<": sg < 0, "<=": sg <= 0}[f[0]]


def rational_poly(e, x):
    """Return a nonzero QQ polynomial entailed by e=0, or refuse.

    Abs signs are exhaustively branched. unrad's documented superset output
    is accepted only without a change-of-variable covariance condition.
    Norm over a coefficient number field retains every original root.
    """
    ab = sorted(e.atoms(s.Abs), key=s.default_sort_key)
    if len(ab) > 6:
        raise Unsupported("more than 64 absolute-value branches")
    result = s.Poly(1, x, domain=s.QQ)
    traces = []
    for signs in itertools.product((-1, 1), repeat=len(ab)):
        b = e
        # Inner absolute values first, then simplify the completed branch.
        for a, sg in sorted(zip(ab, signs), key=lambda p: s.count_ops(p[0]), reverse=True):
            b = b.xreplace({a: sg * a.args[0]})
        b = s.factor(s.together(b))
        if b == 0:
            raise Unsupported("an absolute-value branch has no finite anchor")
        used_unrad = False
        try:
            p = s.Poly(s.fraction(b)[0], x, extension=True)
        except (s.PolynomialError, s.polys.polyerrors.CoercionFailed):
            ur = unrad(b, x)
            if ur is None:
                ur = unrad(b)
            if ur is None or ur[1]:
                raise Unsupported("radical elimination requires covariance or failed")
            b = ur[0]
            p = s.Poly(s.fraction(s.together(b))[0], x, extension=True)
            used_unrad = True
        if not p.domain.is_QQ and not p.domain.is_ZZ:
            if not p.domain.is_AlgebraicField:
                raise Unsupported("nonalgebraic polynomial coefficients")
            p = p.norm()
        p = s.Poly(p.as_expr(), x, domain=s.QQ)
        if p.is_zero:
            raise Unsupported("zero necessary polynomial")
        result *= p
        result = result.sqf_part()
        if result.degree() > 64:
            raise Unsupported("necessary polynomial degree exceeds 64")
        traces.append({"abs_signs": list(signs), "unrad": used_unrad,
                       "factor": str(p.as_expr())})
    result = result.clear_denoms()[1].primitive()[1]
    if result.LC() < 0:
        result = -result
    if result.degree() <= 0:
        raise Unsupported("constant anchor")
    return result, traces


def choose_anchor(c):
    candidates = []
    failures = []
    for i, (label, formula) in enumerate(c.conditions):
        for j, expr in enumerate(necessary(formula)):
            expr = s.factor(expr)
            if expr == 0 or c.x not in expr.free_symbols:
                continue
            try:
                p, trace = rational_poly(expr, c.x)
            except (Unsupported, NotImplementedError, s.PolynomialError,
                    s.polys.polyerrors.CoercionFailed) as err:
                failures.append({"label": label, "reason": str(err)[:240]})
                continue
            candidates.append((p.degree(), int(s.count_ops(p.as_expr())), i, j,
                               p, label, expr, trace))
    if not candidates:
        raise Unsupported("no finite polynomial anchor: " + json.dumps(failures[:4]))
    chosen = min(candidates, key=lambda a: a[:4])
    _, _, _, _, p, label, expr, trace = chosen
    return p, {"condition": label, "source_expression": str(expr),
               "polynomial": str(p.as_expr()), "coefficients": [str(v) for v in p.all_coeffs()],
               "degree": p.degree(), "branches": trace,
               "candidate_count": len(candidates), "failed_anchors": failures}


def root_wire(r):
    if r.is_Rational:
        return {"rational": str(r)}
    if isinstance(r, s.CRootOf):
        return {"poly_coefficients": [str(v) for v in r.poly.all_coeffs()],
                "index": int(r.index)}
    raise Unsupported("unexpected exact root representation")


def root_from_wire(w):
    if "rational" in w:
        return s.Rational(w["rational"])
    z = s.Symbol("z")
    return s.CRootOf(s.Poly.from_list([s.Rational(a) for a in w["poly_coefficients"]], z), w["index"])


def classify_root(c, root):
    undecided = []
    checks = 0
    for label, formula in c.domains + c.conditions:
        try:
            ok = eval_formula(formula, c.x, root)
        except (Unsupported, NotImplementedError, ValueError, TypeError) as err:
            undecided.append({"label": label, "reason": str(err)[:200]})
            continue
        checks += 1
        if not ok:
            return {"status": "rejected", "reason": label, "checked_atoms_or_formulas": checks}
    if undecided:
        return {"status": "unresolved", "undecided": undecided}
    value = s.cancel(s.simplify(c.target.subs(c.x, root)))
    if value.has(s.nan, s.zoo, s.oo, -s.oo) or value.free_symbols:
        return {"status": "unresolved", "reason": "target undefined/nonconstant"}
    # Require a real algebraic target, but do not approximate it to identify it.
    a = s.to_number_field(value)
    canonical = a.to_root(radicals=False)
    if canonical.is_real is not True:
        return {"status": "unresolved", "reason": "target not real algebraic"}
    return {"status": "accepted", "target": str(value), "target_wire": root_wire(canonical),
            "target_decimal": str(value.evalf(30)), "checked_atoms_or_formulas": checks}


def solve(dsl, progress=lambda stage: None):
    progress("compile")
    c = Compiler(dsl).run()
    progress("necessary_polynomial")
    p, anchor = choose_anchor(c)
    progress("real_root_isolation")
    roots = p.real_roots(radicals=False)
    intervals = p.intervals(eps=s.Rational(1, 10**12))
    if len(roots) != len(intervals) or any(m != 1 for _, m in intervals):
        raise AssertionError("square-free root/interval mismatch")
    records = []
    answer_values = []
    answer_wires = []
    for index, (r, ((lo, hi), _)) in enumerate(zip(roots, intervals)):
        progress("classify_root:" + str(index) + "/" + str(len(roots)))
        rec = {"index": index, "root": root_wire(r), "root_decimal": str(r.evalf(24)),
               "isolating_interval": [str(lo), str(hi)]}
        rec.update(classify_root(c, r))
        records.append(rec)
        if rec["status"] == "accepted":
            value = root_from_wire(rec["target_wire"])
            if not any(exact_sign(value - old) == 0 for old in answer_values):
                answer_values.append(value)
                answer_wires.append(rec["target_wire"])
    complete = all(r["status"] in ("accepted", "rejected") for r in records)
    return {"id": dsl["id"], "input_sha256": digest(dsl),
            "status": "complete" if complete else "unresolved",
            "answer_set": answer_wires, "answer_decimals": [str(v.evalf(30)) for v in answer_values],
            "anchor": anchor, "roots": records, "rewrites": c.rewrites,
            "domain_count": len(c.domains), "condition_count": len(c.conditions),
            "n_real_roots": len(roots),
            "n_accepted": sum(r["status"] == "accepted" for r in records),
            "n_rejected": sum(r["status"] == "rejected" for r in records)}
