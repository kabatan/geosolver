"""Q6: stored endpoint audit only. No optimizer is called; writes stay here."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "jssa/difficulty"))
from probe_basins import (GeometryProblem, load_case, load_problem_bundle,
                          build_ir_evaluator, reference_values, answer_float)
from geosolver.engine.standard.evaluation.search_point import evaluate_search_point

MAIN = ["HMMT-2007-FEB-GEO-04", "JMO-2017-PRE-01", "AIME-2021-II-14"]


def clean(v):
    if isinstance(v, dict):
        return {str(k): clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [clean(x) for x in v]
    if isinstance(v, np.generic):
        return clean(v.item())
    if isinstance(v, float) and not math.isfinite(v):
        return None
    return v


def write_json(name, obj):
    (HERE / name).write_text(json.dumps(clean(obj), ensure_ascii=False, indent=2) + "\n")


def write_csv(name, rows):
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with (HERE / name).open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: json.dumps(clean(v), ensure_ascii=False) if isinstance(v, (list, dict, tuple)) else clean(v)
                        for k, v in r.items()})


def context(cid):
    case = load_case(cid)
    b = load_problem_bundle(GeometryProblem.model_validate(case["dsl"]).engine_document())
    return case, b, build_ir_evaluator(b)


def hard(ev, x):
    try:
        return bool(ev.evaluate_float_hard_feasibility(x, include_margins=False).hard_feasible)
    except Exception:
        return False


def assess(ev, x, bounds, refs):
    out = {"in_box": all(lo <= z <= hi for z, (lo, hi) in zip(x, bounds))}
    try:
        er = ev.evaluate_float_residual(x)
        s = evaluate_search_point(evaluator=ev, values=x, residual=er)
        ans = answer_float(ev, x)
        finite = bool(er.is_finite and math.isfinite(er.residual_norm_float))
        out.update(res=float(er.residual_norm_float), residual_vector=list(er.residual_vector),
                   finite=finite, guard_ok=bool(s.guard_ok), hard_ok=bool(s.hard.hard_feasible),
                   hard_tags=list(s.hard.failure_tags), guard_tags=list(s.guard_violations), ans=ans,
                   ans_ok=bool(ans is not None and any(abs(ans-v) <= 1e-6*max(1, abs(v)) for v in refs)))
        nobox = ("error" if not finite else "stuck" if out["res"] > 1e-8 else
                 "wrong_branch" if not out["guard_ok"] or not out["hard_ok"] else
                 "hit" if out["ans_ok"] else "wrong_answer")
        out["no_box_cls"] = nobox
        out["replay_cls"] = nobox if out["in_box"] else "left_box"
    except Exception as exc:
        out.update(error=repr(exc), no_box_cls="error", replay_cls="error" if out["in_box"] else "left_box")
    return out


def mm(seq):
    a = [float(z) for z in seq if z is not None and math.isfinite(z)]
    return {"n": len(a), "min": min(a), "median": float(np.median(a)), "max": max(a)} if a else {"n": 0}


def classify_specific(cid, x, start):
    if cid == "HMMT-2007-FEB-GEO-04":
        u, v = x
        points = np.array([[0, 0], [13, 0], [13-12*u/13, 5*u/13], [13-12*v/13, -5*v/13]])
        ds = [np.linalg.norm(p-q) for i, p in enumerate(points) for q in points[i+1:]]
        return {"coinc": min(ds)/max(ds), "min_uv": min(u,v), "sum_uv": u+v,
                "saturated_tangent_polynomial": 12*u*v-169*(u+v)+2028,
                "area_ABC_formula": 60*u*v/169,
                "opposite_side_product_formula": (120*u*v/169)*(120*u*v/169-5*(u+v))}
    if cid == "JMO-2017-PRE-01":
        cross = x[1]-math.sqrt(3)*x[0]
        return {"ACD_cross": cross, "start_ACD_cross": start[1]-math.sqrt(3)*start[0],
                "radius_over_4": float(np.linalg.norm(x)/4),
                "ACD_cross_normalized": cross/(2*max(float(np.linalg.norm(x)),1e-300)),
                "angle_DAB_deg": math.degrees(math.atan2(x[1],x[0]))}
    return {}


def main():
    began = time.monotonic()
    census_path = ROOT / "jssa/strategy/astra-consult-17/G/census.csv"
    census = list(csv.DictReader(census_path.open()))
    selected = [r for r in census if int(r["n_F"]) >= 10 and int(r["n_I"]) >= 10
                and float(r["p_I"]) > float(r["p_F"])
                and int(r["F_left_box"])+int(r["F_wrong_answer"]) > 0]
    selected.sort(key=lambda r: (-int(r["F_left_box"])-int(r["F_wrong_answer"]), r["id"]))
    ids = [r["id"] for r in selected]
    inputs = [HERE / "preregistration.md", ROOT / "benchmarks/cases.jsonl", census_path,
              ROOT / "jssa/difficulty/start-feasibility-1023/per-problem.csv",
              ROOT / "jssa/difficulty/probe_basins.py"]
    inputs += [ROOT / "jssa/difficulty/minima/raw-323" / (cid+".json") for cid in ids]
    manifest = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    write_json("input-manifest.json", {"preregistration_fixed_before_endpoint_audit": True, "sha256": manifest,
                                      "selected_ids": ids, "deep_ids": list(dict.fromkeys(MAIN + ids[:3])),
                                      "new_local_search_runs": 0})
    write_csv("selection.csv", selected)
    allrows, summaries, deep = [], [], {}
    for cid in ids:
        case, b, ev = context(cid)
        raw = json.loads((ROOT / "jssa/difficulty/minima/raw-323" / (cid+".json")).read_text())
        bounds, refs = raw["box"], reference_values(case["answer"])
        rows = []
        for rec in raw["records"]:
            row = {"id": cid, "seed": 0, "k": rec["k"], "cls": rec["cls"]}
            if "x" not in rec or "start" not in rec:
                row["missing_coordinates"] = True
                rows.append(row)
                continue
            x, start = rec["x"], rec["start"]
            row.update(x=x, start=start, start_F=hard(ev, start))
            row.update(assess(ev,x,bounds,refs))
            row.update(classify_specific(cid, x, start))
            if cid == "AIME-2021-II-14":
                z = np.asarray(x)/max(abs(q) for q in x)
                score = assess(ev,z.tolist(),bounds,refs)
                row.update(normalized_x=z.tolist(), normalized_cls=score["replay_cls"],
                           normalized_res=score.get("res"), normalized_ans=score.get("ans"),
                           normalized_hard=score.get("hard_ok"))
            rows.append(row)
        allrows.extend(rows)
        summary = {"id": cid, "n": len(rows), "method": "LM" if raw["n_constraints"] >= raw["n_vars"] else "Powell",
                   "classification_mismatches": sum(r.get("replay_cls") != r["cls"] for r in rows),
                   "missing_coordinates": sum(r.get("missing_coordinates",False) for r in rows)}
        for group in [True, False]:
            group_rows = [r for r in rows if r.get("start_F") is group]
            prefix = "F" if group else "I"
            summary[prefix+"_n"] = len(group_rows)
            summary[prefix+"_original"] = dict(Counter(r["cls"] for r in group_rows))
            summary[prefix+"_without_box"] = dict(Counter(r.get("no_box_cls") for r in group_rows))
            box_rows = [r for r in group_rows if r["cls"] == "left_box"]
            summary[prefix+"_left_box_without_box"] = dict(Counter(r.get("no_box_cls") for r in box_rows))
            summary[prefix+"_left_box_res"] = mm(r.get("res") for r in box_rows)
            summary[prefix+"_left_box_ans_ok"] = sum(r.get("ans_ok",False) for r in box_rows)
            if cid == "AIME-2021-II-14":
                summary[prefix+"_normalized"] = dict(Counter(r["normalized_cls"] for r in group_rows))
        summaries.append(summary)
        if cid in MAIN + ids[:3]:
            dr = {"dsl": case["dsl"], "answer": case["answer"], "source_in_case": case.get("source"),
                  "bounds": bounds, "summary": summary}
            if cid == "HMMT-2007-FEB-GEO-04":
                bad = [r for r in rows if r["cls"] == "wrong_answer"]
                dr.update(wrong_answer_coinc=mm(r["coinc"] for r in bad),
                          wrong_answer_min_uv=mm(r["min_uv"] for r in bad),
                          wrong_answer_saturated_polynomial=mm(r["saturated_tangent_polynomial"] for r in bad),
                          F_wrong_answer_near=sum(r["start_F"] and r["coinc"]<1e-4 for r in bad),
                          wrong_answer_res=mm(r["res"] for r in bad))
            if cid == "JMO-2017-PRE-01":
                bad = [r for r in rows if r["cls"] == "left_box"]
                dr.update(left_box_radius_over_4=mm(r["radius_over_4"] for r in bad),
                          left_box_radius_gt100=sum(r["radius_over_4"]>100 for r in bad),
                          left_box_cross_normalized=mm(r["ACD_cross_normalized"] for r in bad),
                          left_box_answer=mm(r["ans"] for r in bad),
                          side_outcomes=dict(Counter(("F" if r["start_F"] else "I")+":"+
                               ("positive" if r["start_ACD_cross"]>0 else "negative")+":"+r["cls"] for r in rows)))
                # Deterministic point evaluations, not local search or optimization.
                radial=[]
                for r in bad:
                    for mult in [0.5,1.0,2.0,10.0]:
                        z=(np.array(r["x"])*mult).tolist()
                        a=assess(ev,z,bounds,refs)
                        radial.append({"k":r["k"], "multiplier":mult,"x":z,
                                       "res":a.get("res"),"hard_ok":a.get("hard_ok"),"ans":a.get("ans")})
                write_csv("jmo-radial-evaluations.csv",radial)
            seed1_path = ROOT / "jssa/difficulty/minima/raw-323-seed1" / (cid+".json")
            if seed1_path.exists():
                d1=json.loads(seed1_path.read_text())
                dr["seed1"]={"n":len(d1["records"]),"counts":dict(Counter(r["cls"] for r in d1["records"])),
                             "records_with_start":sum("start" in r for r in d1["records"]),
                             "records_with_x":sum("x" in r for r in d1["records"]),
                             "sha256":hashlib.sha256(seed1_path.read_bytes()).hexdigest()}
            deep[cid]=dr
        print(cid, "F",summary["F_original"],"F_box_regrade",summary["F_left_box_without_box"],flush=True)
    write_csv("per-start.csv", allrows)
    write_json("per-problem.json",summaries)
    write_json("deep-audit.json",deep)
    write_csv("per-problem.csv",summaries)
    write_json("run-summary.json",{"problems":len(ids),"endpoints":len(allrows),
               "classification_mismatches":sum(s["classification_mismatches"] for s in summaries),
               "missing_coordinates":sum(s["missing_coordinates"] for s in summaries),
               "new_local_search_runs":0,"elapsed_seconds":time.monotonic()-began})


if __name__ == "__main__":
    main()
