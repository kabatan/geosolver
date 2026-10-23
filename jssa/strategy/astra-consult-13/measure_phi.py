"""Independent static feasibility measurement; no optimization, all writes local."""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True
for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
from geosolver import GeometryProblem
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle

SALT = "consult13-phi-20261023"
N = 1024


def main():
    cases = {d["id"]: d for d in map(json.loads, (ROOT / "benchmarks/cases.jsonl").open())}
    existing = list(csv.DictReader((ROOT / "jssa/difficulty/start-feasibility-1023/per-problem.csv").open()))
    fields = ["id", "n", "n_feas", "phi", "n_raised", "n_construction_error", "seconds"]
    tags = {}
    t_all = time.perf_counter()
    with (OUT / "phi-independent.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for i, row in enumerate(existing):
            cid = row["id"]
            t0 = time.perf_counter()
            raw = json.loads((ROOT / "jssa/difficulty/minima/raw-323" / (cid + ".json")).read_text())
            box = np.asarray(raw["box"], dtype=float)
            bundle = load_problem_bundle(GeometryProblem.model_validate(cases[cid]["dsl"]).engine_document())
            ev = build_ir_evaluator(bundle)
            assert len(bundle.var_names) == len(box) == int(row["n_vars"])
            seed = int.from_bytes(hashlib.sha256((SALT + ":" + cid).encode()).digest()[:16], "little")
            rng = np.random.default_rng(seed)
            points = box[:, 0] + rng.random((N, len(box))) * (box[:, 1] - box[:, 0])
            nf = raised = construction_error = 0
            counts = {}
            for point in points:
                try:
                    snap = ev.evaluate_float_hard_feasibility(list(point), include_margins=False)
                    nf += bool(snap.hard_feasible)
                    violations = tuple(snap.failure_tags)
                    construction_error += any(str(s).startswith("construction_error:") for s in violations)
                    for tag in violations:
                        short = str(tag).split(":", 1)[0]
                        counts[short] = counts.get(short, 0) + 1
                except Exception as exc:
                    # Keep evaluation exceptions separate from geometrically invalid starts.
                    raised += 1
                    key = "exception:" + type(exc).__name__
                    counts[key] = counts.get(key, 0) + 1
            result = dict(id=cid, n=N, n_feas=nf, phi=nf/N, n_raised=raised,
                          n_construction_error=construction_error, seconds=time.perf_counter()-t0)
            w.writerow(result)
            f.flush()
            tags[cid] = counts
            if i % 20 == 0 or i == len(existing)-1:
                print(i+1, len(existing), cid, "phi", nf/N, "elapsed", round(time.perf_counter()-t_all, 1), flush=True)
    manifest = {
        "salt": SALT, "points_per_problem": N, "problems": len(existing),
        "seconds": time.perf_counter()-t_all, "python": sys.version,
        "executable": sys.executable, "numpy": np.__version__,
        "local_optimizations": 0,
        "sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [
            OUT / "analysis-plan.md", Path(__file__), ROOT / "benchmarks/cases.jsonl",
            ROOT / "src/geosolver/engine/standard/evaluation/evaluate_float_hard_feasibility.py",
            ROOT / "jssa/difficulty/start-feasibility-1023/per-problem.csv"]}}
    (OUT / "phi-tags.json").write_text(json.dumps(tags, ensure_ascii=False, indent=2)+"\n")
    (OUT / "measurement.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n")


if __name__ == "__main__":
    main()
