"""Do the 'stuck' end points of probe_basins.py sit at true local minima?

Restart the solver's own single-start local solver from every saved stuck end point
(up to --max per case) and see whether the residual still drops.  ``settled`` means
the residual changed by less than 1 % (relative) and the point moved by less than
1e-3 of the box; otherwise the first run was cut off before reaching a minimum.

Usage: python recheck_stuck.py CASE_ID PROBE.json OUT.json [--dsl VARIANT.json] [--max 40]
"""
import argparse, json, sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import probe_basins as pb  # noqa: E402
from geosolver import GeometryProblem
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.search import scipy_multistart_backend as smb
from geosolver.engine.standard.contracts.external_pipeline_config import ExternalPipelineConfig
import time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("case_id"); ap.add_argument("probe"); ap.add_argument("out")
    ap.add_argument("--dsl"); ap.add_argument("--max", type=int, default=40)
    a = ap.parse_args()
    case = pb.load_case(a.case_id)
    dsl = json.loads(Path(a.dsl).read_text()) if a.dsl else case["dsl"]
    bundle = load_problem_bundle(GeometryProblem.model_validate(dsl).engine_document())
    ev = build_ir_evaluator(bundle)
    bounds = infer_problem_bounds(bundle)
    lo = np.array([b[0] for b in bounds]); hi = np.array([b[1] for b in bounds])
    cfg = ExternalPipelineConfig.production_baseline_tier(seed=0, total_time_budget_sec=180.0).search
    tel = smb._SearchTelemetry()
    d = json.loads(Path(a.probe).read_text())
    stuck = [r for r in d["records"] if r["cls"] == "stuck" and "x" in r][: a.max]
    dead = time.monotonic() + 100
    out = []
    for r in stuck:
        try:
            c = smb._collect_local_start_record(bundle=bundle, evaluator=ev, bounds=bounds, config=cfg, seed=0,
                                                start_index=100000 + r["k"], start=np.array(r["x"]),
                                                deadline_monotonic=dead, telemetry=tel)
        except Exception:
            break
        if c is None or not np.isfinite(c.residual_norm_float):
            continue
        move = float(np.max(np.abs((np.array(c.x_float) - np.array(r["x"])) / (hi - lo))))
        rel = (r["res"] - c.residual_norm_float) / max(r["res"], 1e-300)
        out.append({"k": r["k"], "res0": r["res"], "res1": c.residual_norm_float, "rel_drop": rel, "move": move,
                    "settled": bool(rel < 0.01 and move < 1e-3), "reached_zero": bool(c.residual_norm_float <= pb.RES_TOL)})
    Path(a.out).write_text(json.dumps({"case": a.case_id, "n": len(out), "settled": sum(o["settled"] for o in out), "reached_zero": sum(o["reached_zero"] for o in out), "rows": out}))
    print(a.case_id, len(out), sum(o["settled"] for o in out))


if __name__ == "__main__":
    main()
