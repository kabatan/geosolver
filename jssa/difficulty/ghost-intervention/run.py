"""Preregistered sol-4; all generated files stay beside this script.

prepare freezes targets, safe pairs and RNG selections without intervention outcomes.
run uses the original backend, appending only optimization residual rows.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path

for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[key] = "1"
sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "jssa/difficulty")]

import numpy as np
import scipy
from ghost_scan import point_names
from probe_basins import (ANS_RTOL, RES_TOL, answer_float, construction_coordinates,
                          reference_values)
from geosolver import GeometryProblem
from geosolver.engine.standard.contracts.external_pipeline_config import ExternalPipelineConfig
from geosolver.engine.standard.evaluation.ir_evaluator import IREvaluator, build_ir_evaluator
from geosolver.engine.standard.evaluation.snapshots import EvaluationStore
from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.search import scipy_multistart_backend as smb
from geosolver.problem.ir.schema import IRConstruction

EPSILON = 0.02
WEIGHT = 1.0
RAW = ROOT / "jssa/difficulty/minima/raw-323"


def dump(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    tmp.replace(path)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def readcsv(path):
    with path.open() as f:
        return list(csv.DictReader(f))


def bundle_for(dsl):
    return load_problem_bundle(GeometryProblem.model_validate(dsl).engine_document())


def coordinate_evaluator(bundle, coords, names):
    expressions = [coords[f"{a}_{p}"][1].bundle.spec.answer_expr for p in names for a in "xy"]
    spec = replace(bundle.spec,
                   construction=[IRConstruction("ORIGINZ", "Point(0, 0)"), *bundle.spec.construction],
                   constraints=expressions, v=[0] * len(expressions), m=len(expressions))
    b = replace(bundle, spec=spec, targets=(0,) * len(expressions))
    return IREvaluator(b, (), EvaluationStore(b, capacity=16))


def hit_figure(coords, var_names, x, names):
    vals = dict(zip(var_names, x, strict=True))
    fig = {}
    for p in names:
        values = []
        for a in "xy":
            ns, ev = coords[f"{a}_{p}"]
            v = answer_float(ev, [vals[n] for n in ns])
            values.append(v)
        if all(v is not None and math.isfinite(v) for v in values):
            fig[p] = np.asarray(values)
    return fig


def prepare_one(arg):
    cid, index, dsl, pairs = arg
    began = time.monotonic()
    raw = json.loads((RAW / f"{cid}.json").read_text())
    bundle = bundle_for(dsl)
    names = sorted(point_names(dsl))
    coords = construction_coordinates(dsl, names)
    hits = [r for r in raw["records"] if r["cls"] == "hit"]
    figs = [hit_figure(coords, bundle.var_names, r["x"], names) for r in hits]
    diameters = [max(float(np.linalg.norm(a-b)) for a in f.values() for b in f.values()) for f in figs]
    L = float(np.median(diameters))
    assert math.isfinite(L) and L > 0 and hits and raw["seed"] == 0
    bounds = [list(map(float, b)) for b in infer_problem_bounds(bundle)]
    assert bounds == raw["box"]
    assert all("start" in r for r in raw["records"])
    treatment, placebo_pool, exclusions = [], [], []
    checks = []
    for r in pairs:
        p, q = r["P"], r["Q"]
        distances = [float(np.linalg.norm(f[p]-f[q])) if p in f and q in f else None for f in figs]
        safe = all(d is not None and d > EPSILON * L for d in distances)
        row = dict(P=p, Q=q, found=int(r["found"]), safe=safe,
                   min_hit_distance=min((d for d in distances if d is not None), default=None),
                   n_undefined_hits=sum(d is None for d in distances))
        checks.append(row)
        if not safe:
            exclusions.append(row)
        elif int(r["found"]):
            treatment.append([p, q])
        else:
            placebo_pool.append([p, q])
    # Stable lexicographic order, same zero-based full basins-323 row index as sol-2.
    treatment.sort()
    placebo_pool.sort()
    if len(placebo_pool) >= len(treatment):
        ix = np.random.default_rng([7, index]).choice(len(placebo_pool), len(treatment), replace=False)
        placebo = [placebo_pool[int(i)] for i in ix]
        placebo_status = "ok"
    else:
        placebo = None
        placebo_status = "insufficient_distinct_safe_found0_pairs"
    return dict(id=cid, problem_index=index, n_vars=len(bundle.var_names),
                n_constraints=len(bundle.spec.constraints), n_original=len(raw["records"]),
                n_hits=len(hits), L=L, threshold=EPSILON*L, treatment=treatment,
                placebo=placebo, placebo_status=placebo_status,
                placebo_pool=placebo_pool, exclusions=exclusions, pair_checks=checks,
                n_found_before_safety=sum(int(r["found"]) for r in pairs),
                prep_seconds=time.monotonic()-began)


def prepare(workers):
    if (OUT / "plan.json").exists():
        raise RuntimeError("plan.json already exists; do not overwrite a frozen selection")
    rows = readcsv(ROOT / "jssa/difficulty/minima/basins-323.csv")
    problem_rows = readcsv(ROOT / "jssa/difficulty/ghost-exact/per-problem.csv")
    selected = {r["id"] for r in problem_rows if int(r["n_pairs_found"]) > 0 and int(r["has_hits"])}
    assert len(selected) == 58, len(selected)
    pair_rows = readcsv(ROOT / "jssa/difficulty/ghost-exact/per-pair.csv")
    cases = {c["id"]: c for c in map(json.loads, (ROOT / "benchmarks/cases.jsonl").open())}
    inputs = ["benchmarks/cases.jsonl", "jssa/difficulty/minima/basins-323.csv",
              "jssa/difficulty/ghost-exact/per-pair.csv", "jssa/difficulty/ghost-exact/per-problem.csv",
              "jssa/difficulty/ghost-1023/preregistration-2.md", "jssa/difficulty/probe_basins.py",
              "jssa/difficulty/ghost_scan.py", "src/geosolver/engine/standard/search/scipy_multistart_backend.py"]
    inputs += [str((RAW / f"{cid}.json").relative_to(ROOT)) for cid in sorted(selected)]
    hashes = {p: digest(ROOT / p) for p in inputs}
    jobs = [(r["id"], i, cases[r["id"]]["dsl"], [p for p in pair_rows if p["id"] == r["id"]])
            for i, r in enumerate(rows) if r["id"] in selected]
    problems = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for future in as_completed([pool.submit(prepare_one, j) for j in jobs]):
            p = future.result()
            problems.append(p)
            print(f"PREP {len(problems)}/58 {p['id']} treatment={len(p['treatment'])} "
                  f"placebo={p['placebo_status']} pool={len(p['placebo_pool'])}", flush=True)
    plan = dict(frozen_at=datetime.now(UTC).isoformat(), epsilon=EPSILON, weight=WEIGHT,
                seed=0, placebo_seed=7, index_convention="zero-based full basins-323.csv row",
                placebo_sampling="without replacement from safe found=0 pairs; missing if insufficient",
                safety="all original hit distances strictly > epsilon*L; applies to both arms",
                inputs_sha256=hashes, problems=sorted(problems, key=lambda p: p["problem_index"]))
    dump(OUT / "plan.json", plan)
    print("FROZEN", digest(OUT / "plan.json"), flush=True)


class PairPenalty:
    def __init__(self, bundle, dsl, pairs, threshold):
        self.pairs = pairs
        self.names = sorted({p for pair in pairs for p in pair})
        coords = construction_coordinates(dsl, self.names)
        self.ev = coordinate_evaluator(bundle, coords, self.names) if self.names else None
        self.indices = [(self.names.index(p), self.names.index(q)) for p, q in pairs]
        self.threshold = threshold
        self.nonfinite_calls = 0

    def __call__(self, x):
        if not self.pairs:
            return np.zeros(0)
        try:
            v = np.asarray(self.ev.evaluate_float_residual(list(x)).residual_vector).reshape(-1, 2)
            distances = np.asarray([np.linalg.norm(v[i]-v[j]) for i, j in self.indices])
            if not np.all(np.isfinite(distances)):
                raise ValueError("undefined pair coordinates")
            return WEIGHT * np.maximum(0.0, 1.0 - distances / self.threshold)
        except TimeoutError:
            raise
        except Exception:
            self.nonfinite_calls += 1
            return np.full(len(self.pairs), smb._NONFINITE_RESIDUAL_PENALTY)


@contextmanager
def extra_residuals(penalty):
    original = smb._evaluate_augmented_residual_vector

    def augmented(**kwargs):
        # Call the unmodified original equation/guard/hard residual implementation.
        original_vector = original(**kwargs)
        return np.concatenate([original_vector, penalty(kwargs["values"])])

    smb._evaluate_augmented_residual_vector = augmented
    try:
        yield
    finally:
        smb._evaluate_augmented_residual_vector = original


def classify(cand, evaluator, refs, err=None):
    result = dict(cls="error", err=err)
    if cand is None:
        return result
    result["x"] = list(map(float, cand.x_float))
    if "out_of_bounds" in cand.hard_violation_tags:
        result["cls"] = "left_box"
    elif not math.isfinite(cand.residual_norm_float):
        result["err"] = "nonfinite"
    else:
        result["res"] = cand.residual_norm_float
        if cand.residual_norm_float > RES_TOL:
            result["cls"] = "stuck"
        elif not (bool(cand.guard_ok) and cand.hard_feasible is not False):
            result["cls"] = "wrong_branch"
        else:
            value = answer_float(evaluator, cand.x_float)
            result["ans"] = value if value is not None and math.isfinite(value) else None
            result["cls"] = "wrong_answer"
            if value is not None:
                for j, ref in enumerate(refs):
                    if abs(value-ref) <= ANS_RTOL * max(1.0, abs(ref)):
                        result.update(cls="hit", ref=j)
                        break
    return result


def run_arm(p, case, arm, total_budget):
    began = time.monotonic()
    raw = json.loads((RAW / f"{p['id']}.json").read_text())
    bundle = bundle_for(case["dsl"])
    evaluator = build_ir_evaluator(bundle)
    bounds = infer_problem_bounds(bundle)
    config = ExternalPipelineConfig.production_baseline_tier(seed=0, total_time_budget_sec=180.0).search
    refs = reference_values(case["answer"])
    assert refs == raw["references"]
    penalty = PairPenalty(bundle, case["dsl"], p[arm], p["threshold"])
    telemetry = smb._SearchTelemetry()
    # probe_basins starts its aggregate clock after evaluator construction.
    search_began = time.monotonic()
    deadline = search_began + total_budget if total_budget is not None else None
    records = []
    with extra_residuals(penalty):
        for r in raw["records"]:
            t0 = time.monotonic()
            n0 = telemetry.evaluation_count
            try:
                if deadline is not None and t0 > deadline:
                    break
                cand = smb._collect_local_start_record(
                    bundle=bundle, evaluator=evaluator, bounds=bounds, config=config,
                    seed=0, start_index=r["k"], start=np.asarray(r["start"], dtype=float),
                    deadline_monotonic=deadline, telemetry=telemetry)
            except smb._SearchDeadlineExceeded:
                break
            except Exception as error:
                cand, err = None, f"{type(error).__name__}: {error}"
            else:
                err = None
            rec = classify(cand, evaluator, refs, err)
            rec.update(k=r["k"], sec=time.monotonic()-t0, nfev=telemetry.evaluation_count-n0)
            records.append(rec)
    return dict(id=p["id"], arm=arm, complete=len(records)==len(raw["records"]),
                records=records, total_seconds=time.monotonic()-began,
                search_seconds=time.monotonic()-search_began,
                nonfinite_penalty_calls=penalty.nonfinite_calls,
                total_budget=total_budget, n_expected=len(raw["records"]))


def check_inputs(plan):
    changed = [p for p, h in plan["inputs_sha256"].items() if digest(ROOT/p) != h]
    if changed:
        raise RuntimeError(f"frozen inputs changed: {changed}")


def run(workers, total_budget):
    plan = json.loads((OUT / "plan.json").read_text())
    check_inputs(plan)
    settings = dict(total_budget=total_budget, lm_max_nfev=smb._LM_MAX_NFEV,
                    powell_maxiter=smb._UNDERDETERMINED_POWELL_MAXITER,
                    workers=workers, plan_sha256=digest(OUT / "plan.json"),
                    code_sha256=digest(Path(__file__)), python=sys.version,
                    numpy=np.__version__, scipy=scipy.__version__)
    if (OUT / "run-settings.json").exists():
        old = json.loads((OUT / "run-settings.json").read_text())
        for key in ("total_budget", "plan_sha256", "code_sha256"):
            assert old[key] == settings[key], (key, old[key], settings[key])
    else:
        settings["started_at"] = datetime.now(UTC).isoformat()
        dump(OUT / "run-settings.json", settings)
    (OUT / "checkpoints").mkdir(exist_ok=True)
    cases = {c["id"]: c for c in map(json.loads, (ROOT / "benchmarks/cases.jsonl").open())}
    jobs = [(p, arm) for p in plan["problems"] for arm in ("treatment", "placebo")
            if p[arm] is not None]
    unfinished = [(p, a) for p, a in jobs if not (OUT/"checkpoints"/f"{p['id']}.{a}.json").exists()]
    began = time.monotonic()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        pending = {pool.submit(run_arm, p, cases[p["id"]], a, total_budget): (p, a)
                   for p, a in unfinished}
        for i, future in enumerate(as_completed(pending), 1):
            p, a = pending[future]
            result = future.result()
            dump(OUT/"checkpoints"/f"{p['id']}.{a}.json", result)
            print(f"RUN {i}/{len(unfinished)} {p['id']} {a} "
                  f"done={len(result['records'])}/{result['n_expected']} "
                  f"hits={sum(r['cls']=='hit' for r in result['records'])} "
                  f"sec={result['total_seconds']:.1f} wall={time.monotonic()-began:.1f}", flush=True)
    settings = json.loads((OUT / "run-settings.json").read_text())
    settings.update(finished_at=datetime.now(UTC).isoformat(), last_run_seconds=time.monotonic()-began)
    dump(OUT / "run-settings.json", settings)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=["prepare", "run"])
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--total-budget", type=float, default=120.0)
    ap.add_argument("--all-saved-starts", action="store_true")
    args = ap.parse_args()
    if not 1 <= args.workers <= 4:
        ap.error("workers must be 1..4")
    if args.action == "prepare":
        prepare(args.workers)
    else:
        run(args.workers, None if args.all_saved_starts else args.total_budget)


if __name__ == "__main__":
    main()
