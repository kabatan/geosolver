"""Read-only exploratory census. Only writes into this script's directory.

No seed-1 local outcomes are read here. No solver is run.
"""
from pathlib import Path
import csv
import hashlib
import json
import math
from collections import defaultdict
import numpy as np
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
manifest = []


def read_bytes(rel):
    p = ROOT / rel
    b = p.read_bytes()
    manifest.append({"path": rel, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()})
    return b


def table(rel):
    import io
    def convert(v):
        if v is None or v == "": return None
        if v in ["True", "False"]: return v == "True"
        try: return int(v)
        except ValueError: pass
        try: return float(v)
        except ValueError: return v
    return [{k:convert(v) for k,v in r.items()} for r in csv.DictReader(io.StringIO(read_bytes(rel).decode()))]


def write_csv(name, rows):
    if not rows: return
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with (OUT / name).open("w") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader(); w.writerows(rows)


def avg(xs):
    xs = [x for x in xs if x is not None and np.isfinite(x)]
    return float(np.mean(xs)) if xs else None


def median(xs):
    xs = [x for x in xs if x is not None and np.isfinite(x)]
    return float(np.median(xs)) if xs else None


def grouped(rows, key):
    g = defaultdict(list)
    for r in rows: g[r[key]].append(r)
    return sorted(g.items(), key=lambda kv: (kv[0] is None, kv[0] if kv[0] is not None else 0))


def bin_left(x, bounds):
    for a,b in zip(bounds[:-1], bounds[1:]):
        if a <= x < b: return f"[{a},{b})"
    return "missing"


def dump(name, obj):
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str) + "\n")


def summarize(df, col):
    rows=[]
    for v,rs in grouped(df,col):
        p=[r['p'] for r in rs]
        rows.append({col:v,"problems":len(rs),"starts":sum(r['n'] for r in rs),"hits":sum(r['h'] for r in rs),
            "p_mean":avg(p),"p_median":median(p),"p_q10":float(np.quantile(p,.1)),"p_q90":float(np.quantile(p,.9)),
            "p_zero":p.count(0),"p_one":p.count(1),"truncated":sum(r['n']<200 for r in rs),
            "left":avg([r['left_box'] for r in rs]),"stuck":avg([r['stuck'] for r in rs]),
            "full_correct":sum(r['full_correct'] for r in rs),"full_runs":sum(r['full_runs'] for r in rs),
            "wall_median":median([r['full_wall'] for r in rs])})
    return rows


def fit_predict(kind, d, y, target):
    def predict(theta, x):
        if kind == "exponential":
            # p=a exp[-b(d-1)], a in (0,1), b>=0.
            return 1 / (1 + np.exp(-theta[0])) * np.exp(-theta[1] * (x-1))
        if kind == "power":
            return 1 / (1 + np.exp(-theta[0])) * x ** (-theta[1])
        if kind == "logistic":
            return 1 / (1 + np.exp(-(theta[0] - theta[1] * x)))
        if kind == "step":
            return np.where(x <= theta[2], theta[0], theta[1])
        if kind == "constant":
            return np.repeat(theta[0], len(x))
    if kind == "constant":
        theta = [float(y.mean())]
    elif kind == "step":
        trials = []
        for t in range(1, 9):
            a, b = y[d <= t], y[d > t]
            if len(a) < 10 or len(b) < 10:
                continue
            th = [float(a.mean()), float(b.mean()), t]
            trials.append((float(np.mean((y - predict(th, d))**2)), th))
        theta = min(trials, key=lambda x: x[0])[1]
    else:
        res = minimize(lambda th: np.mean((y - predict(th, d))**2), [1., .2],
                       method="L-BFGS-B", bounds=[(-12, 12), (0, 8)])
        if not res.success:
            raise RuntimeError((kind, res.message))
        theta = res.x.tolist()
    return predict(theta, target), theta


def main():
    census = table("jssa/difficulty/minima/basins-323.csv")
    rows = []
    audits = []
    for cr in census:
        cid = cr['id']
        rel = f"jssa/difficulty/minima/raw-323/{cid}.json"
        obj = json.loads(read_bytes(rel))
        rec = obj.get("records", [])
        d = obj["n_vars"]
        if not d:
            continue
        n = len(rec)
        h = sum(r["cls"] == "hit" for r in rec)
        cnt = {c: sum(r["cls"] == c for r in rec) for c in set(r["cls"] for r in rec)}
        audits.append({"id": cid, "counts_agree": cnt == obj["counts"],
                       "p_agrees": abs(h/n - obj["p_any"]) < 1e-12,
                       "records": n, "trajectory_present": any("trajectory" in r or "trace" in r for r in rec)})
        r = {"id": cid, "d": d, "m": obj["n_constraints"], "n": n, "h": h, "p": h/n,
             "alpha": obj["n_constraints"] / d,
             "p_first20": np.mean([a["cls"] == "hit" for a in rec[:20]]) if n >= 20 else np.nan,
             "nfev_med": np.median([a["nfev"] for a in rec]),
             "contest": cid.split("-")[0].upper()}
        for c in ["left_box", "stuck", "wrong_branch", "wrong_answer", "error", "no_candidate"]:
            r[c] = cnt.get(c, 0) / n
        rows.append(r)
    df = rows
    exact = table("jssa/strategy/astra-consult-17/H/sources/comparison-cases.csv")
    stages = table("jssa/results/stage-profile-20261023/per-case.csv")
    full = dict(grouped(stages,'case_id'))
    feas = table("jssa/difficulty/start-feasibility-1023/per-problem.csv")
    answer = table("jssa/strategy/astra-consult-18/q21b-number-theory/problem-summary.csv")
    for source,keys in [(exact,['poly_vars','poly_eqs','max_degree','bezout','msolve_class','real_solutions','msolve_s']),
                        (feas,['n_feas','n_infeas','hit_feas','hit_infeas','n_checks']),
                        (answer,['degree','height','first_correct_grid','stable_correct_grid'])]:
        lookup={r['id']:r for r in source}
        assert len(lookup)==len(source)
        for r in df: r.update({k:lookup[r['id']][k] for k in keys})
    for r in df:
        fs=full[r['id']]
        r.update(full_correct=sum(x['correct'] for x in fs),full_runs=len(fs),
                 full_wall=median([x['wall_time_s'] for x in fs]),refinement_s=median([x['refinement_time_s'] for x in fs]),
                 identify_s=median([x['identification_verification_time_s'] for x in fs]))
        r['phi']=r['n_feas']/r['n']
        r['pF']=r['hit_feas']/r['n_feas'] if r['n_feas'] else None
        r['pI']=r['hit_infeas']/r['n_infeas'] if r['n_infeas'] else None
        r['alpha_bin']=bin_left(r['alpha'],[-math.inf,1,1.25,1.5,1.75,2,math.inf])
        r['large_poly']=(r['poly_vars'] or 0)>=10 or (r['max_degree'] or 0)>=8
        D=r['max_degree']
        r['degree_bin']='missing' if D is None else ('<=2' if D<=2 else '2<D<=4' if D<=4 else '4<D<=8' if D<=8 else '>8')
    write_csv('census-seed0.csv',df)
    audit = {"problems": len(census), "variable_problems": len(df), "starts": sum(r['n'] for r in df),
             "hits": sum(r['h'] for r in df), "raw_consistent": all(a["counts_agree"] and a["p_agrees"] for a in audits),
             "n_min": min(r['n'] for r in df), "n_lt200": sum(r['n']<200 for r in df), "n_lt20": sum(r['n']<20 for r in df),
             "full_runs":len(stages), "full_correct":sum(r['correct'] for r in stages),
             "trajectory_fields_present":sum(a["trajectory_present"] for a in audits)}
    dump("data-audit.json", audit)
    for key in ["d", "m", "alpha_bin", "degree_bin", "degree", "large_poly", "msolve_class", "contest"]:
        s = summarize(df, key)
        write_csv(f'by-{key}.csv',s)
        if key in ["d", "alpha_bin", "degree_bin", "degree", "msolve_class"]:
            print('GROUP',key,json.dumps(s))
    strat,feasible=[],[]
    for d,rs in grouped(df,'d'):
        for flag in [False,True]:
            sub=[r for r in rs if r['large_poly']==flag]
            if sub: strat.append({'d':d,'large_poly':flag,'n':len(sub),'p':avg([r['p'] for r in sub]),
                'phi':avg([r['phi'] for r in sub]),'pF':avg([r['pF'] for r in sub]),'pI':avg([r['pI'] for r in sub]),
                'wall':median([r['full_wall'] for r in sub])})
        f={'d':d,'n':len(rs),'phi':avg([r['phi'] for r in rs]),
           'mean_pF':avg([r['pF'] for r in rs]),'mean_pI':avg([r['pI'] for r in rs]),'p20':avg([r['p_first20'] for r in rs])}
        for k in ['n_feas','n_infeas','hit_feas','hit_infeas']: f[k]=sum(r[k] for r in rs)
        f['pooled_pF']=f['hit_feas']/f['n_feas'] if f['n_feas'] else None
        f['pooled_pI']=f['hit_infeas']/f['n_infeas'] if f['n_infeas'] else None
        feasible.append(f)
    write_csv('dimension-polynomial.csv',strat)
    write_csv('dimension-feasibility.csv',feasible)
    print('FEASIBILITY',json.dumps(feasible))
    # Whole-problem folds: no start-level leakage or assumption of 55k independent problems.
    folds = np.array([int(hashlib.sha256(r['id'].encode()).hexdigest()[:8], 16)%5 for r in df])
    d, y = np.array([r['d'] for r in df],float),np.array([r['p'] for r in df],float)
    fits, errors = [], [{k:r[k] for k in ['id','d','p']} for r in df]
    for kind in ["constant", "exponential", "power", "logistic", "step"]:
        pred, params = fit_predict(kind, d, y, d)
        cv = np.empty(len(y))
        for k in range(5):
            cv[folds==k], _ = fit_predict(kind, d[folds!=k], y[folds!=k], d[folds==k])
        fits.append({"model": kind, "parameters":params, "rmse_in":float(np.sqrt(np.mean((y-pred)**2))),
                     "rmse_cv":float(np.sqrt(np.mean((y-cv)**2))), "mae_cv":float(np.mean(abs(y-cv)))})
        for r,cvp in zip(errors,cv): r[kind]=cvp
    write_csv('curve-cv-predictions.csv',errors)
    dump("curve-fits.json", fits)
    # Counts of robustly large ranking inversions, without pairwise independence claims.
    inversions = []
    for a in df:
        for b in df:
            if b['d'] >= a['d']+2 and b['p'] >= a['p']+.5:
                inversions.append({"low_id":a['id'],"high_id":b['id'],"d_low":a['d'],"d_high":b['d'],"p_low":a['p'],"p_high":b['p']})
    write_csv('dimension-inversions.csv',inversions)
    # Existing expansion comparison: actual N can be < requested N.
    exp = table("jssa/difficulty/holdout-1023/out/scored.csv")
    exp=[{'id':r['case_id'],**{k:r[k] for k in ['picks','col_inflation','N','pE','pY','pZ']}} for r in exp]
    for r in exp:
        r['deltaY']=r['pY']-r['pE'];r['deltaZ']=r['pZ']-r['pE']
    write_csv('expansion.csv',exp)
    print('EXPANSION',json.dumps(sorted(exp,key=lambda r:r['deltaY'],reverse=True)[:8]))
    print('POLY WITHIN D',json.dumps(strat))
    print("AUDIT",json.dumps(audit))
    print("FITS",json.dumps(fits))
    print("INVERSION",len(inversions),"unique ids",len(set(r[k] for r in inversions for k in ['low_id','high_id'])))
    dump("input-manifest.json", manifest)


if __name__ == "__main__":
    main()
