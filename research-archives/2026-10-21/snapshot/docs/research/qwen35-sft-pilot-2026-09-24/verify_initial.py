"""Verifier-side checks for initial model claims; never provided to the model."""
from sympy import Point, Rational, simplify, sqrt, symbols


def eq(a, b):
    assert simplify(a - b) == 0, (a, b)


def neq(a, b):
    assert simplify(a - b) != 0, (a, b)


def sqdist(a, b):
    return (a.x - b.x) ** 2 + (a.y - b.y) ** 2


# DA05: one exact acute scalene instance. B,C,A,D,M,E follow its prompt.
A = Point(Rational(1, 2), 2)
B = Point(0, 0)
C = Point(4, 0)
D = Point(Rational(100, 97), Rational(128, 97))
M = Point(2, 0)
E = Point(Rational(36, 65), Rational(128, 65))
eq((E.x - A.x) * (C.y - A.y), (E.y - A.y) * (C.x - A.x))
eq(D.y * (A.x**2 + A.y**2), A.y * (D.x**2 + D.y**2))
eq(sqdist(D, M) * sqdist(E, M), sqdist(B, M) ** 2)
eq(sqrt(sqdist(A, E)) / sqrt(sqdist(E, C)), Rational(1, 64))
neq(Rational(1, 64), 7)  # DA05-0: AE/EC=tan B/tan C.
neq(Rational(1, 64), sqrt(sqdist(B, C)) / sqrt(sqdist(A, B)))  # DA05-1.
neq((A.x - D.x) * (E.x - D.x) + (A.y - D.y) * (E.y - D.y), 0)  # DA05-2.

# DA05-3: show its final statement is generally true, despite missing proof.
c, u, v = symbols("c u v", positive=True)
den = 4*c*c - 4*c*u + u*u + v*v
ex = 2*c*(-2*c*u + u*u + v*v)/den
ey = 4*c*c*v/den
k = (u*u + v*v + 2*c*u)/(2*c*v)
dy = (u*u + v*v)/(v*(k*k+1))
dx = k*dy
eq(dx*dx + dy*dy, (u*u + v*v)*dy/v)  # D is on omega1.
eq(dx*dx + dy*dy, 2*c*dx - 2*c*u*dy/v)  # D is on omega2.
eq((ex-u)*(-v) - (ey-v)*(2*c-u), 0)  # E is on AC.
eq((ex-c)*dy - ey*(dx-c), 0)  # M,D,E are collinear.
eq(ex*ex + ey*ey, (u*u + v*v)*ey/v)  # E lies on circle through A,B,D.
eq(((dx-c)**2+dy**2)*((ex-c)**2+ey**2), c**4)
# Since M,D,E are collinear and MB is tangent to circle ABD,
# the preceding circle-membership identity yields MD*ME=c^2 for order M-D-E.

# DA15: exact acute scalene instance for false final claims.
A = Point(Rational(1, 2), 3)
B = Point(-2, 0)
C = Point(2, 0)
M = Point(0, 0)
F = Point(Rational(53, 148), Rational(63, 74))
O = Point(0, Rational(7, 8))
H = Point(Rational(1, 2), Rational(5, 4))
neq(sqdist(F, B) * sqdist(A, C), sqdist(F, C) * sqdist(A, B))  # DA15-0.
neq(F.x, H.x)  # DA15-3.
# AF perpendicular OF is the verifier's true target, not supplied as feedback.
eq((F.x-A.x)*(F.x-O.x)+(F.y-A.y)*(F.y-O.y), 0)

# DA15 general coordinates: B=(-b,0), C=(b,0), A=(u,v).
b, u, v = symbols("b u v", positive=True)
s = u*u + v*v
td = (s-b*b)/(2*(s+b*u))
te = (s-b*b)/(2*(s-b*u))
ddx, ddy = td*u, td*v
eex, eey = te*u, te*v
eq((ddx-u)**2+(ddy-v)**2, (ddx+b)**2+ddy**2)
eq((eex-u)**2+(eey-v)**2, (eex-b)**2+eey**2)
fx = u*(b*b+s)/(2*s)
fy = v*(s-b*b)/(2*s)
eq((fx+b)*ddy - fy*(ddx+b), 0)  # F is on BD.
eq((fx-b)*eey - fy*(eex-b), 0)  # F is on CE.
ox = 0
oy = (s-b*b)/(2*v)
eq((fx-u)*(fx-ox)+(fy-v)*(fy-oy), 0)

# H01: a self-revision introduced an incorrect factor 1/4.
ha = Point(Rational(1, 2), 3)
hh = Point(Rational(1, 2), Rational(5, 4))
median = sqrt(ha.x**2 + ha.y**2)
hp = abs(ha.x*hh.y-ha.y*hh.x)/median
eq(hp, 7*sqrt(37)/148)
neq(hp, 7*sqrt(37)/296)

# H01-fresh-1's final self-contained subanswer: MP*AM = BC^2/4.
a, x, y = symbols("a x y", positive=True)
h_y = (a*a/4-x*x)/y
eq(x*x + y*h_y, a*a/4)

print("self-material claim checks passed")
