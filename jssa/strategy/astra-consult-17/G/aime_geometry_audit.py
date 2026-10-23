"""Post-hoc evaluation only: distinguish a disconnected feasible set from a numerical wall."""
from __future__ import annotations

import csv
import json
from collections import Counter

import numpy as np

from common import HERE, case_context, equality, feasible, write_json


def main():
    cid = "AIME-2010-II-14"
    case, bundle, ev, raw, bounds, lo, width = case_context(cid)
    hit = np.array(next(r["x"] for r in raw["records"] if r["cls"] == "hit"))
    details = [json.loads(s) for s in (HERE / "endpoint-diagnostics.jsonl").read_text().splitlines()]
    ks = {r["k"] for r in details if r["id"] == cid and r["cls"] != "hit"}
    data = []
    for r in raw["records"]:
        if r["k"] not in ks:
            continue
        x = np.array(r["x"])
        # SciPy default two-point floating-point perturbation at these positive coordinates.
        h = np.sqrt(np.finfo(float).eps) * np.maximum(1, np.abs(x))
        crosses = []
        for j in range(len(x)):
            xp = x.copy(); xp[j] += h[j]
            if not feasible(ev, xp):
                crosses.append(j)
        f = equality(ev, x)
        row = {"k": r["k"], "p": x[0], "cx": x[1], "cy": x[2],
               "p_face_gap_over_fd": (4-x[0])/h[0],
               "angle_face_gap_over_fd_cy": (x[1]-x[2])/h[2],
               "fd_cross_variables": ";".join(bundle.var_names[j] for j in crosses),
               "fd_cross_any": bool(crosses),
               "eq_ss": float(f@f)}
        for t in [1e-6, 1e-4]:
            xx = (1-t)*x + t*hit
            ff = equality(ev, xx)
            row[f"t{t}_feasible"] = feasible(ev, xx)
            row[f"t{t}_eq_decrease"] = float(f@f-ff@ff)
        row["segment_21_all_feasible"] = all(feasible(ev, (1-t)*x+t*hit) for t in np.linspace(0, 1, 21))
        data.append(row)
    summary = {"n": len(data), "fd_cross": sum(r["fd_cross_any"] for r in data),
               "fd_cross_variables": dict(Counter(r["fd_cross_variables"] for r in data)),
               "segment_all_feasible": sum(r["segment_21_all_feasible"] for r in data),
               "hit": hit.tolist(), "guards": bundle.spec.guards,
               "checks": [c.kind for c in bundle.hard_feasibility_checks],
               "note": "post-hoc; evaluations only; segment sampling alone is not a proof of connectedness"}
    for t in [1e-6, 1e-4]:
        summary[f"t{t}_feasible_descent"] = sum(r[f"t{t}_feasible"] and r[f"t{t}_eq_decrease"] > 0 for r in data)
        summary[f"t{t}_eq_decrease_min"] = min(r[f"t{t}_eq_decrease"] for r in data)
    with (HERE / "aime-finite-difference.csv").open("w") as f:
        w = csv.DictWriter(f, fieldnames=list(data[0])); w.writeheader(); w.writerows(data)
    write_json(HERE / "aime-geometry-summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
