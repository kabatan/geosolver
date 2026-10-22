"""Measure how often the residual is undefined at uniform random points of the search box.

For each case, draw N points uniformly in the box inferred by the solver and evaluate the
float residual.  A point is 'undefined' if evaluation raises, returns a non-finite value or a
non-ok status (for example an intersection that does not exist).  Also records how often the
branch guards hold.  Usage: python hidden_constraints.py OUT.csv [--n 2000]
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np

from geosolver import GeometryProblem
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--n", type=int, default=2000)
    args = ap.parse_args()
    rng = np.random.default_rng(0)
    rows = []
    for line in (ROOT / "benchmarks" / "cases.jsonl").open():
        case = json.loads(line)
        try:
            bundle = load_problem_bundle(GeometryProblem.model_validate(case["dsl"]).engine_document())
            ev = build_ir_evaluator(bundle)
        except Exception as error:  # noqa: BLE001
            rows.append({"case_id": case["id"], "status": type(error).__name__})
            continue
        d = len(bundle.var_names)
        if d == 0:
            rows.append({"case_id": case["id"], "status": "no_variables", "d": 0})
            continue
        b = np.array(infer_problem_bounds(bundle), dtype=float)
        undefined = guard_ok = 0
        statuses = {}
        for _ in range(args.n):
            x = b[:, 0] + rng.random(d) * (b[:, 1] - b[:, 0])
            try:
                r = ev.evaluate_float_residual(list(x))
                st = str(getattr(r.evaluation_status, "value", r.evaluation_status))
                bad = (not r.is_finite) or (not math.isfinite(r.residual_norm_float)) or not st.upper().endswith("OK")
            except Exception as error:  # noqa: BLE001
                st, bad = type(error).__name__, True
            statuses[st] = statuses.get(st, 0) + 1
            if bad:
                undefined += 1
                continue
            try:
                if ev.evaluate_guard(list(x))[0]:
                    guard_ok += 1
            except Exception:  # noqa: BLE001
                pass
        rows.append({"case_id": case["id"], "status": "ok", "d": d, "n": args.n,
                     "undefined_frac": undefined / args.n, "guard_ok_frac": guard_ok / args.n,
                     "statuses": json.dumps(statuses)})
    keys = sorted({k for r in rows for k in r})
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
