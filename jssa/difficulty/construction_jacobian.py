"""Size of the construction Jacobian H = dh/du for the rewritten points, and how much it inflates
the LM column scale of the u-variables in the free-point system Y.

For each start u0 (same RNG as probe_common), compute by central differences
  H (2q x d) and J_R (m x d, equality residuals of E),
and report median over starts of  ratio_j = |[J_R; -H] e_j| / |J_R e_j|  (median over j).
Usage: [KDIR=dir K=k] construction_jacobian.py OUT.csv CASE...
"""
import csv, math, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_basins import answer_float, construction_coordinates  # noqa: E402
from probe_common import build  # noqa: E402
from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds  # noqa: E402
import json

import os
D = Path(os.environ.get("KDIR", "benchmarks/extra-variables/dsl"))
K = os.environ.get("K", "3")
rows = []
for case in sys.argv[2:]:
    dsl, b, ev = build(D / f"{case}.k0.json")
    y = json.loads((D / f"{case}.k{K}.json").read_text())
    picks = sorted({v[2:] for v in y["variables"] if v[:2] in ("x_", "y_") and v not in dsl["variables"]})
    hc = construction_coordinates(dsl, picks)
    box = np.array(infer_problem_bounds(b), dtype=float)
    n = len(box)

    def h(u):
        return np.array([answer_float(e, list(u)) if True else 0 for _, (names, e) in hc.items()], dtype=float)

    def r(u):
        return np.array(ev.evaluate_float_residual(list(u)).residual_vector, dtype=float)

    hn, ratios = [], []
    for k in range(30):
        rng = np.random.default_rng([0, k])
        u = box[:, 0] + rng.random(n) * (box[:, 1] - box[:, 0])
        try:
            H = np.column_stack([(h(u + 1e-6 * e) - h(u - 1e-6 * e)) / 2e-6 for e in np.eye(n)])
            J = np.column_stack([(r(u + 1e-6 * e) - r(u - 1e-6 * e)) / 2e-6 for e in np.eye(n)])
        except Exception:
            continue
        if not (np.all(np.isfinite(H)) and np.all(np.isfinite(J))):
            continue
        hn.append(np.linalg.norm(H))
        cj = np.linalg.norm(J, axis=0); cy = np.sqrt(cj ** 2 + np.linalg.norm(H, axis=0) ** 2)
        ok = cj > 0
        if ok.any():
            ratios.append(float(np.median(cy[ok] / cj[ok])))
    rows.append({"case_id": case, "H_fro_median": float(np.median(hn)) if hn else None,
                 "col_inflation_median": float(np.median(ratios)) if ratios else None, "n": len(hn)})
    print(rows[-1])
with open(sys.argv[1], "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
