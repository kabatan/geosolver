"""Exact rational witnesses for disputed claims in the discovery audit."""
from fractions import Fraction as F
from math import dist


def add(p, q):
    return p[0] + q[0], p[1] + q[1]


def sub(p, q):
    return p[0] - q[0], p[1] - q[1]


def scale(t, p):
    return t * p[0], t * p[1]


def dot(p, q):
    return p[0] * q[0] + p[1] * q[1]


def cross(p, q):
    return p[0] * q[1] - p[1] * q[0]


def intersect(p, u, q, v):
    t = cross(sub(q, p), v) / cross(u, v)
    return add(p, scale(t, u))


def main():
    # Acute scalene triangle with both DA15 construction rays defined and F interior.
    a, b, c = (F(1, 5), F(17, 10)), (F(-1), F(0)), (F(1), F(0))
    m = (F(0), F(0))
    norm_a = dot(a, a)
    o = (F(0), (norm_a - 1) / (2 * a[1]))
    td = (norm_a - 1) / (2 * (norm_a - dot(a, b)))
    te = (norm_a - 1) / (2 * (norm_a - dot(a, c)))
    d, e = scale(td, a), scale(te, a)
    f = intersect(b, sub(d, b), c, sub(e, c))
    assert td > 0 and te > 0 and f[1] > 0
    assert cross(sub(b, a), sub(f, a)) > 0
    assert cross(sub(f, a), sub(c, a)) > 0
    assert cross(sub(c, b), sub(f, b)) > 0
    assert f != scale(F(1, 2), add(o, m))  # False midpoint claim in dose DA15-1.
    circle_d = (1 - o[1] * o[1]) / o[1]
    assert dot(f, f) + circle_d * f[1] - 1 == 0  # B,C,O,F concyclic.
    bf, cf, of, ob, bc = (dist(tuple(map(float, x)), tuple(map(float, y)))
                            for x, y in ((b, f), (c, f), (o, f), (o, b), (b, c)))
    assert abs(of - ob * abs(bf - cf) / bc) < 1e-12
    assert abs(of - ob * (bf + cf) / bc) > 0.1  # Wrong Ptolemy order in mapped DA15-1.

    # For DA08, the antipode of O on the circle BOC has Q=(0,-1/O_y).
    q = (F(0), -1 / o[1])
    assert dot(sub(q, a), sub(c, a)) != 0  # AQ is not perpendicular to AC || MN.
    m_da08 = intersect(c, sub(q, c), a, sub(c, b))  # CQ and A-line parallel BC.
    n_da08 = sub(add(a, c), m_da08)  # ANCM is a parallelogram.
    t_da08 = intersect(a, sub(q, a), m_da08, sub(n_da08, m_da08))
    assert t_da08[1] != 0  # False T on BC claim in dose DA08.

    # DA01: two circles tangent to AC/AB at A for the right triangle below.
    aa, bb, cc = (F(0), F(0)), (F(3), F(0)), (F(0), F(4))
    t = (F(48, 25), F(36, 25))
    assert dot(t, t) == 3 * t[0] == 4 * t[1]
    bt2, ct2 = dot(sub(bb, t), sub(bb, t)), dot(sub(cc, t), sub(cc, t))
    assert bt2 / ct2 == F(81, 256)  # BT/CT=9/16, while AB/AC=3/4.
    assert F(9, 16) == (F(3, 4)) ** 2
    print(dict(DA15_F=tuple(map(str, f)), DA15_O=tuple(map(str, o)),
               DA15_true_OF=of, DA15_wrong_OF=ob * (bf + cf) / bc,
               DA08_AQ_dot_AC=str(dot(sub(q, a), sub(c, a))),
               DA08_T=tuple(map(str, t_da08)),
               DA01_BT_over_CT="9/16", DA01_AB_over_AC="3/4"))


if __name__ == "__main__":
    main()
