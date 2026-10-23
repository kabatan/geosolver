"""astra-F: read-only input audit; every output is local to this directory.

Use the specified existing interpreter with -B. No installation is required.
Subcommands: features, stats, penalties, verify. See protocol.md for estimands.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import sys
import time
from collections import Counter
from pathlib import Path

for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[name] = "1"
sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "jssa/difficulty")]

import numpy as np
import scipy
from scipy.optimize import least_squares, minimize
from scipy.special import expit
from scipy.stats import binomtest, rankdata, spearmanr

from geosolver import GeometryProblem
from geosolver.engine.standard.contracts.external_pipeline_config import ExternalPipelineConfig
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.search import scipy_multistart_backend as smb
from probe_basins import answer_float, reference_values

SF = ROOT / "jssa/difficulty/start-feasibility-1023/per-problem.csv"
HF = ROOT / "jssa/difficulty/ghost-1023/human_feat.csv"
B = ROOT / "jssa/strategy/astra-consult-12/B"
MODES = ("base", "nohard", "nohard_guard10", "nohard_guard100", "hard100",
         "eqonly", "tight", "sharpen", "sharpen_nohard")
IDS = ("AIME-2023-I-12", "HMMT-2024-FEB-GEO-04")


def clean(v):
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (float, np.floating)):
        return float(v) if np.isfinite(v) else None
    if isinstance(v, (int, np.integer)):
        return int(v)
    if isinstance(v, np.ndarray):
        return clean(v.tolist())
    if isinstance(v, dict):
        return {str(k): clean(x) for k, x in v.items()}
    if isinstance(v, (tuple, list)):
        return [clean(x) for x in v]
    return v


def dump(name, obj):
    (OUT / name).write_text(json.dumps(clean(obj), ensure_ascii=False, indent=2) + "\n")


def csvread(path):
    with Path(path).open() as f:
        return list(csv.DictReader(f))


def csvwrite(name, rows):
    with (OUT / name).open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def cases():
    return {r["id"]: r for r in map(json.loads, (ROOT / "benchmarks/cases.jsonl").open())}


def context(case):
    b = load_problem_bundle(GeometryProblem.model_validate(case["dsl"]).engine_document())
    return b, build_ir_evaluator(b), np.asarray(infer_problem_bounds(b), dtype=float)


def key(cid):
    return int(hashlib.sha256(cid.encode()).hexdigest()[:8], 16)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def leaf_count(g):
    return sum(leaf_count(c) for c in g.children) if g.children else 1


def features():
    data = cases()
    humans = {r["case_id"]: r for r in csvread(HF)}
    rows, raw_audit, tag_counts = [], [], Counter()
    started = time.monotonic()
    for i, old in enumerate(csvread(SF)):
        cid = old["id"]
        b, ev, box = context(data[cid])
        r0 = json.loads((ROOT / "jssa/difficulty/minima/raw-323" / f"{cid}.json").read_text())
        r1 = json.loads((ROOT / "jssa/difficulty/minima/raw-323-seed1" / f"{cid}.json").read_text())
        recs0 = [r for r in r0.get("records", []) if "start" in r]
        recs1 = r1.get("records", [])
        h0 = sum(r["cls"] == "hit" for r in recs0)
        h1 = sum(r["cls"] == "hit" for r in recs1)
        assert len(recs0) == int(old["starts"]), cid
        assert h0 == int(old["hit_feas"]) + int(old["hit_infeas"]), cid
        assert abs(h0 / len(recs0) - float(old["p"])) < 1e-12, cid
        assert len(b.var_names) == int(old["n_vars"]), cid
        assert len(b.hard_feasibility_checks) == int(old["n_checks"]), cid
        raw_audit.append({"id": cid, "n0": len(recs0), "n1": len(recs1), "hits0": h0,
                          "hits1": h1, "raw0_records_without_start": len(r0.get("records", []))-len(recs0)})
        rng = np.random.default_rng([1402301, key(cid)])
        nfeas, tags, errors, guard_fail, guard_error, construction_fail, other_fail = 0, Counter(), 0, 0, 0, 0, 0
        for _ in range(256):
            x = box[:, 0] + rng.random(len(box)) * (box[:, 1]-box[:, 0])
            try:
                snap = ev.evaluate_float_hard_feasibility(list(x), include_margins=False)
                nfeas += bool(snap.hard_feasible)
                kinds = {("guard_error" if " raised" in t else "guard_false")
                         if t.startswith("guard[") else t.split(":")[0]
                         for t in snap.failure_tags}
                tags.update(kinds)
                guard_fail += "guard_false" in kinds
                guard_error += "guard_error" in kinds
                construction_fail += "construction_error" in kinds
                other_fail += bool(kinds - {"guard_false", "guard_error", "construction_error"})
            except Exception as exc:
                errors += 1
                tags.update([f"exception_{type(exc).__name__}"])
        h = humans[cid]
        row = dict(id=cid, contest=h["contest"], human=h["human"],
                   n_vars=len(b.var_names), n_checks=len(b.hard_feasibility_checks),
                   n_ineq=int(h["n_ineq"]), n_eq=int(h["n_eq"]), n_cons=int(h["n_cons"]),
                   dsl_len=int(h["dsl_len"]), ir_eq=len(b.spec.constraints),
                   ir_guards=len(b.spec.guards), guard_leaves=sum(leaf_count(g) for g in ev.compiled_guards),
                   n0=len(recs0), h0=h0, p0=h0/len(recs0),
                   n1=len(recs1), h1=h1, p1=h1/len(recs1),
                   phi0=int(old["n_feas"])/len(recs0), phi256=nfeas/256,
                   nf=int(old["n_feas"]), hf=int(old["hit_feas"]),
                   ni=int(old["n_infeas"]), hi=int(old["hit_infeas"]),
                   fresh_feasible=nfeas, fresh_errors=errors,
                   fresh_guard_fail=guard_fail, fresh_guard_error=guard_error, fresh_construction_fail=construction_fail,
                   fresh_other_fail=other_fail, logC=h["logC"])
        rows.append(row)
        tag_counts.update(tags)
        if (i+1) % 20 == 0:
            print(f"features {i+1}/292 {time.monotonic()-started:.1f}s", flush=True)
    csvwrite("features.csv", rows)
    csvwrite("raw-audit.csv", raw_audit)
    inputs = [SF, HF, ROOT/"benchmarks/cases.jsonl", Path(smb.__file__),
              ROOT/"jssa/difficulty/probe_basins.py", OUT/"protocol.md"]
    # Hash full source inputs that are used again; no large files are copied.
    for sub in ("raw-323", "raw-323-seed1"):
        inputs.extend(sorted((ROOT/"jssa/difficulty/minima"/sub).glob("*.json")))
    dump("manifest.json", {"inputs": {str(p.relative_to(ROOT)): sha(p) for p in inputs},
         "python": sys.version, "executable": sys.executable, "numpy": np.__version__,
         "scipy": scipy.__version__, "platform": platform.platform(),
         "seconds_features": time.monotonic()-started, "points_evaluated": 256*len(rows),
         "fresh_failure_tags_points_multilabel": tag_counts})
    print("features complete", len(rows), "seconds", time.monotonic()-started, flush=True)


def corr(x, y):
    x, y = np.asarray(x), np.asarray(y)
    return float(np.corrcoef(x, y)[0, 1]) if np.std(x) > 0 and np.std(y) > 0 else float("nan")


def rho(x, y):
    return corr(rankdata(x), rankdata(y))


def dcats(d):
    return np.column_stack([d == j for j in (2, 3, 4)] + [d >= 5]).astype(float)


def partial(x, y, d, controls=(), categorical=True):
    cols = [np.ones(len(x))]
    if categorical:
        cols.extend(dcats(d).T)
    else:
        cols.append(rankdata(d))
    cols.extend(rankdata(z) for z in controls)
    z = np.column_stack(cols)
    xr, yr = rankdata(x), rankdata(y)
    return corr(xr-z@np.linalg.lstsq(z, xr, rcond=None)[0],
                yr-z@np.linalg.lstsq(z, yr, rcond=None)[0])


def boot_stat(fun, n, seed=1402302, groups=None, count=2000):
    rng = np.random.default_rng(seed)
    groups = [np.arange(n)] if groups is None else groups
    vals = []
    for _ in range(count):
        idx = np.concatenate([rng.choice(g, size=len(g), replace=True) for g in groups])
        vals.append(fun(idx))
    return np.nanquantile(np.asarray(vals), [.025, .975]).tolist()


def stat(fun, n, groups=None):
    return {"n": n, "value": fun(np.arange(n)), "ci95": boot_stat(fun, n, groups=groups)}


def logistic_predict(x, y, xt):
    mean, sd = x.mean(axis=0), x.std(axis=0)
    sd[sd < 1e-12] = 1
    a = np.column_stack([np.ones(len(x)), (x-mean)/sd])
    at = np.column_stack([np.ones(len(xt)), (xt-mean)/sd])
    def loss(beta):
        eta = a@beta
        value = np.sum(np.logaddexp(0, eta)-y*eta) + .5*np.sum(beta[1:]**2)
        grad = a.T@(expit(eta)-y)
        grad[1:] += beta[1:]
        return value, grad
    opt = minimize(loss, np.zeros(a.shape[1]), jac=True, method="L-BFGS-B",
                   options={"maxiter": 1000, "gtol": 1e-9, "ftol": 1e-12})
    if not opt.success:
        raise RuntimeError(opt.message)
    return np.clip(expit(at@opt.x), 1e-9, 1-1e-9)


def within_ranks(x, contests):
    out = np.zeros(len(x))
    for c in set(contests):
        mask = contests == c
        out[mask] = (rankdata(x[mask])-.5)/mask.sum()
    return out


def stats():
    rows = csvread(OUT/"features.csv")
    n = len(rows)
    arr = {k: np.array([float(r[k]) for r in rows]) for k in rows[0] if k not in ("id", "contest", "human")}
    p, p1, phi, new, d = (arr[k] for k in ("p0", "p1", "phi0", "phi256", "n_vars"))
    controls = [arr[k] for k in ("n_ineq", "n_checks", "n_eq", "dsl_len")]
    result = {"counts": {k: int(arr[k].sum()) for k in ("n0", "h0", "n1", "h1", "nf", "hf", "ni", "hi")}}
    result["counts"].update(n=n, fewer_than_200=int((arr["n0"]<200).sum()),
                            phi0_zero=int((phi==0).sum()), phi0_one=int((phi==1).sum()),
                            phi_one_low_p=int(((phi==1)&(p<.3)).sum()),
                            phi_zero_positive_p=int(((phi==0)&(p>0)).sum()))
    stats_out = {}
    for name, x, y in (("phi0_p0", phi, p), ("phi256_p0", new, p), ("phi256_p1", new, p1),
                        ("phi0_phi256", phi, new), ("p0_p1", p, p1)):
        stats_out[name] = stat(lambda idx: rho(x[idx], y[idx]), n)
    for name, x, y, cat, cov in (("phi0_p0_d_rank", phi, p, False, []),
        ("phi0_p0_d_categories", phi, p, True, []),
        ("phi0_p0_all_counts", phi, p, True, controls),
        ("phi256_p1_all_counts", new, p1, True, controls),
        ("phi256_p1_ir_counts", new, p1, True, [arr[k] for k in ("ir_eq", "ir_guards", "n_checks", "guard_leaves", "dsl_len")])):
        stats_out[name] = stat(lambda idx: partial(x[idx], y[idx], d[idx], [z[idx] for z in cov], cat), n)
    for k in ("n_vars", "n_checks", "n_ineq", "n_eq", "n_cons", "dsl_len", "guard_leaves"):
        stats_out[f"phi0_{k}"] = {"value": rho(phi, arr[k])}
        stats_out[f"p0_{k}"] = {"value": rho(p, arr[k])}
    # Exact (n_vars, n_checks, n_ineq) strata: linear rank adjustment is not the only check.
    strata = {}
    for i, r in enumerate(rows):
        strata.setdefault(tuple(r[k] for k in ("n_vars", "n_checks", "n_ineq")), []).append(i)
    good = [np.array(v) for v in strata.values() if len(v)>=2 and np.ptp(phi[v])>0]
    xx, yy = rankdata(phi), rankdata(p)
    xr, yr = [], []
    for ids in good:
        xr.extend(xx[ids]-xx[ids].mean()); yr.extend(yy[ids]-yy[ids].mean())
    obs = corr(xr, yr)
    rng = np.random.default_rng(1402309)
    perm = []
    for _ in range(5000):
        xp = np.concatenate([rng.permutation(xx[ids]-xx[ids].mean()) for ids in good])
        perm.append(corr(xp, yr))
    stats_out["exact_count_strata"] = {"strata": len(good), "n": len(xr), "rho_residual_ranks": obs,
        "permutation_two_sided_p": (1+sum(abs(v)>=abs(obs) for v in perm))/5001}
    result["correlations"] = stats_out
    nf, ni, hf, hi = (arr[k] for k in ("nf", "ni", "hf", "hi"))
    mask = (nf>=10)&(ni>=10)
    pf, pi = hf[mask]/nf[mask], hi[mask]/ni[mask]
    diff = pf-pi
    low = p<.3
    pooled = {"p_feasible": hf.sum()/nf.sum(), "p_infeasible": hi.sum()/ni.sum(),
              "infeasible_fraction": ni.sum()/(nf+ni).sum(), "both_ge10_n": int(mask.sum()),
              "within_mean_diff": float(diff.mean()), "within_median_diff": float(np.median(diff)),
              "within_mean_ci95": boot_stat(lambda ii: float(diff[ii].mean()), len(diff)),
              "within_positive": int((diff>0).sum()), "within_negative": int((diff<0).sum()),
              "within_abs_large_positive": int((diff>.2).sum()), "within_abs_large_negative": int((diff<-.2).sum()),
              "low_p_n": int(low.sum()), "low_p_nf": int(nf[low].sum()), "low_p_ni": int(ni[low].sum()),
              "low_p_feasible": hf[low].sum()/nf[low].sum(), "low_p_infeasible": hi[low].sum()/ni[low].sum(),
              "sample_decomposition_max_error": float(np.max(abs(p-(hf+hi)/(nf+ni))))}
    # Common problem weights: both conditions get the same problems, equally weighted.
    pooled.update(matched_p_feasible=float(pf.mean()), matched_p_infeasible=float(pi.mean()))
    result["feasibility_split"] = pooled
    csvwrite("counterexamples.csv", [dict(id=r["id"], n_vars=r["n_vars"], n_checks=r["n_checks"],
        n_ineq=r["n_ineq"], phi0=r["phi0"], phi256=r["phi256"], p0=r["p0"], p1=r["p1"],
        type="phi1_p_low" if phi[i]==1 else "phi0_p_positive")
        for i,r in enumerate(rows) if (phi[i]==1 and p[i]<.3) or (phi[i]==0 and p[i]>0)])
    # Human comparisons use exactly the same subset for all competing correlations.
    human_out = {}
    for contest in ("all", "AIME", "HMMT", "within_contest"):
        idx = np.array([i for i,r in enumerate(rows) if r["human"] and (contest in ("all", "within_contest") or r["contest"]==contest)])
        h = np.array([float(rows[i]["human"]) for i in idx])
        cc = np.array([rows[i]["contest"] for i in idx])
        xx, yy, zz, pp1 = phi[idx], p[idx], new[idx], p1[idx]
        groups = [np.where(cc==c)[0] for c in sorted(set(cc))]
        def hr(a, b, ii):
            if contest == "within_contest":
                return corr(within_ranks(a[ii], cc[ii]), within_ranks(b[ii], cc[ii]))
            return rho(a[ii], b[ii])
        entry = {"n": len(idx)}
        for name, a, b in (("human_phi0", h, xx), ("human_phi256", h, zz),
                            ("human_p0", h, yy), ("human_p1", h, pp1),
                            ("phi0_p0_same_cases", xx, yy), ("phi256_p1_same_cases", zz, pp1)):
            entry[name] = stat(lambda ii: hr(a,b,ii), len(idx), groups)
        entry["rho_phi_p_minus_abs_rho_phi_human"] = stat(
            lambda ii: hr(xx, yy, ii)-abs(hr(xx, h, ii)), len(idx), groups)
        human_out[contest] = entry
    result["human"] = human_out
    print("correlations and human complete", flush=True)
    # Development-set CV: train y0 on train problems, test y1 on held-out problems.
    base = np.column_stack([dcats(d)] + [arr[k] for k in ("n_ineq", "n_checks", "n_eq")] + [np.log(arr["dsl_len"])])
    models = {"d": dcats(d), "d_phi": np.column_stack([dcats(d), new]),
              "counts": base, "counts_phi": np.column_stack([base, new])}
    preds = {m: np.zeros((10,n)) for m in models}
    cvrows = []
    for repeat in range(10):
        permids = np.random.default_rng([1402303,repeat]).permutation(n)
        for fold, test in enumerate(np.array_split(permids,5)):
            train = np.setdiff1d(np.arange(n),test)
            for name,x in models.items():
                preds[name][repeat,test] = logistic_predict(x[train],p[train],x[test])
        print(f"CV {repeat+1}/10", flush=True)
    losses = {m: -p1[None,:]*np.log(v)-(1-p1[None,:])*np.log1p(-v) for m,v in preds.items()}
    cv = {m: {"log_loss": float(losses[m].mean()), "rmse": float(np.sqrt(np.mean((v-p1[None,:])**2)))} for m,v in preds.items()}
    for name,oldm,newm in (("counts_phi_minus_counts","counts","counts_phi"),("d_phi_minus_d","d","d_phi")):
        diff = (losses[newm]-losses[oldm]).mean(axis=0)
        cv[name] = {"log_loss_delta": float(diff.mean()), "ci95_descriptive": boot_stat(lambda ii:float(diff[ii].mean()),n),
                    "repeat_deltas": (losses[newm]-losses[oldm]).mean(axis=1).tolist()}
    for i,r in enumerate(rows):
        row = dict(id=r["id"], p0=p[i], p1=p1[i], phi256=new[i])
        for m in models:
            row[f"pred_{m}"] = float(preds[m][:,i].mean())
            row[f"loss_{m}"] = float(losses[m][:,i].mean())
        cvrows.append(row)
    csvwrite("cv-predictions.csv",cvrows)
    result["cv"] = cv
    # Sensitivity in the same held-out predictions; these are not refitted models.
    sens = {}
    for name, mask in (("at_least_100_starts_both", (arr["n0"]>=100)&(arr["n1"]>=100)),
                       ("lm_only", arr["n_vars"]<=arr["ir_eq"])):
        ids = np.where(mask)[0]
        sens[name] = {"n": len(ids), "partial_phi256_p1": partial(new[ids],p1[ids],d[ids],[z[ids] for z in controls]),
            "cv_log_loss_counts": float(losses["counts"][:,ids].mean()),
            "cv_log_loss_counts_phi": float(losses["counts_phi"][:,ids].mean())}
    result["sensitivity"] = sens
    dump("stats.json", result)
    print(json.dumps(clean({"counts":result["counts"],"split":pooled,"cv":cv,"human":human_out}),ensure_ascii=False,indent=2),flush=True)


def vector(b, ev, deadline=None):
    tel = smb._SearchTelemetry()
    fn = smb._AugmentedResidualVectorFn(bundle=b, evaluator=ev, n_constraints=len(b.spec.constraints),
        deadline_monotonic=deadline, telemetry=tel, constraint_scales=None)
    return fn,tel


def modified(r, mode, a):
    r = r.copy()
    if mode in ("nohard", "nohard_guard10", "nohard_guard100", "eqonly", "sharpen_nohard"):
        r[-1] = 0
    if mode == "nohard_guard10": r[-2] *= 10
    if mode == "nohard_guard100": r[-2] *= 100
    if mode == "hard100": r[-1] *= .01
    if mode == "eqonly": r[-2] = 0
    if mode in ("sharpen", "sharpen_nohard"):
        r *= 1 + (math.hypot(*r)/a)**2
    return r


def classify(b, ev, box, refs, x, k, tel):
    config = ExternalPipelineConfig.production_baseline_tier(seed=0,total_time_budget_sec=180).search
    cand = smb._build_candidate(evaluator=ev, config=config, bounds=[tuple(r) for r in box],
        values=np.array(x,dtype=float), origin_seed=0, family_code=smb._LM_FAMILY_CODE,
        origin_start_point_index=k, telemetry=tel)
    rec = dict(res=cand.residual_norm_float, guard_ok=bool(cand.guard_ok),
               hard_feasible=cand.hard_feasible, hard_tags=list(cand.hard_violation_tags))
    if "out_of_bounds" in cand.hard_violation_tags: cls = "left_box"
    elif not math.isfinite(cand.residual_norm_float): cls = "nonfinite"
    elif cand.residual_norm_float>1e-8: cls = "stuck"
    elif not (cand.guard_ok and cand.hard_feasible is not False): cls = "wrong_branch"
    else:
        value = answer_float(ev,x)
        rec["answer"] = value
        cls = "hit" if value is not None and any(abs(value-v)<=1e-6*max(1,abs(v)) for v in refs) else "wrong_answer"
    rec["cls"] = cls
    return rec


def solve(b, ev, box, refs, start, a, mode, k):
    t0 = time.monotonic()
    fn,tel = vector(b,ev,t0+30)
    rec = {"mode":mode}
    try:
        tol = 1e-15 if mode=="tight" else 1e-14
        opt = least_squares(lambda x: modified(fn(x),mode,a),start,method="lm",max_nfev=320,
                            ftol=tol,xtol=tol,gtol=tol)
        rec.update(status=int(opt.status),message=opt.message,x=opt.x,scipy_nfev=int(opt.nfev),
                   optimality=float(opt.optimality))
        rec.update(classify(b,ev,box,refs,opt.x,k,tel))
    except (smb._SearchDeadlineExceeded,TimeoutError):
        rec.update(cls="timeout",status=-9)
    except Exception as exc:
        rec.update(cls="error",status=-8,error=repr(exc))
    rec.update(seconds=time.monotonic()-t0,evaluations=tel.evaluation_count,
               eval_failures=tel.failure_count)
    return rec


def penalties():
    data = cases()
    summary, gradients, mismatches = [], [], []
    started = time.monotonic()
    for cid in IDS:
        path = OUT/f"penalty-{cid}.json"
        b, ev, box = context(data[cid])
        refs = reference_values(data[cid]["answer"])
        source = json.loads((B/"replication"/f"{cid}.json").read_text())
        if not path.exists():
            rows = []
            fn,tel = vector(b,ev)
            for k,old in enumerate(source["rows"]):
                x = np.array(old["start"])
                raw = fn(x)
                cols = []
                for j in range(len(x)):
                    h = 1e-5*max(1,abs(x[j]))
                    xp,xm = x.copy(),x.copy()
                    xp[j]+=h; xm[j]-=h
                    cols.append((fn(xp)[-2]-fn(xm)[-2])/(2*h))
                row = {"k":k,"start":x,"start_guard":raw[-2],"start_hard":raw[-1],
                       "start_guard_gradient_norm":math.hypot(*cols)}
                # Deterministic rotated order; all conditions see the identical physical start.
                for j in range(len(MODES)):
                    mode = MODES[(j+k)%len(MODES)]
                    row[mode] = solve(b,ev,box,refs,x,source["a"],mode,k)
                rows.append(row)
                if (k+1)%20==0:
                    print(cid,k+1,{m:sum(r[m]["cls"]=="hit" for r in rows) for m in MODES},flush=True)
            dump(path.name,{"id":cid,"a":source["a"],"source_sha256":sha(B/"replication"/f"{cid}.json"),"rows":rows})
        saved = json.loads(path.read_text())
        rows = saved["rows"]
        base = np.array([r["base"]["cls"]=="hit" for r in rows])
        for k,r in enumerate(rows):
            for mode in ("base","sharpen"):
                if r[mode]["cls"] != source["rows"][k][mode]["cls"]:
                    mismatches.append([cid,k,mode,r[mode]["cls"],source["rows"][k][mode]["cls"]])
        invalid = [r for r in rows if r["start_hard"]>=9999]
        gradients.append(dict(id=cid,invalid_starts=len(invalid),
            nonzero_guard=sum(r["start_guard"]>0 for r in invalid),
            nonzero_guard_gradient=sum(r["start_guard_gradient_norm"]>1e-8 for r in invalid),
            guard_gradient_median=float(np.median([r["start_guard_gradient_norm"] for r in invalid]))))
        for mode in MODES:
            hit = np.array([r[mode]["cls"]=="hit" for r in rows])
            dif = hit.astype(float)-base
            gain,loss = int((hit&~base).sum()),int((base&~hit).sum())
            summary.append(dict(id=cid,mode=mode,n=len(rows),hits=int(hit.sum()),delta=float(dif.mean()),
                ci95=boot_stat(lambda ii:float(dif[ii].mean()),len(dif)),gain=gain,loss=loss,
                mcnemar_unadjusted_p=binomtest(gain,gain+loss,.5).pvalue if gain+loss else 1,
                classes=dict(Counter(r[mode]["cls"] for r in rows)),
                stop_status=dict(Counter(r[mode]["status"] for r in rows)),
                median_evaluations=float(np.median([r[mode]["evaluations"] for r in rows])),
                total_evaluations=sum(r[mode]["evaluations"] for r in rows),
                total_seconds=sum(r[mode]["seconds"] for r in rows)))
    dump("penalty-summary.json",{"rows":summary,"guard_gradients":gradients,
         "existing_B_class_mismatches":mismatches,"seconds_including_reused":time.monotonic()-started})
    print(json.dumps(clean({"rows":summary,"guard_gradients":gradients,"mismatches":mismatches}),ensure_ascii=False,indent=2),flush=True)


def verify():
    man = json.loads((OUT/"manifest.json").read_text())
    changed = [p for p,h in man["inputs"].items() if sha(ROOT/p)!=h]
    data = cases()
    verified,fail = 0,[]
    for cid in IDS:
        b,ev,box = context(data[cid]); refs=reference_values(data[cid]["answer"])
        for r in json.loads((OUT/f"penalty-{cid}.json").read_text())["rows"]:
            for mode in MODES:
                if r[mode]["cls"]=="hit":
                    checked = classify(b,ev,box,refs,np.array(r[mode]["x"]),r["k"],smb._SearchTelemetry())
                    verified += 1
                    if checked["cls"]!="hit": fail.append([cid,r["k"],mode,checked])
    files = sorted(p for p in OUT.rglob("*") if p.is_file())
    dump("verification.json",{"changed_inputs":changed,"hits_reclassified":verified,
         "hit_verification_failures":fail,"total_output_bytes":sum(p.stat().st_size for p in files),
         "largest_file_bytes":max(p.stat().st_size for p in files),
         "code_sha256":sha(__file__)})
    assert not changed and not fail,(changed,fail)
    print("verified",verified,"hits, immutable input hashes unchanged",flush=True)


if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("command",choices=("features","stats","penalties","verify"))
    args=ap.parse_args()
    globals()[args.command]()
