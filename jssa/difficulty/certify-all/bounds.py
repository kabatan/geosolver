"""Conservative rational interval propagation from the original DSL only.

No numerical candidate, search box, or reference answer enters these bounds.
Dependencies may widen intervals; this can cause false negatives, not exclusions.
"""
import ast
import math
import sympy as sp

FULL = (-sp.oo, sp.oo)
NONNEG = (sp.S.Zero, sp.oo)


def parse(s):
    return ast.parse(str(s), mode="eval").body


def key(n):
    return ast.dump(n, include_attributes=False)


def rational(n):
    if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
        return sp.Rational(str(n.value))
    if isinstance(n, ast.UnaryOp):
        a = rational(n.operand)
        if a is not None:
            if isinstance(n.op, ast.USub):
                return -a
            if isinstance(n.op, ast.UAdd):
                return a
    if isinstance(n, ast.BinOp):
        a, b = rational(n.left), rational(n.right)
        if a is not None and b is not None:
            if isinstance(n.op, ast.Add): return a + b
            if isinstance(n.op, ast.Sub): return a - b
            if isinstance(n.op, ast.Mult): return a * b
            if isinstance(n.op, ast.Div) and b: return a / b
            if isinstance(n.op, ast.Pow) and b.is_Integer and abs(b) <= 30 and (a or b >= 0): return a ** b
    return None


def clean(lo, hi):
    if lo is sp.nan or hi is sp.nan or lo > hi:
        return FULL
    return lo, hi


def add(a, b): return clean(a[0] + b[0], a[1] + b[1])
def neg(a): return -a[1], -a[0]
def sub(a, b): return add(a, neg(b))


def mul(a, b):
    def safe(x, y): return sp.S.Zero if x == 0 or y == 0 else x * y
    vals = [safe(x, y) for x in a for y in b]
    return min(vals), max(vals)


def inverse(b):
    lo, hi = b
    if lo < 0 < hi or lo == hi == 0: return FULL
    if lo == 0: return 1 / hi, sp.oo
    if hi == 0: return -sp.oo, 1 / lo
    return 1 / hi, 1 / lo


def power(a, n):
    if n < 0: return inverse(power(a, -n))
    if n == 0: return sp.S.One, sp.S.One
    vals = [a[0] ** n, a[1] ** n]
    lo = 0 if n % 2 == 0 and a[0] <= 0 <= a[1] else min(vals)
    return sp.sympify(lo), max(vals)


def sqrt_endpoint(a, upper=False):
    if a == sp.oo: return sp.oo
    if a <= 0: return sp.S.Zero
    # floor(sqrt(a) * 10^12) is computed using integer arithmetic.
    den = 10**12
    n = math.isqrt(int(a.p) * den**2 // int(a.q))
    exact = sp.Rational(n, den) ** 2 == a
    return sp.Rational(n + int(upper and not exact), den)


def sqrt_interval(a):
    if a[1] < 0: return NONNEG
    return sqrt_endpoint(max(0, a[0])), sqrt_endpoint(a[1], True)


class Bounds:
    def __init__(self, dsl):
        self.dsl = dsl
        self.defs = {c["name"]: parse(c["expression"]) for c in dsl["constructions"]}
        self.explicit = {}
        self.rules = []
        # Expand construction aliases for comparison, with a recursion guard.
        for i, c in enumerate(dsl["conditions"]):
            if c.get("operator") not in ("<", "<=", ">", ">=", "="): continue
            left, right = parse(c["left"]), parse(c["right"])
            op = c["operator"]
            v = rational(right)
            if v is None:
                v = rational(left)
                left, right = right, left
                op = {"<": ">", "<=": ">=", ">": "<", ">=": "<=", "=": "="}[op]
            if v is None: continue
            k = key(self.expand(left))
            lo, hi, lop, hip = self.explicit.get(k, (-sp.oo, sp.oo, False, False))
            if op in (">", ">=", "=") and v >= lo:
                lop = (lop or op == ">") if v == lo else op == ">"
                lo = v
            if op in ("<", "<=", "=") and v <= hi:
                hip = (hip or op == "<") if v == hi else op == "<"
                hi = v
            self.explicit[k] = lo, hi, lop, hip
            self.rules.append({"condition_index": i, "normalized_expression": ast.unparse(self.expand(left)), "operator": op, "rational_endpoint": str(v)})

    def expand(self, n, seen=()):
        if isinstance(n, ast.Name) and n.id in self.defs and n.id not in seen:
            return self.expand(self.defs[n.id], seen + (n.id,))
        # Preserve the AST; no algebraic transformations with hidden domain assumptions.
        if isinstance(n, ast.BinOp):
            return ast.BinOp(left=self.expand(n.left, seen), op=n.op, right=self.expand(n.right, seen))
        if isinstance(n, ast.UnaryOp):
            return ast.UnaryOp(op=n.op, operand=self.expand(n.operand, seen))
        if isinstance(n, ast.Call):
            return ast.Call(func=n.func, args=[self.expand(a, seen) for a in n.args], keywords=[ast.keyword(arg=k.arg, value=self.expand(k.value, seen)) for k in n.keywords])
        if isinstance(n, (ast.List, ast.Tuple)):
            return type(n)(elts=[self.expand(a, seen) for a in n.elts], ctx=ast.Load())
        if isinstance(n, ast.Attribute):
            return ast.Attribute(value=self.expand(n.value, seen), attr=n.attr, ctx=ast.Load())
        return n

    def point(self, n):
        n = self.expand(n)
        if not isinstance(n, ast.Call) or not isinstance(n.func, ast.Name): return None
        f, a = n.func.id, n.args
        if f == "Point" and len(a) == 2: return self.scalar(a[0]), self.scalar(a[1])
        if f == "Midpoint" and len(a) == 2:
            p, q = self.point(a[0]), self.point(a[1])
            if p and q: return tuple(mul(add(x, y), (sp.Rational(1, 2),) * 2) for x, y in zip(p, q))
        if f == "PointOnSegment" and len(a) == 3:
            p, q, t = self.point(a[0]), self.point(a[1]), self.scalar(a[2])
            if p and q: return tuple(add(x, mul(sub(y, x), t)) for x, y in zip(p, q))
        return None

    def scalar(self, n):
        n = self.expand(n)
        val = rational(n)
        if val is not None: out = val, val
        elif isinstance(n, ast.UnaryOp):
            a = self.scalar(n.operand)
            out = neg(a) if isinstance(n.op, ast.USub) else a if isinstance(n.op, ast.UAdd) else FULL
        elif isinstance(n, ast.BinOp):
            a, b = self.scalar(n.left), self.scalar(n.right)
            if isinstance(n.op, ast.Add): out = add(a, b)
            elif isinstance(n.op, ast.Sub): out = sub(a, b)
            elif isinstance(n.op, ast.Mult): out = mul(a, b)
            elif isinstance(n.op, ast.Div): out = mul(a, inverse(b))
            elif isinstance(n.op, ast.Pow):
                k = rational(n.right)
                out = power(a, int(k)) if k is not None and k.is_Integer and abs(k) <= 30 else sqrt_interval(a) if k == sp.Rational(1, 2) else FULL
            else: out = FULL
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
            f, a = n.func.id, n.args
            if f == "sqrt" and len(a) == 1: out = sqrt_interval(self.scalar(a[0]))
            elif f == "abs" and len(a) == 1:
                u = self.scalar(a[0]); out = (sp.S.Zero if u[0] <= 0 <= u[1] else min(abs(u[0]), abs(u[1])), max(abs(u[0]), abs(u[1])))
            elif f == "Distance" and len(a) == 2:
                p, q = self.point(a[0]), self.point(a[1])
                out = sqrt_interval(add(power(sub(p[0], q[0]), 2), power(sub(p[1], q[1]), 2))) if p and q else NONNEG
            elif f in ("Distance", "Length", "Area", "Perimeter"): out = NONNEG
            # Radius(Circle(..., r)) may retain signed r in the translator;
            # use only an explicit radius bound, not an unverified sign assumption.
            elif f == "Radius" and len(a) == 1 and isinstance(a[0], ast.Call) and isinstance(a[0].func, ast.Name) and a[0].func.id == "Circle" and len(a[0].args) == 2:
                out = self.scalar(a[0].args[1])
            else: out = FULL
        elif isinstance(n, ast.Attribute):
            p = self.point(n.value)
            out = p["xy".index(n.attr)] if p and n.attr in ("x", "y") else FULL
        else: out = FULL
        if key(n) in self.explicit:
            lo, hi, _, _ = self.explicit[key(n)]
            # Inconsistent bounds are not used to certify by vacuity.
            out = clean(max(lo, out[0]), min(hi, out[1]))
        return out

    def target(self):
        n = self.expand(parse(self.dsl["target"]))
        lo, hi = self.scalar(n)
        elo, ehi, lop, hip = self.explicit.get(key(n), (-sp.oo, sp.oo, False, False))
        return lo, hi, lop and lo == elo, hip and hi == ehi


def target_bounds(dsl):
    b = Bounds(dsl)
    return b.target(), {"method": "conservative_rational_interval_arithmetic", "explicit_rules": b.rules, "bounds": list(map(str, b.target()))}
