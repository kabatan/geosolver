"""Does the start already satisfy the problem's inequalities?  Split each 200-start run by it.

For every saved start of minima/raw-323, evaluate the hard-feasibility check of the frozen solver
(guards = the problem's inequalities and order conditions, distinct lines, non-degenerate triangles,
intersection selection). If it fails, the local search sees a constant penalty there.
Writes one row per problem: starts with a feasible / infeasible start and hits in each group.

Usage: start_feasibility.py RAW_DIR OUT.csv [ids...]
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_basins import load_case  # noqa: E402
from probe_common import build_ir_evaluator, load_problem_bundle, GeometryProblem  # noqa: E402


def feasible(ev, x):
    try:
        return bool(ev.evaluate_float_hard_feasibility(list(x), include_margins=False).hard_feasible)
    except Exception:  # noqa: BLE001
        return False


def main():
    raw, out = Path(sys.argv[1]), sys.argv[2]
    ids = sys.argv[3:] or sorted(p.stem for p in raw.glob("*.json"))
    w = csv.writer(open(out, "w", newline=""))
    w.writerow(["id", "n_vars", "starts", "p", "n_feas", "hit_feas", "n_infeas", "hit_infeas", "n_checks"])
    for cid in ids:
        d = json.loads((raw / f"{cid}.json").read_text())
        recs = [r for r in d.get("records") or [] if "start" in r]
        if not recs:
            continue
        bundle = load_problem_bundle(GeometryProblem.model_validate(load_case(cid)["dsl"]).engine_document())
        ev = build_ir_evaluator(bundle)
        nf = hf = ni = hi = 0
        for r in recs:
            hit = r["cls"] == "hit"
            if feasible(ev, r["start"]):
                nf += 1; hf += hit
            else:
                ni += 1; hi += hit
        w.writerow([cid, d["n_vars"], len(recs), (hf + hi) / len(recs), nf, hf, ni, hi, len(bundle.hard_feasibility_checks)])
        print(cid, nf, hf, ni, hi, flush=True)


if __name__ == "__main__":
    main()
