"""Diagnose individual starts of the common-start comparison: where each system ends and why.

For each start k (same u0 rule as probe_common), run E, Y, Z and report for the endpoint:
  orig  - norm of the original equality residuals (first m rows, the conditions of E),
  cons  - norm of the construction rows (Y: y - h(u) characterisation; Z: offsets),
  E_at_u- norm of E's residual at the endpoint's u (i.e. if the points were put back on h(u)),
  tau   - answer value, guard, in_region, stop status, nfev.
Usage: diagnose_endpoints.py CASE E.json Y.json Z.json K1 [K2 ...]
"""
import json, math, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import probe_common as pc  # noqa: E402
from probe_basins import answer_float, load_case, reference_values  # noqa: E402
from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds  # noqa: E402

case, fe, fy, fz = sys.argv[1:5]
ks = [int(k) for k in sys.argv[5:]]
e_dsl, e_b, e_ev = pc.build(fe); _, y_b, y_ev = pc.build(fy); _, z_b, z_ev = pc.build(fz)
m = len(e_b.spec.constraints)
base = list(e_b.var_names)
e_box = np.array(infer_problem_bounds(e_b), dtype=float)
y_box = dict(zip(y_b.var_names, map(tuple, np.array(infer_problem_bounds(y_b), dtype=float))))
extra = sorted({v[2:] for v in y_b.var_names if v[:2] in ("x_", "y_") and v not in base})
hc = pc.construction_coordinates(e_dsl, extra)
refs = reference_values(load_case(case)["answer"])
cfg = pc.ExternalPipelineConfig.production_baseline_tier(seed=0, total_time_budget_sec=180.0).search
tel = pc.smb._SearchTelemetry()


def h_of(u):
    vals = dict(zip(base, u))
    return {v: answer_float(ev, [vals[n] for n in names]) for v, (names, ev) in hc.items()}


for k in ks:
    rng = np.random.default_rng([0, k])
    u0 = e_box[:, 0] + rng.random(len(base)) * (e_box[:, 1] - e_box[:, 0])
    h0 = h_of(u0); u0d = dict(zip(base, u0))
    for s, (b, ev) in {"E": (e_b, e_ev), "Y": (y_b, y_ev), "Z": (z_b, z_ev)}.items():
        start = np.array([u0d[n] if n in u0d else (0.0 if n.startswith("ofs") else h0[n]) for n in b.var_names])
        n0 = tel.evaluation_count
        cand, stop = pc.local_solve(b, ev, start, cfg, tel, k)
        x = np.array(cand.x_float) if cand else start
        r = np.array(ev.evaluate_float_residual(list(x)).residual_vector, dtype=float)
        vals = dict(zip(b.var_names, x)); u = np.array([vals[n] for n in base])
        rE = np.array(e_ev.evaluate_float_residual(list(u)).residual_vector, dtype=float)
        tau = answer_float(ev, list(x))
        inbox_u = bool(np.all((u >= e_box[:, 0]) & (u <= e_box[:, 1])))
        pts = {n: vals[n] for n in vals if n[:2] in ("x_", "y_")} if s == "Y" else {}
        inbox_y = all(y_box[n][0] <= v <= y_box[n][1] for n, v in pts.items())
        hit = tau is not None and any(abs(tau - q) <= 1e-6 * max(1, abs(q)) for q in refs)
        print(f"k={k} {s} stop={stop} nfev={tel.evaluation_count-n0} orig={np.linalg.norm(r[:m]):.1e} cons={np.linalg.norm(r[m:]):.1e} "
              f"E_at_u={np.linalg.norm(rE):.1e} tau={tau if tau is None else round(tau,6)} correct={hit} u_in_box={inbox_u} y_in_box={inbox_y} "
              f"guard={getattr(cand,'guard_ok',None)} |u|max={np.abs(u).max():.1f}")
