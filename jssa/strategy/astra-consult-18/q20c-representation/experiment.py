"""Bounded, deterministic Q20c linear-algebra experiment; no solver searches.

Run with the Python and single-thread environment specified in README.md.
All writes are relative to this file's directory.
"""
from __future__ import annotations

import csv
import hashlib
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import mpmath as mp
import numpy as np

OUT = Path(__file__).resolve().parent
NS = [4, 8, 12, 16, 24, 32, 40, 48, 56, 64]
RIGHT_SIDES = [("unit", "1", "1"), ("decimal", "1.3", "0.7")]
A = np.array([[1.25, 0.75], [0.75, 1.25]], dtype=float)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(n: int, a: mp.mpf, b: mp.mpf):
    return [((b * mp.power(2, i - n) + a * mp.power(2, -i)) / 2,
             (b * mp.power(2, i - n) - a * mp.power(2, -i)) / 2)
            for i in range(n + 1)]


def lifted_system(n: int, a: float, b: float):
    size = 2 * (n + 1)
    mat = np.zeros((size, size))
    rhs = np.zeros(size)
    for i in range(n):
        mat[2*i:2*i+2, 2*i:2*i+2] = -A
        mat[2*i:2*i+2, 2*i+2:2*i+4] = np.eye(2)
    mat[-2, :2] = [1, -1]
    rhs[-2] = a
    mat[-1, -2:] = [1, 1]
    rhs[-1] = b
    return mat, rhs


def forward(z0, n: int):
    points = [np.array(z0, dtype=float)]
    for _ in range(n):
        points.append(A @ points[-1])
    return np.array(points)


def max_error(points, ref):
    return max(abs(mp.mpf(float(p[j])) - r[j])
               for p, r in zip(points, ref) for j in range(2))


def run():
    mp.mp.dps = 100
    started = time.perf_counter()
    stamp = datetime.now(timezone.utc).isoformat()
    prereg_hash = sha(OUT / "preregistration.md")
    code_hash = sha(Path(__file__))
    (OUT / "registration-lock.json").write_text(json.dumps({
        "started_utc": stamp,
        "preregistration_sha256": prereg_hash,
        "experiment_sha256": code_hash,
        "python": platform.python_version(), "numpy": np.__version__,
        "mpmath": mp.__version__, "new_local_searches": 0,
    }, indent=2) + "\n")
    rows, matrices = [], []
    for n in NS:
        for label, astr, bstr in RIGHT_SIDES:
            if time.perf_counter() - started > 300:
                raise TimeoutError("Fixed five-minute computation budget")
            ma, mb = mp.mpf(astr), mp.mpf(bstr)
            a, b = float(ma), float(mb)
            ref = reference(n, ma, mb)
            by, ry = lifted_system(n, a, b)
            be = np.array([[2.0**n, 2.0**n], [1.0, -1.0]])
            re = np.array([b, a])
            br = np.array([[1.0, 1.0], [1.0, -1.0]])
            rr = np.array([b * 2.0**(-n), a])
            for representation, mat, rhs in [("E", be, re), ("E-row", br, rr),
                                              ("Y", by, ry)]:
                cinf = float(np.linalg.cond(mat, np.inf))
                ctwo = float(np.linalg.cond(mat, 2))
                if label == "unit":
                    matrices.append({"N": n, "representation": representation,
                                     "dimension": len(mat), "kappa_inf": cinf,
                                     "kappa_2": ctwo})
                for solver in ["LU", "SVD"]:
                    st = time.perf_counter()
                    rank = len(mat)
                    if solver == "LU":
                        x = np.linalg.solve(mat, rhs)
                    else:
                        x, _, rank, _ = np.linalg.lstsq(mat, rhs, rcond=None)
                    points = x.reshape(-1, 2) if representation == "Y" else forward(x, n)
                    rows.append({
                        "N": n, "rhs": label, "representation": representation,
                        "solver": solver, "dimension": len(mat), "reported_rank": int(rank),
                        "max_point_error": float(max_error(points, ref)),
                        "local_equation_residual_inf": float(np.max(np.abs(by @ points.ravel() - ry))),
                        "own_equation_residual_inf": float(np.max(np.abs(mat @ x - rhs))),
                        "initial_point_error": float(max_error(points[:1], ref[:1])),
                        "seconds": time.perf_counter() - st,
                    })
            # A better two-variable coordinate representation, not a lifted system.
            p0, q0 = b * 2.0**(-n), a
            mode_points = np.array([((2.0**i*p0 + 2.0**(-i)*q0)/2,
                                     (2.0**i*p0 - 2.0**(-i)*q0)/2)
                                    for i in range(n + 1)])
            oracle_points = forward([float(v) for v in ref[0]], n)
            for name, points in [("E-mode", mode_points), ("E-oracle", oracle_points)]:
                rows.append({
                    "N": n, "rhs": label, "representation": name,
                    "solver": "direct", "dimension": 2, "reported_rank": 2,
                    "max_point_error": float(max_error(points, ref)),
                    "local_equation_residual_inf": float(np.max(np.abs(by @ points.ravel() - ry))),
                    "own_equation_residual_inf": "",
                    "initial_point_error": float(max_error(points[:1], ref[:1])), "seconds": "",
                })
            bm = mp.matrix([[mp.power(2, n), mp.power(2, n)], [1, -1]])
            xm = mp.lu_solve(bm, mp.matrix([mb, ma]))
            pm = [tuple(xm)]
            for _ in range(n):
                x, y = pm[-1]
                pm.append(((5*x+3*y)/4, (3*x+5*y)/4))
            error_mp = max(abs(p[j]-r[j]) for p, r in zip(pm, ref) for j in range(2))
            rows.append({
                "N": n, "rhs": label, "representation": "E-mp", "solver": "LU-100dps",
                "dimension": 2, "reported_rank": 2, "max_point_error": float(error_mp),
                "local_equation_residual_inf": "", "own_equation_residual_inf": "",
                "initial_point_error": float(max(abs(pm[0][j]-ref[0][j]) for j in range(2))),
                "seconds": "",
            })
    for filename, data in [("experiment-rows.csv", rows), ("matrix-conditions.csv", matrices)]:
        with (OUT / filename).open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(data[0]))
            w.writeheader()
            w.writerows(data)
    te = [abs(m["kappa_inf"]/(2.0**m["N"]+1)-1) for m in matrices if m["representation"] == "E"]
    tr = [abs(m["kappa_inf"]/2-1) for m in matrices if m["representation"] == "E-row"]
    ty = max(m["kappa_inf"] for m in matrices if m["representation"] == "Y")
    t2_examples = []
    for n in NS:
        for label, _, _ in RIGHT_SIDES:
            rs = [r for r in rows if r["N"] == n and r["rhs"] == label]
            oracle = next(r for r in rs if r["representation"] == "E-oracle")
            yl = next(r for r in rs if r["representation"] == "Y" and r["solver"] == "LU")
            if n >= 56 and oracle["max_point_error"] >= .1 and yl["max_point_error"] <= 1e-10:
                t2_examples.append({"N": n, "rhs": label})
    modes = max(r["max_point_error"] for r in rows if r["representation"] == "E-mode")
    highprec = max(r["max_point_error"] for r in rows if r["representation"] == "E-mp")
    summary = {
        "started_utc": stamp, "finished_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_compute_seconds": time.perf_counter() - started,
        "parameter_instances": len(NS)*len(RIGHT_SIDES), "result_rows": len(rows),
        "new_local_searches": 0, "complete_solver_runs": 0,
        "T1": {"passed": max(te+tr) <= 1e-10 and ty <= 9*(1+1e-10),
               "max_E_relative_error": max(te), "max_Erow_relative_error": max(tr),
               "max_Y_kappa_inf": ty},
        "T2": {"passed": bool(t2_examples), "examples": t2_examples},
        "T3": {"passed": modes <= 1e-12 and highprec <= 1e-25,
               "max_mode_error": modes, "max_100digit_error": highprec},
        "max_Y_LU_point_error": max(r["max_point_error"] for r in rows if r["representation"] == "Y" and r["solver"] == "LU"),
        "preregistration_unchanged": sha(OUT / "preregistration.md") == prereg_hash,
        "experiment_unchanged": sha(Path(__file__)) == code_hash,
    }
    (OUT / "experiment-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    run()
