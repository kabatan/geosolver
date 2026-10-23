"""One local adjoint correction and a one-GN-step control at saved hits.

No answer enters the correction or PSLQ. References are used only for scoring.
This is a diagnostic, not a rerun of the production refiner.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "jssa/difficulty"))

import numpy as np
import sympy as sp
from mpmath import mp
from geosolver import GeometryProblem
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from probe_basins import _ascii_expr
from survey import read_csv, write_csv

DPS = 100
DIFF_H = "1e-25"
SVD_TOL = "1e-12"


def refs_hp(case):
    items = case["answer"]
    items = items if isinstance(items, list) else [items]
    out = []
    for item in items:
        texts = str(item).split(",") if "CRootOf" not in str(item) else [str(item)]
        for text in texts:
            expr = sp.sympify(_ascii_expr(text), locals={"cbrt": sp.cbrt, "CRootOf": sp.CRootOf})
            out.append(mp.mpf(str(sp.N(expr, DPS+15))))
    return out


def eval_ft(ev, x):
    with high_precision_mode():
        r = ev.evaluate_hp_residual(x, precision=DPS)
        a = ev.evaluate_answer_hp(x, precision=DPS)
    if not r.is_finite or a.answer_hp is None:
        raise ValueError("non-finite residual or answer")
    tau = mp.mpf(a.answer_hp)
    if not mp.isfinite(tau):
        raise ValueError("non-real or non-finite answer")
    return mp.matrix(r.residual_vector), tau


def digits(error):
    return min(100., float(-mp.log10(abs(error)))) if error else 100.


def evaluate_guards(ev, x):
    try:
        with high_precision_mode():
            ok, tags = ev.evaluate_guard(x)
            hard = ev.evaluate_hp_hard_feasibility(x, precision=DPS)
        return {"guard": bool(ok), "guard_tags": list(tags), "hard": bool(hard.hard_feasible)}
    except Exception as exc:
        return {"guard": None, "hard": None, "guard_error": f"{type(exc).__name__}: {exc}"}


def identify(tau, refs):
    if not mp.isfinite(tau):
        return {"poly": None, "correct_relation": False}
    for degree in range(1, 5):
        try:
            coeff = ([0, 1] if abs(tau) < mp.mpf("1e-25") else
                     mp.pslq(mp.matrix([tau**j for j in range(degree+1)]),
                             tol=mp.mpf("1e-25"), maxcoeff=10**6, maxsteps=2000))
        except Exception as exc:
            return {"poly": None, "correct_relation": False, "error": type(exc).__name__}
        if coeff is not None:
            # Check relation against the *same nearest reference* selected solely
            # for evaluation. Numerical check at >85 digits, not a proof.
            vals = [abs(mp.fsum(c*t**j for j,c in enumerate(coeff))) /
                    max(mp.mpf(1), mp.fsum(abs(c*t**j) for j,c in enumerate(coeff))) for t in refs]
            return {"poly": list(map(int, coeff)), "correct_relation": bool(min(vals) < mp.mpf("1e-85")),
                    "reference_relation_digits": digits(min(vals))}
    return {"poly": None, "correct_relation": False}


def one_correction(ev, x, references):
    t0 = time.monotonic()
    with mp.workdps(DPS):
        x = [mp.mpf(repr(float(v))) for v in x]
        f, tau = eval_ft(ev, x)
        ref_index = min(range(len(references)), key=lambda k: abs(tau-references[k]))
        ref = references[ref_index]
        scale = [max(mp.mpf(1), abs(v)) for v in x]
        h = mp.mpf(DIFF_H)
        jmat = mp.matrix(len(f), len(x))
        g = mp.matrix(len(x), 1)
        for j in range(len(x)):
            xp, xm = list(x), list(x)
            xp[j] += h*scale[j]
            xm[j] -= h*scale[j]
            fp, tp = eval_ft(ev, xp)
            fm, tm = eval_ft(ev, xm)
            for i in range(len(f)):
                jmat[i,j] = (fp[i]-fm[i])/(2*h)
            g[j] = (tp-tm)/(2*h)
        weights = []
        for i in range(len(f)):
            w = mp.sqrt(mp.fsum(jmat[i,j]**2 for j in range(len(x))))
            w = w if w > mp.mpf("1e-40") else mp.mpf(1)
            weights.append(w)
            for j in range(len(x)):
                jmat[i,j] /= w
        fn = mp.matrix([v/w for v,w in zip(f, weights)])
        if not jmat.rows:
            raise ValueError("empty Jacobian")
        u, s, v = mp.svd_r(jmat)
        rank = sum(si > s[0]*mp.mpf(SVD_TOL) for si in s) if s[0] else 0
        delta = mp.matrix(len(x), 1)
        lamb = mp.matrix(len(f), 1)
        gproj = mp.matrix(len(x), 1)
        for k in range(rank):
            uf = mp.fsum(u[i,k]*fn[i] for i in range(len(f)))
            vg = mp.fsum(v[k,j]*g[j] for j in range(len(x)))
            for j in range(len(x)):
                delta[j] -= v[k,j]*uf/s[k]
                gproj[j] += v[k,j]*vg
            for i in range(len(f)):
                lamb[i] += u[i,k]*vg/s[k]
        corrected = tau - mp.fsum(lamb[i]*fn[i] for i in range(len(f)))
        gn_x = [a+b*sc for a,b,sc in zip(x,delta,scale)]
        gn_f, gn_tau = eval_ft(ev, gn_x)
        score_scale = max(mp.mpf(1), abs(ref))
        gn_guard = evaluate_guards(ev, gn_x)
        anchor_guard = evaluate_guards(ev, x)
        raw_poly = identify(tau, [ref])
        corr_poly = identify(corrected, [ref])
        gn_poly = identify(gn_tau, [ref])
        out = {"rank": int(rank), "n_vars": len(x), "ref_index": ref_index,
               "raw_digits": digits((tau-ref)/score_scale),
               "corrected_digits": digits((corrected-ref)/score_scale),
               "gn_digits": digits((gn_tau-ref)/score_scale),
               "res_digits": digits(mp.norm(f)), "gn_res_digits": digits(mp.norm(gn_f)),
               "null_projection": float(mp.norm(g-gproj)/mp.norm(g)) if mp.norm(g) else 0.,
               "delta_norm": float(mp.norm(delta)),
               "lambda_norm": float(mp.norm(lamb)),
               "correction_size": float(abs(corrected-tau)),
               "linear_identity_error": float(abs(corrected-tau-mp.fsum(a*b for a,b in zip(g,delta)))),
               "raw_poly": raw_poly["poly"], "raw_identified": raw_poly["correct_relation"],
               "corrected_poly": corr_poly["poly"], "corrected_identified": corr_poly["correct_relation"],
               "gn_poly": gn_poly["poly"], "gn_identified": gn_poly["correct_relation"],
               "anchor_guard": anchor_guard.get("guard"), "anchor_hard": anchor_guard.get("hard"),
               "gn_guard": gn_guard.get("guard"), "gn_hard": gn_guard.get("hard"),
               "sec": time.monotonic()-t0}
        detail = {"x": list(map(str,x)), "gn_x": list(map(str,gn_x)),
                  "raw": str(tau), "corrected": str(corrected), "gn": str(gn_tau),
                  "reference": str(ref), "residual": list(map(str,f)), "svals": list(map(str,s)),
                  "lambda": list(map(str,lamb)), "scale": list(map(str,scale)),
                  "weights": list(map(str,weights)), "g": list(map(str,g)),
                  "raw_relation": raw_poly, "corrected_relation": corr_poly, "gn_relation": gn_poly,
                  "anchor_checks": anchor_guard, "gn_checks": gn_guard}
        return out, detail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", nargs="*")
    args = ap.parse_args()
    cases = {c["id"]: c for c in map(json.loads, (ROOT/"benchmarks/cases.jsonl").read_text().splitlines())}
    surveys = {r["id"]: r for r in read_csv(HERE/"survey.csv")}
    rows, detail = [], {}
    started = time.monotonic()
    for cid, survey in surveys.items():
        if args.ids and cid not in args.ids:
            continue
        if survey["status"] != "ok":
            continue
        bundle = load_problem_bundle(GeometryProblem.model_validate(cases[cid]["dsl"]).engine_document())
        ev = build_ir_evaluator(bundle)
        with mp.workdps(DPS):
            refs = refs_hp(cases[cid])
        # Only selected rank/observable candidates need a second anchor for P2.
        seeds = [0, 1] if survey["candidate"]=="True" else [0]
        for seed in seeds:
            folder = "raw-323" if seed==0 else "raw-323-seed1"
            data = json.loads((ROOT/"jssa/difficulty/minima"/folder/(cid+".json")).read_text())
            if not data.get("first_hit"):
                rows.append({"id":cid, "seed":seed, "status":"no_first_hit"})
                continue
            hit = data["first_hit"][sorted(data["first_hit"], key=int)[0]]
            try:
                result, record = one_correction(ev, hit["x"], refs)
                rows.append({"id":cid, "seed":seed, "status":"ok", **result})
                detail[f"{cid}:{seed}"] = record
            except Exception as exc:
                rows.append({"id":cid, "seed":seed, "status":"error", "error":f"{type(exc).__name__}: {exc}"})
        if len(rows)%20==0:
            print(f"{len(rows)} anchors, elapsed={time.monotonic()-started:.1f}s", flush=True)
    prefix = "pilot-" if args.ids else ""
    write_csv(HERE/(prefix+"correction.csv"), rows)
    (HERE/(prefix+"correction-details.json")).write_text(json.dumps(detail, indent=2)+"\n")
    valid0 = [r for r in rows if r["seed"]==0 and r["status"]=="ok"]
    stats = {"n_rows":len(rows), "n_valid0":len(valid0),
             "errors":[r for r in rows if r["status"]!="ok"],
             "P1_gain8_n":sum(r["corrected_digits"]-r["raw_digits"]>=8 for r in valid0),
             "P1_fraction":sum(r["corrected_digits"]-r["raw_digits"]>=8 for r in valid0)/max(1,len(valid0)),
             "median_raw_digits":float(np.median([r["raw_digits"] for r in valid0])),
             "median_corrected_digits":float(np.median([r["corrected_digits"] for r in valid0])),
             "median_gn_digits":float(np.median([r["gn_digits"] for r in valid0])),
             "raw_identified":sum(r["raw_identified"] for r in valid0),
             "corrected_identified":sum(r["corrected_identified"] for r in valid0),
             "gn_identified":sum(r["gn_identified"] for r in valid0),
             "corrected_worse_by2":[r["id"] for r in valid0 if r["corrected_digits"]<r["raw_digits"]-2],
             "corrected_wrong_relations":[r["id"] for r in valid0 if r["corrected_poly"] and not r["corrected_identified"]],
             "elapsed_sec":time.monotonic()-started}
    paired = []
    for cid,survey in surveys.items():
        if survey["candidate"]!="True" or survey.get("nullity")=="0":
            continue
        key0,key1 = f"{cid}:0",f"{cid}:1"
        if key0 not in detail or key1 not in detail:
            paired.append({"id":cid,"valid":False,"success":False})
            continue
        a,b = detail[key0],detail[key1]
        with mp.workdps(DPS):
            dist = mp.sqrt(mp.fsum(((mp.mpf(u)-mp.mpf(v))/max(1,abs(mp.mpf(u))))**2 for u,v in zip(a["x"],b["x"])))
            agreement = digits((mp.mpf(a["corrected"])-mp.mpf(b["corrected"]))/max(1,abs(mp.mpf(a["reference"]))))
        r0=next(r for r in rows if r["id"]==cid and r["seed"]==0)
        r1=next(r for r in rows if r["id"]==cid and r["seed"]==1)
        matched = a["reference"] == b["reference"]
        success = float(dist)>=.01 and min(r0["corrected_digits"],r1["corrected_digits"])>=25 and matched
        paired.append({"id":cid,"valid":True,"distance":float(dist),"same_branch":matched,
                       "digits0":r0["corrected_digits"],"digits1":r1["corrected_digits"],
                       "agreement_digits":agreement,"success":success})
    stats["P2_n"] = len(paired)
    stats["P2_success"] = sum(r["success"] for r in paired)
    write_csv(HERE/(prefix+"anchor-pairs.csv"),paired)
    (HERE/(prefix+"correction-stats.json")).write_text(json.dumps(stats,indent=2)+"\n")
    print(json.dumps(stats,indent=2),flush=True)


if __name__ == "__main__":
    main()
