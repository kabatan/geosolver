"""Generate Q22b stimuli and analytic references. Never runs an optimizer."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys

from mpmath import mp

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(ROOT / "jssa/difficulty"))

from geosolver import GeometryProblem
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from probe_basins import answer_float


def write(name, value):
    p = OUT / name
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    assert p.stat().st_size < 10_000_000


def eq(left, right):
    return {"left": left, "operator": "=", "right": right}


def cons(name, expression):
    return {"name": name, "expression": expression}


def dist(p, q):
    return mp.sqrt(sum((u-v)**2 for u, v in zip(p, q)))


def foot(p, u, v):
    w = tuple(b-a for a, b in zip(u, v))
    t = sum((b-a)*c for a, b, c in zip(u, p, w)) / sum(c*c for c in w)
    return tuple(a+t*c for a, c in zip(u, w))


def area(a, b, c):
    return abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))/2


def h_reference(L, xx, yy, family):
    L, x, y = map(mp.mpf, [L, xx, yy])
    A, B, C = (mp.mpf(0), mp.mpf(0)), (L, mp.mpf(0)), (x, y)
    a, b, c = dist(B, C), dist(C, A), L
    O = (L/2, (x*x+y*y-L*x)/(2*y))
    I = ((b*L+c*x)/(a+b+c), c*y/(a+b+c))
    H = (x, y-2*O[1])
    N = tuple((o+h)/2 for o, h in zip(O, H))
    if family == "OI":
        hard = dist(O, I)
        # A second closed identity, distinct from the coordinate evaluator.
        R, r = dist(O, A), 2*area(A, B, C)/(a+b+c)
        identity = mp.sqrt(R*(R-2*r))
    elif family == "OH":
        hard = dist(O, H)
        R = dist(O, A)
        identity = mp.sqrt(9*R*R-a*a-b*b-c*c)
    elif family == "orthic":
        hard = area(foot(A, B, C), foot(B, C, A), foot(C, A, B))
        ca = (b*b+c*c-a*a)/(2*b*c)
        cb = (c*c+a*a-b*b)/(2*c*a)
        cc = (a*a+b*b-c*c)/(2*a*b)
        identity = 2*area(A, B, C)*ca*cb*cc
    elif family == "NI":
        hard = dist(N, I)
        R, r = dist(O, A), 2*area(A, B, C)/(a+b+c)
        identity = R/2-r
    elif family == "intouch":
        hard = area(foot(I, B, C), foot(I, C, A), foot(I, A, B))
        r, R, semiperimeter = 2*area(A, B, C)/(a+b+c), dist(O, A), (a+b+c)/2
        identity = r*r*semiperimeter/(2*R)
    else:
        raise ValueError(family)
    assert abs(hard-identity) < mp.mpf("1e-65"), (family, hard, identity)
    return [mp.nstr(area(A, B, C), 70), mp.nstr(hard, 70)], mp.nstr(identity, 70)


def main():
    mp.dps = 80
    pairs = []
    for aa in ["3/2", "2"]:
        for hh in ["13/20", "18/25", "4/5", "22/25", "19/20"]:
            idx = len(pairs)+1
            a = mp.mpf(3)/2 if aa == "3/2" else mp.mpf(2)
            hn, hd = hh.split("/")
            h = mp.mpf(hn)/mp.mpf(hd)
            pair_id = f"S{idx:02d}"
            common = [cons("A", f"Point(-({aa}),0)"), cons("B", f"Point({aa},0)"),
                      cons("C", f"Point(0,{hh})"), cons("D", f"Point(({aa})/3,({hh})/2)"),
                      cons("P", "Point(x,y)")]
            variants = {}
            for encoding in ["power", "length"]:
                for sign, label in [(1, "near"), (-1, "far")]:
                    d = 1-sign*h
                    distance_source = f"(1-({hh}))" if sign == 1 else f"(1+({hh}))"
                    rhs_ab = f"({aa})**2+1"
                    if encoding == "power":
                        conditions = [eq("Distance(P,A)**2", rhs_ab), eq("Distance(P,B)**2", rhs_ab),
                                      eq("Distance(P,C)**2", distance_source+"**2")]
                    else:
                        conditions = [eq("Distance(P,A)", f"sqrt({rhs_ab})"),
                                      eq("Distance(P,B)", f"sqrt({rhs_ab})"), eq("Distance(P,C)", distance_source)]
                    name = f"{encoding}_{label}"
                    dsl = {"id": f"{pair_id}_{name}", "variables": ["x", "y"],
                           "constructions": copy.deepcopy(common), "conditions": conditions,
                           "target": "Distance(P,D)"}
                    ref = mp.sqrt((a/3)**2+(sign-h/2)**2)
                    variants[name] = {"dsl": dsl, "reference": mp.nstr(ref,70),
                                      "root": [0.0, float(sign)], "d": str(d)}
            pairs.append({"id": pair_id, "group": "S", "a": str(a), "h": str(h),
                          "bounds": [[-3,3],[-3,3]], "variants": variants,
                          "human_evidence": "同一の3段階の解析解。人間成績の測定なし。",
                          "prediction": "p(power_near)-p(power_far)>=0.20; p(power_near)>=0.95"})

    shapes = [(4,1,3),(5,2,4),(6,2,4),(7,3,5),(5,2,3),
              (6,3,4),(8,3,5),(7,2,4),(9,4,5),(8,3,6)]
    families = ["OI", "OI", "OH", "OH", "orthic", "orthic", "NI", "NI", "intouch", "intouch"]
    for j, ((L, xx, yy), family) in enumerate(zip(shapes, families),1):
        pid = f"H{j:02d}"
        constructions = [cons("A", "Point(0,0)"),cons("B",f"Point({L},0)"),cons("C","Point(x,y)")]
        if family in {"OI", "OH", "NI"}:
            constructions.append(cons("O", "Circumcenter(A,B,C)"))
        if family in {"OI", "NI", "intouch"}:
            constructions.append(cons("I", "Incenter(A,B,C)"))
        if family in {"OH", "NI"}:
            constructions.append(cons("H", "Orthocenter(A,B,C)"))
        if family == "NI":
            constructions.append(cons("N", "Midpoint(O,H)"))
        if family in {"orthic", "intouch"}:
            for name, line, point in [("D","Line(B,C)","A"),("E","Line(C,A)","B"),("F","Line(A,B)","C")]:
                constructions.append(cons(name, f"FootOfPerpendicular({line},{'I' if family == 'intouch' else point})"))
        target = {"OI":"Distance(O,I)","OH":"Distance(O,H)","NI":"Distance(N,I)",
                  "orthic":"Area(D,E,F)","intouch":"Area(D,E,F)"}[family]
        refs, identity = h_reference(L, xx, yy, family)
        variants = {}
        for label, goal, ref in [("easy","Area(A,B,C)",refs[0]),("hard",target,refs[1])]:
            dsl = {"id":pid, "variables":["x","y"], "constructions":copy.deepcopy(constructions),
                   "conditions":[eq("Distance(A,C)**2",xx*xx+yy*yy),
                                 eq("Distance(B,C)**2",(xx-L)**2+yy*yy)], "target":goal}
            variants[label] = {"dsl":dsl,"reference":ref,"root":[xx,yy]}
        pairs.append({"id":pid,"group":"H","family":family,"shape":[L,xx,yy],
                      "bounds":[[-2*L,2*L],[-2*L,2*L]],"variants":variants,
                      "independent_identity":identity,
                      "human_evidence":"手書き解答の追加関係を根拠とする弱い仮説。人間難度差は未確認。",
                      "prediction":"abs(p(easy)-p(hard))<=0.05; human_hard>human_easy (unmeasured)"})
    write("stimuli.json", pairs)
    audits = []
    for pair in pairs:
        for label, v in pair["variants"].items():
            bundle = load_problem_bundle(GeometryProblem.model_validate(v["dsl"]).engine_document())
            ev = build_ir_evaluator(bundle)
            root = v["root"]
            residual = list(ev.evaluate_float_residual(root).residual_vector)
            ans = answer_float(ev, root)
            guards = ev.evaluate_guard(root)
            hard = ev.evaluate_float_hard_feasibility(root,include_margins=False).hard_feasible
            good = max(abs(float(z)) for z in residual) < 1e-10 and ans is not None and abs(ans-float(v["reference"])) < 1e-10 and guards[0] and hard
            audits.append({"pair":pair["id"],"variant":label,"ok":bool(good),"n_vars":len(bundle.var_names),
                           "n_constraints":len(bundle.spec.constraints),"constraints":list(bundle.spec.constraints),
                           "targets":list(bundle.targets),"guards":list(bundle.spec.guards),
                           "hard_checks":repr(bundle.hard_feasibility_checks),
                           "root_residual":list(map(float,residual)),"answer":ans})
    write("preflight.json", {"optimizer_calls":0,"count":len(audits),"all_pass":all(a["ok"] for a in audits),"audits":audits})
    print(json.dumps({"pairs":len(pairs),"variants":len(audits),"preflight_all_pass":all(a["ok"] for a in audits)}))
    assert all(a["ok"] for a in audits)


if __name__ == "__main__":
    main()
