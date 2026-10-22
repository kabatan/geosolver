"""probe_common.py with the local solver replaced by plain Gauss-Newton with backtracking.

The Gauss-Newton step argmin |J d + r| does not depend on the coordinates: if x = A x' (A invertible),
the step in x' maps to the step in x. Backtracking only compares residual values along that step,
so it is coordinate-free as well. Levenberg-Marquardt is not, because its damping lambda*D^2 and the
column scaling D are taken in the given coordinates. So when the free-point system Y and the offset
system Z are linear reparametrisations of each other (affine constructions), Gauss-Newton gives the
same iterates on both; any gap that remains under LM comes from its damping, not from the number of
variables. Same arguments as probe_common.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import probe_common as pc  # noqa: E402
from probe_common import smb  # noqa: E402

GN_MAX_ITER = 200
FD_STEP = 1.4901161193847656e-08  # sqrt(machine eps), as in MINPACK's forward differences


def gn(f, x0):
    x = np.array(x0, dtype=float)
    r = np.asarray(f(x), dtype=float)
    if not np.all(np.isfinite(r)):
        return x, "undefined"
    cost = float(r @ r)
    for _ in range(GN_MAX_ITER):
        if cost < 1e-28:
            return x, "conv"
        J = np.empty((r.size, x.size))
        for j in range(x.size):
            h = FD_STEP * max(1.0, abs(x[j]))
            xp = x.copy(); xp[j] += h
            rp = np.asarray(f(xp), dtype=float)
            if not np.all(np.isfinite(rp)):
                xp[j] = x[j] - h
                rp = -np.asarray(f(xp), dtype=float) + 2 * r
            J[:, j] = (rp - r) / h
        if not np.all(np.isfinite(J)):
            return x, "stuck"
        d = np.linalg.lstsq(J, -r, rcond=None)[0]
        a = 1.0
        while a > 1e-10:
            xn = x + a * d
            rn = np.asarray(f(xn), dtype=float)
            if np.all(np.isfinite(rn)) and float(rn @ rn) < cost:
                break
            a *= 0.5
        else:
            return x, "stuck"
        step = np.linalg.norm(xn - x)
        x, r, cost = xn, rn, float(rn @ rn)
        if step <= 1e-14 * (1.0 + np.linalg.norm(x)):
            return x, "conv"
    return x, "cap"


def gn_local_solve(bundle, evaluator, start, config, telemetry, k):
    n = len(bundle.var_names)
    m = len(bundle.spec.constraints)
    if n > m:
        return pc.__dict__["_orig_local_solve"](bundle, evaluator, start, config, telemetry, k)
    bounds = [(-pc.WIDE, pc.WIDE)] * n
    vector_fn = smb._AugmentedResidualVectorFn(
        bundle=bundle, evaluator=evaluator, n_constraints=m,
        deadline_monotonic=None, telemetry=telemetry, constraint_scales=None,
    )
    try:
        x, status = gn(vector_fn, start)
    except Exception as error:  # noqa: BLE001
        return None, f"exception:{type(error).__name__}"
    cand = smb._build_candidate(evaluator=evaluator, config=config, bounds=bounds,
                                values=np.array(x, dtype=float), origin_seed=0, family_code=smb._LM_FAMILY_CODE,
                                origin_start_point_index=k, telemetry=telemetry)
    return cand, status


pc._orig_local_solve = pc.local_solve
pc.local_solve = gn_local_solve

if __name__ == "__main__":
    sys.exit(pc.main())
