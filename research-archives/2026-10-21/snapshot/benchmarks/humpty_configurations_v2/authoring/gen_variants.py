#!/usr/bin/env python3
"""Numeric-variant generator for the v2 training configurations.

For every training config this samples new seed parameters, rebuilds the
configuration with the SAME construction code as the authoring verifiers
(verify_{h,da,db}_revision.py), applies the same validity checks, and emits
problems whose givens/answers are exact values recomputed from the built
geometry. The original problem is kept as variant ``v0``.

Outputs ``training_variants.jsonl`` (split=train) and ``eval_variants.jsonl``
(split=dev). Run ``--only ID`` to debug a single config.
"""

import argparse
import hashlib
import json
import math
import random
import re
import runpy
import sys
from fractions import Fraction
from functools import lru_cache
from pathlib import Path

import sympy as s

HERE = Path(__file__).resolve().parent
DATA = HERE.parent
sys.path.insert(0, str(DATA.parents[1]))
from qwen.answer_check import parse_numeric  # noqa: E402

G = runpy.run_path(str(HERE / "geo_primitives.py"))

# ------------------------------------------------------------------ primitives
# complex-float helpers (DA family, mirrors verify_da_revision.py)
fline = G["line"]
fcircle = G["circle"]
ftangent_circle = G["tangent_circle"]
flc = G["lc"]
fcc = G["cc"]
fother = G["other"]
ffoot = G["foot"]
funit = G["unit"]
fdot = G["dot"]
fcross = G["cross"]
fpair = G["tangent_pair"]
finside = G["inside_triangle"]
fchoose_minor = G["choose_minor"]


def fangle(a, v, b):
    return math.degrees(math.acos(max(-1.0, min(1.0, fdot(funit(a - v), funit(b - v))))))


def facute(a, b, c):
    assert min(fdot(b - a, c - a), fdot(a - b, c - b), fdot(a - c, b - c)) > 1e-9


# sympy-exact helpers (H/DB families, mirrors the verify scripts)
def pt(x, y):
    return s.Matrix([s.sympify(x), s.sympify(y)])


def simp(p):
    return p.applyfunc(s.simplify) if isinstance(p, s.MatrixBase) else s.simplify(p)


def norm(p):
    return s.factor(p.dot(p))


def scross(p, q):
    return s.factor(p[0] * q[1] - p[1] * q[0])


def rot(p):
    return pt(-p[1], p[0])


def sline(a, b, c, d):
    return simp(a + (b - a) * scross(c - a, d - c) / scross(b - a, d - c))


def sfoot(p, a, b):
    return simp(a + (b - a) * (p - a).dot(b - a) / norm(b - a))


def sreflect(p, a, b):
    return simp(2 * sfoot(p, a, b) - p)


def scircle(a, b, c):
    mat = s.Matrix([[a[0], a[1], 1], [b[0], b[1], 1], [c[0], c[1], 1]])
    return simp(mat.inv() * s.Matrix([-norm(a), -norm(b), -norm(c)]))


def scenter(w):
    return simp(-w[:2, :] / 2)


def son(p, w):
    return s.simplify(norm(p) + w[0] * p[0] + w[1] * p[1] + w[2])


def ssecond(a, b, w, known):
    assert son(known, w) == 0
    v = b - a
    return simp(known - v * (2 * known.dot(v) + w[0] * v[0] + w[1] * v[1]) / norm(v))


def sother_circle(w, z, known):
    v = rot((w - z)[:2, :])
    return ssecond(known, known + v, w, known)


def sray_circle(a, b, w):
    t = s.symbols("t", real=True)
    roots = s.solve(son(a + t * (b - a), w), t)
    positive = [r for r in roots if float(r.evalf()) > 0]
    assert len(positive) == 1
    return simp(a + positive[0] * (b - a))


def sorthocenter(a, b, c):
    return sline(a, a + rot(c - b), b, b + rot(c - a))


def sbisector(a, b, c):
    return a, simp(a + (b - a) / s.sqrt(norm(b - a)) + (c - a) / s.sqrt(norm(c - a)))


def slength(a, b):
    return s.simplify(s.sqrt(norm(a - b)))


def sarea(a, b, c):
    return s.simplify(s.Abs(scross(b - a, c - a)) / 2)


def eq(a, b=0):
    diff = simp(a - b)
    assert all(v == 0 for v in diff) if isinstance(diff, s.MatrixBase) else diff == 0


def sacute(a, b, c):
    assert len({s.simplify(norm(a - b)), s.simplify(norm(b - c)), s.simplify(norm(c - a))}) == 3
    assert all(
        float(((q - p).dot(r - p)).evalf()) > 0 for p, q, r in [(a, b, c), (b, a, c), (c, a, b)]
    )


def pos(x):
    assert float(s.N(x)) > 0


def sd2(x, y):
    return s.factor((x - y).dot(x - y))


def db_center(a, b, c):
    mat = s.Matrix.vstack((2 * (b - a)).T, (2 * (c - a)).T)
    return simp(mat.inv() * s.Matrix([b.dot(b) - a.dot(a), c.dot(c) - a.dot(a)]))


def db_other(o, a, v):
    return simp(a - 2 * (a - o).dot(v) / v.dot(v) * v)


def db_common(o1, o2, a):
    v = o2 - o1
    return db_other(o1, a, pt(-v[1], v[0]))


def positive_sqrt(x):
    return simp(s.sqrtdenest(s.sqrt(s.factor(x))))


def rotate(u, co, si):
    return simp(pt(co * u[0] - si * u[1], si * u[0] + co * u[1]))


def trig(u, v):
    n = s.sqrt(u.dot(u) * v.dot(v))
    return u.dot(v) / n, abs(scross(u, v)) / n


def angle_eq(a, v, b, c, w, d):
    u1, u2, v1, v2 = a - v, b - v, c - w, d - w
    p, q = u1.dot(u2), v1.dot(v2)
    eq(p * p * v1.dot(v1) * v2.dot(v2), q * q * u1.dot(u1) * u2.dot(u2))
    assert float(s.N(p)) * float(s.N(q)) >= 0


# ------------------------------------------------------------- exact rendering


def exactify(v, tol=1e-9):
    """Return an exact sympy value for a float, else None."""
    fr = Fraction(v).limit_denominator(10**6)
    if abs(float(fr) - v) < tol * max(1.0, abs(v)):
        return s.Rational(fr.numerator, fr.denominator)
    sq = Fraction(v * v).limit_denominator(10**8)
    if abs(math.sqrt(float(sq)) - abs(v)) < tol * max(1.0, abs(v)):
        return positive_sqrt(s.Rational(sq.numerator, sq.denominator))
    return None


def fmt_given(v):
    """Problem-text formatting: ints and rationals plain, radicals as a√b."""
    v = s.simplify(s.sympify(v))
    if v.is_integer:
        return str(int(v))
    if v.is_rational:
        return f"{v.p}/{v.q}"
    sq = s.simplify(v * v)
    if sq.is_rational:
        for den in range(1, 200):
            num = s.nsimplify(sq * den * den)
            if num.is_integer:
                rat = s.Rational(num)
                fac = s.factorint(int(rat))
                out, inner = 1, 1
                for prime, e in fac.items():
                    out *= prime ** (e // 2)
                    inner *= prime ** (e % 2)
                coeff = s.Rational(out, den)
                if coeff == 1:
                    return f"√{inner}" if inner != 1 else str(out)
                return f"{coeff}√{inner}" if coeff.q == 1 else f"({coeff})√{inner}"
    return None


def answer_str(v):
    """sympy-parseable answer_exact string."""
    return s.sstr(s.simplify(s.sympify(v)))


def render(template, values):
    """Substitute {name} placeholders; verifies every value is filled."""
    text = template
    for name, val in values.items():
        token = "{" + name + "}"
        assert token in text, (name, template)
        assert val is not None, (name, template)
        text = text.replace(token, str(val))
    assert "{" not in text, text
    return text


@lru_cache(maxsize=1)
def templates():
    return json.loads((HERE / "variant_templates.json").read_text())


def render_config(cid, values):
    """Substitute numerical slots in exactly the approved construction text."""
    spec = templates()[cid]
    givens = {k: s.sympify(v) for k, v in spec["base_givens"].items()}
    if set(values) - set(givens):
        raise ValueError(f"{cid}: unapproved given names {set(values) - set(givens)}")
    for key, value in values.items():
        if value is None:
            raise ValueError(f"{cid}: unrenderable given {key}")
        givens[key] = parse_numeric(value) if isinstance(value, str) else s.sympify(value)
    for key, parent in spec["linked_givens"].items():
        if key in values and s.simplify(givens[key] - givens[parent]) != 0:
            raise ValueError(f"{cid}: inconsistent linked givens")
        givens[key] = givens[parent]
    slots = set(spec["base_literals"])
    for key in set(givens) - slots - set(spec["linked_givens"]):
        if s.simplify(givens[key] - s.sympify(spec["base_givens"][key])) != 0:
            raise ValueError(f"{cid}: attempted to change a fixed condition {key}")
    rendered = {key: fmt_given(givens[key]) for key in slots}
    if any(value is None for value in rendered.values()):
        raise ValueError(f"{cid}: unrenderable givens")
    return spec["template"].format(**rendered)


def read_givens(cid, problem):
    """Full-match the template: missing conditions and extra hints fail closed."""
    spec = templates()[cid]
    pattern = re.escape(spec["template"])
    groups = {f"g{i}": key for i, key in enumerate(spec["base_literals"])}
    for group, key in groups.items():
        pattern = pattern.replace(re.escape("{" + key + "}"), f"(?P<{group}>.+?)")
    match = re.fullmatch(pattern, problem)
    if match is None:
        raise ValueError(f"{cid}: construction text differs from the approved template")
    values = {k: s.sympify(v) for k, v in spec["base_givens"].items()}
    values.update({groups[k]: parse_numeric(v) for k, v in match.groupdict().items()})
    for key, parent in spec["linked_givens"].items():
        values[key] = values[parent]
    return values


def signature(cid, problem):
    return cid, tuple(sorted((k, str(s.simplify(v))) for k, v in read_givens(cid, problem).items()))


def independent_shape_answer(cid, g):
    """Approved short relations, checked against raw construction targets."""
    if cid == "H01":
        return g["AM"] - g["BC"] ** 2 / (4 * g["AM"])
    if cid == "H02":
        return g["AM"] * abs(g["BD2"] - g["BD1"]) / g["AK"]
    if cid == "H03":
        return 2 * g["OH"] / 3
    if cid == "H04":
        return s.sqrt(g["BT"] * (g["BT"] + g["BC"]))
    if cid == "H07":
        return g["AB"] * g["MF"] * (1 - g["AB"] ** 2 / (4 * g["ON"] ** 2))
    if cid == "H08":
        t = g["tan_BAQ"]
        return g["AP"] * g["AC"] * t / (2 * s.sqrt(1 + t**2))
    if cid == "H12":
        return s.sqrt(g["QM"] ** 2 - g["PM"] ** 2 + g["PV"] ** 2) - g["PV"]
    if cid == "H13":
        return g["BK"] / (2 * s.sqrt(1 - g["cos_ACB"] ** 2))
    if cid == "H14":
        return g["AR"] * s.sqrt(g["AH"] ** 2 - g["AR"] ** 2) / 2
    if cid == "H15":
        return s.sqrt((g["AB"] ** 2 + g["BD"] ** 2) / 2 - g["AD"] ** 2 / 4)
    if cid == "HX01":
        return g["AC"] ** 2 / g["AL"]
    raise ValueError(f"No independent shape check for {cid}")


def checked_record(cid, record, variant, split):
    givens = read_givens(cid, record["problem"])
    answer = parse_numeric(record["answer_exact"])
    params = record.get("params", {})
    if params and set(params) != {"scale"}:
        eq(answer, independent_shape_answer(cid, givens))
    return {
        **record,
        "id": cid,
        "variant": variant,
        "split": split,
        "givens": {k: str(v) for k, v in givens.items()},
        "augmentation": "original"
        if variant == "v0"
        else ("similarity" if set(params) == {"scale"} else "shape"),
        "template_sha256": hashlib.sha256(templates()[cid]["template"].encode()).hexdigest(),
    }


def tri_from_sides(a, b, c):
    """B=0, C=a, A from side lengths (BC=a, CA=b, AB=c)."""
    x = (c * c + a * a - b * b) / (2 * a)
    return complex(x, math.sqrt(max(0.0, c * c - x * x))), 0j, complex(a, 0)


def stri_from_sides(a, b, c):
    """Exact version: returns sympy points A,B,C."""
    x = (s.sympify(c) ** 2 + s.sympify(a) ** 2 - s.sympify(b) ** 2) / (2 * s.sympify(a))
    return pt(x, s.sqrt(s.sympify(c) ** 2 - x * x)), pt(0, 0), pt(a, 0)


# ------------------------------------------------------------------ generators
# each gen_<id>(rng) -> dict(problem, answer_exact, params) or None on reject.

GENERATORS = {}


def register(cid):
    def deco(fn):
        GENERATORS[cid] = fn
        return fn

    return deco


@register("H01")
def gen_H01(rng):
    m = rng.choice([4, 5, 7, 8, 9, 10, 11])
    t = rng.choice([x for x in (6, 8, 9, 10, 11, 13, 14, 15) if x > m])
    u = rng.choice([s.Rational(1, 3), s.Rational(1, 4), s.Rational(2, 5), s.Rational(1, 5)])
    ax = t * (1 - u * u) / (1 + u * u)
    ay = t * 2 * u / (1 + u * u)
    a, b, c = pt(ax, ay), pt(-m, 0), pt(m, 0)
    try:
        sacute(a, b, c)
    except AssertionError:
        return None
    mm = (b + c) / 2
    h = sorthocenter(a, b, c)
    p = sfoot(h, a, mm)
    ans = slength(a, p)
    problem = render_config("H01", {"BC": fmt_given(2 * m), "AM": fmt_given(t)})
    return dict(
        problem=problem, answer_exact=answer_str(ans), params=dict(m=str(m), t=str(t), u=str(u))
    )


@register("H02")
def gen_H02(rng):
    w = rng.choice([7, 8, 9, 10, 12])
    ax = s.Rational(rng.choice([3, 4, 5, 6]))
    ay = s.Rational(rng.choice([7, 8, 9, 10, 11]))
    a, b, c = pt(ax, ay), pt(-w, 0), pt(w, 0)
    try:
        sacute(a, b, c)
    except AssertionError:
        return None
    m, k = (b + c) / 2, sfoot(a, b, c)
    i1 = s.Rational(rng.choice([3, 4, 5, 6]))
    i2 = s.Rational(rng.choice([7, 8, 9, 10, 11]))
    d1, d2 = b + pt(i1, 0), b + pt(i2, 0)
    if not (float(d1[0]) < float(d2[0]) < float(c[0])):
        return None
    zs = []
    for d in (d1, d2):
        u = ssecond(a, c, scircle(a, b, d), a)
        v = ssecond(a, b, scircle(a, c, d), a)
        z = scenter(scircle(a, u, v))
        eq(sfoot(z, b, c), d)
        zs.append(z)
    ans = slength(*zs)
    g = [fmt_given(x) for x in (slength(b, c), slength(a, m), slength(a, k), i1, i2)]
    if None in g:
        return None
    problem = render_config("H02", dict(zip(["BC", "AM", "AK", "BD1", "BD2"], g, strict=True)))
    return dict(
        problem=problem,
        answer_exact=answer_str(ans),
        params=dict(w=w, ax=str(ax), ay=str(ay), i1=str(i1), i2=str(i2)),
    )


@register("H03")
def gen_H03(rng):
    target = s.Rational(rng.choice([5, 6, 8, 9, 10]))
    bx = s.Rational(rng.choice([-7, -6, -5]))
    cx = s.Rational(rng.choice([5, 6, 7, 8]))
    ax = s.Rational(rng.choice([2, 3, 4]))
    ay = s.Rational(rng.choice([7, 8, 9]))
    a, b, c = pt(ax, ay), pt(bx, 0), pt(cx, 0)
    try:
        sacute(a, b, c)
    except AssertionError:
        return None
    o = scenter(scircle(a, b, c))
    h = sorthocenter(a, b, c)
    scale = target / slength(o, h)
    a, b, c = simp(scale * a), simp(scale * b), simp(scale * c)
    h, o = sorthocenter(a, b, c), scenter(scircle(a, b, c))
    ps = []
    for v, q, r in [(a, b, c), (b, c, a), (c, a, b)]:
        lq, lr = slength(v, q), slength(v, r)
        ki = simp((lr * q + lq * r) / (lr + lq))
        ke = simp((lr * q - lq * r) / (lr - lq))
        mid = (q + r) / 2
        p = ssecond(v, mid, scircle(v, ki, ke), v)
        ps.append(p)
        eq(p, sfoot(h, v, mid))
    z = scenter(scircle(*ps))
    # verified identity: Z is the midpoint of H and the centroid, so OZ=2*OH/3.
    eq(z, (h + (a + b + c) / 3) / 2)
    ans = slength(o, z)
    problem = render_config("H03", {"OH": fmt_given(target)})
    return dict(
        problem=problem,
        answer_exact=answer_str(ans),
        params=dict(target=str(target), bx=str(bx), cx=str(cx), ax=str(ax), ay=str(ay)),
    )


@register("H04")
def gen_H04(rng):
    bc = s.Rational(rng.choice([5, 6, 7, 8, 9]))
    ax = s.Rational(rng.choice([1, 2, 3]))
    ay2 = s.Rational(rng.choice([5, 6, 7, 11]))
    a, b, c = pt(ax, s.sqrt(ay2)), pt(0, 0), pt(bc, 0)
    try:
        sacute(a, b, c)
    except AssertionError:
        return None
    m, h = (b + c) / 2, sorthocenter(a, b, c)
    p = sfoot(h, a, m)
    t = sline((a + p) / 2, (a + p) / 2 + rot(a - p), b, c)
    if not float(t[0]) < 0:
        return None
    g = fmt_given(slength(b, t))
    if g is None:
        return None
    ans = slength(a, t)
    problem = render_config("H04", {"BT": g, "BC": fmt_given(bc)})
    return dict(
        problem=problem,
        answer_exact=answer_str(ans),
        params=dict(bc=str(bc), ax=str(ax), ay2=str(ay2)),
    )


@register("H07")
def gen_H07(rng):
    # two circles tangent to the x-axis at A=0, B=c, both through X.
    c = s.Rational(rng.choice([5, 6, 7, 8]))
    x0 = s.Rational(rng.choice([2, 3]))
    y0 = s.Rational(rng.choice([2, 3]))
    if float(x0) >= float(c):
        return None
    a, b, x = pt(0, 0), pt(c, 0), pt(x0, y0)
    r1 = (x0 * x0 + y0 * y0) / (2 * y0)
    r2 = ((x0 - c) ** 2 + y0 * y0) / (2 * y0)
    w = s.Matrix([0, -2 * r1, 0])
    z = s.Matrix([-2 * c, -2 * r2, c * c])
    n = sother_circle(w, z, x)
    try:
        sacute(n, a, b)
        assert 0 < float(x[1]) < float(n[1])
    except AssertionError:
        return None
    o = (a + b) / 2
    f = sfoot(x, a, b)
    g1, g2 = fmt_given(slength(o, n)), fmt_given(slength(x, f))
    if g1 is None or g2 is None:
        return None
    cc_, dd = ssecond(x, x + pt(1, 0), w, x), ssecond(x, x + pt(1, 0), z, x)
    e = sline(a, cc_, b, dd)
    p, q = sline(a, n, cc_, dd), sline(b, n, cc_, dd)
    try:
        eq((p + q) / 2, x)
        eq(e, sreflect(x, a, b))
    except AssertionError:
        return None
    ans = sarea(e, p, q)
    problem = render_config("H07", {"AB": fmt_given(c), "ON": g1, "MF": g2})
    return dict(
        problem=problem, answer_exact=answer_str(ans), params=dict(c=str(c), x0=str(x0), y0=str(y0))
    )


@register("H08")
def gen_H08(rng):
    # A',B' intersections of circles tangent to PQ at P,Q; C=reflect(B',PQ).
    px, qx = s.Rational(rng.choice([0, 1])), s.Rational(rng.choice([4, 5, 6, 8]))
    ax = s.Rational(rng.choice([2, 3]))
    ay = s.Rational(rng.choice([2, 3, 4]))
    pp, qq = pt(px, 0), pt(qx, 0)
    aa = pt(ax, ay)
    # circle tangent to x-axis at pp through aa: center (px, r)
    r1 = ((ax - px) ** 2 + ay * ay) / (2 * ay)
    r2 = ((ax - qx) ** 2 + ay * ay) / (2 * ay)
    ww = s.Matrix([-2 * px, -2 * r1, px * px])
    zz = s.Matrix([-2 * qx, -2 * r2, qx * qx])
    try:
        eq((pp - scenter(ww)).dot(qq - pp), 0)
        eq((qq - scenter(zz)).dot(qq - pp), 0)
    except AssertionError:
        return None
    bb = sother_circle(ww, zz, aa)
    if not (0 < float(bb[1]) < float(aa[1])):
        return None
    try:
        sacute(aa, pp, qq)
    except AssertionError:
        return None
    cc = sreflect(bb, pp, qq)
    tan_angle = s.simplify(s.Abs(scross(bb - aa, qq - aa)) / (bb - aa).dot(qq - aa))
    g = [fmt_given(v) for v in (slength(aa, pp), slength(aa, cc), tan_angle)]
    if None in g:
        return None
    ans = sarea(aa, pp, cc)
    problem = render_config("H08", {"AP": g[0], "tan_BAQ": g[2], "AC": g[1]})
    return dict(
        problem=problem,
        answer_exact=answer_str(ans),
        params=dict(px=str(px), qx=str(qx), ax=str(ax), ay=str(ay)),
    )


@register("H12")
def gen_H12(rng):
    # convex ABCD with equal angles at B and D (D on mirrored circumcircle).
    p_, q_ = s.Rational(rng.choice([1, 2])), s.Rational(rng.choice([4, 5, 6]))
    a, c = pt(-p_, 0), pt(q_, 0)
    bx = s.Rational(rng.choice([0, 1]))
    by = s.Rational(rng.choice([2, 3]))
    b = pt(bx, by)
    w1 = scircle(a, b, c)
    # mirror circle across AC (x-axis)
    w2 = s.Matrix([w1[0], -w1[1], w1[2]])
    dx = s.Rational(rng.choice([0, 1, 2]))
    # D on w2 below x-axis: parametrize y negative
    yy = s.symbols("yy", negative=True)
    sols = s.solve(son(pt(dx, yy), w2), yy)
    cand = [pt(dx, simp(rr)) for rr in sols if float(s.N(rr)) < 0]
    if len(cand) != 1:
        return None
    d = cand[0]
    try:
        e_, f_ = sline(*sbisector(b, a, c), a, c), sline(*sbisector(d, a, c), a, c)
        p = sline(b, e_, d, f_)
        m = (a + c) / 2
        w = scircle(b, p, d)
        x, y = ssecond(b, m, w, b), ssecond(d, m, w, d)
        q = sline(x, e_, y, f_)
        v = sfoot(p, a, c)
        cos_b = s.simplify((a - b).dot(c - b) / (slength(a, b) * slength(c, b)))
        cos_d = s.simplify((a - d).dot(c - d) / (slength(a, d) * slength(c, d)))
        eq(cos_b, cos_d)
        assert float(cos_b) > 0
        assert all(
            scross(vv - uu, zz - vv) < 0
            for uu, vv, zz in [(a, b, c), (b, c, d), (c, d, a), (d, a, b)]
        )
        for point, vertex in [(x, b), (y, d)]:
            assert 0 < float((point - vertex).dot(m - vertex) / norm(m - vertex)) < 1
        eq((q - p).dot(c - a), 0)
        assert float(p[1]) > 0 and float(q[1]) > float(p[1])
    except AssertionError:
        return None
    g = [fmt_given(v) for v in (slength(p, m), slength(p, v), slength(q, m))]
    if None in g:
        return None
    ans = slength(p, q)
    problem = render_config("H12", {"PM": g[0], "PV": g[1], "QM": g[2]})
    return dict(
        problem=problem,
        answer_exact=answer_str(ans),
        params=dict(p=str(p_), q=str(q_), bx=str(bx), by=str(by), dx=str(dx)),
    )


@register("H13")
def gen_H13(rng):
    # triangle with rational cos C via Pythagorean AC; K = tangent at C to circle BCM.
    bc = s.Rational(rng.choice([5, 6, 7, 8]))
    tri = rng.choice([(3, 4, 5), (5, 12, 13), (8, 15, 17), (7, 24, 25), (9, 12, 15)])
    scale = s.Rational(rng.choice([1, 2]))
    du, dv = tri[0] * scale, tri[1] * scale
    a = pt(bc - s.Rational(du), s.Rational(dv))
    b, c = pt(0, 0), pt(bc, 0)
    try:
        sacute(a, b, c)
    except AssertionError:
        return None
    m = (a + c) / 2
    w = scircle(b, m, c)
    k = sline(c, c + rot(c - scenter(w)), b, b + rot(c - b))
    j = sline(a, k, b, m)
    z = scenter(scircle(b, j, k))
    try:
        eq(scross(z - a, c - a), 0)
        for u, v in [(a, k), (b, m)]:
            assert 0 < float((j - u).dot(v - u) / norm(v - u)) < 1
    except AssertionError:
        return None
    cos_c = s.simplify((a - c).dot(b - c) / (slength(a, c) * slength(b, c)))
    g = [fmt_given(v) for v in (slength(b, c), slength(b, k), cos_c)]
    if None in g:
        return None
    ans = slength(c, z)
    problem = render_config("H13", {"BC": g[0], "BK": g[1], "cos_ACB": g[2]})
    return dict(
        problem=problem,
        answer_exact=answer_str(ans),
        params=dict(bc=str(bc), tri=tri, scale=str(scale)),
    )


@register("H14")
def gen_H14(rng):
    w_ = s.Rational(rng.choice([8, 10, 12, 14]))
    ax = s.Rational(rng.choice([10, 12, 14, 16]))
    ay = s.Rational(rng.choice([8, 10, 12]))
    a, b, c = pt(ax, ay), pt(-w_, 0), pt(w_, 0)
    try:
        sacute(a, b, c)
    except AssertionError:
        return None
    m, h = (b + c) / 2, sorthocenter(a, b, c)
    w = scircle(a, b, c)

    def radial(center_, r2):
        return s.Matrix([-2 * center_[0], -2 * center_[1], norm(center_) - r2])

    d = ssecond(a, b, radial(c, norm(c - a)), a)
    e = ssecond(a, c, radial(b, norm(b - a)), a)
    try:
        p, q = sray_circle(m, d, w), sray_circle(m, e, w)
        r = sother_circle(scircle(b, p, m), scircle(c, q, m), m)
        eq(r, sfoot(h, a, m))
    except AssertionError:
        return None
    g = [fmt_given(v) for v in (slength(a, h), slength(a, r))]
    if None in g:
        return None
    ans = sarea(a, h, r)
    problem = render_config("H14", {"AH": g[0], "AR": g[1]})
    return dict(
        problem=problem,
        answer_exact=answer_str(ans),
        params=dict(w=str(w_), ax=str(ax), ay=str(ay)),
    )


@register("H15")
def gen_H15(rng):
    # angle A = 60°: A=0, B=(c,0), C=(b/2, b*sqrt3/2).
    c_ = s.Rational(rng.choice([3, 4, 5, 6]))
    b_ = s.Rational(rng.choice([3, 4, 5, 7]))
    if b_ == c_:
        return None
    a, b, c = pt(0, 0), pt(c_, 0), pt(b_ / 2, s.sqrt(3) * b_ / 2)
    w = scircle(a, b, c)
    x = sline(b, b + rot(b - scenter(w)), c, c + rot(c - scenter(w)))
    d = ssecond(a, x, w, a)
    e = sreflect(d, b, c)
    b0, c0 = sreflect(e, a, c), sreflect(e, a, b)
    k = sline(b, b0, c, c0)
    try:
        eq(k, (a + d) / 2)
    except AssertionError:
        return None
    g = [fmt_given(v) for v in (slength(a, b), slength(b, d), slength(a, d))]
    if None in g:
        return None
    ans = slength(b, k)
    problem = render_config("H15", {"AB": g[0], "BD": g[1], "AD": g[2]})
    return dict(problem=problem, answer_exact=answer_str(ans), params=dict(b=str(b_), c=str(c_)))


@register("HX01")
def gen_HX01(rng):
    bc = s.Rational(rng.choice([5, 6, 7]))
    ax = s.Rational(rng.choice([2, 3]))
    ay_num = s.Rational(rng.choice([5, 7, 11]))
    a = pt(ax, s.sqrt(ay_num) * ax)
    b, c = pt(0, 0), pt(bc, 0)
    try:
        sacute(a, b, c)
    except AssertionError:
        return None
    d, e, p = (b + c) / 2, (c + a) / 2, sfoot(a, b, c)
    w = scircle(a, b, c)
    x = sline(b, b + rot(b - scenter(w)), c, c + rot(c - scenter(w)))
    l = ssecond(a, x, w, a)  # noqa: E741
    j = sother_circle(scircle(c, e, p), scircle(c, d, l), c)
    q = (a + l) / 2
    try:
        eq(scross(j - a, l - a), 0)
        eq(son(q, scircle(c, e, p)), 0)
    except AssertionError:
        return None
    g = [fmt_given(v) for v in (slength(a, c), slength(a, l))]
    if None in g:
        return None
    ans = slength(a, j)
    problem = render_config("HX01", {"AC": g[0], "AL": g[1]})
    return dict(
        problem=problem,
        answer_exact=answer_str(ans),
        params=dict(bc=str(bc), ax=str(ax), ay_num=str(ay_num)),
    )


# --- similarity-scaled variants -------------------------------------------
# Spec: given name -> (text template with {v}, exponent). Scale-invariant
# givens (angles, cosines, ratios) are simply omitted. ans_exp is the
# homogeneity degree of the answer (1=length, 2=area/square, 0=dimensionless).

SCALE_FACTORS = [
    s.Rational(2),
    s.Rational(3),
    s.Rational(3, 2),
    s.Rational(1, 2),
    s.Rational(5, 2),
    s.Rational(4, 3),
    s.Rational(2, 3),
    s.Rational(5, 4),
]


def load_cards():
    cards = {}
    for name in ("h_revision.json", "da_revision.json", "db_revision.json"):
        for card in json.loads((HERE / name).read_text()):
            if card.get("decision") in ("main", "probe"):
                cards[card["id"]] = card
    return cards


def scaled_variant(row, card, k):
    """Similarity augmentation is explicit and never changes the problem prose."""
    spec = templates()[row["id"]]
    k = s.Rational(k)
    if k <= 0:
        raise ValueError("scale must be positive")
    givens = {
        name: s.sympify(value) * k ** spec["given_scale_degrees"][name]
        for name, value in spec["base_givens"].items()
    }
    ans = s.sympify(row["answer_exact"]) * k ** spec["answer_scale_degree"]
    return dict(
        problem=render_config(row["id"], givens),
        answer_exact=answer_str(ans),
        params=dict(scale=str(k)),
    )


REPLAY_ORDER = {
    "H01": ("m", "t", "u"),
    "H02": ("w", "ax", "ay", "i1", "i2"),
    "H03": ("target", "bx", "cx", "ax", "ay"),
    "H04": ("bc", "ax", "ay2"),
    "H07": ("c", "x0", "y0"),
    "H08": ("px", "qx", "ax", "ay"),
    "H12": ("p", "q", "bx", "by", "dx"),
    "H13": ("bc", "tri", "scale"),
    "H14": ("w", "ax", "ay"),
    "H15": ("c", "b"),
    "HX01": ("bc", "ax", "ay_num"),
}


class Replay:
    def __init__(self, cid, params):
        self.values = iter(params[key] for key in REPLAY_ORDER[cid])

    def choice(self, choices):
        value = next(self.values)
        for candidate in choices:
            if isinstance(value, list):
                if tuple(value) == tuple(candidate):
                    return candidate
            elif s.sympify(candidate) == s.sympify(value):
                return candidate
        raise ValueError(f"Recorded choice {value} is not in {choices}")


def replay_record(row, originals, cards):
    cid = row["id"]
    if row["variant"] == "v0":
        return dict(originals[cid])
    if set(row["params"]) == {"scale"}:
        return scaled_variant(originals[cid], cards[cid], s.Rational(row["params"]["scale"]))
    return GENERATORS[cid](Replay(cid, row["params"]))


def sample_shape(cid, rng, seen, max_tries):
    generator = GENERATORS.get(cid)
    if generator is None:
        raise ValueError(
            f"{cid}: no non-similarity generator; explicitly allow similarity augmentation"
        )
    for _ in range(max_tries):
        try:
            record = generator(rng)
            if record is not None and signature(cid, record["problem"]) not in seen:
                checked_record(cid, record, "check", "check")
                return record
        except (AssertionError, ZeroDivisionError, ValueError, TypeError):
            continue
    raise ValueError(f"{cid}: no valid distinct shape after {max_tries} attempts")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", default="")
    parser.add_argument("--train-variants", type=int, default=3)
    parser.add_argument("--dev-variants", type=int, default=1)
    parser.add_argument("--max-tries", type=int, default=80)
    parser.add_argument("--seed", type=int, default=20260921)
    parser.add_argument("--dry", action="store_true")
    parser.add_argument(
        "--allow-similarity",
        action="store_true",
        help="Explicitly permit and label similarity augmentation; never a silent fallback",
    )
    parser.add_argument(
        "--repair-from",
        type=Path,
        help="Replay frozen historical train/dev JSONL parameters using approved text",
    )
    parser.add_argument("--output-dir", type=Path, default=DATA)
    args = parser.parse_args()
    originals = {
        row["id"]: row
        for row in map(json.loads, (DATA / "training_problems.jsonl").read_text().splitlines())
    }
    cards = load_cards()
    for cid, row in originals.items():
        spec = templates()[cid]
        assert (
            hashlib.sha256(row["problem"].encode()).hexdigest() == spec["approved_problem_sha256"]
        )
        assert spec["template"].format(**spec["base_literals"]) == row["problem"]
    outputs = {"train": [], "dev": []}
    seen, changes = set(), []
    rng = random.Random(args.seed)
    if args.repair_from:
        for split, filename in [
            ("train", "training_variants.jsonl"),
            ("dev", "eval_variants.jsonl"),
        ]:
            for old in map(json.loads, (args.repair_from / filename).read_text().splitlines()):
                cid = old["id"]
                if args.only and cid != args.only:
                    continue
                reason = "canonical_text_and_verified_givens"
                record = replay_record(old, originals, cards)
                if record is None or signature(cid, record["problem"]) in seen:
                    reason = "invalid_domain" if record is None else "duplicate_numerical_problem"
                    record = sample_shape(cid, rng, seen, args.max_tries)
                record = checked_record(cid, record, old["variant"], split)
                seen.add(signature(cid, record["problem"]))
                outputs[split].append(record)
                changes.append(
                    {
                        "id": cid,
                        "variant": old["variant"],
                        "reason": reason,
                        "problem_changed": record["problem"] != old["problem"],
                        "answer_changed": s.simplify(
                            s.sympify(record["answer_exact"]) - s.sympify(old["answer_exact"])
                        )
                        != 0,
                    }
                )
                print(f"verified {cid}/{old['variant']}: {reason}", flush=True)
    else:
        for cid, original in originals.items():
            if args.only and cid != args.only:
                continue
            outputs["train"].append(checked_record(cid, original, "v0", "train"))
            seen.add(signature(cid, original["problem"]))
            for split, count, prefix in [
                ("train", args.train_variants, "v"),
                ("dev", args.dev_variants, "d"),
            ]:
                for i in range(1, count + 1):
                    if cid in GENERATORS:
                        record = sample_shape(cid, rng, seen, args.max_tries)
                    elif args.allow_similarity:
                        choices = SCALE_FACTORS[:]
                        rng.shuffle(choices)
                        candidates = [scaled_variant(original, cards[cid], k) for k in choices]
                        record = next(
                            (r for r in candidates if signature(cid, r["problem"]) not in seen),
                            None,
                        )
                        if record is None:
                            raise ValueError(f"{cid}: insufficient distinct scales")
                    else:
                        raise ValueError(
                            f"{cid}: no shape generator; use --allow-similarity explicitly"
                        )
                    seen.add(signature(cid, record["problem"]))
                    outputs[split].append(checked_record(cid, record, f"{prefix}{i}", split))
    from collections import Counter

    report = {
        "version": "canonical-variants-v2",
        "source": str(args.repair_from) if args.repair_from else None,
        "seed": args.seed,
        "counts": {
            k: dict(Counter(r["augmentation"] for r in rows)) for k, rows in outputs.items()
        },
        "numerical_duplicates": 0,
        "changes": changes,
        "verification_scope": "Approved immutable templates; exact replay and independent "
        "relations for shape records; positive similarity of verified originals "
        "for scale records. Not a solver-generated corpus.",
        "general_proof_limits": "Inherits source-card proof scope, "
        "including DA13/DA16/DA17 limitations (DB09 is a probe, not in this set).",
        "source_hashes": {
            str(p.relative_to(DATA)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [
                Path(__file__),
                HERE / "variant_templates.json",
                DATA / "training_problems.jsonl",
                DATA / "revisions.json",
                HERE / "verify_h_revision.py",
                HERE / "verify_da_revision.py",
                HERE / "verify_db_revision.py",
            ]
        },
    }
    if not args.dry:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for split, filename in [
            ("train", "training_variants.jsonl"),
            ("dev", "eval_variants.jsonl"),
        ]:
            dest = args.output_dir / filename
            dest.write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in outputs[split])
            )
            report.setdefault("output_hashes", {})[filename] = hashlib.sha256(
                dest.read_bytes()
            ).hexdigest()
        (args.output_dir / "variant_validation.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        )
    print(
        json.dumps(
            {k: v for k, v in report.items() if k != "changes"}, ensure_ascii=False, indent=2
        )
    )


if __name__ == "__main__":
    main()
