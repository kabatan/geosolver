"""Independent 70-digit substitution only. No solver, optimizer, root finder or PSLQ.

Coordinates are explicit analytic witnesses, kept out of the authored DSL.
This evaluator implements elementary Euclidean definitions independently of GeoSolver.
"""
from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import mpmath as mp

HERE = Path(__file__).resolve().parent
mp.mp.dps = 70
TOL = mp.mpf('1e-50')


@dataclass
class Point:
    x: object
    y: object

    def __add__(self, q): return Point(self.x + q.x, self.y + q.y)
    def __sub__(self, q): return Point(self.x - q.x, self.y - q.y)
    def __mul__(self, k): return Point(self.x * k, self.y * k)
    def __truediv__(self, k): return self * (1 / k)


@dataclass
class Line:
    a: Point
    b: Point


@dataclass
class Circle:
    center: Point
    radius: object


def dot(p, q): return p.x * q.x + p.y * q.y
def cross(p, q): return p.x * q.y - p.y * q.x
def norm(p): return mp.sqrt(dot(p, p))
def Distance(p, q):
    if isinstance(q, Line):
        return abs(cross(q.b - q.a, p - q.a)) / norm(q.b - q.a)
    return norm(p - q)


def Area(*pts):
    return abs(sum(cross(a, b) for a, b in zip(pts, pts[1:] + pts[:1]))) / 2


def Angle(a, b, c):
    u, v = a - b, c - b
    return mp.acos(max(-1, min(1, dot(u, v) / (norm(u) * norm(v)))))


def FootOfPerpendicular(line, p):
    d = line.b - line.a
    return line.a + d * (dot(p - line.a, d) / dot(d, d))


def IntersectLines(l, m):
    d, e = l.b - l.a, m.b - m.a
    return l.a + d * (cross(m.a - l.a, e) / cross(d, e))


def Circumcircle(a, b, c):
    u, v = b - a, c - a
    den = 2 * cross(u, v)
    offset = Point((dot(u, u) * v.y - dot(v, v) * u.y) / den,
                   (u.x * dot(v, v) - v.x * dot(u, u)) / den)
    return Circle(a + offset, norm(offset))


def Incircle(a, b, c):
    x, y, z = Distance(b, c), Distance(c, a), Distance(a, b)
    center = (a * x + b * y + c * z) / (x + y + z)
    return Circle(center, 2 * Area(a, b, c) / (x + y + z))


def Rotate(p, angle, origin):
    d = p - origin
    return origin + Point(d.x * mp.cos(angle) - d.y * mp.sin(angle),
                          d.x * mp.sin(angle) + d.y * mp.cos(angle))


def convex_margins(pts):
    orientation = mp.sign(sum(cross(a, b) for a, b in zip(pts, pts[1:] + pts[:1])))
    return [orientation * cross(b - a, p - a)
            for i, (a, b) in enumerate(zip(pts, pts[1:] + pts[:1]))
            for j, p in enumerate(pts) if j not in (i, (i + 1) % len(pts))]


def ConvexPolygon(pts): return min(convex_margins(pts)) > TOL


ENV = dict(Point=Point, Line=Line, Circle=Circle, Distance=Distance, Area=Area,
    Angle=Angle, FootOfPerpendicular=FootOfPerpendicular, IntersectLines=IntersectLines,
    Circumcircle=Circumcircle, Incircle=Incircle, Rotate=Rotate,
    Midpoint=lambda a, b: (a + b) / 2,
    PointOnSegment=lambda a, b, t: a * (1 - t) + b * t,
    Reflect=lambda p, l: FootOfPerpendicular(l, p) * 2 - p,
    PerpendicularLine=lambda l, p: Line(p, p + Point(-(l.b-l.a).y, (l.b-l.a).x)),
    Parallel=lambda l, m: cross(l.b-l.a, m.b-m.a),
    Center=lambda c: c.center, Radius=lambda c: c.radius,
    ConvexPolygon=ConvexPolygon, pi=mp.pi, cos=mp.cos, sin=mp.sin, sqrt=mp.sqrt,
    min=min, max=max, abs=abs, mpf=mp.mpf)


class ExactLiterals(ast.NodeTransformer):
    def visit_Constant(self, node):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return ast.copy_location(ast.Call(func=ast.Name(id='mpf', ctx=ast.Load()),
                args=[ast.Constant(str(node.value))], keywords=[]), node)
        return node


def ev(expression, env):
    if not isinstance(expression, str): return mp.mpf(expression)
    tree = ExactLiterals().visit(ast.parse(expression, mode='eval'))
    return eval(compile(ast.fix_missing_locations(tree), '<substitution>', 'eval'),
                {'__builtins__': {}}, env)


def witnesses():
    q = mp.mpf
    w = {}
    def add(year, section, n, values, derivation):
        w.setdefault(f'HMMT-{year}-FEB-{section}-{n:02}', []).append((values, derivation))
    for vertices in [((2, 8), (1, 13), (5, 10)), ((1, 9), (2, 13), (5, 8))]:
        add(2010, 'GUTS', 13, {n+axis: q(value) for n,p in zip('abc',vertices)
            for axis,value in zip('xy',p)}, 'Alternating vertices of the six projection support lines; both allowable triangles.')
    for b, x in [('2', '1'), ('3', '-1')]:
        add(2011, 'GUTS', 1, dict(b=q(b), x=q(x), y=2/q(b), u=q(1)/3, v=q(1)/3),
            'Choose a base and apex horizontal coordinate; height 2/base gives area 1. D,E are one third along the sides from A.')
    add(2012, 'GUTS', 6, dict(ex=q(6), ey=q(6)), 'The two perpendicular distances in the positive interior give E=(6,6).')
    add(2013, 'GUTS', 1, dict(k=mp.sqrt(q(31)**2-q(4)**2)/4), 'Distance between markers separated by four x units: 4*sqrt(1+k^2)=31; positive k.')
    add(2014, 'GUTS', 3, {}, 'Unit regular hexagon; no unknown coordinates. Evaluate definitions only.')
    # Official solution's secant-length calculation, used ONLY to supply this witness.
    ea, eb = q(128)/21, q(152)/21
    ex = (ea**2-eb**2+100)/20
    e = Point(ex, -mp.sqrt(ea**2-ex**2)); a=Point(q(0),q(0)); b=Point(q(10),q(0))
    d = a + (a-e)*(12/ea); c=b+(b-e)*(8/eb)
    center=(e*(-10)+a*eb+b*ea)/(ea+eb-10)
    add(2015, 'GUTS', 24, dict(cx=c.x, cy=c.y, dx=d.x, dy=d.y, wx=center.x, wy=center.y, r=center.y),
        'Let E=AD intersect BC. Similar triangles give EA=128/21, EB=152/21. Construct E below AB, extend EA by 12 and EB by 8; use the E-excenter of EAB. All three contact feet must independently lie on the segments.')
    cx=(q(15)**2+q(13)**2-q(14)**2)/26
    add(2016, 'GUTS', 14, dict(cx=cx,cy=mp.sqrt(q(15)**2-cx**2)), 'Three-side coordinate construction of ABC; then independently construct altitude feet, circumcircle, tangents and their intersections.')
    xy,xz,yz=q(11)/3,q(9)/2,q(14)/3
    zx=(xy**2+xz**2-yz**2)/(2*xy)
    add(2017, 'GUTS', 2, dict(t=xy,zx=zx,zy=mp.sqrt(xz**2-zx**2)),
        'Power of a point gives 3(z+10)=2(y+16), 4(x+12)=10(z+3), 12(x+4)=16(y+2), hence XY=11/3,XZ=9/2,YZ=14/3. Use three-side coordinates, then check all six circle points and their order.')
    add(2018, 'GUTS', 1, dict(s=q(2)), 'Four unit squares in a 2-by-2 grid, as drawn in the official problem.')
    h=1/mp.sqrt(3)
    add(2019, 'GUTS', 17, dict(ax=q(0),ay=q(3),px=q(1),py=q(1),s=2*h,
        t1=(1-h)/4,t2=(1+h)/4,u1=q(3)/5-h/5,u2=q(3)/5+h/5,v1=(2-h)/3,v2=(2+h)/3),
        'The 3-4-5 right triangle has incenter (1,1) and inradius 1. From each foot on a side move +/-1/sqrt(3) along that side. All nine equal lengths and convex cyclic order are checked, not assumed in the DSL.')
    add(2020, 'GUTS', 13, dict(ax=q(0),ay=4*mp.sqrt(3),u=q(4)/5,v=q(12)/13,tx=q(16)/65,ty=q(16)/65),
        'Right triangle at C. Intersect AB with rays at 60 and 30 degrees to obtain D,E. Circle through 0,D,E has center (8/65,32*sqrt(3)/65), so its other intercepts give tx=ty=16/65.')
    length=mp.sqrt(73)-3
    cx=(q(6)**2+length**2-q(8)**2)/(2*length)
    add(2021, 'GUTS', 14, dict(b=length,cx=cx,cy=mp.sqrt(36-cx**2)),
        'Official similar triangles give AB*(AB+6)=64; take positive root sqrt(73)-3. Three-side coordinates verify the original angle equality independently.')
    add(2022, 'GUTS', 11, {}, 'Unit regular dodecagon; evaluate its two intersections and sector-minus-triangle area without unknowns.')
    for cx,cy in [(q(2),q(-2)), (q(1),-mp.sqrt(3))]:
        add(2023, 'GUTS', 3, dict(d=q(4),a=mp.sqrt(5),cx=cx,cy=cy),
            'BD is the diameter of the circle centered at M with radius CM=2; A=(0,sqrt(5)). Choose two C positions on the lower semicircle, then verify right angles, distances and convexity.')
    add(2024, 'GUTS', 4, {}, 'Unit regular pentagon and two exterior 60-degree rotations; evaluate the requested angle directly.')
    add(2025, 'GUTS', 6, dict(ax=q(5)/2,ay=5*mp.sqrt(3)/2,t=q(2)/5,u=q(8)/5),
        'Equilateral triangle over BC=5. Midpoint equations give t+u=2 and t-u=-6/5, hence t=2/5,u=8/5; F is beyond B on the allowed ray.')
    # The earlier illustrative f=.8,h=.3 was concave and is retained in
    # revisions/substitution-first-pass.json as a rejected witness, not a DSL edit.
    for f,h in [(q('0.7'),q('0.25'))]:
        theta=mp.pi/18
        fc=mp.mpc(f*mp.cos(theta),-f*mp.sin(theta))
        vector=h*mp.exp(mp.j*155*mp.pi/180)
        pc=fc+vector; dc=1+vector; cc=pc/fc
        add(2010,'TEAM1',7,dict(fx=fc.real,fy=fc.imag,dx=dc.real,dy=dc.imag,cx=cc.real,cy=cc.imag),
            f'Choose AF={f}, FP={h}, arg(AF)=-10deg and arg(FP)=155deg, set D=Q+FP. The official spiral-similarity construction gives complex C=P/F with A=0,Q=1. Verify all four original angles, convexity and strict interior of P; the derived similarity is not in the DSL.')
    return w


def serial(v):
    if isinstance(v, Point): return dict(x=serial(v.x),y=serial(v.y))
    if isinstance(v, Line): return dict(a=serial(v.a),b=serial(v.b))
    if isinstance(v, Circle): return dict(center=serial(v.center),radius=serial(v.radius))
    if isinstance(v, bool): return v
    return mp.nstr(v, 65)


def main():
    assert not (HERE/'prediction.lock.json').exists(), 'Prediction already locked'
    rows=[json.loads(x) for x in (HERE/'cases.jsonl').read_text().splitlines()]
    ws=witnesses(); records=[]
    for row in rows:
        dsl=row['dsl']; attempts=[]
        for values,derivation in ws[row['id']]:
            assert set(values)==set(dsl['variables'])
            env=ENV | values; constructions={}
            for c in dsl['constructions']:
                env[c['name']]=ev(c['expression'],env); constructions[c['name']]=serial(env[c['name']])
            checks=[]
            for i,c in enumerate(dsl['conditions']):
                if 'predicate' in c:
                    ok=bool(ev(c['predicate'],env))
                    checks.append(dict(index=i,predicate=c['predicate'],passed=ok))
                else:
                    lhs,rhs=ev(c['left'],env),ev(c['right'],env);op=c['operator']
                    delta=lhs-rhs;scale=max(1,abs(lhs),abs(rhs))
                    ok={'=':abs(delta)<=TOL*scale,'>':delta>TOL,'<':delta<-TOL,
                        '>=':delta>=-TOL,'<=':delta<=TOL,'!=':abs(delta)>TOL}[op]
                    checks.append(dict(index=i,left=serial(lhs),right=serial(rhs),operator=op,
                        residual=serial(delta),scaled_residual=serial(abs(delta)/scale),passed=bool(ok)))
            target=ev(dsl['target'],env);reference=ev(row['answer'][0],ENV)
            target_ok=abs(target-reference)<=TOL*max(1,abs(reference))
            attempts.append(dict(derivation=derivation,variables={k:serial(v) for k,v in values.items()},
                constructions=constructions,checks=checks,target=serial(target),reference=serial(reference),
                target_error=serial(abs(target-reference)),target_passed=bool(target_ok),
                passed=bool(target_ok and all(c['passed'] for c in checks))))
        records.append(dict(id=row['id'],dsl_sha256=hashlib.sha256((HERE/row['dsl_path']).read_bytes()).hexdigest(),
            witnesses=attempts,passed=all(a['passed'] for a in attempts)))
    report=dict(method='Independent explicit analytic coordinate substitution; no search, solve, optimization, root finding, precision refinement or PSLQ',
        precision_decimal_digits=70,tolerance=str(TOL),solver_executed=False,
        all_passed=all(r['passed'] for r in records),records=records)
    (HERE/'audit/substitution.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    for r in records:
        print(r['id'], 'PASS' if r['passed'] else 'FAIL',
              'targets', [a['target'][:25] for a in r['witnesses']],
              'bad_conditions', [[c['index'] for c in a['checks'] if not c['passed']] for a in r['witnesses']])
    assert report['all_passed']


if __name__=='__main__':main()
