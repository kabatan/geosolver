"""Detect output cancellation from fresh, unoptimized feasible diagrams.

calibrate accesses DSLs and inferred boxes, never reference answers or saved
endpoints. validate uses a different seed and references for scoring only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
from mpmath import mp
from geosolver import GeometryProblem
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds
from correction import DPS, DIFF_H, SVD_TOL, eval_ft, evaluate_guards, refs_hp, digits
from survey import write_csv


def dual_at(ev, xx):
    with mp.workdps(DPS):
        x = [mp.mpf(repr(float(v))) for v in xx]
        f,tau = eval_ft(ev,x)
        if not len(f):
            return {"x": list(map(float,xx)), "raw":str(tau), "corrected":str(tau),
                    "res_norm": "0", "lambda": [], "rank":0, "null_projection":None}
        h = mp.mpf(DIFF_H)
        scale = [max(1,abs(t)) for t in x]
        jmat = mp.matrix(len(f),len(x))
        g = mp.matrix(len(x),1)
        for j in range(len(x)):
            xp,xm = list(x),list(x)
            xp[j] += h*scale[j]
            xm[j] -= h*scale[j]
            fp,tp = eval_ft(ev,xp)
            fm,tm = eval_ft(ev,xm)
            for i in range(len(f)):
                jmat[i,j] = (fp[i]-fm[i])/(2*h)
            g[j]=(tp-tm)/(2*h)
        weights=[]
        for i in range(len(f)):
            w=mp.sqrt(mp.fsum(jmat[i,j]**2 for j in range(len(x))))
            w=w if w>mp.mpf("1e-40") else mp.mpf(1)
            weights.append(w)
            for j in range(len(x)):
                jmat[i,j] /= w
        fn=mp.matrix([v/w for v,w in zip(f,weights)])
        u,s,v=mp.svd_r(jmat)
        rank=sum(t>s[0]*mp.mpf(SVD_TOL) for t in s) if s[0] else 0
        lamb=mp.matrix(len(f),1)
        gp=mp.matrix(len(x),1)
        for k in range(rank):
            vg=mp.fsum(v[k,j]*g[j] for j in range(len(x)))
            for i in range(len(f)):
                lamb[i]+=u[i,k]*vg/s[k]
            for j in range(len(x)):
                gp[j]+=v[k,j]*vg
        corr=tau-mp.fsum(a*b for a,b in zip(lamb,fn))
        return {"x":list(map(float,xx)), "raw":str(tau), "corrected":str(corr),
                "res_norm":str(mp.norm(f)), "lambda":[str(a/w) for a,w in zip(lamb,weights)],
                "rank":int(rank), "null_projection":float(mp.norm(g-gp)/mp.norm(g)) if mp.norm(g) else 0.}


def sample(dsl, cid, seed, n, max_draws):
    t0=time.monotonic()
    b=load_problem_bundle(GeometryProblem.model_validate(dsl).engine_document())
    ev=build_ir_evaluator(b)
    box=np.asarray(infer_problem_bounds(b),float)
    key=int(hashlib.sha256(cid.encode()).hexdigest()[:8],16)
    rng=np.random.default_rng([seed,key])
    records=[]
    float_feasible=0
    for k in range(max_draws):
        x=box[:,0]+rng.random(len(b.var_names))*(box[:,1]-box[:,0])
        try:
            guard,_=ev.evaluate_guard(x.tolist())
            hard=ev.evaluate_float_hard_feasibility(x.tolist())
            if not guard or not hard.hard_feasible:
                continue
            float_feasible+=1
            with mp.workdps(DPS):
                hx=[mp.mpf(repr(float(v))) for v in x]
                checks=evaluate_guards(ev,hx)
            if not checks.get("guard") or not checks.get("hard"):
                continue
            try:
                record=dual_at(ev,x)
                records.append({"k":k,"status":"ok",**record})
            except Exception as exc:
                records.append({"k":k,"status":"dual_error","error":f"{type(exc).__name__}: {exc}"})
        except Exception:
            # An undefined sampled diagram is not a valid calibration point.
            continue
        if len(records)>=n:
            break
    with mp.workdps(DPS):
        good=[r for r in records if r["status"]=="ok"]
        summary={"id":cid,"n_vars":len(b.var_names),"n_eq":len(b.targets),
                 "draws":k+1,"float_feasible":float_feasible,"n_feasible":len(records),
                 "n_ok":len(good),"requested":n,"sec":time.monotonic()-t0}
        if len(good)==n:
            cc=[mp.mpf(r["corrected"]) for r in good]
            rr=[mp.mpf(r["raw"]) for r in good]
            norm=max(mp.mpf(1),abs(cc[0]))
            spread=(max(cc)-min(cc))/norm
            raw_spread=(max(rr)-min(rr))/max(mp.mpf(1),abs(rr[0]))
            summary.update(spread=str(spread),raw_spread=str(raw_spread),
                           candidate=bool(spread<=mp.mpf("1e-30")),
                           raw_constant=bool(raw_spread<=mp.mpf("1e-30")),
                           value=str(cc[0]),
                           residual_min=str(min(mp.mpf(r["res_norm"]) for r in good)),
                           residual_max=str(max(mp.mpf(r["res_norm"]) for r in good)))
        else:
            summary.update(candidate=False,raw_constant=False)
    return summary,records


def calibrate(cases):
    # This function uses only id and dsl; not case['answer'] or minima/.
    rows,records=[],{}
    start=time.monotonic()
    for cid,case in cases.items():
        if not case["dsl"].get("variables"):
            continue
        try:
            summary,data=sample(case["dsl"],cid,10231401,8,256)
        except Exception as exc:
            summary={"id":cid,"candidate":False,"status":"error","error":f"{type(exc).__name__}: {exc}"}
            data=[]
        rows.append(summary)
        records[cid]=data
        if len(rows)%25==0:
            print(f"calibration {len(rows)} problems, elapsed={time.monotonic()-start:.1f}s",flush=True)
    write_csv(HERE/"fresh-calibration.csv",rows)
    (HERE/"fresh-calibration.json").write_text(json.dumps({"rows":rows,"records":records},indent=2)+"\n")
    stats={"n_problems":len(rows),"n_complete":sum(r.get("n_ok")==8 for r in rows),
           "nonconstant_candidates":[r["id"] for r in rows if r.get("candidate") and not r["raw_constant"]],
           "constant_candidates":[r["id"] for r in rows if r.get("candidate") and r["raw_constant"]],
           "elapsed_sec":time.monotonic()-start}
    (HERE/"fresh-calibration-stats.json").write_text(json.dumps(stats,indent=2)+"\n")
    print(json.dumps(stats,indent=2),flush=True)


def validate(cases):
    cal=json.loads((HERE/"fresh-calibration.json").read_text())
    candidates=[r for r in cal["rows"] if r.get("candidate")]
    rows,all_records=[],{}
    start=time.monotonic()
    for source in candidates:
        cid=source["id"]
        try:
            summary,recs=sample(cases[cid]["dsl"],cid,10231402,32,1024)
            with mp.workdps(DPS):
                refs=refs_hp(cases[cid])
                target=mp.mpf(source["value"])
                ref_index=min(range(len(refs)),key=lambda k:abs(refs[k]-target))
                ref=refs[ref_index]
                for rec in recs:
                    if rec["status"]=="ok":
                        rec["error_digits"]=digits((mp.mpf(rec["corrected"])-ref)/max(1,abs(ref)))
                        rec["raw_error_digits"]=digits((mp.mpf(rec["raw"])-ref)/max(1,abs(ref)))
                success=sum(r.get("error_digits",-1000)>=30 for r in recs)
                summary.update(raw_constant=source["raw_constant"],ref_index=ref_index,
                               n_references=len(refs),success30=success,all32=success==32,
                               digits_min=min((r.get("error_digits",-1000) for r in recs),default=-1000),
                               calibration_digits=digits((target-ref)/max(1,abs(ref))))
            rows.append(summary)
            all_records[cid]=recs
        except Exception as exc:
            rows.append({"id":cid,"raw_constant":source["raw_constant"],"all32":False,
                         "status":"error","error":f"{type(exc).__name__}: {exc}"})
        print(cid,rows[-1].get("success30"),"/32",flush=True)
    write_csv(HERE/"fresh-validation.csv",rows)
    (HERE/"fresh-validation.json").write_text(json.dumps({"rows":rows,"records":all_records},indent=2)+"\n")
    active=[r for r in rows if not r["raw_constant"]]
    stats={"n_candidates":len(candidates),"n_nonconstant":len(active),
           "P3_all32":sum(r["all32"] for r in active),
           "P3_fraction":sum(r["all32"] for r in active)/max(1,len(active)),
           "failures":[r for r in active if not r["all32"]],
           "elapsed_sec":time.monotonic()-start}
    (HERE/"fresh-validation-stats.json").write_text(json.dumps(stats,indent=2)+"\n")
    print(json.dumps(stats,indent=2),flush=True)


if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("mode",choices=["calibrate","validate"])
    args=ap.parse_args()
    cases={c["id"]:c for c in map(json.loads,(ROOT/"benchmarks/cases.jsonl").read_text().splitlines())}
    if args.mode=="calibrate":
        calibrate(cases)
    else:
        validate(cases)
