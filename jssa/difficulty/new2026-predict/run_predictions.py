"""Run preregistration-2 A through prediction freeze, NEVER aggregate p.

Uses four processes at most; all outputs stay beside this file. A later,
separate score_predictions.py command requires the user's committed artifact.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[key] = "1"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
PYTHON = "/home/kabatan/work/solver/.venv/bin/python"
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "jssa/difficulty")]
os.environ["PYTHONPATH"] = os.pathsep.join([str(ROOT / "src"), str(ROOT / "jssa/difficulty")])

import numpy as np
import ghost_exact as ghost
from geosolver import GeometryProblem
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from probe_basins import _hard_feasible, build_ir_evaluator


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, data, *, allow_nan=False):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=allow_nan) + "\n")


def probe(cid):
    target = OUT / "raw" / f"{cid}.json"
    if target.exists():
        data = json.loads(target.read_text())
        assert data["seed"] == 5 and data["starts_done"] == 200
        assert data["summary_deferred"] and "p_any" not in data and "counts" not in data
        return cid, "reused"
    command = [PYTHON, str(ROOT / "jssa/difficulty/probe_basins.py"), cid, str(target),
               "--cases", str(OUT / "inputs/cases.jsonl"), "--seed", "5", "--starts", "200",
               "--budget", "86400", "--defer-summary"]
    with (OUT / "logs" / f"{cid}.log").open("x") as log:
        subprocess.run(command, cwd=ROOT, env=os.environ.copy(), stdout=log,
                       stderr=subprocess.STDOUT, check=True)
    data = json.loads(target.read_text())
    assert data["starts_done"] == 200, f"{cid}: incomplete probe; do not freeze"
    assert data["summary_deferred"] and "p_any" not in data and "counts" not in data
    return cid, f"200 starts saved; {data['elapsed']:.1f}s"


def prepare(case):
    cid = case["id"]
    raw = json.loads((OUT / "raw" / f"{cid}.json").read_text())
    assert raw["starts_done"] == len(raw["records"]) == 200
    bundle = load_problem_bundle(GeometryProblem.model_validate(case["dsl"]).engine_document())
    assert len(bundle.var_names) == raw["n_vars"] >= 1
    evaluator = build_ir_evaluator(bundle)
    bounds = np.asarray(raw["box"])
    rng = np.random.default_rng(5)
    feasibility = []
    for k, rec in enumerate(raw["records"]):
        expected = bounds[:, 0] + rng.random(len(bundle.var_names)) * (bounds[:, 1] - bounds[:, 0])
        assert rec["k"] == k and np.array_equal(expected, rec["start"])
        feasible = _hard_feasible(evaluator, rec["start"])
        assert feasible == rec["start_feasible"]
        feasibility.append(feasible)
    meta, indices = ghost.prepare_summary({"id": cid, "n_vars": raw["n_vars"]}, case, OUT / "raw")
    # G's exclusion rule may read hit coordinates, but the hit count is never
    # exposed or persisted in features/predictions before the commit gate.
    del meta["n_hits"]
    meta["phi"] = sum(feasibility) / 200
    return meta, indices


def verify_inputs(manifest):
    for name, sha in manifest["input_sha256"].items():
        assert digest(ROOT / name) == sha, f"input changed: {name}"


def linear_prediction(model, n_vars, phi=0.0, G=0):
    level = str(min(7, n_vars))
    return (model["intercept"] + model["n_vars"].get(level, 0.0)
            + model.get("phi", 0.0) * phi + model.get("G", 0.0) * G)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=4, choices=range(1, 5))
    args = parser.parse_args()
    if (OUT / "predictions.csv").exists() or (OUT / "predictions.sha256").exists():
        parser.error("predictions are frozen; this script will NEVER overwrite them")
    for folder in ("raw", "logs", "inputs", "ghost-checkpoints"):
        (OUT / folder).mkdir(exist_ok=True)
    manifest_path = OUT / "run-manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        assert manifest["workers"] == args.workers
        verify_inputs(manifest)
    else:
        sources = ["jssa/difficulty/new2026/cases.jsonl", "jssa/difficulty/ghost-1023/model-1023.json",
                   "jssa/difficulty/ghost-1023/preregistration-2.md", "jssa/difficulty/probe_basins.py",
                   "jssa/difficulty/ghost_exact.py", "jssa/difficulty/ghost_scan.py",
                   "jssa/difficulty/new2026-predict/run_predictions.py",
                   "jssa/difficulty/new2026-predict/score_predictions.py"]
        manifest = dict(started_utc=datetime.now(UTC).isoformat(), workers=args.workers,
                        python=PYTHON, seed=5, starts=200, probe_budget_seconds=86400,
                        ghost_starts_per_pair=20, ghost_rng="default_rng([0,i,j])",
                        input_sha256={name: digest(ROOT / name) for name in sources})
        dump(manifest_path, manifest)
        for source, name in zip(sources[:3], ("cases.jsonl", "model-1023.json", "preregistration-2.md")):
            (OUT / "inputs" / name).write_bytes((ROOT / source).read_bytes())
    cases = [json.loads(line) for line in (OUT / "inputs/cases.jsonl").read_text().splitlines()]
    assert len(cases) == len({c["id"] for c in cases}) == 20
    began = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(probe, c["id"]) for c in cases]
        for f in as_completed(futures):
            print("PROBE", *f.result(), flush=True)
    probe_seconds = time.monotonic() - began
    print("PROBE complete; no hit counts or p aggregated", flush=True)
    ghost_began = time.monotonic()
    metadata, indices, pairs = {}, {}, {}
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(prepare, case): case["id"] for case in cases}
        for f in as_completed(futures):
            cid = futures[f]
            metadata[cid], indices[cid] = f.result()
        pending, remaining = {}, {}
        for case in cases:
            cid = case["id"]
            checkpoint = OUT / "ghost-checkpoints" / f"{cid}.json"
            if checkpoint.exists():
                pairs[cid] = json.loads(checkpoint.read_text())["pairs"]
                assert len(pairs[cid]) == len(indices[cid])
                continue
            pairs[cid] = []
            remaining[cid] = math.ceil(len(indices[cid]) / 8)
            for k in range(0, len(indices[cid]), 8):
                f = pool.submit(ghost.solve_chunk, cid, json.dumps(case["dsl"]),
                                indices[cid][k:k+8], metadata[cid]["has_hits"])
                pending[f] = cid
        print(f"G prepared: 20 problems; {sum(map(len, indices.values()))} pairs; "
              f"{len(pending)} pending chunks", flush=True)
        for f in as_completed(pending):
            cid = pending[f]
            chunk, seconds = f.result()
            pairs[cid].extend(chunk)
            remaining[cid] -= 1
            if remaining[cid] == 0:
                pairs[cid].sort(key=lambda r: (r["i"], r["j"]))
                # As in the original sol-1 outputs, all-failed pairs have inf
                # best_res. Internal Python checkpoints preserve that value.
                dump(OUT / "ghost-checkpoints" / f"{cid}.json", {"pairs": pairs[cid]}, allow_nan=True)
                print(f"G completed {cid}; pairs={len(pairs[cid])}", flush=True)
    ghost_seconds = time.monotonic() - ghost_began
    # No outcome-dependent model fit, feature selection, or coefficient change.
    model = json.loads((OUT / "inputs/model-1023.json").read_text())
    rows, all_pairs = [], []
    for case in cases:
        cid = case["id"]
        m, pp = metadata[cid], pairs[cid]
        assert len(pp) == len(indices[cid])
        assert {(p["i"], p["j"]) for p in pp} == set(indices[cid])
        assert all(p["n_starts"] == 20 for p in pp)
        found = sum(p["found"] for p in pp)
        G = int(found > 0)
        row = dict(id=cid, n_vars=m["n_vars"], starts=200, seed=5, phi=m["phi"], G=G,
                   has_hits=m["has_hits"], n_pairs=len(pp), n_pairs_found=found,
                   n_pairs_excluded=m["n_pairs_excluded"],
                   n_pairs_all_failed=sum(p["n_failed"] == 20 for p in pp),
                   pred_logit_full=linear_prediction(model["full"], m["n_vars"], m["phi"], G),
                   pred_logit_nvars_only=linear_prediction(model["nvars_only"], m["n_vars"]))
        rows.append(row)
        all_pairs.extend(pp)
    ghost.write_csv(OUT / "per-pair.csv", ghost.PAIR_FIELDS, all_pairs)
    verify_inputs(manifest)
    for source, name in zip(list(manifest["input_sha256"])[:3], ("cases.jsonl", "model-1023.json", "preregistration-2.md")):
        assert digest(OUT / "inputs" / name) == manifest["input_sha256"][source]
    frozen_path = OUT / "predictions.csv"
    with frozen_path.open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
        stream.flush()
        os.fsync(stream.fileno())
    created = datetime.now(UTC).isoformat()
    sha = digest(frozen_path)
    with (OUT / "predictions.sha256").open("x") as stream:
        stream.write(f"{sha}  predictions.csv\ncreated_utc: {created}\n")
    dump(OUT / "freeze-manifest.json", dict(
        frozen_utc=created, predictions_sha256=sha, probe_wall_seconds=probe_seconds,
        ghost_wall_seconds=ghost_seconds, this_invocation_wall_seconds=time.monotonic()-began,
        raw_sha256={c["id"]: digest(OUT / "raw" / f"{c['id']}.json") for c in cases},
        per_pair_sha256=digest(OUT / "per-pair.csv"),
        note="Steps (1)-(3) complete; p not aggregated. Await user commit/push before step (4)."))
    print(f"FROZEN {sha}  predictions.csv; created_utc={created}", flush=True)
    print("STOP: awaiting user commit/push; step (4) has NOT been run.", flush=True)


if __name__ == "__main__":
    main()
