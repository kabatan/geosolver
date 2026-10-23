"""No-optimizer checks of the intervention and the unchanged residual rows."""
import numpy as np
from mpmath import mp
import run
from geosolver.engine.standard.interpreter.guards.compile import compile_guard_expr, guard_violation_value

ctx = run.case_context("AIME-2010-II-14")
case, bundle, ev, raw, *_ = ctx
g = compile_guard_expr("AssumeGt(x, 0)")
v1 = float(guard_violation_value(g, dict(bundle.base_context, mpf=mp.mpf, x=-1.0)))
v2 = float(guard_violation_value(g, dict(bundle.base_context, mpf=mp.mpf, x=-2.0)))
assert abs(v2 - 2*v1) < 1e-10
rows = []
for k in (0, 2, 3):
    r = next(r for r in raw["records"] if r["k"] == k)
    x = np.array(r["start"])
    p = run.DistancePenalty(ev)
    old = run.smb._evaluate_hard_feasibility_penalty
    def vec():
        return run.smb._evaluate_augmented_residual_vector(
            bundle=bundle, evaluator=ev, values=x, n_constraints=len(bundle.spec.constraints),
            telemetry=run.smb._SearchTelemetry())
    b = vec()
    try:
        run.smb._evaluate_hard_feasibility_penalty = lambda **kw: 0.0
        n = vec()
        run.smb._evaluate_hard_feasibility_penalty = p
        g2 = vec()
    finally:
        run.smb._evaluate_hard_feasibility_penalty = old
    assert np.array_equal(b[:-1], n[:-1]) and np.array_equal(b[:-1], g2[:-1])
    assert n[-1] == 0
    rows.append({"k": k, "B_last": b[-1], "N_last": n[-1], "G2_last": g2[-1], "g2": dict(p.counts)})
run.write_json(run.HERE / "preflight.json", {
    "utc": run.stamp(), "optimizer_runs": 0, "guard_slope_check": True,
    "equalities_and_guard_unchanged": True, "rows": rows,
    "setup_failures": ["Two synthetic guard checks lacked mpf (plain dict and bundle.base_context); corrected by adding mp.mpf. No optimizer had run."]})
print("Preflight passed; no optimizer runs.")
