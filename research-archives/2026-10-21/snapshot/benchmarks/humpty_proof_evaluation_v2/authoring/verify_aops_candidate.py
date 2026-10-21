#!/usr/bin/env python3
"""Read-only construction and exact-identity audit for AP01 (USAMO 2008/2).

Run with the repository .venv/bin/python (SymPy). Numerical checks alone need
only the standard library: python3 verify_aops_candidate.py --numerical-only.
All configurations are constructed from their original definitions; the JSON
contains the complete synthetic proof, separately from these algebraic checks.
"""
import argparse
import math
import runpy
from pathlib import Path

BENCHMARKS = Path(__file__).resolve().parents[2]
geo = runpy.run_path(str(BENCHMARKS / "humpty_configurations_v2/authoring/geo_primitives.py"))
line, circle, lc, other, inside, dot, cross, near = (
    geo[name] for name in ("line", "circle", "lc", "other", "inside_triangle", "dot", "cross", "near")
)


def symbolic():
    import sympy as sp
    u, v = sp.symbols("u v", real=True)
    a, b, c = sp.Matrix([u,v]), sp.Matrix([-1,0]), sp.Matrix([1,0])
    m = sp.zeros(2,1)
    p, n = (a+b)/2, (a+c)/2
    norm = lambda z: z.dot(z)
    det = lambda z,w: z[0]*w[1]-z[1]*w[0]
    rot = lambda z: sp.Matrix([-z[1],z[0]])
    simp = lambda z: z.applyfunc(sp.factor) if isinstance(z,sp.MatrixBase) else sp.factor(z)
    def meet(a,b,c,d):
        return simp(a+(b-a)*det(c-a,d-c)/det(b-a,d-c))

    # Original construction: perpendicular bisectors and median, then BD ∩ CE.
    d = meet(a,m,p,p+rot(b-a))
    e = meet(a,m,n,n+rot(c-a))
    f = meet(b,d,c,e)
    o = sp.Matrix([0,(norm(a)-1)/(2*v)])
    # Independent auxiliary: B,C circumcircle tangents, then their cevian.
    tangent_cross = meet(b,b+rot(b-o),c,c+rot(c-o))
    direction = tangent_cross-a
    ll = simp(a-2*direction*(a-o).dot(direction)/norm(direction))
    g = simp((a+ll)/2)
    tt = (p+n)/2
    checks = {
        "D equidistant from A,B": norm(d-a)-norm(d-b),
        "E equidistant from A,C": norm(e-a)-norm(e-c),
        "L on circumcircle": norm(ll-o)-norm(a-o),
        "isogonal AG and AM": det(b-a,g-a)*(m-a).dot(c-a)-det(m-a,c-a)*(b-a).dot(g-a),
        "G on BD": det(g-b,d-b),
        "G on CE": det(g-c,e-c),
        "G equals F x": (g-f)[0],
        "G equals F y": (g-f)[1],
        "AG AN similarity ratio": norm(g-a)*norm(m-a)-norm(n-a)*norm(b-a),
        "T on AM": det(tt-a,m-a),
        "AP AT similarity ratio": norm(p-a)*norm(m-a)-norm(tt-a)*norm(b-a),
        "F on circle APN": norm(f-(a+o)/2)-norm(a-o)/4,
        "AF perpendicular OF": (f-a).dot(f-o),
    }
    for name,expr in checks.items():
        assert simp(expr)==0, (name,simp(expr))
    # Strict inequalities are checked numerically below and are explained in the
    # proof. General identity denominators use v≠0, u≠0, s=u²+v²>1 and
    # s±u>0, which follow from the acute, scalene geometric domain here.
    print(f"AP01 symbolic: {len(checks)} general rational identities PASS")


def numeric():
    count = 0
    def angle(z,w):
        return math.acos(max(-1,min(1,dot(z,w)/abs(z)/abs(w))))
    for a in (.5+2j, -.4+1.5j, .2+1.2j, .8+1.8j, .6+2.5j):
        b,c,m = -1+0j,1+0j,0j
        p,n = (a+b)/2,(a+c)/2
        sides = [abs(a-b),abs(b-c),abs(c-a)]
        assert min(abs(sides[i]-sides[j]) for i in range(3) for j in range(i)) > 1e-6
        for vertex,x,y in ((a,b,c),(b,c,a),(c,a,b)):
            assert dot(x-vertex,y-vertex)>0
        d = line(a,m,p,p+(b-a)*1j)
        e = line(a,m,n,n+(c-a)*1j)
        f = line(b,d,c,e)
        for point in (d,e):
            near(cross(point-a,m-a))
            assert dot(point-a,m-a)>0
        assert inside(f,a,b,c)
        o,r = circle(a,b,c)
        tangent_cross = line(b,b+(b-o)*1j,c,c+(c-o)*1j)
        ll = other(lc(a,tangent_cross,(o,r)),a)
        g = (a+ll)/2
        near(g,f)
        near(angle(g-b,a-b),angle(b-a,m-a))
        near(angle(g-c,a-c),angle(c-a,m-a))
        center,radius = circle(a,p,n)
        near(abs(f-center),radius)
        if count==0:
            print("AP01 witness:", {k:[z.real,z.imag] for k,z in dict(A=a,B=b,C=c,D=d,E=e,F=f,L=ll,G=g).items()})
        count += 1
    print(f"AP01 numeric: {count} original-construction witnesses with domain checks PASS")


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--numerical-only", action="store_true")
    args=parser.parse_args()
    if not args.numerical_only:
        symbolic()
    numeric()
