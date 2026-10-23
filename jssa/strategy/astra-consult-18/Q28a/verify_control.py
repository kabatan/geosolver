"""A rejection-control check, not an execution of GeoSolver."""
from __future__ import annotations

import csv
import hashlib
import json
import random
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
SEEDS = (280101, 280102)
M_VALUES = (1, 10000, 100000000)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(name: str, data: object) -> None:
    (OUT / name).write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    started = time.monotonic()
    inputs = [
        OUT / "preregistration.md",
        Path(__file__).resolve(),
        ROOT / "jssa/difficulty/minima/basins-323.csv",
        ROOT / "jssa/strategy/astra-consult-18/q21d-conditioning/per-problem.csv",
        ROOT / "src/geosolver/engine/standard/search/scipy_multistart_backend.py",
        ROOT / "src/geosolver/engine/standard/refinement/mpmath_refiner.py",
    ]
    initial_hashes = {str(p.relative_to(ROOT)): sha(p) for p in inputs}
    lock = {
        "registered_before_computation_utc": datetime.now(timezone.utc).isoformat(),
        "python_executable": sys.executable,
        "input_hashes": initial_hashes,
        "scope": "elementary control and descriptive audit; no solver runs",
    }
    lock_path = OUT / "registration-lock.json"
    if lock_path.exists():
        raise RuntimeError("Refusing to overwrite an existing registration lock")
    dump("registration-lock.json", lock)

    starts = {}
    for seed in SEEDS:
        rng = random.Random(seed)
        starts[str(seed)] = [repr(rng.uniform(-1, 1)) for _ in range(200)]
    dump("control-starts.json", starts)

    rows, cells = [], []
    with localcontext() as ctx:
        ctx.prec = 80
        one, two, three = map(Decimal, (1, 2, 3))
        tolerance = Decimal("1e-30")
        radii = {}
        for m_integer in M_VALUES:
            m = Decimal(m_integer)
            # f'(0)=1, f''(0)=0, f'''(0)=6M; higher derivatives vanish.
            gamma_from_derivatives = max(Decimal(0), (6 * m / 6).sqrt())
            radius = one / (20 * gamma_from_derivatives)
            radii[m_integer] = radius
            # Homogeneous cubic X0^2 X1 + M X1^3 at [1:0].
            mu = (one + three * m * m).sqrt()
            for seed in SEEDS:
                cell_rows = []
                for index, start in enumerate(starts[str(seed)]):
                    if time.monotonic() - started > 60:
                        raise TimeoutError("Fixed 60-second total budget exceeded")
                    x = Decimal(start)
                    steps = 0
                    while abs(x) > tolerance and steps < 100:
                        x = two * m * x**3 / (one + three * m * x**2)
                        steps += 1
                    row = {
                        "M": m_integer,
                        "seed": seed,
                        "start_index": index,
                        "start": start,
                        "steps": steps,
                        "final_error": str(abs(x)),
                        "success": abs(x) <= tolerance,
                    }
                    rows.append(row)
                    cell_rows.append(row)
                cells.append({
                    "M": m_integer,
                    "seed": seed,
                    "n": len(cell_rows),
                    "successes": sum(r["success"] for r in cell_rows),
                    "max_steps": max(r["steps"] for r in cell_rows),
                    "max_error": str(max(Decimal(r["final_error"]) for r in cell_rows)),
                    "gamma": str(gamma_from_derivatives),
                    "guaranteed_radius": str(radius),
                    "mu_normalized_at_projective_root": str(mu),
                })
        radius_ratio = radii[1] / radii[100000000]
        c1 = all(c["successes"] == 200 for c in cells)
        checks = {
            "C1": c1,
            "C2": c1 and abs(radius_ratio - Decimal(10000)) <= Decimal("1e-60"),
            "C3": all(r["success"] and r["steps"] <= 40 for r in rows),
        }
    with (OUT / "control-runs.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    dump("control-results.json", {
        "checks": checks,
        "radius_ratio": str(radius_ratio),
        "cells": cells,
        "total_runs": len(rows),
        "failed_runs": [r for r in rows if not r["success"]],
        "over_40_steps": [r for r in rows if r["steps"] > 40],
        "warning": "These are scalar Newton controls, not competition problems or GeoSolver runs.",
    })

    with inputs[2].open(newline="", encoding="utf-8") as f:
        basins = list(csv.DictReader(f))
    with inputs[3].open(newline="", encoding="utf-8") as f:
        prior = list(csv.DictReader(f))
    stable = [r for r in prior if r["status"] == "regular_stable"]
    shapes = Counter()
    for r in stable:
        n, m = int(r["n_vars"]), int(r["n_smooth"])
        shapes["square" if m == n else "overdetermined" if m > n else "underdetermined"] += 1
    dump("applicability-audit.json", {
        "basins_total": len(basins),
        "basins_with_variables": sum(int(r["n_vars"]) > 0 for r in basins),
        "basins_without_variables": sum(int(r["n_vars"]) == 0 for r in basins),
        "prior_q21d_total": len(prior),
        "prior_q21d_status_counts": dict(Counter(r["status"] for r in prior)),
        "prior_q21d_regular_stable_smooth_shapes": dict(shapes),
        "interpretation": "Shape and finite-difference status do not certify analytic regularity or applicability of an alpha theorem.",
    })
    unchanged = all(sha(p) == initial_hashes[str(p.relative_to(ROOT))] for p in inputs)
    dump("verification.json", {
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": time.monotonic() - started,
        "all_registered_inputs_unchanged": unchanged,
        "control_start_sha256": sha(OUT / "control-starts.json"),
        "rows": len(rows),
        "cells": len(cells),
        "checks": checks,
    })
    print(json.dumps({"checks": checks, "cells": cells, "input_hashes_unchanged": unchanged}, indent=2))


if __name__ == "__main__":
    main()
