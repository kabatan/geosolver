"""Output-specific conditioning at saved first-hit endpoints; no local search.

All writes are local to this directory. See protocol.md for definitions.
"""
from __future__ import annotations

import csv
import argparse
import hashlib
import json
import math
import platform
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "jssa/difficulty"))

import numpy as np
import scipy
from mpmath import mp
from scipy.stats import rankdata, spearmanr

from geosolver import GeometryProblem
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from probe_basins import answer_float


def read_csv(path):
    with Path(path).open() as f:
        return list(csv.DictReader(f))


def write_csv(path, rows):
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with Path(path).open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def finite(v):
    try:
        return math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


def correlation(rows, x, y, adjust=()):
    use = [r for r in rows if all(finite(r.get(k)) for k in [x, y, *adjust])]
    if len(use) < 5:
        return {"n": len(use), "rho": None}
    a = rankdata([float(r[x]) for r in use])
    b = rankdata([float(r[y]) for r in use])
    if adjust:
        design = np.column_stack([np.ones(len(use)), *[rankdata([float(r[k]) for r in use]) for k in adjust]])
        a -= design @ np.linalg.lstsq(design, a, rcond=None)[0]
        b -= design @ np.linalg.lstsq(design, b, rcond=None)[0]
    rho = float(np.corrcoef(a, b)[0, 1])
    rng = np.random.default_rng(102314)
    vals = []
    for _ in range(1000):
        ix = rng.integers(len(use), size=len(use))
        if np.std(a[ix]) and np.std(b[ix]):
            vals.append(np.corrcoef(a[ix], b[ix])[0, 1])
    return {"n": len(use), "rho": rho, "bootstrap_residual_rank_ci": np.quantile(vals, [.025, .975]).tolist()}


def measure(evaluator, x, h, arithmetic="hp"):
    x = np.asarray(x, float)
    scale = np.maximum(1, np.abs(x))
    f0 = np.asarray(evaluator.evaluate_float_residual(x.tolist()).residual_vector, float)
    t0 = answer_float(evaluator, x)
    if t0 is None or not np.isfinite(f0).all() or not math.isfinite(t0):
        raise ValueError("non-finite anchor")
    jcols, gg = [], []
    for j in range(len(x)):
        xp, xm = x.copy(), x.copy()
        xp[j] += h * scale[j]
        xm[j] -= h * scale[j]
        if arithmetic == "float":
            fp = np.asarray(evaluator.evaluate_float_residual(xp.tolist()).residual_vector, float)
            fm = np.asarray(evaluator.evaluate_float_residual(xm.tolist()).residual_vector, float)
            col = (fp - fm) / (2 * h)
        else:
            # Subtract before conversion to float: identity constraints otherwise
            # get amplified from roundoff-sized rows to norm one.
            with mp.workdps(60), high_precision_mode():
                xx = [mp.mpf(repr(float(v))) for v in x]
                step = mp.mpf(repr(h)) * mp.mpf(repr(float(scale[j])))
                xxp, xxm = list(xx), list(xx)
                xxp[j] += step
                xxm[j] -= step
                fp = evaluator.evaluate_hp_residual(xxp, precision=60).residual_vector
                fm = evaluator.evaluate_hp_residual(xxm, precision=60).residual_vector
                hpcol = [(a-b)/(2*mp.mpf(repr(h))) for a,b in zip(fp,fm)]
            col = np.asarray([float(v) for v in hpcol])
        tp, tm = answer_float(evaluator, xp), answer_float(evaluator, xm)
        if tp is None or tm is None:
            raise ValueError("undefined target at difference point")
        jcols.append(col)
        gg.append((tp - tm) / (2 * h * max(1, abs(t0))))
    jmat = np.column_stack(jcols)
    rownorm = np.linalg.norm(jmat, axis=1)
    rownorm = np.where(rownorm > 1e-14, rownorm, 1)
    jmat = jmat / rownorm[:, None]
    g = np.asarray(gg)
    if not np.isfinite(jmat).all() or not np.isfinite(g).all() or not jmat.size:
        raise ValueError("empty or non-finite Jacobian")
    u, s, vh = np.linalg.svd(jmat, full_matrices=True)
    rank = int(np.sum(s > s[0] * 1e-8)) if s[0] else 0
    normg = np.linalg.norm(g)
    null = float(np.linalg.norm(vh[rank:] @ g) / normg) if normg else 0.
    target_cond = float(np.linalg.norm((vh[:rank] @ g) / s[:rank])) if rank else 0.
    full = rank == len(x)
    q = float(target_cond * s[-1] / normg) if full and normg > 1e-12 else None
    vals = {"rank": rank, "nullity": len(x)-rank, "smax": float(s[0]),
            "smin": float(s[-1]) if len(s)==len(x) else 0.,
            "cond_nonzero": float(s[0]/s[rank-1]) if rank else None,
            "cond_full": float(s[0]/s[-1]) if full else None,
            "g_norm": float(normg), "g_null_ratio": null, "target_cond": target_cond,
            "q": q, "res": float(np.linalg.norm(f0)), "target": t0,
            "weak_target_projection": float(abs(vh[-1] @ g)),
            "g_zero": bool(normg < 1e-12),
            "candidate": bool((not full and null <= 1e-5) or (q is not None and q < .01))}
    detail = {"x": x.tolist(), "scale": scale.tolist(), "row_scale": rownorm.tolist(),
              "g": g.tolist(), "s": s.tolist(), "vh": vh.tolist(), "j": jmat.tolist()}
    return vals, detail


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--arithmetic", choices=("hp", "float"), default="hp")
    args = parser.parse_args()
    started = time.monotonic()
    cases = {c["id"]: c for c in map(json.loads, (ROOT / "benchmarks/cases.jsonl").read_text().splitlines())}
    human = {r["case_id"]: r for r in read_csv(ROOT / "jssa/difficulty/ghost-1023/human_feat.csv")}
    stages = defaultdict(list)
    for r in read_csv(ROOT / "jssa/results/stage-profile-20261023/per-case.csv"):
        stages[r["case_id"]].append(r)
    rows, details, errors, files = [], {}, [], []
    for path in sorted((ROOT / "jssa/difficulty/minima/raw-323").glob("*.json")):
        data = json.loads(path.read_text())
        cid = data["case_id"]
        if not data.get("n_vars", 0) or not data.get("first_hit"):
            continue
        t0 = time.monotonic()
        files.append(path)
        hit = data["first_hit"][sorted(data["first_hit"], key=int)[0]]
        row = {"id": cid, "n_vars": data["n_vars"], "n_constraints": data["n_constraints"],
               "p0": data["p_any"], "first_hit_k0": hit["k"],
               "human": human.get(cid, {}).get("human", ""), "contest": human.get(cid, {}).get("contest", "")}
        for f in ["refinement_time_s", "identification_verification_time_s", "wall_time_s",
                  "candidates_sent_to_refinement", "candidates_converged"]:
            row[f] = float(np.median([float(s[f]) for s in stages[cid]]))
        row["conv_fraction"] = row["candidates_converged"] / max(1, row["candidates_sent_to_refinement"])
        try:
            bundle = load_problem_bundle(GeometryProblem.model_validate(cases[cid]["dsl"]).engine_document())
            ev = build_ir_evaluator(bundle)
            a, detail = measure(ev, hit["x"], 1e-6, args.arithmetic)
            b, _ = measure(ev, hit["x"], 1e-5, args.arithmetic)
            row.update(a)
            row.update(rank_h5=b["rank"], q_h5=b["q"], g_null_ratio_h5=b["g_null_ratio"],
                       candidate_h5=b["candidate"], rank_stable=a["rank"]==b["rank"])
            details[cid] = {**detail, "var_names": list(bundle.var_names), "h6": a, "h5": b}
            p1path = ROOT / "jssa/difficulty/minima/raw-323-seed1" / path.name
            if p1path.exists():
                files.append(p1path)
                d1 = json.loads(p1path.read_text())
                row["p1"] = d1.get("p_any")
                if d1.get("first_hit"):
                    hit1 = d1["first_hit"][sorted(d1["first_hit"], key=int)[0]]
                    aa, dd = measure(ev, hit1["x"], 1e-6, args.arithmetic)
                    row.update(rank_seed1=aa["rank"], q_seed1=aa["q"], g_null_ratio_seed1=aa["g_null_ratio"],
                               candidate_seed1=aa["candidate"])
                    details[cid]["seed1"] = {**dd, "measurement": aa}
            row["status"] = "ok"
        except Exception as exc:
            row.update(status="error", error=f"{type(exc).__name__}: {exc}")
            errors.append({"id": cid, "error": row["error"]})
        row["elapsed_sec"] = time.monotonic()-t0
        rows.append(row)
        if len(rows) % 25 == 0:
            print(f"{len(rows)} anchors, elapsed={time.monotonic()-started:.1f}s", flush=True)
    prefix = "binary64-" if args.arithmetic=="float" else ""
    write_csv(HERE / (prefix+"survey.csv"), rows)
    (HERE / (prefix+"survey-details.json")).write_text(json.dumps(details, indent=2)+"\n")
    good = [r for r in rows if r["status"]=="ok"]
    stats = {"n_anchors": len(rows), "n_ok": len(good), "errors": errors,
             "rank_unstable": [r["id"] for r in good if not r["rank_stable"]],
             "rank_deficient": [r["id"] for r in good if r["nullity"]],
             "candidates": [r["id"] for r in good if r["candidate"]],
             "full_rank_q001": [r["id"] for r in good if r["q"] is not None and r["q"] < .01],
             "zero_gradient": [r["id"] for r in good if r["g_zero"]],
             "correlations": {}, "elapsed_sec": time.monotonic()-started}
    for feature in ["cond_full", "target_cond", "q", "g_null_ratio", "nullity"]:
        for outcome in ["p1", "refinement_time_s", "conv_fraction"]:
            for adjust in [(), ("n_vars", "n_constraints")]:
                key = f"{feature}:{outcome}" + (":adjusted" if adjust else "")
                stats["correlations"][key] = correlation(good, feature, outcome, adjust)
        for contest in ["AIME", "HMMT"]:
            stats["correlations"][f"{feature}:human:{contest}"] = correlation([r for r in good if r["contest"]==contest], feature, "human")
    (HERE / (prefix+"survey-stats.json")).write_text(json.dumps(stats, indent=2, allow_nan=True)+"\n")
    print(json.dumps({k:v for k,v in stats.items() if k not in {"correlations", "errors"}}, indent=2), flush=True)
    manifest_files = [ROOT / "benchmarks/cases.jsonl", ROOT / "jssa/difficulty/ghost-1023/human_feat.csv",
                      ROOT / "jssa/results/stage-profile-20261023/per-case.csv", *files,
                      *sorted((ROOT / "src").rglob("*.py"))]
    manifest = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in manifest_files}
    (HERE / "input-sha256.json").write_text(json.dumps(manifest, indent=2)+"\n")
    (HERE / (prefix+"environment.json")).write_text(json.dumps({"python": sys.version, "executable": sys.executable,
        "platform": platform.platform(), "numpy": np.__version__, "scipy": scipy.__version__, "mpmath": mp.dps,
        "survey_sec": time.monotonic()-started, "arithmetic": args.arithmetic}, indent=2)+"\n")


if __name__ == "__main__":
    main()
