"""Verifier-side checks for the thinking-mode candidates; never used as model input."""
import sympy as s


def da15_symbolic():
    u, v = s.symbols("u v", real=True, nonzero=True)
    A, B, C = s.Point(u, v), s.Point(-1, 0), s.Point(1, 0)
    a2 = u * u + v * v
    D = s.Point(u * (a2 - 1) / (2 * (a2 + u)), v * (a2 - 1) / (2 * (a2 + u)))
    E = s.Point(u * (a2 - 1) / (2 * (a2 - u)), v * (a2 - 1) / (2 * (a2 - u)))
    F = s.Line(B, D).intersection(s.Line(C, E))[0]
    O = s.Point(0, (a2 - 1) / (2 * v))
    assert s.simplify(F.x - u * (a2 + 1) / (2 * a2)) == 0
    # F.x = u(a2+1)/(2a2), so u != 0 keeps F distinct from O.
    circle = s.Circle(B, C, O)
    assert s.simplify((F.x-circle.center.x)**2 + (F.y-circle.center.y)**2 - circle.radius**2) == 0


def da04_exact():
    A, B = s.Point(-s.Rational(3, 5), s.Rational(4, 5)), s.Point(s.Rational(3, 5), s.Rational(4, 5))
    P, Q, T = s.Point(0, s.Rational(4, 5)), s.Point(0, 0), s.Point(0, s.Rational(5, 4))
    omega_a = s.Circle(A / 2, s.Rational(1, 2))
    omega_b = s.Circle(B / 2, s.Rational(1, 2))
    for point in (A, P, Q):
        assert s.simplify(point.distance(omega_a.center)**2 - omega_a.radius**2) == 0
    for point in (B, P, Q):
        assert s.simplify(point.distance(omega_b.center)**2 - omega_b.radius**2) == 0
    assert s.simplify(T.distance(P) * T.distance(Q) - T.distance(A)**2) == 0
    assert s.simplify(T.distance(A)**2 - T.distance(B)**2) == 0


if __name__ == "__main__":
    da15_symbolic()
    da04_exact()
    print("thinking-material claim checks passed")
