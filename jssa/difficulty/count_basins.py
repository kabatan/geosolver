"""Cluster the end points saved by probe_basins.py into basins (valleys) and count them.

Usage: python count_basins.py DIR_323 DIR_60 OUT_DIR

An end point is one local search finishing.  Points are normalised by the search box
and joined (single linkage) when their max-norm distance is below EPS.  Runs that left
the box or failed to evaluate are counted together as 'left_box' / 'error' and are not
clustered.  A basin is called reliable when at least two end points fall in it.
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.stats import spearmanr

EPS = 1e-3


def basins(rec_list, lo, hi):
    pts = [r for r in rec_list if "x" in r and r["cls"] in ("hit", "wrong_answer", "wrong_branch", "stuck")]
    out = {"n_pts": len(pts), "clusters": []}
    if not pts:
        return out
    X = (np.array([r["x"] for r in pts]) - lo) / (hi - lo)
    lab = np.ones(len(pts), int) if len(pts) == 1 else fcluster(linkage(X, "single", metric="chebyshev"), EPS, "distance")
    for c in sorted(set(lab)):
        idx = np.where(lab == c)[0]
        cls = [pts[i]["cls"] for i in idx]
        res = [pts[i].get("res", float("nan")) for i in idx]
        top = max(set(cls), key=cls.count)
        out["clusters"].append({"size": len(idx), "cls": top, "res_med": float(np.nanmedian(res)),
                                "mixed": len(set(cls)) > 1})
    out["clusters"].sort(key=lambda c: -c["size"])
    return out


def levels(rec_list, rel=0.02):
    """Group stuck end points by residual value (log scale, relative width ``rel``).

    A valley floor that is a curve (degenerate direction) gives many positions but one
    residual level, so levels count distinct local minima values robustly."""
    res = sorted(r["res"] for r in rec_list if r["cls"] == "stuck" and "res" in r and r["res"] > 0)
    groups = []
    for v in res:
        if groups and v <= groups[-1][-1] * (1 + rel):
            groups[-1].append(v)
        else:
            groups.append([v])
    return sorted((len(g) for g in groups), reverse=True)


def process(dirpath):
    rows = []
    for f in sorted(Path(dirpath).glob("*.json")):
        d = json.loads(f.read_text())
        row = {"id": f.stem, "status": d.get("status"), "n_vars": d.get("n_vars", 0)}
        if d.get("status") != "ok":
            rows.append(row); continue
        recs = d["records"]
        n = len(recs)
        b = basins(recs, np.array([x[0] for x in d["box"]]), np.array([x[1] for x in d["box"]]))
        cl = b["clusters"]
        cnt = d["counts"]
        correct = [c for c in cl if c["cls"] == "hit"]
        row.update({
            "n_starts": n, "p": cnt.get("hit", 0) / n,
            "frac_left_box": cnt.get("left_box", 0) / n, "frac_error": cnt.get("error", 0) / n,
            "frac_stuck": cnt.get("stuck", 0) / n, "frac_wrong_answer": cnt.get("wrong_answer", 0) / n,
            "frac_wrong_branch": cnt.get("wrong_branch", 0) / n,
            "n_basins": len(cl), "n_basins_ge2": sum(c["size"] >= 2 for c in cl),
            "n_correct_basins": len(correct), "n_wrong_basins_ge2": sum(c["size"] >= 2 for c in cl if c["cls"] != "hit"),
            "top_wrong_share": max([c["size"] for c in cl if c["cls"] != "hit"] or [0]) / n,
            "wrong_basin_sizes": ";".join(str(c["size"]) for c in cl if c["cls"] != "hit")[:200],
            "correct_basin_sizes": ";".join(str(c["size"]) for c in correct),
        })
        lv = levels(recs)
        row.update({"n_levels": len(lv), "n_levels_ge2": sum(v >= 2 for v in lv),
                    "top_level_share": (lv[0] / n) if lv else 0.0,
                    "stuck_in_levels_ge2": sum(v for v in lv if v >= 2) / n})
        k = f.stem.rsplit(".k", 1)
        row["k"] = int(k[1]) if len(k) == 2 else ""
        rows.append(row)
    return rows


def main():
    d323, d60, out = sys.argv[1:4]
    Path(out).mkdir(parents=True, exist_ok=True)
    for name, d in (("basins-323", d323), ("basins-extra60", d60)):
        rows = process(d)
        keys = list(dict.fromkeys(k for r in rows for k in r))
        with open(Path(out) / f"{name}.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, keys); w.writeheader(); w.writerows(rows)
        ok = [r for r in rows if r.get("status") == "ok"]
        print(name, len(rows), "ok", len(ok))
        for a, b in (("n_vars", "n_basins_ge2"), ("n_vars", "p"), ("p", "n_basins_ge2"), ("n_vars", "n_basins"), ("p", "n_basins"),
                     ("p", "top_wrong_share"), ("n_vars", "n_levels_ge2"), ("p", "n_levels_ge2"), ("p", "stuck_in_levels_ge2")) + ((("k", "n_basins_ge2"), ("k", "p")) if name.endswith("60") else ()):
            x = [r[a] for r in ok if r[a] != ""]; y = [r[b] for r in ok if r[a] != ""]
            if len(set(x)) > 1 and len(set(y)) > 1:
                print("  spearman %s vs %s = %.2f (n=%d)" % (a, b, spearmanr(x, y)[0], len(x)))


if __name__ == "__main__":
    main()
