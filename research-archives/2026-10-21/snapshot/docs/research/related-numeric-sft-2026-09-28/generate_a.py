#!/usr/bin/env python3
"""Constructive numeric variants for PN01--PN05 (original DA01--DA04, DA06).

Only elementary circle/line intersections determine labels. General answer
relations are used below solely as independent audit checks.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "benchmarks/humpty_configurations_v2/authoring"))
from geo_primitives import cc, circle, cross, dot, inside_triangle, lc, line, other, tangent_circle  # noqa: E402


def num(x: float) -> str:
    return format(x, ".17g")


def rel(x: float, y: float) -> float:
    return abs(x-y) / max(1.0, abs(x), abs(y))


def check(x: float, y: float, name: str, audits: dict, tol: float = 2e-9) -> None:
    e = rel(x, y)
    audits[name] = e
    if not math.isfinite(e) or e > tol:
        raise ValueError(f"{name}: {x} != {y}; relative error {e}")


def acute_scalene(A: complex, B: complex, C: complex) -> None:
    ss = sorted((abs(A-B), abs(B-C), abs(C-A)))
    if min(ss[1]-ss[0], ss[2]-ss[1]) < .015 * ss[2]:
        raise ValueError("almost isosceles")
    if min(dot(B-A, C-A), dot(A-B, C-B), dot(A-C, B-C)) < .015 * ss[2]**2:
        raise ValueError("not safely acute")


def angle(a: complex, v: complex, b: complex) -> float:
    u, w = a-v, b-v
    return math.degrees(math.acos(max(-1., min(1., dot(u, w)/abs(u)/abs(w)))))


def base(A: complex, B: complex, C: complex) -> list[float]:
    a, b, c = abs(B-C), abs(C-A), abs(A-B)
    return [b/a, c/a]


def record(pack_id: str, source_id: str, question: str, target: float,
           points: dict[str, complex], givens: dict[str, float],
           signature: list[float], query: str, audits: dict) -> dict:
    if target <= 1e-6 or not math.isfinite(target):
        raise ValueError("invalid target")
    if not all(math.isfinite(x) and x > 0 for x in givens.values()):
        raise ValueError("invalid givens")
    return {
        "source_id": source_id, "pack_id": pack_id,
        "problem_en": question, "target": num(target),
        "points": {k: [z.real, z.imag] for k, z in points.items()},
        "givens": givens, "shape_signature": signature,
        "query": query, "audit_checks": audits,
    }


def pn01(rng: random.Random) -> dict:
    a = rng.uniform(7, 19)
    x = rng.uniform(.26, .74)*a
    y = rng.uniform(.72, 1.35)*a
    A, B, C = complex(x, y), 0j, complex(a)
    acute_scalene(A, B, C)
    w1 = tangent_circle(A, C, B)
    w2 = tangent_circle(A, B, C)
    T = other(cc(w1, w2), A)
    audits = {}
    for i, w in enumerate((w1, w2), 1):
        check(abs(A-w[0]), w[1], f"omega{i}_A", audits)
        check(abs(T-w[0]), w[1], f"omega{i}_T", audits)
    check(dot(w1[0]-A, C-A), 0, "omega1_tangent", audits)
    check(dot(w2[0]-A, B-A), 0, "omega2_tangent", audits)
    c, b = abs(A-B), abs(A-C)
    check(abs(A-T), b*c/math.sqrt(2*(b*b+c*c)-a*a), "independent_identity", audits)
    givens = {"AB": c, "BC": a, "CA": b}
    prompt = (f"Triangle ABC has AB={num(c)}, BC={num(a)}, and CA={num(b)}. "
              "The circle through B tangent to line AC at A and the circle through C "
              "tangent to line AB at A meet again at T. Find the length AT. "
              "The stated circles are nondegenerate and the intersections are distinct and finite.")
    return record("PN01", "DA01", prompt, abs(A-T), dict(A=A,B=B,C=C,T=T),
                  givens, base(A,B,C), "AT", audits)


def fermat(A: complex, B: complex, C: complex) -> complex:
    T = (A+B+C)/3
    for _ in range(50000):
        weights = [1/abs(T-z) for z in (A,B,C)]
        nxt = sum(w*z for w,z in zip(weights,(A,B,C))) / sum(weights)
        if abs(nxt-T) < 2e-14*max(1,abs(B),abs(C)):
            return nxt
        T = nxt
    raise ValueError("Fermat iteration did not converge")


def pn02(rng: random.Random) -> dict:
    c = rng.uniform(6, 19)
    ratio = rng.choice((-1,1))*rng.uniform(.13, .55)
    b = c*(1+ratio)
    A, B, C = 0j, complex(c), b*complex(.5, math.sqrt(3)/2)
    T = fermat(A,B,C)
    G = (A+B+C)/3
    if not inside_triangle(T,A,B,C):
        raise ValueError("Fermat point outside triangle")
    if abs(T-G) < .01*max(b,c):
        raise ValueError("T nearly G")
    w = circle(B,T,C)
    K = other(lc(T,G,w), T)
    if dot(G-T,K-G) <= 0:
        raise ValueError("G not between T and K")
    audits = {}
    for u,v,n in ((A,B,"ATB"),(B,C,"BTC"),(C,A,"CTA")):
        check(angle(u,T,v),120,f"angle_{n}",audits,1e-10)
    check(angle(B,A,C),60,"angle_BAC",audits)
    for z,n in ((B,"B"),(C,"C"),(T,"T"),(K,"K")):
        check(abs(z-w[0]),w[1],f"circle_BTC_{n}",audits)
    check(cross(G-T,K-T),0,"TGK_collinear",audits)
    check(abs(T-K),abs(b-c),"independent_identity",audits)
    givens = {"angle_BAC_deg": 60.0, "AB": c, "AC": b}
    prompt = (f"In triangle ABC, angle BAC is 60 degrees, AB={num(c)}, and "
              f"AC={num(b)}. An interior point T satisfies angle ATB = angle BTC "
              "= angle CTA = 120 degrees. Let G be the centroid of ABC. Line TG "
              "meets circle BTC again at K. Find the length TK. The stated circle "
              "is nondegenerate and the intersections are distinct and finite.")
    return record("PN02","DA02",prompt,abs(T-K),
                  dict(A=A,B=B,C=C,T=T,G=G,K=K),givens,base(A,B,C),"TK",audits)


def pn03(rng: random.Random) -> dict:
    a = rng.uniform(8, 18)
    x = rng.uniform(.20, .42)*a
    y = rng.uniform(.75, 1.32)*a
    A, B, C = complex(x,y), 0j, complex(a)
    acute_scalene(A,B,C)
    O,R = circle(A,B,C)
    w1 = tangent_circle(A,B,C)
    w2 = circle(B,O,C)
    T = other(cc(w1,w2),C)
    K = line(T,O,B,C)
    if not K.real < B.real-.25*a or abs(B-K)>6*a or abs(K.imag)>1e-8*a:
        raise ValueError("wrong K-B-C branch")
    audits = {}
    for z,n in ((A,"A"),(C,"C"),(T,"T")):
        check(abs(z-w1[0]),w1[1],f"tangent_circle_{n}",audits)
    for z,n in ((B,"B"),(O,"O"),(C,"C"),(T,"T")):
        check(abs(z-w2[0]),w2[1],f"circle_BOC_{n}",audits)
    check(dot(w1[0]-A,B-A),0,"A_tangency",audits)
    check(cross(T-O,K-O),0,"TOK_collinear",audits)
    check(abs(A-K),math.sqrt(abs(B-K)*abs(C-K)),"independent_identity",audits)
    givens = {"BC": a, "BK": abs(B-K)}
    prompt = ("Let O be the circumcenter of an acute scalene triangle ABC. The "
              "circle through A and C tangent to line AB at A meets circle BOC "
              "again at T, other than C. Let K be the intersection of lines TO "
              f"and BC, with K, B, C in that order. If BC={num(a)} and "
              f"BK={num(abs(B-K))}, find the length AK. The stated circles are "
              "nondegenerate and the intersections are distinct and finite.")
    return record("PN03","DA03",prompt,abs(A-K),
                  dict(A=A,B=B,C=C,O=O,T=T,K=K),givens,base(A,B,C),"AK",audits)


def pn04(rng: random.Random) -> dict:
    p = rng.uniform(2, 10)
    q = rng.uniform(2, 11)
    if abs(p-q) < .08*(p+q):
        raise ValueError("near-symmetric chord division")
    L = p+q
    h = rng.uniform(.34, 1.55)*L
    A, B, P = 0j, complex(L), complex(p)
    O = complex(L/2,h)
    R = abs(O-A)
    O1 = A+(p/L)*(O-A)
    O2 = B+(q/L)*(O-B)
    w1,w2 = (O1,abs(O1-A)),(O2,abs(O2-B))
    Q = other(cc(w1,w2),P)
    X,Y = lc(P,Q,(O,R))
    audits = {}
    for w,z,n in ((w1,A,"omega1_A"),(w1,P,"omega1_P"),
                  (w1,Q,"omega1_Q"),(w2,B,"omega2_B"),
                  (w2,P,"omega2_P"),(w2,Q,"omega2_Q")):
        check(abs(z-w[0]),w[1],n,audits)
    check(abs(O-O1)+w1[1],R,"omega1_internal_tangency",audits)
    check(abs(O-O2)+w2[1],R,"omega2_internal_tangency",audits)
    for z,n in ((A,"A"),(B,"B"),(X,"X"),(Y,"Y")):
        check(abs(z-O),R,f"outer_circle_{n}",audits)
    check(cross(Q-P,X-P),0,"PQX_collinear",audits)
    check(cross(Q-P,Y-P),0,"PQY_collinear",audits)
    check(abs(P-Q),math.sqrt((abs(X-Y)/2)**2-p*q),"independent_identity",audits)
    givens = {"AP":p,"PB":q,"XY":abs(X-Y)}
    prompt = ("Point P lies inside chord AB of circle Omega, with "
              f"AP={num(p)} and PB={num(q)}. A circle through A and P "
              "internally tangent to Omega at A and a circle through B and P "
              "internally tangent to Omega at B meet again at Q, other than P. "
              f"Line PQ cuts Omega at X and Y. If XY={num(abs(X-Y))}, find the "
              "length PQ. The stated circles are nondegenerate and the "
              "intersections are distinct and finite.")
    return record("PN04","DA04",prompt,abs(P-Q),
                  dict(A=A,B=B,P=P,O=O,O1=O1,O2=O2,Q=Q,X=X,Y=Y),
                  givens,[p/L,q/L,h/L,abs(X-Y)/L],"PQ",audits)


def pn05(rng: random.Random) -> dict:
    a = rng.uniform(8, 18)
    x = rng.uniform(.58,.80)*a
    y = rng.uniform(.75,1.32)*a
    A,B,C = complex(x,y),0j,complex(a)
    acute_scalene(A,B,C)
    if abs(A-B) <= abs(A-C):
        raise ValueError("AB <= AC")
    O,R = circle(A,B,C)
    M = (B+C)/2
    w1,w2 = tangent_circle(A,C,B),tangent_circle(A,B,C)
    D = other(cc(w1,w2),A)
    E = other(lc(A,M,w2),A)
    audits = {}
    for w,z,n in ((w1,A,"omega1_A"),(w1,B,"omega1_B"),
                  (w1,D,"omega1_D"),(w2,A,"omega2_A"),
                  (w2,C,"omega2_C"),(w2,D,"omega2_D"),
                  (w2,E,"omega2_E")):
        check(abs(z-w[0]),w[1],n,audits)
    check(dot(w1[0]-A,C-A),0,"omega1_tangency",audits)
    check(dot(w2[0]-A,B-A),0,"omega2_tangency",audits)
    check(cross(M-A,E-A),0,"AME_collinear",audits)
    check(abs(O-E),math.sqrt(R*R-abs(A-D)**2),"independent_identity",audits)
    givens = {"AO":R,"AD":abs(A-D)}
    prompt = ("Let O be the circumcenter and M the midpoint of BC in an acute "
              "scalene triangle ABC with AB>AC. Circle omega1 passes through A "
              "and B and is tangent to line AC at A; circle omega2 passes through "
              "A and C and is tangent to line AB at A. Let D be their intersection "
              "other than A, and E the intersection of line AM with omega2 other "
              f"than A. If AO={num(R)} and AD={num(abs(A-D))}, find the length "
              "OE. The stated circles are nondegenerate and the intersections "
              "are distinct and finite.")
    return record("PN05","DA06",prompt,abs(O-E),
                  dict(A=A,B=B,C=C,O=O,M=M,D=D,E=E),
                  givens,base(A,B,C),"OE",audits)


BUILDERS = (pn01,pn02,pn03,pn04,pn05)


def generate(seed: int = 20260928, per_type: int = 12) -> list[dict]:
    if per_type < 1:
        raise ValueError("per_type must be positive")
    rng = random.Random(seed)
    out = []
    for builder in BUILDERS:
        seen = set()
        n_try = 0
        while len(seen) < per_type:
            n_try += 1
            if n_try > per_type*100:
                raise RuntimeError(f"insufficient valid {builder.__name__} variants")
            try:
                item = builder(rng)
            except (ValueError, AssertionError, ZeroDivisionError):
                continue
            sig = tuple(round(v,4) for v in item["shape_signature"])
            if sig in seen:
                continue
            seen.add(sig)
            item["variant_index"] = len(seen)
            out.append(item)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed",type=int,default=20260928)
    ap.add_argument("--per-type",type=int,default=12)
    ap.add_argument("--output",type=Path)
    args = ap.parse_args()
    records = generate(args.seed,args.per_type)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in records))
    print(json.dumps({"count":len(records),"by_type":{b.__name__:sum(r["pack_id"]=="PN"+b.__name__[-2:] for r in records) for b in BUILDERS},"max_audit_relative_error":max(max(r["audit_checks"].values()) for r in records)},ensure_ascii=False))


if __name__ == "__main__":
    main()
