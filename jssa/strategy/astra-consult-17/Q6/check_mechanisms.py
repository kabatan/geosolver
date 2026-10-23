"""Post-audit analytic checks and read-only reuse of G's stored traces.

No optimization. These secondary checks do not redefine preregistered P1-P3.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter

import numpy as np
import sympy as sp

from audit_existing import (ROOT, HERE, context, assess, reference_values,
                            write_json, write_csv, mm)


def saved(cid):
    return json.loads((ROOT / "jssa/difficulty/minima/raw-323" / (cid+".json")).read_text())


def outcome_rows(cid):
    return [r for r in csv.DictReader((HERE / "per-start.csv").open()) if r["id"] == cid]


def main():
    report = {"stage": "post-audit supplementary checks; no new local search",
              "preregistration_sha256": hashlib.sha256((HERE / "preregistration.md").read_bytes()).hexdigest()}

    cid="HMMT-2007-FEB-GEO-04"
    c,b,e=context(cid); raw=saved(cid); refs=reference_values(c["answer"])
    u,v=sp.symbols("u v",real=True)
    B=sp.Matrix([13-12*u/13,5*u/13]); C=sp.Matrix([13-12*v/13,-5*v/13])
    vec=C-B
    det=sp.det(sp.Matrix.hstack(vec,-B))
    norm2=sp.expand(vec.dot(vec))
    numerator=sp.factor(det**2-25*norm2)
    assert sp.simplify(numerator-sp.Rational(1200,28561)*u*v*(12*u*v-169*(u+v)+2028)) == 0
    witness=[(17+math.sqrt(22/3))/2,(17-math.sqrt(22/3))/2]
    report["hmmt_2007"]={
        "BC_squared":str(norm2),"tangency_numerator":str(numerator),
        "nondegenerate_equation":"12*u*v-169*(u+v)+2028=0 (u*v>0)",
        "sum_equation":"(u+v-24)^2=49",
        "s31_discriminant":str(sp.Rational(31)**2-4*sp.Rational(169,12)*(31-12)),
        "s17_discriminant":str(sp.Rational(17)**2-4*sp.Rational(169,12)*(17-12)),
        "exact_root_float_witness":assess(e,witness,raw["box"],refs),
        "degenerate_limit_7_0":assess(e,[7.,0.],raw["box"],refs),
        "hard_checks":[str(x) for x in b.hard_feasibility_checks],
    }

    cid="JMO-2017-PRE-01"
    c,b,e=context(cid); raw=saved(cid); refs=reference_values(c["answer"])
    rows=outcome_rows(cid)
    Ffail=[r for r in rows if r["start_F"]=="True" and r["cls"]!="hit"]
    Fbox=[r for r in Ffail if r["cls"]=="left_box"]
    transverse=[]
    for r in Ffail:
        x=json.loads(r["x"])
        z=[x[0],x[1]-24e-6]  # Same 1e-6 box-width scale as G.
        a=assess(e,z,raw["box"],refs)
        transverse.append({"k":int(r["k"]),"original_cls":r["cls"],"base_x":x,"trial_x":z,
                           "base_res":float(r["res"]),"trial_res":a.get("res"),
                           "trial_hard":a.get("hard_ok"),"trial_guard_tags":a.get("guard_tags"),
                           "eq_descent":a.get("res",math.inf)<float(r["res"])})
    write_csv("jmo-transverse-evaluations.csv",transverse)
    gp=ROOT/"jssa/strategy/astra-consult-17/G/mechanism-data"/(cid+".json")
    traces=json.loads(gp.read_text())["records"]
    trace_summary={}
    trace_rows=[]
    for condition in ["B","N"]:
        runs=[r for r in traces if r["F"]]
        for r in runs:
            q=r[condition]; native=q["native"]
            events=[t for t in native["tail"] if t.get("decision")=="rejected" and t.get("base")
                    and t["eq_ss"]<t["base"]["eq_ss"] and t["guard"]>t["base"]["guard"]]
            trace_rows.append({"k":r["k"],"condition":condition,"cls":q["cls"],
                "eq_descent_F_to_I_rejected":native["F_to_I_eq_descent_rejected"],
                "guard_increase_eq_descent_rejected_in_last8":len(events),
                "hard_increase_other_ss_decrease_rejected":native["F_to_I_eq_descent_rejected_other_ss_decrease"],
                "raw_info":native["raw_info"],"x":q.get("x"),
                "example":events[0] if events else None})
        fail=[r for r in trace_rows if r["condition"]==condition and r["cls"]!="hit"]
        trace_summary[condition]={"F_counts":dict(Counter(r[condition]["cls"] for r in runs)),
            "failed":len(fail),
            "fail_with_F_to_I_eq_descent_rejection":sum(r["eq_descent_F_to_I_rejected"]>0 for r in fail),
            "fail_with_guard_increase_eq_descent_rejection_in_last8":sum(r["guard_increase_eq_descent_rejected_in_last8"]>0 for r in fail),
            "fail_with_hard_only_decline_rejection":sum(r["hard_increase_other_ss_decrease_rejected"]>0 for r in fail)}
    write_csv("jmo-existing-G-traces.csv",trace_rows)
    report["jmo_2017_1"]={
        "F_failed":len(Ffail),"F_box":len(Fbox),
        "F_box_radius_over_4":mm(float(r["radius_over_4"]) for r in Fbox),
        "F_box_radius_over_4_gt100":sum(float(r["radius_over_4"])>100 for r in Fbox),
        "F_box_normalized_cross":mm(float(r["ACD_cross_normalized"]) for r in Fbox),
        "transverse_descent_and_guard_failure":sum(t["eq_descent"] and not t["trial_hard"] for t in transverse),
        "transverse_guard_tags":dict(Counter(str(t["trial_guard_tags"]) for t in transverse)),
        "exact_simple_solution":assess(e,[1.5,math.sqrt(3)/2],raw["box"],refs),
        "exact_crossed_solution":assess(e,[3.,math.sqrt(3)],raw["box"],refs),
        "boundary_ray":"D=t*(1,sqrt(3)), t>1: angle(DAB)=pi/3, angle(BCD)=pi/2",
        "boundary_residual":math.pi*math.sqrt(5)/6,
        "G_trace_sha256":hashlib.sha256(gp.read_bytes()).hexdigest(),
        "G_trace_counts":trace_summary,
    }

    cid="HMMT-2024-FEB-GEO-02"
    c,b,e=context(cid); raw=saved(cid); refs=reference_values(c["answer"])
    rows=outcome_rows(cid)
    curves=[]
    for exponent in range(2,12):
        s=10.**exponent
        x=[s,s/2-2,s/2,s/2-5]
        a=assess(e,x,raw["box"],refs)
        curves.append({"s":s,"x":x,**a})
    write_csv("hmmt-2024-expansion-curve.csv",curves)
    boundary=[]
    for r in rows:
        if r["cls"]=="left_box" and r["no_box_cls"]=="hit":
            x=json.loads(r["x"])
            z=[min(max(q,lo),hi) for q,(lo,hi) in zip(x,raw["box"])]
            boundary.append({"k":int(r["k"]),"start_F":r["start_F"],"x":x,
                             "overshoot_ulps":(x[0]-20)/math.ulp(20.),"clipped_x":z,
                             "clipped_score":assess(e,z,raw["box"],refs)})
    s=sp.symbols("s",positive=True)
    exact_branches=[]
    for d in [-5,5]:
        for t in [-3,3]:
            ee=s/2+d; uu=ee+t
            poly=sp.factor(ee**2*(s-uu)-(s-ee)**2*uu)
            roots=sp.solve(poly,s)
            exact_branches.append({"e_minus_half_s":d,"u_minus_e":t,"polynomial":str(poly),
                                   "positive_roots":[str(q) for q in roots],
                                   "valid_roots":[str(q) for q in roots if bool(0<ee.subs(s,q)<q) and bool(0<uu.subs(s,q)<q)]})
    report["hmmt_2024_2"]={"exact_angle_bisector_branches":exact_branches,
        "curve":"s=S, u=S/2-2, v=S/2, e=S/2-5; DE=3, EF=5 exactly; angle/perpendicular residuals ->0",
        "boundary_false_negatives":boundary,
        "F_box_s_range":mm(json.loads(r["x"])[0] for r in rows if r["start_F"]=="True" and r["cls"]=="left_box"),
        "F_box_s_over_1e6":sum(json.loads(r["x"])[0]>1e6 for r in rows if r["start_F"]=="True" and r["cls"]=="left_box")}

    cid="JMO-2017-PRE-04"
    c,b,e=context(cid); raw=saved(cid); refs=reference_values(c["answer"])
    rows=outcome_rows(cid)
    Fbox=[r for r in rows if r["start_F"]=="True" and r["cls"]=="left_box"]
    # First saved F box escape with radius >100*the 4-unit fixed base and h<1e-2.
    eligible=[r for r in Fbox if json.loads(r["x"])[3]>400 and 0<json.loads(r["x"])[0]<1e-2]
    curves=[]
    if eligible:
        seed=eligible[0]; h,ox,oy,r=json.loads(seed["x"]); R=abs(oy); delta=r-R
        for t in [1.,2.,10.,100.,1000.]:
            z=[h/t,ox,oy*t,R*t+delta/t]
            curves.append({"source_k":int(seed["k"]),"multiplier":t,"x":z,**assess(e,z,raw["box"],refs)})
    write_csv("jmo-4-reciprocal-curve.csv",curves)
    report["jmo_2017_4"]={"F_left_box":len(Fbox),
        "F_left_box_r_gt400_and_h_lt01":len(eligible),
        "F_left_box_h":mm(json.loads(r["x"])[0] for r in Fbox),
        "F_left_box_radius":mm(json.loads(r["x"])[3] for r in Fbox),
        "exact_shape":{"h":"sqrt(15)","ox":"-2","oy":"12/sqrt(15)","r":"12/sqrt(15)",
                       "E":"(1/4,sqrt(15)/4)","F":"(-5,sqrt(15))","EF":"6"},
        "exact_shape_float_score":assess(e,[math.sqrt(15),-2.,12/math.sqrt(15),12/math.sqrt(15)],raw["box"],refs)}

    # Directly count the prespecified claims without changing their thresholds.
    H=outcome_rows("HMMT-2007-FEB-GEO-04")
    J=outcome_rows("JMO-2017-PRE-01")
    A=outcome_rows("AIME-2021-II-14")
    P1=[r for r in H if r["start_F"]=="True" and r["cls"]=="wrong_answer"]
    P2=[r for r in J if r["start_F"]=="True" and r["cls"]=="left_box"]
    P3=[r for r in A if r["start_F"]=="True" and r["cls"]=="left_box"]
    report["preregistered_predictions"]={
        "P1":{"n":len(P1),"pass":sum(float(r["coinc"])<1e-4 for r in P1),"threshold":.8},
        "P2":{"n":len(P2),"pass":sum(float(r["res"])>1e-8 for r in P2),"threshold":.8},
        "P3":{"n":len(P3),"pass":sum(r["normalized_cls"]=="hit" for r in P3),"threshold":.5}}
    write_json("mechanism-checks.json",report)
    print(json.dumps(report["preregistered_predictions"],ensure_ascii=False))
    print(json.dumps(report["jmo_2017_1"]["G_trace_counts"],ensure_ascii=False))


if __name__=="__main__":
    main()
