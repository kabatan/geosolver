"""292-problem endpoint census plus input-only one-step diagnostics. No LM runs."""
from __future__ import annotations

import csv
import json
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from common import HERE, RAW, case_context, clean, equality, feasible, hard, write_json


def perturb(ev, x, width, pindex, k, hits):
    n = len(x)
    axes = np.vstack([np.eye(n), -np.eye(n)])
    rng = np.random.default_rng([17001, pindex, k])
    rand = rng.normal(size=(8, n))
    rand /= np.linalg.norm(rand, axis=1)[:, None]
    result = {}
    tags = Counter()
    for eps, ds, name in [(1e-8, axes, "b8"),
                          (1e-6, np.vstack([axes, rand]), "b6"),
                          (1e-4, axes, "b4")]:
        flips = 0
        for direction in ds:
            h = hard(ev, x + eps * width * direction)
            if h is None or not h.hard_feasible:
                flips += 1
                if eps == 1e-6:
                    tags.update(h.failure_tags if h is not None else ["exception"])
        result[name] = int(flips > 0)
        if name == "b6":
            result["flip_fraction"] = flips / len(ds)
    result["tags"] = dict(tags)
    if len(hits):
        dist = np.linalg.norm((hits - x) / width, axis=1)
        j = int(np.argmin(dist))
        z = (hits[j] - x) / width
        norm = float(np.linalg.norm(z))
        result["hit_distance"] = norm
        for eps, name in [(1e-6, "toward6"), (1e-4, "toward4"), (1e-2, "toward2")]:
            result[name] = int(norm > 0 and not feasible(ev, x + min(eps, norm) * width * z / max(norm, 1e-300)))
    return result


def input_diagnostic(ev, lo, width, pindex):
    rng = np.random.default_rng([17002, pindex])
    nf = nq = valid = 0
    for z in rng.random((64, len(lo))):
        x = lo + width * z
        if not feasible(ev, x):
            continue
        nf += 1
        f = equality(ev, x)
        if f is None or not len(f):
            continue
        cols = []
        for j in range(len(x)):
            dx = np.zeros(len(x)); dx[j] = 1e-6 * width[j]
            fp, fm = equality(ev, x + dx), equality(ev, x - dx)
            if fp is None or fm is None or fp.shape != f.shape or fm.shape != f.shape:
                break
            cols.append((fp - fm) / 2e-6)
        if len(cols) != len(x):
            continue
        try:
            step = np.linalg.lstsq(np.column_stack(cols), -f, rcond=None)[0]
        except np.linalg.LinAlgError:
            continue
        snorm = np.linalg.norm(step)
        if not np.isfinite(snorm):
            continue
        if snorm > 0.25:
            step *= 0.25 / snorm
        valid += 1
        crossing = False
        for a in [1.0, 0.5, 0.25, 0.125]:
            xx = x + a * width * step
            ff = equality(ev, xx)
            if ff is not None and ff @ ff < f @ f and not feasible(ev, xx):
                crossing = True
        nq += crossing
    return {"probe_feasible": nf, "probe_valid_gn": valid, "probe_cross": nq,
            "phi_probe": nf / 64, "Q": nq / valid if valid else None}


def one_case(task):
    pindex, cid = task
    t0 = time.monotonic()
    case, bundle, ev, raw, bounds, lo, width = case_context(cid)
    dsl = case["dsl"]
    conditions = dsl["conditions"]
    inequalities = [c for c in conditions if c.get("operator") != "="]
    text = json.dumps(inequalities)
    ct = Counter(c.kind for c in bundle.hard_feasibility_checks)
    result = {"id": cid, "n_vars": len(lo), "n_eq": len(bundle.spec.constraints),
              "method": "LM" if len(lo) <= len(bundle.spec.constraints) else "Powell",
              "n_guards": len(bundle.spec.guards), "n_checks": len(bundle.hard_feasibility_checks),
              "n_strict": sum(c.get("operator") in ["<", ">"] for c in inequalities),
              "n_not_equal": sum(c.get("operator") == "!=" for c in inequalities),
              "angle_guard": int("Angle(" in text), "area_guard": int("Area(" in text),
              "product_guard": int("*" in text), "predicate_guard": int(any("predicate" in c for c in inequalities))}
    for kind in ["guard", "line_distinct", "triangle_nondegenerate", "intersection_exclude_distinct", "intersection_selection_trace"]:
        result[f"checks_{kind}"] = ct[kind]
    records = raw["records"]
    hits = np.array([r["x"] for r in records if r.get("cls") == "hit" and "x" in r])
    detail = []
    nF = hF = nI = hI = 0
    classes = Counter()
    bcounts = Counter()
    endF = 0
    ffailed = 0
    hits_tested = 0
    margins = []
    for r in records:
        if "start" not in r:
            continue
        F = feasible(ev, r["start"])
        hit = r["cls"] == "hit"
        if F:
            nF += 1; hF += hit
            classes[r["cls"]] += 1
        else:
            nI += 1; hI += hit
        if not F:
            continue
        if hit and hits_tested >= 10:
            continue
        entry = {"id": cid, "k": r["k"], "cls": r["cls"], "end_feasible": None}
        if "x" not in r or not np.isfinite(r["x"]).all():
            detail.append(entry)
            continue
        x = np.array(r["x"])
        ef = feasible(ev, x)
        entry["end_feasible"] = ef
        if not hit:
            ffailed += 1
            endF += ef
        else:
            hits_tested += 1
            try:
                margin = ev.evaluate_float_hard_feasibility(list(x), include_margins=True).min_margin
                if margin is not None and np.isfinite(float(margin)):
                    margins.append(float(margin))
            except Exception:
                pass
        if ef:
            diag = perturb(ev, x, width, pindex, r["k"], hits)
            entry.update(diag)
            category = "hit" if hit else "fail"
            for flag in ["b8", "b6", "b4", "toward6", "toward4", "toward2"]:
                bcounts[f"{category}_{flag}"] += diag.get(flag, 0)
            if not hit and r["cls"] == "stuck":
                bcounts["wall_count"] += diag["b6"]
        detail.append(entry)
    result.update(n_F=nF, hit_F=hF, n_I=nI, hit_I=hI,
                  p_F=hF/nF if nF else None, p_I=hI/nI if nI else None,
                  p=(hF+hI)/(nF+nI) if nF+nI else None,
                  gap=hF/nF-hI/nI if nF and nI else None,
                  F_failed_finite=ffailed, F_failed_endF=endF, hit_tested=hits_tested,
                  hit_min_margin_median=float(np.median(margins)) if margins else None,
                  W=bcounts["wall_count"]/nF if nF else None)
    for k in ["hit", "stuck", "wrong_answer", "wrong_branch", "left_box", "error"]:
        result[f"F_{k}"] = classes[k]
    result.update(bcounts)
    result.update(input_diagnostic(ev, lo, width, pindex))
    result["seconds"] = time.monotonic()-t0
    return clean(result), clean(detail)


def main():
    ids = [p.stem for p in sorted(RAW.glob("*.json"))
           if json.loads(p.read_text()).get("n_vars", 0) > 0]
    results = []
    # Only the parent writes files; workers only evaluate read-only inputs.
    with (HERE / "endpoint-diagnostics.jsonl").open("w") as fd:
        with ProcessPoolExecutor(max_workers=4) as pool:
            for result, detail in pool.map(one_case, enumerate(ids), chunksize=1):
                results.append(result)
                for row in detail:
                    fd.write(json.dumps(row, ensure_ascii=False) + "\n")
                fd.flush()
                print(len(results), result["id"], "W", result["W"], "Q", result["Q"], flush=True)
    write_json(HERE / "census.json", results)
    cols = sorted({k for r in results for k in r})
    with (HERE / "census.csv").open("w") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(results)


if __name__ == "__main__":
    main()
