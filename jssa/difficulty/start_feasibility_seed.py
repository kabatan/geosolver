"""start_feasibility.py for runs that did not save their starts: regenerate them.

probe_basins.py draws start k as lower + rng.random(n) * (upper - lower) with rng = default_rng(seed),
in order, so the starts of a saved run are reproduced exactly from the seed and the box.
Usage: start_feasibility_seed.py RAW_DIR SEED OUT.csv [ids...]
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_basins import load_case  # noqa: E402
from probe_common import build_ir_evaluator, load_problem_bundle, GeometryProblem  # noqa: E402
from start_feasibility import feasible  # noqa: E402


def main():
    raw, seed, out = Path(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
    ids = sys.argv[4:] or sorted(p.stem for p in raw.glob("*.json"))
    w = csv.writer(open(out, "w", newline=""))
    w.writerow(["id", "n_vars", "starts", "p", "n_feas", "hit_feas", "n_infeas", "hit_infeas"])
    for cid in ids:
        d = json.loads((raw / f"{cid}.json").read_text())
        recs = d.get("records") or []
        if not recs or not d.get("box"):
            continue
        box = np.array(d["box"], dtype=float)
        rng = np.random.default_rng(seed)
        ev = build_ir_evaluator(load_problem_bundle(GeometryProblem.model_validate(load_case(cid)["dsl"]).engine_document()))
        nf = hf = ni = hi = 0
        for k, r in enumerate(recs):
            assert r["k"] == k
            start = box[:, 0] + rng.random(len(box)) * (box[:, 1] - box[:, 0])
            hit = r["cls"] == "hit"
            if feasible(ev, start):
                nf += 1; hf += hit
            else:
                ni += 1; hi += hit
        w.writerow([cid, d["n_vars"], len(recs), (hf + hi) / len(recs), nf, hf, ni, hi])


if __name__ == "__main__":
    main()
