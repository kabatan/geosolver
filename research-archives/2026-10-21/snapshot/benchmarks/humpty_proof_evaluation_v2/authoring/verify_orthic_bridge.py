"""Exact audit of the orthic Humpty-to-Dumpty bridge, without using the bridge.

The two tangent circles and their second intersection are constructed from the
problem's original definitions.  The altitude projection and its half-point
are then computed independently.  No model calls or dataset mutations.
"""

import argparse
import json

import sympy as s


def pt(x, y):
    return s.Matrix([s.sympify(x), s.sympify(y)])


def simp(z):
    if isinstance(z, s.MatrixBase):
        return z.applyfunc(s.factor)
    return s.factor(z)


def norm(z):
    return simp(z.dot(z))


def cross(z, w):
    return simp(s.det(s.Matrix.hstack(z, w)))


def equal(z, w=0):
    delta = z - w
    values = list(delta) if isinstance(delta, s.MatrixBase) else [delta]
    assert all(simp(t) == 0 for t in values), simp(delta)


def foot(z, a, b):
    return simp(a + (b - a) * (z - a).dot(b - a) / norm(b - a))


def circle_value(z, circle):
    return simp(norm(z) + circle[0] * z[0] + circle[1] * z[1] + circle[2])


def tangent_circle(a, e, tangent_direction):
    # |z|^2 + alpha*x + beta*y + gamma = 0.  The circle contains
    # a,e and its gradient at a is perpendicular to the tangent direction.
    matrix = s.Matrix([
        [a[0], a[1], 1],
        [e[0], e[1], 1],
        [tangent_direction[0], tangent_direction[1], 0],
    ])
    rhs = s.Matrix([-norm(a), -norm(e), -2 * a.dot(tangent_direction)])
    return simp(matrix.inv() * rhs)


def second_intersection(a, circle1, circle2):
    # The radical axis contains the known intersection a.  Substitute its
    # direction into the first circle and divide out the known zero root.
    difference = circle1 - circle2
    direction = pt(-difference[1], difference[0])
    scale = -(2 * a.dot(direction) + circle1[0] * direction[0]
              + circle1[1] * direction[1]) / norm(direction)
    return simp(a + scale * direction)


def construct(u, v):
    # Acute, unequal-AB/AC domain: -1<u<1, v>0, u^2+v^2>1, u!=0.
    a, b, c, n = pt(u, v), pt(-1, 0), pt(1, 0), pt(0, 0)
    e, f = foot(b, a, c), foot(c, a, b)
    circle1 = tangent_circle(a, e, f - a)
    circle2 = tangent_circle(a, f, e - a)
    x = second_intersection(a, circle1, circle2)
    # Construct H from its two altitude equations, not from a special-point
    # formula: BC horizontal gives H_x=A_x; (H-B) dot (C-A)=0 gives H_y.
    h = pt(u, (1 - u * u) / v)
    p = foot(h, a, n)
    m = simp((a + p) / 2)
    return {"A": a, "B": b, "C": c, "N": n, "E": e, "F": f,
            "H": h, "P": p, "M": m, "X": x}, (circle1, circle2)


def audit(points, circles):
    a, b, c, n, e, f, h, p, m, x = [points[k] for k in
        ("A", "B", "C", "N", "E", "F", "H", "P", "M", "X")]
    circle1, circle2 = circles
    equal((b - e).dot(c - a))
    equal((c - f).dot(b - a))
    equal((h - b).dot(c - a))
    equal((h - c).dot(b - a))
    equal(cross(p - a, n - a))
    equal((h - p).dot(n - a))
    for z in (a, e, x):
        equal(circle_value(z, circle1))
    for z in (a, f, x):
        equal(circle_value(z, circle2))
    equal((2 * a + circle1[:2, 0]).dot(f - a))
    equal((2 * a + circle2[:2, 0]).dot(e - a))
    for z in (e, f, p):
        equal((z - a).dot(z - h))  # common circle of diameter AH
    equal(norm(p - e) * norm(a - f), norm(p - f) * norm(a - e))
    equal(x, m)
    equal(cross(x - a, n - a))


def general_check():
    u, v = s.symbols("u v", real=True, nonzero=True)
    points, circles = construct(u, v)
    audit(points, circles)
    a = points["A"]
    q = norm(a)
    equal(points["P"], a / q)
    equal(points["X"], a * (q + 1) / (2 * q))
    # q>1 implies 0<1/q<1 and 0<(q+1)/(2q)<1.  Thus P,M,X are
    # distinct from A and lie on the open segment AN in the stated domain.
    return {"passed": True,
            "domain": "-1<u<1, v>0, u^2+v^2>1, u!=0",
            "P": [str(t) for t in points["P"]],
            "X": [str(t) for t in points["X"]]}


def witness():
    points, circles = construct(s.Rational(1, 2), s.Rational(3, 2))
    audit(points, circles)
    a, b, c = (points[k] for k in ("A", "B", "C"))
    assert all((r - z).dot(t - z) > 0
               for z, r, t in ((a, b, c), (b, c, a), (c, a, b)))
    assert norm(a - b) != norm(a - c)
    assert norm(points["X"] - a) > 0
    assert circles[0] != circles[1]
    for circle in circles:
        assert simp((circle[0]**2 + circle[1]**2) / 4 - circle[2]) > 0
    return {"points": {k: [str(z) for z in p] for k, p in points.items()},
            "circle_coefficients": [[str(z) for z in circle] for circle in circles],
            "checks": ["acute triangle and AB != AC",
                       "altitude feet and both tangent circles built from definitions",
                       "second intersection X independently constructed",
                       "X=(A+P)/2 and A,N,X collinear"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = {"general": general_check(), "witness": witness()}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("OB01: general identities and exact nondegenerate witness passed")
