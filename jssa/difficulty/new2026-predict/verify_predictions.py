"""Verify frozen features and G witnesses without aggregating ANY hit count/p."""
from __future__ import annotations

import csv
import json
import math
import os
import sys
import time
from pathlib import Path

for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"
OUT = Path(__file__).resolve().parent
sys.path[:0] = [str(OUT.parents[2] / "src"), str(OUT.parent)]

import numpy as np
import ghost_exact as ghost
from run_predictions import digest, linear_prediction, verify_inputs


def main():
    began = time.monotonic()
    frozen = (OUT / "predictions.csv").read_bytes()
    freeze = json.loads((OUT / "freeze-manifest.json").read_text())
    assert digest(OUT / "predictions.csv") == freeze["predictions_sha256"]
    assert (OUT / "predictions.sha256").read_text().split()[0] == freeze["predictions_sha256"]
    verify_inputs(json.loads((OUT / "run-manifest.json").read_text()))
    assert digest(OUT / "per-pair.csv") == freeze["per_pair_sha256"]
    predictions = list(csv.DictReader(frozen.decode().splitlines()))
    pairs = list(csv.DictReader((OUT / "per-pair.csv").open()))
    cases = {c["id"]: c for c in map(json.loads, (OUT / "inputs/cases.jsonl").read_text().splitlines())}
    model = json.loads((OUT / "inputs/model-1023.json").read_text())
    assert len(predictions) == len(cases) == 20
    checked_witnesses = checked_ranks = 0
    for row in predictions:
        cid = row["id"]
        raw_path = OUT / "raw" / f"{cid}.json"
        assert digest(raw_path) == freeze["raw_sha256"][cid]
        raw = json.loads(raw_path.read_text())
        assert raw["starts_done"] == len(raw["records"]) == 200 and raw["seed"] == 5
        assert not {"counts", "hits_by_ref", "p_any", "p_min_ref"}.intersection(raw)
        phi = sum(r["start_feasible"] for r in raw["records"]) / 200
        pp = [p for p in pairs if p["id"] == cid]
        found = sum(int(p["found"]) for p in pp)
        assert len(pp) == int(row["n_pairs"]) and found == int(row["n_pairs_found"])
        assert int(row["G"]) == int(found > 0) and phi == float(row["phi"])
        for name, column in (("full", "pred_logit_full"), ("nvars_only", "pred_logit_nvars_only")):
            expected = linear_prediction(model[name], int(row["n_vars"]), phi, int(row["G"]))
            assert expected == float(row[column])
        bundle, coords, _, names = ghost.chunk_context(json.dumps(cases[cid]["dsl"]))
        for pair in pp:
            assert pair["P"] == names[int(pair["i"])] and pair["Q"] == names[int(pair["j"])]
            assert int(pair["n_starts"]) == 20
            assert int(pair["found"]) == int(float(pair["best_res"]) <= ghost.RES_TOL)
            ev = ghost.augmented_evaluator(bundle, coords, pair["P"], pair["Q"])

            def residual(x):
                return np.asarray(ev.evaluate_float_residual(list(x)).residual_vector, dtype=float)

            if pair["best_x"]:
                norm = float(np.linalg.norm(residual(json.loads(pair["best_x"]))))
                assert math.isclose(norm, float(pair["best_res"]), rel_tol=1e-9, abs_tol=1e-12)
                checked_witnesses += 1
            if pair["dim_x"]:
                dim, svals = ghost.central_dimension(residual, json.loads(pair["dim_x"]))
                assert dim == int(pair["dim"])
                np.testing.assert_allclose(svals, json.loads(pair["singular_values"]), rtol=1e-9, atol=1e-12)
                checked_ranks += 1
    assert (OUT / "predictions.csv").read_bytes() == frozen
    report = dict(status="passed", problems=20, starts=4000, pairs=len(pairs),
                  best_res_witnesses_checked=checked_witnesses, rank_witnesses_checked=checked_ranks,
                  elapsed_seconds=time.monotonic()-began, predictions_sha256=freeze["predictions_sha256"],
                  p_aggregated=False)
    (OUT / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
