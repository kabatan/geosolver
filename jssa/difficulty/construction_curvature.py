"""Curvature of the rewritten constructions h(u): median |h(u+v) - 2h(u) + h(u-v)| / |v| over random u in the box,
with |v| = 10% of the box width: the error of linearising the construction over one early search step.

Zero means h is affine in the search variables, so the free-point system Y coincides with the
eliminated system E under Gauss-Newton (see theory note T8). Usage: construction_curvature.py OUT.csv CASE...
"""
import csv, json, math, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_basins import answer_float, construction_coordinates  # noqa: E402
from probe_common import build  # noqa: E402
from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds  # noqa: E402

D = Path("benchmarks/extra-variables/dsl")
STEP = 0.1  # step as a fraction of the box width, the scale of early search steps
rows = []
for case in sys.argv[2:]:
    dsl, b, _ = build(D / f"{case}.k0.json")
    y = json.loads((D / f"{case}.k3.json").read_text())
    picks = sorted({v[2:] for v in y["variables"] if v[:2] in ("x_", "y_") and v not in dsl["variables"]})
    hc = construction_coordinates(dsl, picks)
    box = np.array(infer_problem_bounds(b), dtype=float)
    rng = np.random.default_rng(0)
    vals = []
    for _ in range(40):
        u = box[:, 0] + rng.random(len(box)) * (box[:, 1] - box[:, 0])
        v = rng.normal(size=len(box)); v *= STEP * float(np.mean(box[:, 1] - box[:, 0])) / np.linalg.norm(v)
        tot = 0.0; ok = True
        for _, (names, ev) in hc.items():
            f = [answer_float(ev, list(u + s * v)) for s in (1, 0, -1)]
            if any(x is None or not math.isfinite(x) for x in f):
                ok = False; break
            tot += (f[0] - 2 * f[1] + f[2]) ** 2
        if ok:
            vals.append(math.sqrt(tot) / float(np.linalg.norm(v)))
    rows.append({"case_id": case, "picks": " ".join(picks), "curv_median": float(np.median(vals)) if vals else None, "n": len(vals)})
    print(case, rows[-1]["curv_median"])
with open(sys.argv[1], "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
