"""Exact witnesses for the H v2 questions; no training or network requests.

Each witness is reconstructed from the original line/circle definitions. The
shortcut identities are asserted afterwards, never used to construct the target.
Existing general identities were documented in the retired v1 verifiers (git
history). This file also
checks the newly used H15 midpoint identity symbolically for a 60-degree vertex.
Run normally to compare all main/probe records, or use --json for witness data.
"""
import argparse
import json
from pathlib import Path

import sympy as s


def pt(x, y):
    return s.Matrix([s.sympify(x), s.sympify(y)])


def simp(p):
    return p.applyfunc(s.simplify) if isinstance(p, s.MatrixBase) else s.simplify(p)


def norm(p):
    return s.factor(p.dot(p))


def cross(p, q):
    return s.factor(p[0] * q[1] - p[1] * q[0])


def rot(p):
    return pt(-p[1], p[0])


def line(a, b, c, d):
    return simp(a + (b - a) * cross(c - a, d - c) / cross(b - a, d - c))


def foot(p, a, b):
    return simp(a + (b - a) * (p - a).dot(b - a) / norm(b - a))


def reflect(p, a, b):
    return simp(2 * foot(p, a, b) - p)


def circle(a, b, c):
    mat = s.Matrix([[a[0], a[1], 1], [b[0], b[1], 1], [c[0], c[1], 1]])
    return simp(mat.inv() * s.Matrix([-norm(a), -norm(b), -norm(c)]))


def center(w):
    return simp(-w[:2, :] / 2)


def on(p, w):
    return s.simplify(norm(p) + w[0] * p[0] + w[1] * p[1] + w[2])


def second(a, b, w, known):
    assert on(known, w) == 0
    v = b - a
    return simp(known - v * (2 * known.dot(v) + w[0] * v[0] + w[1] * v[1]) / norm(v))


def other_circle(w, z, known):
    v = rot((w - z)[:2, :])
    return second(known, known + v, w, known)


def ray_circle(a, b, w):
    t = s.symbols("t", real=True)
    roots = s.solve(on(a + t * (b - a), w), t)
    positive = [r for r in roots if float(r.evalf()) > 0]
    assert len(positive) == 1
    return simp(a + positive[0] * (b - a))


def tangent(p, w):
    return p, p + rot(p - center(w))


def orthocenter(a, b, c):
    return line(a, a + rot(c - b), b, b + rot(c - a))


def bisector(a, b, c):
    return a, simp(a + (b - a) / s.sqrt(norm(b - a)) + (c - a) / s.sqrt(norm(c - a)))


def length(a, b):
    return s.simplify(s.sqrt(norm(a - b)))


def area(a, b, c):
    return s.simplify(s.Abs(cross(b - a, c - a)) / 2)


def eq(a, b):
    diff = simp(a - b)
    assert all(v == 0 for v in diff) if isinstance(diff, s.MatrixBase) else diff == 0


def acute(a, b, c):
    assert len({norm(a-b), norm(b-c), norm(c-a)}) == 3
    assert all(float(((q - p).dot(r - p)).evalf()) > 0 for p, q, r in [(a, b, c), (b, a, c), (c, a, b)])


def save(rows, ident, points, givens, answer):
    rows[ident] = {
        "points": {k: [str(s.simplify(v)) for v in p] for k, p in points.items()},
        "given_values": {k: str(s.simplify(v)) for k, v in givens.items()},
        "answer": str(s.simplify(answer)),
    }


def build():
    rows = {}
    a, b, c = pt(s.Rational(14, 5), s.Rational(48, 5)), pt(-6, 0), pt(6, 0)
    acute(a, b, c)
    m = (b + c) / 2
    h = orthocenter(a, b, c)
    p = foot(h, a, m)
    save(rows, "H01", dict(A=a, B=b, C=c, M=m, H=h, P=p), {"AM": length(a, m), "BC": length(b, c)}, length(a, p))

    a, b, c = pt(6, 8), pt(-8, 0), pt(8, 0)
    acute(a, b, c)
    m, k = (b + c) / 2, foot(a, b, c)
    points = dict(A=a, B=b, C=c, M=m, K=k)
    zs = []
    for i, d in enumerate([pt(-2, 0), pt(1, 0)], start=1):
        u = second(a, c, circle(a, b, d), a)
        v = second(a, b, circle(a, c, d), a)
        z = center(circle(a, u, v))
        points.update({f"D{i}": d, f"U{i}": u, f"V{i}": v, f"Z{i}": z})
        eq(foot(z, b, c), d)
        zs.append(z)
    eq((zs[1] - zs[0]).dot(a - m), 0)
    save(rows, "H02", points, {"AM": length(a, m), "BC": length(b, c), "AK": length(a, k), "BD1": length(b, points["D1"]), "BD2": length(b, points["D2"])}, length(*zs))

    a, b, c = pt(s.Rational(18, 5), s.Rational(72, 5)), pt(-6, 0), pt(6, 0)
    acute(a, b, c)
    h, o = orthocenter(a, b, c), center(circle(a, b, c))
    points = dict(A=a, B=b, C=c, H=h, O=o)
    ps = []
    for tag, (v, q, r) in zip("abc", [(a, b, c), (b, c, a), (c, a, b)], strict=False):
        lq, lr = length(v, q), length(v, r)
        ki, ke = simp((lr * q + lq * r) / (lr + lq)), simp((lr * q - lq * r) / (lr - lq))
        mid = (q + r) / 2
        p = second(v, mid, circle(v, ki, ke), v)
        ps.append(p)
        points.update({f"K_{tag}": ki, f"L_{tag}": ke, f"M_{tag}": mid, f"P_{tag}": p})
        eq(p, foot(h, v, mid))
    z = center(circle(*ps))
    points["Z"] = z
    eq(z, (h + (a + b + c) / 3) / 2)
    save(rows, "H03", points, {"OH": length(o, h)}, length(o, z))

    a, b, c = pt(1, s.sqrt(7)), pt(0, 0), pt(6, 0)
    acute(a, b, c)
    m, h = (b + c) / 2, orthocenter(a, b, c)
    p = foot(h, a, m)
    t = line((a + p) / 2, (a + p) / 2 + rot(a - p), b, c)
    eq(t, pt(-2, 0))
    save(rows, "H04", dict(A=a, B=b, C=c, H=h, M=m, P=p, T=t), {"BC": length(b, c), "BT": length(b, t)}, length(a, t))

    a, b, x = pt(0, 0), pt(6, 0), pt(2, 2)
    w, z = s.Matrix([0, -4, 0]), s.Matrix([-12, -10, 36])
    o1, o2 = center(w), center(z)
    k, l = line(*tangent(x, w), o1, o2), line(*tangent(x, z), o1, o2)
    n, m = second(a, k, w, a), second(b, l, z, b)
    r = line(a, m, b, n)
    eq(cross(r - o1, o2 - o1), 0)
    assert o1[1] < r[1] < o2[1]
    assert 0 < x[1] < other_circle(w, z, x)[1]
    save(rows, "H06", dict(A=a, B=b, X=x, O1=o1, O2=o2, K=k, L=l, M=m, N=n, R=r), {"AB": length(a, b), "r1": s.sqrt(norm(o1) - w[2]), "r2": s.sqrt(norm(o2) - z[2]), "O1R": length(o1, r)}, length(r, foot(r, a, b)))

    # The former H07/H08 witness was isosceles, contrary to the statement.
    a, b, x = pt(0, 0), pt(8, 0), pt(3, 3)
    w, z = s.Matrix([0, -6, 0]), s.Matrix([-16, -s.Rational(34, 3), 64])
    n = other_circle(w, z, x)
    acute(n, a, b)
    cc, dd = second(x, x + pt(1, 0), w, x), second(x, x + pt(1, 0), z, x)
    e = line(a, cc, b, dd)
    p, q = line(a, n, cc, dd), line(b, n, cc, dd)
    o, f = (a + b) / 2, foot(x, a, b)
    eq((p + q) / 2, x)
    eq(e, reflect(x, a, b))
    save(rows, "H07", dict(A=a, B=b, M=x, N=n, C=cc, D=dd, E=e, P=p, Q=q, O=o, F=f), {"AB": length(a, b), "ON": length(o, n), "MF": length(x, f)}, area(e, p, q))

    scale = s.sqrt(5) / 2
    aa, bb, pp, qq = simp(scale * n), simp(scale * x), scale * a, scale * b
    acute(aa, pp, qq)
    assert 0 < float(bb[1]) < float(aa[1])
    cc = reflect(bb, pp, qq)
    # Reconstruct both tangent circles after scaling; their second intersection is aa.
    ww, zz = circle(pp, aa, bb), circle(qq, aa, bb)
    eq((pp - center(ww)).dot(qq - pp), 0)
    eq((qq - center(zz)).dot(qq - pp), 0)
    tan_angle = s.simplify(s.Abs(cross(bb - aa, qq - aa)) / (bb - aa).dot(qq - aa))
    save(rows, "H08", dict(A=aa, B=bb, P=pp, Q=qq, C=cc), {"AP": length(aa, pp), "AC": length(aa, cc), "tan_BAQ": tan_angle}, area(aa, pp, cc))

    a, b, c, d = pt(-1, 0), pt(s.Rational(3, 4), s.Rational(7, 4)), pt(1, 0), pt(-1, s.Rational(-3, 2))
    e, f = line(*bisector(b, a, c), a, c), line(*bisector(d, a, c), a, c)
    p, m = line(b, e, d, f), (a + c) / 2
    w = circle(b, p, d)
    x, y = second(b, m, w, b), second(d, m, w, d)
    q, v = line(x, e, y, f), foot(p, a, c)
    cos_b = s.simplify((a - b).dot(c - b) / (length(a, b) * length(c, b)))
    cos_d = s.simplify((a - d).dot(c - d) / (length(a, d) * length(c, d)))
    eq(cos_b, cos_d)
    assert float(cos_b) > 0
    assert all(cross(v - u, z - v) < 0 for u, v, z in [(a, b, c), (b, c, d), (c, d, a), (d, a, b)])
    for point, vertex in [(x, b), (y, d)]:
        assert 0 < float((point - vertex).dot(m - vertex) / norm(m - vertex)) < 1
    eq((q - p).dot(c - a), 0)
    assert p[1] > 0 and q[1] > p[1]
    save(rows, "H12", dict(A=a, B=b, C=c, D=d, E=e, F=f, P=p, M=m, X=x, Y=y, Q=q, V=v), {"PM": length(p, m), "PV": length(p, v), "QM": length(q, m)}, length(p, q))

    a, b, c = pt(s.Rational(6, 25), s.Rational(192, 25)), pt(0, 0), pt(6, 0)
    acute(a, b, c)
    m = (a + c) / 2
    w = circle(b, m, c)
    k = line(*tangent(c, w), b, b + rot(c - b))
    j = line(a, k, b, m)
    z = center(circle(b, j, k))
    eq(k, pt(0, -24))
    eq(cross(z - a, c - a), 0)
    for u, v in [(a, k), (b, m)]:
        assert 0 < float((j - u).dot(v - u) / norm(v - u)) < 1
    cos_c = s.simplify((a - c).dot(b - c) / (length(a, c) * length(b, c)))
    save(rows, "H13", dict(A=a, B=b, C=c, M=m, K=k, J=j, Z=z), {"BC": length(b, c), "BK": length(b, k), "cos_ACB": cos_c}, length(c, z))

    a, b, c = pt(16, 12), pt(-2 * s.sqrt(70), 0), pt(2 * s.sqrt(70), 0)
    acute(a, b, c)
    m, h = (b + c) / 2, orthocenter(a, b, c)
    w = circle(a, b, c)
    def radial(center_, r2):
        return s.Matrix([-2 * center_[0], -2 * center_[1], norm(center_) - r2])
    d = second(a, b, radial(c, norm(c - a)), a)
    e = second(a, c, radial(b, norm(b - a)), a)
    p, q = ray_circle(m, d, w), ray_circle(m, e, w)
    r = other_circle(circle(b, p, m), circle(c, q, m), m)
    eq(r, foot(h, a, m))
    save(rows, "H14", dict(A=a, B=b, C=c, M=m, H=h, D=d, E=e, P=p, Q=q, R=r), {"AH": length(a, h), "AR": length(a, r)}, area(a, h, r))

    factor = s.sqrt(19) / 3
    a, b, c = pt(0, 0), pt(3 * factor, 0), pt(factor, s.sqrt(3) * factor)
    w = circle(a, b, c)
    x = line(*tangent(b, w), *tangent(c, w))
    d = second(a, x, w, a)
    e = reflect(d, b, c)
    b0, c0 = reflect(e, a, c), reflect(e, a, b)
    k = line(b, b0, c, c0)
    eq(k, (a + d) / 2)
    eq((b - a).dot(c - a) / (length(a, b) * length(a, c)), s.Rational(1, 2))
    save(rows, "H15", dict(A=a, B=b, C=c, X=x, D=d, E=e, B0=b0, C0=c0, K=k), {"angle_BAC_deg": 60, "AB": length(a, b), "BD": length(b, d), "AD": length(a, d)}, length(b, k))

    a, b, c = pt(0, 0), pt(s.Rational(9, 4), 9 * s.sqrt(15) / 4), pt(6, 0)
    acute(a, b, c)
    d, e, p = (b + c) / 2, (c + a) / 2, foot(a, b, c)
    w = circle(a, b, c)
    x = line(*tangent(b, w), *tangent(c, w))
    l = second(a, x, w, a)
    j = other_circle(circle(c, e, p), circle(c, d, l), c)
    q = (a + l) / 2
    eq(cross(j - a, l - a), 0)
    eq(on(q, circle(c, e, p)), 0)
    save(rows, "HX01", dict(A=a, B=b, C=c, D=d, E=e, P=p, X=x, L=l, J=j, Q=q), {"AC": length(a, c), "AL": length(a, l)}, length(a, j))
    return rows


def symbolic_new_identities():
    # H15: at angle A=60 degrees the two reflected lines contain midpoint AD.
    b_len, c_len = s.symbols("b c", positive=True)
    a, b, c = pt(0, 0), pt(c_len, 0), pt(b_len / 2, s.sqrt(3) * b_len / 2)
    w = circle(a, b, c)
    x = line(*tangent(b, w), *tangent(c, w))
    d = second(a, x, w, a)
    e = reflect(d, b, c)
    b0, c0 = reflect(e, a, c), reflect(e, a, b)
    eq(cross(d / 2 - b, b0 - b), 0)
    eq(cross(d / 2 - c, c0 - c), 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    rows = build()
    symbolic_new_identities()
    path = Path(__file__).with_name("h_revision.json")
    if path.exists():
        cards = json.loads(path.read_text())
        required = {r["id"] for r in cards if r["decision"] in ("main", "probe")}
        assert required == set(rows), (required, set(rows))
        for card in cards:
            if card["id"] not in rows:
                continue
            actual = rows[card["id"]]
            eq(s.sympify(actual["answer"]), s.sympify(card["answer_exact"]))
            for given in card["givens"]:
                eq(s.sympify(actual["given_values"][given["name"]]), s.sympify(given["value"]))
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        print(f"{len(rows)} exact H v2 construction witnesses, givens and answers passed; H15 general midpoint identity passed.")


if __name__ == "__main__":
    main()
