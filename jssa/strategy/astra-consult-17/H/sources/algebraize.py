"""Translate a GeoSolver DSL problem into a polynomial system over Q.

The system is a relaxation used by exact baselines: every real configuration of
the DSL problem is a real solution of the equations, but the system ignores
inequalities, branch selectors and orientation. Candidates found by an exact
solver are filtered afterwards by GeoSolver's final verifier on the DSL itself.

Two encodings share this code:
- "fresh": a point whose coordinates need a division gets two new unknowns
  with linear defining equations (the classic coordinate encoding);
- "inline": such points stay as rational functions of earlier unknowns.
"""

from __future__ import annotations

import ast
import itertools
from dataclasses import dataclass, field

import sympy as sp

PI = sp.pi


class Unsupported(Exception):
    pass


# ---------------------------------------------------------------- objects


@dataclass(frozen=True)
class Pt:
    x: sp.Expr
    y: sp.Expr


@dataclass(frozen=True)
class Ln:
    p: Pt
    d: Pt  # direction


@dataclass(frozen=True)
class Circ:
    c: Pt
    r2: sp.Expr
    r: sp.Expr | None = None
    through: tuple = ()  # points on the circle by construction


@dataclass(frozen=True)
class Poly:
    pts: tuple


@dataclass(frozen=True)
class Constraint:
    """Residual-valued predicate; `== 0` adds these equations."""

    eqs: tuple


@dataclass
class AngleLin:
    """value = scale * (sum k_i theta_i + a*pi)."""

    coeffs: dict
    a: sp.Rational = sp.Integer(0)
    scale: sp.Expr = sp.Integer(1)

    def normalized(self, scale):
        ratio = sp.nsimplify(sp.simplify(self.scale / scale))
        if not ratio.is_Rational:
            raise Unsupported("angle scales")
        return {k: v * ratio for k, v in self.coeffs.items()}, self.a * ratio


def sub(p, q):
    return Pt(p.x - q.x, p.y - q.y)


def add(p, q):
    return Pt(p.x + q.x, p.y + q.y)


def scale(p, s):
    return Pt(p.x * s, p.y * s)


def dot(u, v):
    return u.x * v.x + u.y * v.y


def cross(u, v):
    return u.x * v.y - u.y * v.x


def rot90(u):
    return Pt(-u.y, u.x)


def norm2(u):
    return dot(u, u)


# ---------------------------------------------------------------- system


@dataclass
class System:
    mode: str = "fresh"
    variables: list = field(default_factory=list)  # sympy symbols
    dsl_vars: list = field(default_factory=list)
    eqs: list = field(default_factory=list)
    nondeg: list = field(default_factory=list)
    aux_kinds: dict = field(default_factory=dict)
    _sqrt_cache: dict = field(default_factory=dict)
    _angle_cache: dict = field(default_factory=dict)
    _placeholders: dict = field(default_factory=dict)
    defs: list = field(default_factory=list)
    angle_vars: dict = field(default_factory=dict)  # DSL symbol -> (cos, sin) unknowns  # (kind, new unknowns) in creation order
    _n: int = 0

    def new_var(self, kind):
        self._n += 1
        s = sp.Symbol(f"{kind}{self._n}")
        self.variables.append(s)
        self.aux_kinds[s] = kind
        return s

    def placeholder(self, radicand):
        if not radicand.free_symbols and radicand.is_number:
            r = sp.sqrt(radicand)
            if r.is_Rational:
                return r
        self._n += 1
        ph = sp.Symbol(f"_ph{self._n}")
        self._placeholders[ph] = radicand
        return ph

    def materialize(self, expr):
        expr = sp.sympify(expr)
        reps = {}
        for sym in expr.free_symbols:
            if sym in self._placeholders:
                reps[sym] = self.sqrt(self._placeholders[sym])
        return expr.xreplace(reps) if reps else expr

    def add_eq(self, expr):
        expr = sp.together(sp.expand(self.materialize(expr)))
        num, den = sp.fraction(expr)
        num = sp.expand(num)
        if num == 0:
            return
        if num.free_symbols == set():
            raise Unsupported("inconsistent constant equation")
        self._check_rational(num)
        self.add_nondeg(den)
        self.eqs.append(num)

    def add_nondeg(self, den):
        den = sp.expand(self.materialize(den))
        if den.free_symbols:
            self.nondeg.append(den)

    def _check_rational(self, expr):
        for atom in sp.preorder_traversal(expr):
            if atom.is_number and not atom.is_Rational and atom.is_Atom:
                raise Unsupported(f"non-rational coefficient {atom}")
            if isinstance(atom, (sp.Pow,)) and not (atom.exp.is_Integer and atom.exp >= 0):
                raise Unsupported(f"non-polynomial term {atom}")
            if isinstance(atom, sp.Function):
                raise Unsupported(f"function {atom}")

    def rationalize(self, e):
        e = sp.nsimplify(e, rational=False) if isinstance(e, float) else e
        e = sp.sympify(e)
        if e.has(PI):
            raise Unsupported("pi outside angle context")
        return e

    def sqrt(self, e):
        e = sp.cancel(sp.together(e))
        if e.is_number:
            if e.is_negative:
                raise Unsupported("sqrt of negative constant")
            r = sp.sqrt(e)
            if r.is_Rational:
                return r
        key = sp.srepr(e)
        if key in self._sqrt_cache:
            return self._sqrt_cache[key]
        num, den = sp.fraction(e)
        s = self.new_var("s")
        self.defs.append(("sqrt", (s,)))
        self.add_eq(s**2 * den - num)
        self._sqrt_cache[key] = s
        return s

    def fresh_point(self, p):
        """Introduce unknowns for a point with denominators (fresh mode)."""
        if self.mode == "inline":
            return Pt(sp.cancel(sp.together(p.x)), sp.cancel(sp.together(p.y)))
        coords = []
        for c in (p.x, p.y):
            c = sp.cancel(sp.together(c))
            num, den = sp.fraction(c)
            if den.free_symbols:
                v = self.new_var("p")
                self.defs.append(("lin", (v,)))
                self.add_eq(v * den - num)
                coords.append(v)
            else:
                coords.append(c)
        return Pt(*coords)

    def point_on(self, objs):
        """New point constrained to lie on every object (both branches)."""
        X = Pt(self.new_var("p"), self.new_var("p"))
        self.defs.append(("pair", (X.x, X.y)))
        for o in objs:
            for e in incidence(X, o):
                self.add_eq(e)
        return X

    # angle helpers -------------------------------------------------------

    def angle_parts(self, A, B, C):
        key = (sp.srepr(A), sp.srepr(B), sp.srepr(C))
        if key in self._angle_cache:
            return self._angle_cache[key]
        u, v = sub(A, B), sub(C, B)
        d, cr = sp.expand(dot(u, v)), sp.expand(cross(u, v))
        # |cross| and |u||v| become unknowns only if an equation uses them
        w = self.placeholder(sp.expand(cr**2))
        n = self.placeholder(sp.expand(norm2(u) * norm2(v)))
        self._angle_cache[key] = (d, w, n)
        return self._angle_cache[key]


def incidence(X, o):
    if isinstance(o, Ln):
        return [cross(o.d, sub(X, o.p))]
    if isinstance(o, Circ):
        return [norm2(sub(X, o.c)) - o.r2]
    raise Unsupported(f"incidence with {type(o).__name__}")


def on_by_construction(P, c):
    return any(is_zero(P.x - Q.x) and is_zero(P.y - Q.y) for Q in c.through)


def is_zero(e):
    return sp.simplify(sp.together(e)) == 0


# ---------------------------------------------------------------- translator


ANGLE_ARGS = ("Angle",)


class Translator:
    def __init__(self, dsl, mode="fresh"):
        self.dsl = dsl
        self.sys = System(mode=mode)
        self.env = {}
        for name in dsl["variables"]:
            s = sp.Symbol(f"v_{name}")
            self.sys.variables.append(s)
            self.sys.dsl_vars.append(s)
            self.sys.aux_kinds[s] = "dsl"
            self.env[name] = s
        self.env["pi"] = PI

    # entry points ------------------------------------------------------------

    def run(self, with_target=False):
        for c in self.dsl["constructions"]:
            val = self.ev(c["expression"])
            if isinstance(val, Pt) and self.sys.mode == "fresh":
                val = self.sys.fresh_point(val)
            self.env[c["name"]] = val
        for cond in self.dsl["conditions"]:
            if "predicate" in cond:
                self.predicate(cond["predicate"])
                continue
            if cond["operator"] != "=":
                continue  # inequalities are checked by the verifier
            left = self.ev(cond["left"])
            right = self.ev(str(cond["right"]))
            self.equate(left, right)
        used = set().union(*[e.free_symbols for e in self.sys.eqs]) if self.sys.eqs else set()
        if used & set(self.sys.angle_vars):
            raise Unsupported("angle variable also used algebraically")
        target = None
        if with_target:
            t = self.ev(self.dsl["target"])
            if isinstance(t, AngleLin):
                raise Unsupported("angle-valued target")
            tv = self.sys.new_var("t")
            self.sys.add_eq(tv - t)
            target = tv
        return self.sys, target

    def predicate(self, text):
        node = ast.parse(text, mode="eval").body
        alternatives = self.boolean(node)
        if alternatives is None:
            return  # pure inequality/guard predicate
        self.add_disjunction(alternatives)

    def boolean(self, node):
        """Return list of alternatives, each a list of equations; None if no equations."""
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            fn = node.func.id
            if fn == "Or":
                parts = [self.boolean(a) for a in node.args]
                if any(p is None for p in parts):
                    if all(p is None for p in parts):
                        return None
                    raise Unsupported("Or mixing equations and inequalities")
                return [alt for p in parts for alt in p]
            if fn == "And":
                parts = [self.boolean(a) for a in node.args]
                parts = [p for p in parts if p is not None]
                if not parts:
                    return None
                combos = list(itertools.product(*parts))
                if len(combos) > 64:
                    raise Unsupported("And/Or expansion too large")
                return [[e for alt in combo for e in alt] for combo in combos]
            if fn in ("ConvexPolygon", "SimplePolygon", "AcuteTriangle", "AssumeConvex",
                      "Bound", "ObtuseTriangle", "Not", "RightTriangle"):
                if fn == "RightTriangle":
                    raise Unsupported("RightTriangle predicate")
                return None
            if fn == "IsInteger":
                raise Unsupported("IsInteger")
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            if isinstance(node.ops[0], ast.Eq):
                left = self.node(node.left)
                right = self.node(node.comparators[0])
                return [self.equations(left, right)]
            return None
        raise Unsupported(f"predicate {ast.unparse(node)[:60]}")

    def add_disjunction(self, alternatives):
        if len(alternatives) == 1:
            for e in alternatives[0]:
                self.sys.add_eq(e)
            return
        combos = list(itertools.product(*alternatives))
        if len(combos) > 64:
            raise Unsupported("disjunction expansion too large")
        nums = set()
        for combo in combos:
            prod = sp.Integer(1)
            for e in combo:
                num, den = sp.fraction(sp.together(e))
                self.sys.add_nondeg(den)
                prod *= num
            key = sp.srepr(sp.expand(prod))
            if key not in nums:
                nums.add(key)
                self.sys.add_eq(prod)

    def equate(self, left, right):
        for e in self.equations(left, right):
            self.sys.add_eq(e)

    def equations(self, left, right):
        if isinstance(left, Constraint):
            if not (isinstance(right, sp.Expr) and right == 0):
                raise Unsupported("predicate compared to nonzero")
            return list(left.eqs)
        if isinstance(left, Pt) and isinstance(right, Pt):
            return [left.x - right.x, left.y - right.y]
        if isinstance(left, AngleLin) or isinstance(right, AngleLin):
            return [self.angle_equation(left, right)]
        left = self.sys.rationalize(left)
        right = self.sys.rationalize(right)
        return [left - right]

    def angle_equation(self, left, right):
        lin = self.angle_sub(left, right)
        coeffs, a = lin.coeffs, lin.a
        # sum k_i theta_i + a*pi = 0 (mod pi): Im(prod z_i^k_i * e^{i a pi}) = 0
        re, im = self.cos_sin_pi(a)
        for key, k in coeffs.items():
            if not k.is_Integer:
                # scale everything to integer coefficients
                raise Unsupported("fractional angle coefficient")
            d, w, _n = key
            zr, zi = (d, w) if k > 0 else (d, -w)
            for _ in range(abs(int(k))):
                re, im = sp.expand(re * zr - im * zi), sp.expand(re * zi + im * zr)
        return im

    def cos_sin_pi(self, a):
        """(cos(a*pi), sin(a*pi)) as polynomial expressions over Q and new unknowns."""
        try:
            return (self.algebraic_constant(sp.cos(a * PI)),
                    self.algebraic_constant(sp.sin(a * PI)))
        except Unsupported:
            pass
        key = ("cs", a)
        if key not in self.sys._sqrt_cache:
            x = sp.Symbol("_x")
            mp = sp.minimal_polynomial(sp.cos(a * PI), x)
            c, s_ = self.sys.new_var("c"), self.sys.new_var("c")
            self.sys.defs.append(("root", (c,)))
            self.sys.defs.append(("root", (s_,)))
            self.sys.add_eq(mp.subs(x, c))
            self.sys.add_eq(c**2 + s_**2 - 1)
            self.sys._sqrt_cache[key] = (c, s_)
        return self.sys._sqrt_cache[key]

    def algebraic_constant(self, c):
        c = sp.nsimplify(sp.simplify(c))
        if c.is_Rational:
            return c
        # replace sqrt(q) atoms by unknowns s with s^2 = q
        reps = {}
        for atom in c.atoms(sp.Pow):
            if atom.exp == sp.Rational(1, 2) and atom.base.is_Rational:
                reps[atom] = self.sys.sqrt(atom.base)
        out = sp.expand(c.xreplace(reps))
        if not all(s.is_Symbol or s.is_Rational for s in out.atoms()) or out.has(sp.Pow) and any(
            not p.exp.is_Integer for p in out.atoms(sp.Pow)
        ):
            raise Unsupported(f"angle constant {c}")
        return out

    # angle arithmetic ----------------------------------------------------------

    def to_angle(self, v, scale):
        if isinstance(v, AngleLin):
            coeffs, a = v.normalized(scale)
            return AngleLin(coeffs, a, scale)
        v = sp.sympify(v)
        coeffs = {}
        dsl = [x for x in v.free_symbols if x in self.sys.dsl_vars]
        if dsl:
            # a DSL variable measured in radians becomes (cos, sin) unknowns
            p = sp.Poly(v, *dsl)
            if p.total_degree() != 1:
                raise Unsupported(f"angle constant {v}")
            for x in dsl:
                k = sp.nsimplify(p.coeff_monomial(x) / scale)
                if not k.is_Rational:
                    raise Unsupported(f"angle constant {v}")
                coeffs[self.angle_variable(x)] = k
            v = p.coeff_monomial(1)
        a = sp.nsimplify(sp.simplify(v / (scale * PI)))
        if not a.is_Rational:
            raise Unsupported(f"angle constant {v}")
        return AngleLin(coeffs, a, scale)

    def angle_variable(self, x):
        av = self.sys.angle_vars
        if x not in av:
            c, s_ = self.sys.new_var("a"), self.sys.new_var("a")
            self.sys.defs.append(("anglevar", (c, s_)))
            self.sys.add_eq(c**2 + s_**2 - 1)
            av[x] = (c, s_)
        c, s_ = av[x]
        return (c, s_, sp.Integer(1))

    def angle_sub(self, left, right, sign=-1):
        base = left if isinstance(left, AngleLin) else right
        L = self.to_angle(left, base.scale)
        R = self.to_angle(right, base.scale)
        coeffs = dict(L.coeffs)
        for k, v in R.coeffs.items():
            coeffs[k] = coeffs.get(k, 0) + sign * v
        coeffs = {k: v for k, v in coeffs.items() if v != 0}
        return AngleLin(coeffs, L.a + sign * R.a, base.scale)

    # expression evaluation -----------------------------------------------------

    def ev(self, text):
        return self.node(ast.parse(text.strip(), mode="eval").body)

    def node(self, n):
        if isinstance(n, ast.Constant):
            if isinstance(n.value, bool):
                raise Unsupported("boolean literal")
            if isinstance(n.value, (int,)):
                return sp.Integer(n.value)
            if isinstance(n.value, float):
                return sp.Rational(repr(n.value))
            if isinstance(n.value, str):
                return n.value
        if isinstance(n, ast.Name):
            if n.id not in self.env:
                raise Unsupported(f"unknown name {n.id}")
            return self.env[n.id]
        if isinstance(n, ast.Attribute):
            obj = self.node(n.value)
            if isinstance(obj, Pt) and n.attr in ("x", "y"):
                return getattr(obj, n.attr)
            if isinstance(obj, Circ) and n.attr == "center":
                return obj.c
            if isinstance(obj, Circ) and n.attr == "radius":
                return self.f_Radius(obj)
            if isinstance(obj, Ln) and n.attr in ("a", "b", "c"):
                return self.line_coeffs(obj)["abc".index(n.attr)]
            raise Unsupported(f"attribute {n.attr}")
        if isinstance(n, (ast.List, ast.Tuple)):
            return [self.node(e) for e in n.elts]
        if isinstance(n, ast.UnaryOp):
            v = self.node(n.operand)
            if isinstance(n.op, ast.USub):
                return self.mul(sp.Integer(-1), v)
            if isinstance(n.op, ast.UAdd):
                return v
        if isinstance(n, ast.BinOp):
            a, b = self.node(n.left), self.node(n.right)
            if isinstance(n.op, ast.Add):
                return self.addv(a, b)
            if isinstance(n.op, ast.Sub):
                return self.addv(a, self.mul(sp.Integer(-1), b))
            if isinstance(n.op, ast.Mult):
                return self.mul(a, b)
            if isinstance(n.op, ast.Div):
                return self.div(a, b)
            if isinstance(n.op, ast.Pow):
                if isinstance(a, sp.Expr) and isinstance(b, sp.Expr):
                    if b.is_Integer:
                        return a**b
                    if b == sp.Rational(1, 2):
                        return self.sys.sqrt(a)
                raise Unsupported("power")
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
            args = [self.node(a) for a in n.args]
            kw = {k.arg: self.node(k.value) for k in n.keywords}
            fn = getattr(self, "f_" + n.func.id, None)
            if fn is None:
                raise Unsupported(f"function {n.func.id}")
            return fn(*args, **kw)
        raise Unsupported(f"syntax {type(n).__name__}")

    def addv(self, a, b):
        if isinstance(a, AngleLin) or isinstance(b, AngleLin):
            return self.angle_sub(a, b, sign=+1)
        if isinstance(a, Pt) and isinstance(b, Pt):
            return add(a, b)
        if isinstance(a, Constraint) or isinstance(b, Constraint):
            raise Unsupported("arithmetic on predicate")
        return a + b

    def mul(self, a, b):
        if isinstance(a, AngleLin) and isinstance(b, AngleLin):
            raise Unsupported("angle product")
        if isinstance(b, AngleLin):
            a, b = b, a
        if isinstance(a, AngleLin):
            b = sp.sympify(b)
            if b.free_symbols:
                raise Unsupported("angle times variable")
            ratio = sp.nsimplify(b)
            if ratio.is_Rational:
                return AngleLin({k: v * ratio for k, v in a.coeffs.items()}, a.a * ratio, a.scale)
            return AngleLin(dict(a.coeffs), a.a, a.scale * b)
        if isinstance(a, Pt):
            return scale(a, b)
        if isinstance(b, Pt):
            return scale(b, a)
        return a * b

    def div(self, a, b):
        if isinstance(b, AngleLin):
            if isinstance(a, AngleLin):
                raise Unsupported("angle ratio")
            raise Unsupported("divide by angle")
        if isinstance(a, AngleLin):
            return self.mul(a, 1 / sp.sympify(b))
        if isinstance(a, Pt):
            return scale(a, 1 / b)
        self.sys.add_nondeg(sp.fraction(sp.together(b))[0])
        return a / b

    # geometry -------------------------------------------------------------------

    def f_Point(self, x, y):
        return Pt(sp.sympify(x), sp.sympify(y))

    def f_Line(self, A, B=None, C=None):
        if isinstance(A, Ln) and B is None:
            return A
        if C is not None:  # a*x + b*y + c = 0
            a, b, c = (self.sys.rationalize(v) for v in (A, B, C))
            n2 = a**2 + b**2
            return Ln(Pt(-a * c / n2, -b * c / n2), Pt(-b, a))
        return Ln(A, sub(B, A))

    def line_coeffs(self, L):
        """GeoSolver's normalized (a, b, c) with a^2 + b^2 = 1."""
        a, b = -L.d.y, L.d.x
        c = -(a * L.p.x + b * L.p.y)
        n = self.sys.sqrt(sp.expand(a**2 + b**2))
        return a / n, b / n, c / n

    f_Segment = f_Line
    f_Ray = f_Line

    def f_Vector(self, A, B):
        return sub(B, A)

    def f_Dot(self, u, v):
        return dot(u, v)

    def f_Midpoint(self, A, B):
        return scale(add(A, B), sp.Rational(1, 2))

    def f_Centroid(self, A, B, C):
        return scale(add(add(A, B), C), sp.Rational(1, 3))

    def f_Polygon(self, pts):
        return Poly(tuple(pts))

    def f_Triangle(self, pts, *rest):
        if rest:
            pts = [pts, *rest]
        return Poly(tuple(pts))

    def dist(self, A, B):
        if isinstance(B, Ln):
            A, B = B, A
        if isinstance(A, Ln):
            c = cross(A.d, sub(B, A.p))
            return self.sys.sqrt(sp.together(c**2 / norm2(A.d)))
        return self.sys.sqrt(sp.expand(norm2(sub(A, B))))

    def f_Distance(self, A, B=None):
        if B is None and isinstance(A, Ln):
            return self.sys.sqrt(norm2(A.d))
        return self.dist(A, B)

    def f_Length(self, seg):
        return self.sys.sqrt(norm2(seg.d))

    def f_Perimeter(self, *pts):
        if len(pts) == 1 and isinstance(pts[0], (list, Poly)):
            pts = pts[0].pts if isinstance(pts[0], Poly) else pts[0]
        return sum(self.dist(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts)))

    def f_sqrt(self, e, evaluate=True):
        return self.sys.sqrt(self.sys.rationalize(e))

    def f_abs(self, e):
        if isinstance(e, AngleLin):
            raise Unsupported("abs of angle")
        return self.sys.sqrt(sp.expand(e**2))

    def f_Area(self, *pts):
        if len(pts) == 1 and isinstance(pts[0], Circ):
            raise Unsupported("circle area (pi)")
        if len(pts) == 1 and isinstance(pts[0], (list, Poly)):
            pts = pts[0].pts if isinstance(pts[0], Poly) else pts[0]
        s = sum(cross(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts)))
        return self.sys.sqrt(sp.expand(s**2) / 4)

    def f_Intersect(self, o1, o2, n=None, exclude=None, near=None, far=None):
        if isinstance(o1, Circ) and isinstance(o2, Ln):
            o1, o2 = o2, o1
        if isinstance(o1, Ln) and isinstance(o2, Ln):
            det = cross(o1.d, o2.d)
            self.sys.add_nondeg(det)
            t = cross(sub(o2.p, o1.p), o2.d) / det
            return add(o1.p, scale(o1.d, t))
        if isinstance(o1, Ln) and isinstance(o2, Circ):
            if isinstance(exclude, Pt) and self._on_both(exclude, o1, o2):
                A = exclude
                d = o1.d
                t = -2 * dot(d, sub(A, o2.c)) / norm2(d)
                return add(A, scale(d, t))
            return self.sys.point_on([o1, o2])
        if isinstance(o1, Circ) and isinstance(o2, Circ):
            if isinstance(exclude, Pt) and self._on_both(exclude, o1, o2):
                return self.reflect(exclude, Ln(o1.c, sub(o2.c, o1.c)))
            return self.sys.point_on([o1, o2])
        raise Unsupported("Intersect types")

    def _on_both(self, A, o1, o2):
        return all(
            (isinstance(o, Circ) and on_by_construction(A, o))
            or all(is_zero(e) for e in incidence(A, o))
            for o in (o1, o2)
        )

    f_IntersectLines = f_Intersect

    def foot(self, P, L):
        t = dot(sub(P, L.p), L.d) / norm2(L.d)
        return add(L.p, scale(L.d, t))

    def f_FootOfPerpendicular(self, P, L):
        if isinstance(P, Ln):
            P, L = L, P
        return self.foot(P, L)

    f_ClosestPoint = f_FootOfPerpendicular

    def reflect(self, P, L):
        F = self.foot(P, L)
        return sub(scale(F, 2), P)

    def f_Reflect(self, P, L):
        if isinstance(L, Pt):
            return sub(scale(L, 2), P)
        return self.reflect(P, L)

    def f_PerpendicularLine(self, a, b):
        L, P = (a, b) if isinstance(a, Ln) else (b, a)
        return Ln(P, rot90(L.d))

    def f_ParallelLine(self, a, b):
        L, P = (a, b) if isinstance(a, Ln) else (b, a)
        return Ln(P, L.d)

    def f_PerpendicularBisector(self, A, B):
        return Ln(self.f_Midpoint(A, B), rot90(sub(B, A)))

    def f_AngleBisector(self, A, B, C):
        u, v = sub(A, B), sub(C, B)
        nu, nv = self.sys.sqrt(norm2(u)), self.sys.sqrt(norm2(v))
        return Ln(B, add(scale(u, nv), scale(v, nu)))

    def circumcenter(self, A, B, C):
        b, c = sub(B, A), sub(C, A)
        D = 2 * cross(b, c)
        self.sys.add_nondeg(D)
        ux = (c.y * norm2(b) - b.y * norm2(c)) / D
        uy = (b.x * norm2(c) - c.x * norm2(b)) / D
        return add(A, Pt(ux, uy))

    def f_Circumcenter(self, A, B, C):
        return self.circumcenter(A, B, C)

    def f_Circumcircle(self, A, B, C):
        O = self.circumcenter(A, B, C)
        if self.sys.mode == "fresh":
            O = self.sys.fresh_point(O)
        return Circ(O, norm2(sub(A, O)), None, (A, B, C))

    f_CircleThroughThreePoints = f_Circumcircle

    def f_Orthocenter(self, A, B, C):
        O = self.circumcenter(A, B, C)
        return sub(add(add(A, B), C), scale(O, 2))

    def sides(self, A, B, C):
        return (self.dist(B, C), self.dist(C, A), self.dist(A, B))

    def f_Incenter(self, A, B, C):
        a, b, c = self.sides(A, B, C)
        s = a + b + c
        self.sys.add_nondeg(s)
        return scale(add(add(scale(A, a), scale(B, b)), scale(C, c)), 1 / s)

    def f_Incircle(self, A, B, C):
        I = self.f_Incenter(A, B, C)
        if self.sys.mode == "fresh":
            I = self.sys.fresh_point(I)
        a, b, c = self.sides(A, B, C)
        r2 = sp.together(cross(sub(B, A), sub(C, A)) ** 2 / (a + b + c) ** 2)
        return Circ(I, r2)

    def excenter(self, A, B, C, vertex):
        a, b, c = self.sides(A, B, C)
        w = {"A": (-a, b, c), "B": (a, -b, c), "C": (a, b, -c)}[vertex]
        s = sum(w)
        self.sys.add_nondeg(s)
        return scale(add(add(scale(A, w[0]), scale(B, w[1])), scale(C, w[2])), 1 / s)

    def f_Excenter(self, A, B, C, vertex="A"):
        return self.excenter(A, B, C, vertex)

    def f_Excircle(self, A, B, C, vertex="A"):
        J = self.excenter(A, B, C, vertex)
        if self.sys.mode == "fresh":
            J = self.sys.fresh_point(J)
        side = {"A": (B, C), "B": (C, A), "C": (A, B)}[vertex]
        L = Ln(side[0], sub(side[1], side[0]))
        r2 = sp.together(cross(L.d, sub(J, L.p)) ** 2 / norm2(L.d))
        return Circ(J, r2)

    def f_IncircleContactPoint(self, A, B, C, side="BC"):
        I = self.f_Incenter(A, B, C)
        if self.sys.mode == "fresh":
            I = self.sys.fresh_point(I)
        names = {"A": A, "B": B, "C": C}
        P, Q = names[side[0]], names[side[1]]
        return self.foot(I, Ln(P, sub(Q, P)))

    def f_Circle(self, O, r):
        if isinstance(r, Pt):
            return Circ(O, norm2(sub(r, O)), None, (r,))
        r = self.sys.rationalize(r)
        return Circ(O, sp.expand(r**2), r)

    def f_CircleThroughPoint(self, O, P):
        return Circ(O, norm2(sub(P, O)), None, (P,))

    def f_Center(self, c):
        return c.c

    def f_Radius(self, c):
        return c.r if c.r is not None else self.sys.sqrt(c.r2)

    def f_ContactPoint(self, c, L):
        if isinstance(c, Ln):
            c, L = L, c
        return self.foot(c.c, L)

    def f_Tangent(self, P, c, use_first=True):
        if on_by_construction(P, c) or is_zero(norm2(sub(P, c.c)) - c.r2):
            return Ln(P, rot90(sub(P, c.c)))
        T = Pt(self.sys.new_var("p"), self.sys.new_var("p"))
        self.sys.defs.append(("pair", (T.x, T.y)))
        self.sys.add_eq(norm2(sub(T, c.c)) - c.r2)
        self.sys.add_eq(dot(sub(T, c.c), sub(T, P)))
        return Ln(P, sub(T, P))

    f_TangentLine = f_Tangent

    def f_Polar(self, P, c):
        u = sub(P, c.c)
        base = add(c.c, scale(u, c.r2 / norm2(u)))
        return Ln(base, rot90(u))

    def f_PointOnLine(self, L, t):
        a, b, c = self.line_coeffs(L)
        return Pt(-a * c - b * t, -b * c + a * t)

    def f_PointOnSegment(self, A, B, t):
        return add(A, scale(sub(B, A), t))

    def f_Rotate(self, P, angle, center=None):
        O = center if center is not None else Pt(sp.Integer(0), sp.Integer(0))
        if isinstance(angle, AngleLin) and not angle.coeffs:
            theta = angle.scale * angle.a * PI
        else:
            theta = sp.sympify(angle)
        cs = self.algebraic_constant(sp.cos(theta))
        sn = self.algebraic_constant(sp.sin(theta))
        u = sub(P, O)
        return add(O, Pt(u.x * cs - u.y * sn, u.x * sn + u.y * cs))

    # measurements and predicates -----------------------------------------------

    def f_Angle(self, A, B, C):
        key = self.sys.angle_parts(A, B, C)
        return AngleLin({key: sp.Integer(1)})

    def f_Degrees(self, a):
        return self.mul(a, 180 / PI)

    def trig(self, a, which):
        if not isinstance(a, AngleLin):
            a = self.to_angle(a, sp.Integer(1))
        coeffs, c = a.normalized(sp.Integer(1))
        re, im = self.cos_sin_pi(c)
        denom = sp.Integer(1)
        for (d, w, n), k in coeffs.items():
            if not k.is_Integer:
                raise Unsupported("fractional angle coefficient")
            zr, zi = (d, w) if k > 0 else (d, -w)
            for _ in range(abs(int(k))):
                re, im = sp.expand(re * zr - im * zi), sp.expand(re * zi + im * zr)
                denom *= n
        if which == "cos":
            return re / denom
        if which == "sin":
            return im / denom
        return im / re

    def f_cos(self, a):
        return self.trig(a, "cos")

    def f_sin(self, a):
        return self.trig(a, "sin")

    def f_tan(self, a):
        return self.trig(a, "tan")

    def f_OnLine(self, P, A, B=None):
        L = A if isinstance(A, Ln) else Ln(A, sub(B, A))
        return Constraint((cross(L.d, sub(P, L.p)),))

    def f_OnSegment(self, P, A, B):
        return Constraint((cross(sub(B, A), sub(P, A)),))

    def f_OnCircle(self, P, c):
        return Constraint((norm2(sub(P, c.c)) - c.r2,))

    def f_Collinear(self, A, B, C):
        return Constraint((cross(sub(B, A), sub(C, A)),))

    def f_Perpendicular(self, l1, l2):
        return Constraint((dot(l1.d, l2.d),))

    def f_Parallel(self, l1, l2):
        return Constraint((cross(l1.d, l2.d),))

    def f_IsTangent(self, a, b):
        if isinstance(b, Ln):
            a, b = b, a
        if isinstance(a, Ln):
            c = cross(a.d, sub(b.c, a.p))
            return Constraint((c**2 - b.r2 * norm2(a.d),))
        D = norm2(sub(a.c, b.c))
        return Constraint(((D - a.r2 - b.r2) ** 2 - 4 * a.r2 * b.r2,))

    def f_AreConcyclic(self, A, B, C, D):
        rows = [[P.x, P.y, P.x**2 + P.y**2, 1] for P in (A, B, C, D)]
        return Constraint((sp.Matrix(rows).det(),))

    def f_Bound(self, *a, **k):
        raise Unsupported("Bound outside predicate")

    def f_IsInteger(self, *a):
        raise Unsupported("IsInteger")


def translate(dsl, mode="fresh", with_target=False):
    sys_, target = Translator(dsl, mode=mode).run(with_target=with_target)
    return sys_, target

