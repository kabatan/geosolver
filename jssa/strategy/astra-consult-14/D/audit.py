"""Consolidate results, check precision and exact identities, preserve provenance."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT/"src"))

import numpy as np
import scipy
import sympy as sp
import mpmath
from mpmath import mp
from scipy.stats import rankdata
from geosolver import GeometryProblem
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.contracts.candidate_record import FloatCandidate
from geosolver.engine.standard.refinement.mpmath_refiner import MpmathRefiner
import correction
import fresh_dual
from survey import read_csv, write_csv


def partial_bootstrap(rows,x,y,controls=(),nboot=2000):
    def finite(v):
        try:return math.isfinite(float(v))
        except (TypeError,ValueError):return False
    use=[r for r in rows if all(finite(r.get(k)) for k in (x,y,*controls))]
    data=np.asarray([[float(r[k]) for k in (x,y,*controls)] for r in use])
    def calc(data):
        ranks=np.column_stack([rankdata(data[:,j]) for j in range(data.shape[1])])
        a,b=ranks[:,0].copy(),ranks[:,1].copy()
        if controls:
            z=np.column_stack([np.ones(len(data)),ranks[:,2:]])
            a-=z@np.linalg.lstsq(z,a,rcond=None)[0]
            b-=z@np.linalg.lstsq(z,b,rcond=None)[0]
        return float(np.corrcoef(a,b)[0,1])
    rng=np.random.default_rng(10231403)
    vals=[calc(data[rng.integers(len(data),size=len(data))]) for _ in range(nboot)]
    return {"n":len(use),"rho":calc(data),"ci95":np.quantile(vals,[.025,.975]).tolist(),"controls":list(controls)}


def wilson(k,n):
    z=1.959963984540054
    phat=k/n
    center=(phat+z*z/(2*n))/(1+z*z/n)
    half=z*math.sqrt(phat*(1-phat)/n+z*z/(4*n*n))/(1+z*z/n)
    return [center-half,center+half]


def main():
    t0=time.monotonic()
    cases={c["id"]:c for c in map(json.loads,(ROOT/"benchmarks/cases.jsonl").read_text().splitlines())}
    human={r["case_id"]:r for r in read_csv(ROOT/"jssa/difficulty/ghost-1023/human_feat.csv")}
    cal=json.loads((HERE/"fresh-calibration.json").read_text())
    validation=json.loads((HERE/"fresh-validation.json").read_text())
    new=[r for r in validation["rows"] if not r["raw_constant"]]
    baseline=defaultdict(list)
    for r in read_csv(ROOT/"jssa/results/stage-profile-20261023/per-case.csv"):
        baseline[r["case_id"]].append(r)
    summary=[]
    for r in new:
        cid=r["id"]
        p0=json.loads((ROOT/"jssa/difficulty/minima/raw-323"/(cid+".json")).read_text())
        p1=json.loads((ROOT/"jssa/difficulty/minima/raw-323-seed1"/(cid+".json")).read_text())
        hs=human.get(cid,{})
        summary.append({"id":cid,"n_vars":r["n_vars"],"answer":str(cases[cid]["answer"]),
                        "new_success":r["success30"],"new_n":32,"min_digits":r["digits_min"],
                        "min_res":float(r["residual_min"]),"max_res":float(r["residual_max"]),
                        "p0_hits":p0.get("counts",{}).get("hit",0),"p0_n":p0.get("starts_done"),
                        "p1_hits":p1.get("counts",{}).get("hit",0),"p1_n":p1.get("starts_done"),
                        "human":hs.get("human",""),"contest":hs.get("contest",""),
                        "baseline_wall_median":float(np.median([float(t["wall_time_s"]) for t in baseline[cid]])),
                        "baseline_sources":"|".join(sorted({t["final_answer_source"] for t in baseline[cid]}))})
    write_csv(HERE/"fresh-summary.csv",summary)

    # Repeat two validation points per nonconstant candidate at higher working
    # precision and a smaller derivative step, without changing the points.
    correction.DPS=140
    fresh_dual.DPS=140
    fresh_dual.DIFF_H="1e-35"
    checks=[]
    for source in new:
        cid=source["id"]
        b=load_problem_bundle(GeometryProblem.model_validate(cases[cid]["dsl"]).engine_document())
        ev=build_ir_evaluator(b)
        with mp.workdps(140):
            refs=correction.refs_hp(cases[cid])
            for rec in validation["records"][cid][:2]:
                out=fresh_dual.dual_at(ev,rec["x"])
                value=mp.mpf(out["corrected"])
                ref=min(refs,key=lambda v:abs(v-value))
                checks.append({"id":cid,"k":rec["k"],
                               "digits140":float(-mp.log10(abs(value-ref)/max(1,abs(ref)))) if value!=ref else 140,
                               "agreement100_140":float(-mp.log10(abs(value-mp.mpf(rec["corrected"]))/max(1,abs(ref))))
                               if value!=mp.mpf(rec["corrected"]) else 140})

    # Three exact reductions. Geometry/sign hypotheses are explained in answer.md.
    s,y=sp.symbols("s y",positive=True)
    a1=sp.sqrt(3)*s*s/4-s*y/2
    a2=s*y
    tau=3*sp.sqrt(3)*s*s/2
    hex_identity=sp.simplify(tau-6*(a1-20)-3*(a2-23)-189)
    m,d=sp.symbols("m d",real=True)
    l1=168-12*m-9*d
    l2=12*m+5*d
    square_identity=sp.expand(sp.sqrt(2)*d+sp.sqrt(2)*(l1+l2)/4-42*sp.sqrt(2))
    a,b,c,k=sp.symbols("a b c k",positive=True)
    tangent_identity=sp.simplify((a-b+c-(a+c-b))/k)
    exact={"HMMT-2023-FEB-GEO-01":str(hex_identity),
           "HMMT-2023-FEB-GEO-05":str(square_identity),
           "HMMT-2017-FEB-GEO-05_Pitot_reduction":str(tangent_identity)}
    assert all(v=="0" for v in exact.values())

    # Read-only call to the frozen production refiner, one independently saved
    # seed-1 hit, used only AFTER the cold-point experiment as a witness check.
    cid="HMMT-2017-FEB-GEO-05"
    seed1=json.loads((ROOT/"jssa/difficulty/minima/raw-323-seed1"/(cid+".json")).read_text())
    hit=seed1["first_hit"]["0"]
    bundle=load_problem_bundle(GeometryProblem.model_validate(cases[cid]["dsl"]).engine_document())
    ev=build_ir_evaluator(bundle)
    initial=ev.evaluate_float_residual(hit["x"])
    cand=FloatCandidate(x_float=tuple(hit["x"]),score=initial.residual_norm_float**2,
                        residual_norm_float=initial.residual_norm_float,guard_ok=True,
                        evaluation_status=initial.evaluation_status,origin_seed=1,
                        origin_start_point_index=hit["k"],candidate_id=1,hard_feasible=True)
    wt=time.monotonic()
    batch=MpmathRefiner().refine_candidates(bundle=bundle,evaluator=ev,candidates=(cand,),
                                           deadline_monotonic=time.monotonic()+20)
    witnesses=[]
    for q in batch.candidates:
        with mp.workdps(140):
            f,t=correction.eval_ft(ev,list(q.x_hp))
            witnesses.append({"status":q.refinement_status,"res_digits140":correction.digits(mp.norm(f)),
                              "target_error_digits140":correction.digits((t-19)/19),
                              "x":[mp.nstr(v,160) for v in q.x_hp],
                              "checks":correction.evaluate_guards(ev,list(q.x_hp)),
                              "phase_history":list(q.phase_history)})
    (HERE/"witness.json").write_text(json.dumps({"id":cid,"source_seed":1,"source_k":hit["k"],
         "seconds":time.monotonic()-wt,"attempted":batch.attempted_count,
         "converged":batch.converged_count,"witnesses":witnesses},indent=2)+"\n")

    survey=[r for r in read_csv(HERE/"survey.csv") if r["status"]=="ok"]
    stats={}
    for x,y in [("target_cond","refinement_time_s"),("cond_full","refinement_time_s"),
                ("target_cond","p1")]:
        stats[x+":"+y]=partial_bootstrap(survey,x,y,("n_vars","n_constraints"))
    for contest in ["AIME","HMMT"]:
        stats["target_cond:human:"+contest]=partial_bootstrap([r for r in survey if r["contest"]==contest],"target_cond","human")
    valid_obs=[r for r in survey if float(r["g_null_ratio"])<=1e-5]
    stats["target_cond:refinement_time_s:null_safe"]=partial_bootstrap(valid_obs,"target_cond","refinement_time_s",("n_vars","n_constraints"))
    old=json.loads((HERE/"input-sha256.json").read_text())
    changes=[name for name,digest in old.items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest]
    raw_counts={}
    for folder in ["raw-323","raw-323-seed1"]:
        cc=Counter()
        for path in sorted((ROOT/"jssa/difficulty/minima"/folder).glob("*.json")):
            data=json.loads(path.read_text())
            cc["files"]+=1
            cc["positive_vars"]+=data.get("n_vars",0)>0
            for rec in data.get("records",[]):
                cc["records"]+=1
                cc["records_x"]+="x" in rec
                cc["records_start"]+="start" in rec
        raw_counts[folder]=dict(cc)
    crows=read_csv(HERE/"correction.csv")
    c0=[r for r in crows if r["seed"]=="0" and r["status"]=="ok"]
    artifact={"precision_checks":checks,"exact_reductions":exact,"correlations":stats,
              "P1_wilson95":wilson(214,261),"P2_wilson95":wilson(12,21),"P3_wilson95":wilson(9,9),
              "raw_counts":raw_counts,"input_changes":changes,
              "calibration_draws":sum(r.get("draws",0) for r in cal["rows"]),
              "calibration_feasible":sum(len(r) for r in cal["records"].values()),
              "calibration_dual_ok":sum(x["status"]=="ok" for r in cal["records"].values() for x in r),
              "calibration_dual_errors":sum(x["status"]!="ok" for r in cal["records"].values() for x in r),
              "validation_duals":sum(len(r) for r in validation["records"].values()),
              "nonconstant_validation_duals":sum(len(validation["records"][r["id"]]) for r in new),
              "p1_anchor_checks_pass":sum(r["anchor_guard"]=="True" and r["anchor_hard"]=="True" for r in c0),
              "p1_gn_checks_pass":sum(r["gn_guard"]=="True" and r["gn_hard"]=="True" for r in c0),
              "simple_pslq":{name:{"correct_relation":sum(r[name+"_identified"]=="True" for r in c0),
                    "incorrect_relation":sum(bool(r[name+"_poly"]) and r[name+"_identified"]!="True" for r in c0),
                    "no_relation":sum(not r[name+"_poly"] for r in c0)} for name in ["raw","corrected","gn"]},
              "environment":{"executable":sys.executable,"python":sys.version,"numpy":np.__version__,
                             "scipy":scipy.__version__,"sympy":sp.__version__,"mpmath":mpmath.__version__},
              "elapsed_sec":time.monotonic()-t0}
    (HERE/"audit.json").write_text(json.dumps(artifact,indent=2)+"\n")
    print(json.dumps({"n_new":len(new),"precision_min":min(c["digits140"] for c in checks),
          "input_changes":changes,"witnesses":witnesses,"correlations":stats},indent=2),flush=True)


if __name__=="__main__":
    main()
