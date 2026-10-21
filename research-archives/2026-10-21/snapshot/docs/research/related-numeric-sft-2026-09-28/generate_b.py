#!/usr/bin/env python3
"""CPU numerical witnesses for PN06--PN10, sampled from the original constructions.

The target is measured from constructed points. Published solution identities are
checked afterwards and never serve as the label oracle. No GPU or shared data edits.
"""

from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

GEO = Path(__file__).resolve().parents[3] / "benchmarks/humpty_configurations_v2/authoring"
sys.path.insert(0, str(GEO))
from geo_primitives import (cc, circle, cross, dot, inside_triangle, lc, line,
                            other, tangent_circle, unit)  # noqa: E402


def f(z: float) -> str:
    return format(z, ".17g")


def close(x: float, y: float, tol: float = 2e-8) -> float:
    residual = abs(x-y)/max(1.0, abs(x), abs(y))
    assert residual < tol, (x, y, residual)
    return residual


def angle(u: complex, v: complex) -> float:
    return math.degrees(math.acos(max(-1.0, min(1.0, dot(unit(u), unit(v))))))


def acute_scalene(A: complex, B: complex, C: complex) -> bool:
    sides = sorted((abs(A-B), abs(A-C), abs(B-C)))
    if min(sides[1]-sides[0], sides[2]-sides[1]) < .025*sides[2]:
        return False
    return min(dot(B-A,C-A), dot(A-B,C-B), dot(A-C,B-C)) > .02*sides[2]**2


def well_separated(points: dict[str, complex], scale: float) -> bool:
    # Named points that coincide by definition are omitted at each call.
    zz = list(points.values())
    return min(abs(x-y) for i,x in enumerate(zz) for y in zz[i+1:]) > .004*scale


def record(source_id: str, pack_id: str, problem: str, target: float,
           points: dict[str, complex], givens: dict[str, float], query: str,
           audit: dict[str, float]) -> dict:
    A,B,C = (points[k] for k in "ABC")
    a = abs(B-C)
    shape = [abs(A-B)/a, abs(A-C)/a]
    assert all(math.isfinite(v) for v in [target, *givens.values(), *shape, *audit.values()])
    assert target > 0
    return {"source_id": source_id, "pack_id": pack_id,
            "problem_en": problem, "target": f(target),
            "points": {k:[float(z.real),float(z.imag)] for k,z in points.items()},
            "givens": {k:float(v) for k,v in givens.items()},
            "shape_signature": shape, "query": query, "audit": audit}


def sample_abc(rng: random.Random, mode: str):
    a = rng.uniform(7, 21)
    if mode == "pn06":
        x = rng.uniform(.055,.38)*a
        h = rng.uniform(.35,.88)*a
    elif mode == "pn09":
        x = rng.uniform(.25,.75)*a
        h = rng.uniform(.42,.76)*a
    else:
        x = rng.uniform(.15,.85)*a
        h = rng.uniform(.57,1.20)*a
    return complex(x,h), 0j, complex(a,0)


def pn06(rng: random.Random):
    A,B,C=sample_abc(rng,"pn06")
    assert acute_scalene(A,B,C)
    O,_=circle(A,B,C); H=A+B+C-2*O
    wo=circle(B,O,C); wh=circle(B,H,C)
    M=other(cc(((A+O)/2,abs(A-O)/2),wo),O)
    N=other(cc(((A+H)/2,abs(A-H)/2),wh),H)
    X=other(lc(A,M,wo),M); Y=other(lc(A,N,wh),N)
    am,mx,mn=abs(A-M),abs(M-X),abs(M-N)
    ax=abs(A-X)
    assert dot(M-A,X-M)>.02*am*mx  # A,M,X in this order.
    assert abs(A-N)>.01*abs(B-C) and abs(N-Y)>.01*abs(B-C)
    assert well_separated(dict(A=A,B=B,C=C,O=O,H=H,M=M,N=N,X=X,Y=Y),abs(B-C))
    target=abs(X-Y)
    checks={
        "BOC_M":close(abs(M-wo[0]),wo[1]),
        "BOC_X":close(abs(X-wo[0]),wo[1]),
        "BHC_N":close(abs(N-wh[0]),wh[1]),
        "BHC_Y":close(abs(Y-wh[0]),wh[1]),
        "diameter_AO_M":close(dot(M-A,M-O),0),
        "diameter_AH_N":close(dot(N-A,N-H),0),
        "AMX_collinear":close(cross(M-A,X-A),0),
        "ANY_collinear":close(cross(N-A,Y-A),0),
        "solution_identity":close(target,(ax/am)*mn),
    }
    givens={"AM":am,"MX":mx,"MN":mn}
    problem=(f"In an acute scalene triangle ABC, let O and H be the circumcenter and orthocenter. "
             f"Let M be the intersection other than O of the circle through B,O,C and the circle with diameter AO. "
             f"Let N be the intersection other than H of the circle through B,H,C and the circle with diameter AH. "
             f"Line AM meets the circle through B,O,C again at X, and line AN meets the circle through B,H,C again at Y. "
             f"A,M,X occur in that order. Given AM={f(am)}, MX={f(mx)}, and MN={f(mn)}, find XY.")
    return record("DA07","PN06",problem,target,locals_points(A,B,C,O=O,H=H,M=M,N=N,X=X,Y=Y),givens,"XY",checks)


def pn07(rng: random.Random):
    A,B,C=sample_abc(rng,"pn07")
    assert acute_scalene(A,B,C)
    O,_=circle(A,B,C); w=circle(B,O,C); Q=2*w[0]-O
    M=line(C,Q,A,A+C-B)
    N=A+C-M  # ANCM in cyclic order.
    T=line(A,Q,M,N)
    assert well_separated(dict(A=A,B=B,C=C,O=O,Q=Q,M=M,N=N,T=T),abs(B-C))
    oq,qt=abs(O-Q),abs(Q-T)
    target=abs(O-T)
    checks={"BOC_Q":close(abs(Q-w[0]),w[1]),
            "BOC_T":close(abs(T-w[0]),w[1]),
            "CQ_M":close(cross(M-C,Q-C),0),
            "AM_parallel_BC":close(cross(M-A,C-B),0),
            "parallelogram":close(abs(A+C-M-N),0),
            "AQ_T":close(cross(T-A,Q-A),0),
            "MN_T":close(cross(T-M,N-M),0),
            "solution_identity":close(target*target+qt*qt,oq*oq)}
    givens={"OQ":oq,"QT":qt}
    problem=(f"In an acute scalene triangle ABC, let O be the circumcenter. On the circle through B,O,C, "
             f"let Q be the point antipodal to O. Let M be the intersection of line CQ with the line through A parallel to BC. "
             f"Choose N so that A,N,C,M, in that order, form a parallelogram. Let T be the intersection of lines AQ and MN. "
             f"Given OQ={f(oq)} and QT={f(qt)}, find OT.")
    return record("DA08","PN07",problem,target,locals_points(A,B,C,O=O,Q=Q,M=M,N=N,T=T),givens,"OT",checks)


def pn08(rng: random.Random):
    A,B,C=sample_abc(rng,"pn08")
    assert acute_scalene(A,B,C)
    O,R=circle(A,B,C)
    I=(A+B)/2;J=(A+C)/2;K=(I+J)/2
    w1=tangent_circle(I,A,K);w2=tangent_circle(J,A,K)
    T=other(cc(w1,w2),K)
    Z,r=circle(A,B,T)
    assert well_separated(dict(A=A,B=B,C=C,I=I,J=J,K=K,T=T),abs(B-C))
    checks={"I_midpoint":close(abs(2*I-A-B),0),
            "J_midpoint":close(abs(2*J-A-C),0),
            "K_midpoint":close(abs(2*K-I-J),0),
            "tangent_I":close(dot(w1[0]-I,B-A),0),
            "tangent_J":close(dot(w2[0]-J,C-A),0),
            "first_circle_K":close(abs(K-w1[0]),w1[1]),
            "second_circle_K":close(abs(K-w2[0]),w2[1]),
            "first_circle_T":close(abs(T-w1[0]),w1[1]),
            "second_circle_T":close(abs(T-w2[0]),w2[1]),
            "answer_circle":max(close(abs(Z-A),r),close(abs(Z-B),r),close(abs(Z-T),r)),
            "solution_identity":close(r,R*abs(A-B)/abs(B-C))}
    givens={"AB":abs(A-B),"BC":abs(B-C),"R":R}
    problem=(f"An acute scalene triangle ABC has AB={f(givens['AB'])}, BC={f(givens['BC'])}, "
             f"and circumradius {f(R)}. Let I and J be the midpoints of AB and AC, and K the midpoint of IJ. "
             f"The circle through K tangent to AB at I and the circle through K tangent to AC at J meet again at T. "
             f"Find the radius of the circle through A,B,T.")
    return record("DA11","PN08",problem,r,locals_points(A,B,C,O=O,I=I,J=J,K=K,T=T,Z=Z),givens,"circumradius_ABT",checks)


def rotate(z: complex, theta: float) -> complex:
    return z*complex(math.cos(theta),math.sin(theta))


def pn09(rng: random.Random):
    A,B,C=sample_abc(rng,"pn09")
    a,b,c=abs(B-C),abs(C-A),abs(A-B)
    assert a>max(b,c)*1.025
    angC=math.radians(angle(A-C,B-C));angB=math.radians(angle(A-B,C-B))
    P=line(A,A+rotate(B-A,angC),B,C)
    Q=line(A,A+rotate(C-A,-angB),B,C)
    assert .025*a<P.real<.975*a and .025*a<Q.real<.975*a
    M=2*P-A;N=2*Q-A;X=line(B,M,C,N)
    assert well_separated(dict(A=A,B=B,C=C,P=P,Q=Q,M=M,N=N,X=X),a)
    target=abs(B-X)
    checks={"P_on_BC":close(P.imag,0),"Q_on_BC":close(Q.imag,0),
            "angle_PAB_C":close(angle(P-A,B-A),angle(A-C,B-C)),
            "angle_CAQ_B":close(angle(C-A,Q-A),angle(A-B,C-B)),
            "P_midpoint":close(abs(2*P-A-M),0),
            "Q_midpoint":close(abs(2*Q-A-N),0),
            "BM_X":close(cross(X-B,M-B),0),
            "CN_X":close(cross(X-C,N-C),0)}
    # Independent researcher audit, not construction or label generation.
    O,_=circle(A,B,C)
    checks.update({"solution_circumcircle":close(abs(X-O),abs(A-O)),
                   "solution_chord_ratio":close(abs(B-X)*b,abs(C-X)*c)})
    givens={"AB":c,"AC":b,"BC":a}
    problem=(f"Let ABC be a triangle with AB={f(c)}, AC={f(b)}, and BC={f(a)}. "
             f"Choose P and Q in the interior of BC so that angle PAB equals angle BCA and angle CAQ equals angle ABC. "
             f"On rays AP and AQ choose M and N so that P and Q are the midpoints of AM and AN, respectively. "
             f"Lines BM and CN meet at X. Find BX.")
    return record("DB02","PN09",problem,target,locals_points(A,B,C,P=P,Q=Q,M=M,N=N,X=X),givens,"BX",checks)


def pn10(rng: random.Random):
    # A is fixed at the angle vertex; the two adjacent side lengths vary.
    c=rng.uniform(7,19); b=c*rng.uniform(.53,1.85)
    A=0j;B=complex(c,0);C=complex(b/math.sqrt(2),b/math.sqrt(2))
    def grid(t):
        D=B+t*(C-B)
        E=line(D,D+B-A,A,C)
        F=line(D,D+C-A,A,B)
        U,r=circle(A,E,F)
        return D,E,F,U,r
    D1,E1,F1,U1,r1=grid(1/3)
    D2,E2,F2,U2,r2=grid(2/3)
    X=other(cc((U1,r1),(U2,r2)),A)
    assert inside_triangle(X,A,B,C)
    assert well_separated(dict(A=A,B=B,C=C,D1=D1,E1=E1,F1=F1,D2=D2,E2=E2,F2=F2,X=X),abs(B-C))
    bc=abs(B-C); s=abs(B-X)+abs(C-X);target=abs(A-X)
    checks={"angle_A":close(angle(B-A,C-A),45),
            "D1_ratio":close(abs(B-D1)/abs(D1-C),.5),
            "D2_ratio":close(abs(B-D2)/abs(D2-C),2),
            "D1E1_parallel_AB":close(cross(E1-D1,B-A),0),
            "D1F1_parallel_AC":close(cross(F1-D1,C-A),0),
            "D2E2_parallel_AB":close(cross(E2-D2,B-A),0),
            "D2F2_parallel_AC":close(cross(F2-D2,C-A),0),
            "E1_on_AC":close(cross(E1-A,C-A),0),
            "F1_on_AB":close(cross(F1-A,B-A),0),
            "E2_on_AC":close(cross(E2-A,C-A),0),
            "F2_on_AB":close(cross(F2-A,B-A),0),
            "circle1_X":close(abs(X-U1),r1),
            "circle2_X":close(abs(X-U2),r2),
            "solution_identity":close(target*target,(s*s-bc*bc)/2)}
    givens={"angle_BAC_degrees":45.,"BC":bc,"BX_plus_CX":s}
    problem=(f"In triangle ABC, angle BAC is 45 degrees and BC={f(bc)}. Let D_1 and D_2 "
             f"divide BC internally in the ratios BD_1:D_1C=1:2 and BD_2:D_2C=2:1. "
             f"For each i, the line through D_i parallel to AB meets AC at E_i, and the line through D_i parallel to AC meets AB at F_i. "
             f"The circles through A,E_1,F_1 and A,E_2,F_2 meet again at X. "
             f"X lies inside ABC, and BX+CX={f(s)}. Find AX.")
    return record("DB12","PN10",problem,target,
                  locals_points(A,B,C,D_1=D1,E_1=E1,F_1=F1,D_2=D2,E_2=E2,F_2=F2,X=X),
                  givens,"AX",checks)


def locals_points(A,B,C,**rest):
    return {"A":A,"B":B,"C":C,**rest}


BUILDERS=[pn06,pn07,pn08,pn09,pn10]


def generate(seed: int=20260928, per_type: int=12) -> list[dict]:
    rng=random.Random(seed)
    out=[]
    for builder in BUILDERS:
        seen=[]
        for _ in range(per_type):
            for attempt in range(20000):
                try:
                    row=builder(rng)
                except (AssertionError, ValueError, ZeroDivisionError, OverflowError):
                    continue
                shape=row["shape_signature"]
                if any(math.dist(shape,old)<.018 for old in seen):
                    continue
                seen.append(shape);out.append(row);break
            else:
                raise RuntimeError(f"Could not sample {builder.__name__} case after 20000 tries")
    return out


if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed",type=int,default=20260928)
    parser.add_argument("--per-type",type=int,default=12)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    rows=generate(args.seed,args.per_type)
    if args.output:
        args.output.write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in rows))
    else:
        print(json.dumps({"count":len(rows),"per_type":args.per_type,
                          "max_audit_residual":max(v for r in rows for v in r["audit"].values()),
                          "ids":{pid:sum(r["pack_id"]==pid for r in rows) for pid in ["PN06","PN07","PN08","PN09","PN10"]}}))
