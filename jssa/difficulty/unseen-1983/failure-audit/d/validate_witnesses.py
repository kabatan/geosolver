"""Direct 100-decimal substitution of analytic witnesses; no optimization/search."""
from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path[:0] = [str(ROOT / "src"), str(ROOT), str(HERE)]
sys.dont_write_bytecode = True
from mpmath import mp
from prepare import CORPUS, IDS, now, save, sha
from benchmarks import research_runner as rr
from geosolver import GeometryProblem
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.evaluation.snapshots import numerical_snapshot
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.problem.ir.compiler import safe_eval_expr_hp
from geosolver.runtime.integrity import source_tree_hash

def witnesses():
    q = mp.mpf
    s = mp.sqrt
    deg = mp.pi / 180
    d_x = 2*mp.sin(77*deg)*mp.cos(73*deg)
    d_y = 2*mp.sin(77*deg)*mp.sin(73*deg)
    t = (d_x*d_x+d_y*d_y-1)/(2*(mp.cos(30*deg)*(d_x-1)+mp.sin(30*deg)*d_y))
    out = {
        "AIME-1983-12":dict(a=q(6),b=q(5),h=q(33)/2,p=q(33),q=q(2)),
        "AIME-1985-09":dict(r=8/s(15),y2=7/s(15),y3=11/(2*s(15)),y4=2/s(15),
                            alpha=mp.acos(q(17)/32),beta=mp.acos(-q(7)/128),
                            m=q(17),n=q(32),u=q(-15),v=q(8)),
        "AIME-1991-12":dict(w=q(192)/5,h=q(144)/5,rx=q(15),sy=q(44)/5,
                            m=q(672),n=q(5),u=q(-2),v=q(269)),
        "AIME-1995-09":dict(s=q(11)/2,a=q(11),b=q(605)),
        "AIME-1996-13":dict(cx=7*s(30)/20,cy=s(930)/20,t=q(27)/19,
                            m=q(27),n=q(38),u=q(-7),v=q(5)),
        "AIME-1996-15":dict(dx=(1-s(3))/2,dy=(s(3)-1)/2,r=q(7)/9),
        "AIME-1997-04":dict(cx=q(5),cy=q(12),dx=q(5),dy=q(28)/9,r=q(8)/9,
                            m=q(8),n=q(9),u=q(-1),v=q(1)),
        "HMMT-2022-FEB-GEO-07":dict(x=(10-s(69))/2,y=(10-s(69))/2,
                                    a=q(169),b=q(2),h=q(1),k=q(-84)),
        "HMMT-2023-FEB-GEO-06":dict(cx=t*mp.cos(30*deg),cy=t*mp.sin(30*deg),
                                    dx=d_x,dy=d_y,n=q(68)),
    }
    theta = mp.acos(q(5)/6)
    radius = 243/s(11)
    ox,oy = q(31)/2,mp.sqrt(radius**2-(q(31)/2)**2)
    # B=(31,0); rotate OB by successive 2*theta along the convex cyclic hexagon.
    hx = {}
    for k,name in enumerate("cdef",1):
        angle=2*k*theta
        hx[name+"x"]=ox+ox*mp.cos(angle)+oy*mp.sin(angle)
        hx[name+"y"]=oy+ox*mp.sin(angle)-oy*mp.cos(angle)
    out["AIME-1991-14"] = hx
    return out

def fmt(value):
    return mp.nstr(value, 90)

def check(cid, dsl, values):
    problem = GeometryProblem.model_validate(dsl)
    bundle = load_problem_bundle(problem.engine_document())
    evaluator = build_ir_evaluator(bundle)
    ordered = [values[v] for v in bundle.var_names]
    snapshot = numerical_snapshot(bundle.spec,bundle.var_names,ordered,bundle.base_context)
    context = snapshot.materialize(c["name"] for c in dsl["constructions"])
    conditions=[]
    for i,c in enumerate(dsl["conditions"]):
        lhs = safe_eval_expr_hp(str(c["left"]),context)
        rhs = safe_eval_expr_hp(str(c["right"]),context)
        difference = lhs-rhs
        tol = mp.mpf("1e-70") * max(1,abs(lhs),abs(rhs))
        op = c["operator"]
        satisfied = {"=":abs(difference)<=tol,">":difference>0,"<":difference<0,
                     ">=":difference>=-tol,"<=":difference<=tol,"!=":abs(difference)>tol}[op]
        conditions.append({"index_zero_based":i,**c,"lhs_numeric":fmt(lhs),"rhs_numeric":fmt(rhs),
                           "lhs_minus_rhs":fmt(difference),"satisfied":bool(satisfied)})
    target_error = None
    try:
        target = safe_eval_expr_hp(dsl["target"],context)
    except Exception as error:
        if cid != "AIME-1996-15" or dsl["target"] != "(1000*r) // 1":
            raise
        # Record the frozen evaluator's actual failure; this is only a mathematical witness.
        target_error = str(error)
        target = mp.floor(1000*values["r"])
    hp=evaluator.evaluate_hp_residual(ordered,precision=100)
    hard=evaluator.evaluate_hp_hard_feasibility(ordered,precision=100,include_margins=True)
    guards=evaluator.evaluate_guard(ordered)
    coords={}
    for c in dsl["constructions"]:
        item=context[c["name"]]
        if hasattr(item,"x") and hasattr(item,"y"):
            coords[c["name"]]=[fmt(item.x),fmt(item.y)]
    eq=[abs(mp.mpf(c["lhs_minus_rhs"])) for c in conditions if c["operator"]=="="]
    inequalities=[abs(mp.mpf(c["lhs_minus_rhs"])) for c in conditions if c["operator"] in {">","<"}]
    return {"id":cid,"variables":{v:fmt(values[v]) for v in dsl["variables"]},
            "points":coords,"conditions":conditions,"target_expression":dsl["target"],
            "target_numeric":fmt(target),"frozen_target_evaluation_error":target_error,
            "target_evaluated_mathematically_outside_frozen_evaluator":bool(target_error),
            "max_absolute_equality_residual":fmt(max(eq,default=mp.mpf(0))),
            "minimum_strict_inequality_margin":fmt(min(inequalities)) if inequalities else None,
            "frozen_ir_residual_norm":fmt(hp.residual_norm_hp),
            "frozen_ir_all_finite":bool(hp.is_finite),
            "frozen_hard_feasible":bool(hard.hard_feasible),
            "frozen_hard_failure_tags":list(hard.failure_tags),
            "frozen_guard_ok":bool(guards[0]),"frozen_guard_violations":list(guards[1]),
            "all_conditions_satisfied":all(c["satisfied"] for c in conditions)}

def main():
    assert not (HERE/"prediction.lock.json").exists(), "Witnesses are fixed before prediction lock"
    assert source_tree_hash()=="sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5"
    validation=rr.validate_corpus(HERE/"cases.jsonl")
    assert validation["valid"], validation
    rows=[]
    with mp.workdps(100),high_precision_mode():
        data=witnesses()
        for cid in [*IDS,"AIME-1991-14"]:
            original=json.loads((CORPUS/"dsl"/(cid+".json")).read_text())
            variants=[("original",original)]
            if cid in IDS:
                variants.append(("rewritten",json.loads((HERE/"dsl"/(cid+".json")).read_text())))
            for label,dsl in variants:
                row=check(cid,dsl,data[cid]);row["variant"]=label
                rows.append(row)
                print(cid,label,row["all_conditions_satisfied"],row["frozen_hard_feasible"],
                      row["max_absolute_equality_residual"],row["target_numeric"][:25],flush=True)
    save(HERE/"witness-validation.json",{"created_at_utc":now(),"decimal_precision":100,
         "solver_search_executed":False,"source_hash":source_tree_hash(),
         "dsl_validation":validation,"checks":rows})
    assert all(r["all_conditions_satisfied"] and r["frozen_hard_feasible"] and
               r["frozen_guard_ok"] and r["frozen_ir_all_finite"] for r in rows)

if __name__=="__main__":
    main()
