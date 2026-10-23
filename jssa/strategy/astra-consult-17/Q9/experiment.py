"""Q9 orientation-diverse multistart pilot; no edits outside this directory.

prepare reads only id,dsl from the benchmark and emits sanitized inputs.
Workers never load reference answers or historical solver outputs.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import signal
import sys
import time

for _env_name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_env_name] = "1"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True

import numpy as np
from mpmath import mp

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "jssa/difficulty"))
from geosolver import GeometryProblem
from geosolver.engine.standard.contracts.external_pipeline_config import ExternalPipelineConfig
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.evaluation.snapshots import evaluation_session, numerical_snapshot
from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.search import scipy_multistart_backend as smb
from probe_basins import answer_float
from ghost_scan import point_names

METHODS = ("U", "X", "G")
SEEDS = (910231, 910232, 910233)
NPOOL = 256
NSTART = 8
START_LIMIT = 2.0
PREP_LIMIT = 60.0


def clean(obj):
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, (tuple, list)):
        return [clean(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return clean(obj.tolist())
    if isinstance(obj, np.generic):
        return clean(obj.item())
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj


def save(path, obj):
    Path(path).write_text(json.dumps(clean(obj), ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


class LimitExceeded(BaseException):
    pass


@contextmanager
def time_limit(seconds):
    # BaseException deliberately avoids being swallowed by numerical callbacks.
    previous = signal.getsignal(signal.SIGALRM)
    def expired(_sig, _frame):
        raise LimitExceeded()
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def build(dsl):
    bundle = load_problem_bundle(GeometryProblem.model_validate(dsl).engine_document())
    return bundle, build_ir_evaluator(bundle)


def rng_for(cid, seed):
    return np.random.default_rng([seed, int(digest(cid)[:8], 16)])


def strata_at(ev, values):
    try:
        f = bool(ev.evaluate_float_hard_feasibility(list(values), include_margins=False).hard_feasible)
    except Exception:
        f = False
    try:
        r = ev.evaluate_float_residual(list(values))
        defined = bool(np.isfinite(np.asarray(r.residual_vector, dtype=float)).all())
    except Exception:
        defined = False
    return int(f) * 2 + int(defined)


def triples_for(cid, names):
    triples = list(itertools.combinations(range(len(names)), 3))
    if len(triples) > 256:
        triples.sort(key=lambda t: digest(cid + "|" + "|".join(names[i] for i in t)))
        triples = triples[:256]
    return triples


def figure(ev, values, names):
    b = ev.bundle
    arr = np.full((len(names), 2), np.nan)
    with mp.workprec(53), evaluation_session(ev):
        snap = numerical_snapshot(b.spec, b.var_names, list(map(float, values)),
                                  b.base_context, arithmetic="float")
        context = snap.for_expressions(names, partial=True)
        for k, name in enumerate(names):
            obj = context.get(name)
            try:
                arr[k] = float(obj.x), float(obj.y)
            except (AttributeError, TypeError, ValueError, OverflowError):
                pass
    return arr


def orientation_signature(coords, triples):
    if not triples:
        return np.empty(0, dtype=np.int8)
    t = np.asarray(triples, dtype=int)
    a, b, c = coords[t[:, 0]], coords[t[:, 1]], coords[t[:, 2]]
    sig = np.full(len(triples), 2, dtype=np.int8)
    with np.errstate(all="ignore"):
        u, v = b - a, c - a
        finite = np.isfinite(a).all(1) & np.isfinite(b).all(1) & np.isfinite(c).all(1)
        # Scale first to avoid squaring large coordinates; this leaves the ratio unchanged.
        scale = np.maximum(np.max(np.abs(u), axis=1), np.max(np.abs(v), axis=1))
        collapsed = finite & (scale == 0)
        valid = finite & np.isfinite(scale) & (scale > 0)
        un, vn = u[valid] / scale[valid, None], v[valid] / scale[valid, None]
        denom = np.maximum.reduce((np.sum(un * un, 1), np.sum(vn * vn, 1), np.sum((un - vn)**2, 1)))
        area = (un[:, 0] * vn[:, 1] - un[:, 1] * vn[:, 0]) / denom
        vals = np.where(np.abs(area) <= 1e-10, 0, np.sign(area)).astype(np.int8)
        sig[valid] = vals
        sig[collapsed] = 0
    return sig


def geometry_features(ev, pool, cid, names):
    triples = triples_for(cid, names)
    full = []
    points_finite = []
    for x in pool:
        try:
            coords = figure(ev, x, names)
        except Exception:
            coords = np.full((len(names), 2), np.nan)
        full.append(orientation_signature(coords, triples))
        points_finite.append(int(np.isfinite(coords).all(1).sum()))
    full = np.asarray(full, dtype=np.int8)
    varying = np.any(full != full[0], axis=0)
    sig = full[:, varying]
    return sig, {
        "point_names": names,
        "triples": [[names[i] for i in t] for t in triples],
        "varying_columns": np.flatnonzero(varying).tolist(),
        "n_triples": len(triples), "n_varying": int(varying.sum()),
        "pool_unique_signatures": len({tuple(s) for s in sig.tolist()}),
        "finite_points_min": min(points_finite), "finite_points_max": max(points_finite),
        "missing_fraction": float(np.mean(full == 2)) if full.size else 0.0,
    }


def select_diverse(features, strata, method, nstart=NSTART):
    selected = [0]
    used = np.zeros(len(strata), dtype=bool)
    used[0] = True
    distances = np.full(len(strata), np.inf)
    for k in range(1, nstart):
        last = selected[-1]
        if method == "X":
            new = np.linalg.norm(features - features[last], axis=1)
        elif features.shape[1]:
            new = np.mean(features != features[last], axis=1)
        else:
            new = np.zeros(len(strata))
        distances = np.minimum(distances, new)
        candidates = np.flatnonzero((strata == strata[k]) & ~used)
        if not len(candidates):
            raise AssertionError("stratum quota exhausted")
        best = int(candidates[np.argmax(distances[candidates])])
        selected.append(best)
        used[best] = True
    assert len(set(selected)) == nstart
    assert np.array_equal(strata[selected], strata[:nstart])
    return selected


def prepare_method(case, seed, method):
    t0 = time.perf_counter()
    bundle, ev = build(case["dsl"])
    box = np.asarray(infer_problem_bounds(bundle), dtype=float)
    if not (np.isfinite(box).all() and np.all(box[:, 1] > box[:, 0])):
        raise ValueError("invalid finite positive-width box")
    rng = rng_for(case["id"], seed)
    unit = rng.random((NSTART if method == "U" else NPOOL, len(box)))
    pool = box[:, 0] + unit * (box[:, 1] - box[:, 0])
    meta = {"method": method, "box": box, "var_names": bundle.var_names}
    strata = None
    sig = None
    if method == "U":
        indices = list(range(NSTART))
    else:
        tclass = time.perf_counter()
        strata = np.asarray([strata_at(ev, x) for x in pool], dtype=np.int8)
        meta["strata_sec"] = time.perf_counter() - tclass
        meta["pool_strata_counts"] = {str(k): int(np.sum(strata == k)) for k in range(4)}
        if method == "G":
            tg = time.perf_counter()
            sig, geom = geometry_features(ev, pool, case["id"], sorted(point_names(case["dsl"])))
            meta.update(geom)
            meta["geometry_sec"] = time.perf_counter() - tg
            features = sig
        else:
            features = unit
        ts = time.perf_counter()
        indices = select_diverse(features, strata, method)
        meta["selection_sec"] = time.perf_counter() - ts
    config = ExternalPipelineConfig.production_baseline_tier(seed=seed, total_time_budget_sec=180).search
    meta.update({"prep_sec": time.perf_counter() - t0, "indices": indices, "starts": pool[indices]})
    return {"bundle": bundle, "ev": ev, "bounds": box.tolist(), "config": config,
            "telemetry": smb._SearchTelemetry(), "meta": meta, "pool": pool,
            "strata": strata, "sig": sig, "rows": []}


def local_start(state, seed, k):
    start = state["meta"]["starts"][k]
    telemetry = state["telemetry"]
    n0 = telemetry.evaluation_count
    t0 = time.perf_counter()
    row = {"k": k, "start": start, "pool_index": state["meta"]["indices"][k]}
    try:
        with time_limit(START_LIMIT):
            cand = smb._collect_local_start_record(
                bundle=state["bundle"], evaluator=state["ev"], bounds=state["bounds"],
                config=state["config"], seed=seed, start_index=k, start=start,
                deadline_monotonic=time.monotonic() + START_LIMIT, telemetry=telemetry)
    except (LimitExceeded, smb._SearchDeadlineExceeded, TimeoutError):
        cand = None
        row["status"] = "timeout"
    except Exception as exc:
        cand = None
        row.update(status="error", error=type(exc).__name__ + ": " + str(exc)[:200])
    row["solve_sec"] = time.perf_counter() - t0
    tv = time.perf_counter()
    if cand is None:
        row.setdefault("status", "error")
    else:
        row.update(x=list(cand.x_float), residual=cand.residual_norm_float,
                   guard_ok=bool(cand.guard_ok), hard_feasible=cand.hard_feasible,
                   hard_tags=list(cand.hard_violation_tags))
        if "out_of_bounds" in cand.hard_violation_tags:
            row["status"] = "left_box"
        elif not math.isfinite(cand.residual_norm_float):
            row["status"] = "error"
        elif cand.residual_norm_float > 1e-8:
            row["status"] = "stuck"
        elif not (bool(cand.guard_ok) and cand.hard_feasible is not False):
            row["status"] = "wrong_branch"
        else:
            # No reference value is available here. This is only a candidate.
            value = answer_float(state["ev"], cand.x_float)
            row["answer"] = value
            row["status"] = "candidate" if value is not None and math.isfinite(value) else "undefined_answer"
    row["check_sec"] = time.perf_counter() - tv
    row["nfev"] = telemetry.evaluation_count - n0
    row["sec"] = row["solve_sec"] + row["check_sec"]
    state["rows"].append(row)


def run_task(cid, seed):
    # Only these sanitized inputs are read by the numerical worker.
    case = json.loads((OUT / "inputs" / f"{cid}.json").read_text())
    assert set(case) == {"id", "dsl"}
    index = SEEDS.index(seed)
    order = METHODS[index:] + METHODS[:index]
    states, failed = {}, {}
    started = time.perf_counter()
    for method in order:
        ts = time.perf_counter()
        try:
            with time_limit(PREP_LIMIT):
                states[method] = prepare_method(case, seed, method)
        except (LimitExceeded, Exception) as exc:
            failed[method] = {"method": method, "prep_sec": time.perf_counter() - ts,
                              "prep_error": type(exc).__name__ + ": " + str(exc)[:400]}
    if all(m in states for m in METHODS):
        assert np.array_equal(states["U"]["pool"], states["G"]["pool"][:NSTART])
        assert np.array_equal(states["X"]["pool"], states["G"]["pool"])
        assert np.array_equal(states["X"]["strata"], states["G"]["strata"])
    for k in range(NSTART):
        local_order = order[k % 3:] + order[:k % 3]
        for method in local_order:
            if method in states:
                local_start(states[method], seed, k)
    # Audit metadata is not part of U's selection or cost. G already paid for it.
    if "G" in states:
        source = states["G"]
        for method, state in states.items():
            ix = state["meta"]["indices"]
            state["meta"]["selected_strata"] = source["strata"][ix]
            state["meta"]["selected_signatures"] = source["sig"][ix]
            state["meta"]["n_unique_signatures"] = len({tuple(v) for v in source["sig"][ix].tolist()})
            for row, stratum in zip(state["rows"], source["strata"][ix]):
                row["start_feasible"] = bool(stratum // 2)
                row["start_residual_finite"] = bool(stratum % 2)
    result = {"id": cid, "seed": seed, "prep_order": order,
              "task_elapsed": time.perf_counter() - started, "methods": {}}
    for method in METHODS:
        if method in states:
            result["methods"][method] = {**states[method]["meta"], "rows": states[method]["rows"]}
        else:
            result["methods"][method] = {**failed[method], "rows": [
                {"k": k, "status": "prep_failure", "sec": 0, "nfev": 0} for k in range(NSTART)]}
    save(OUT / "raw" / f"{cid}__{seed}.json", result)
    return {"id": cid, "seed": seed, "elapsed": round(result["task_elapsed"], 3), "prep_failed": list(failed)}


def prepare_inputs():
    if (OUT / "freeze.json").exists():
        raise RuntimeError("already frozen; refusing to replace inputs")
    cases = []
    for line in (ROOT / "benchmarks/cases.jsonl").read_text().splitlines():
        original = json.loads(line)
        cases.append({"id": original["id"], "dsl": original["dsl"]})
    inventory, eligible = [], []
    for case in cases:
        cid, dsl = case["id"], case["dsl"]
        d, p = len(dsl["variables"]), len(point_names(dsl))
        info = {"id": cid, "dsl_variables": d, "point_candidates": p}
        if not 2 <= d <= 6:
            info["reason"] = "variable_count"
        elif p < 4:
            info["reason"] = "fewer_than_4_point_candidates"
        else:
            try:
                with time_limit(PREP_LIMIT):
                    b, _ = build(dsl)
                info["n_vars"] = len(b.var_names)
                info["n_constraints"] = len(b.spec.constraints)
                if len(b.var_names) > len(b.spec.constraints):
                    info["reason"] = "Powell_path"
                else:
                    info["reason"] = "eligible"
                    info["selection_hash"] = digest("Q9-orientation-v1|" + cid)
                    eligible.append((info["selection_hash"], case))
            except (LimitExceeded, Exception) as exc:
                info["reason"] = "compile_error"
                info["error"] = type(exc).__name__ + ": " + str(exc)[:300]
        inventory.append(info)
    eligible.sort(key=lambda pair: pair[0])
    chosen = [c for _, c in eligible[:48]]
    selected = {c["id"] for c in chosen}
    for row in inventory:
        row["selected"] = row["id"] in selected
    (OUT / "inputs").mkdir(exist_ok=True)
    for case in chosen:
        save(OUT / "inputs" / f"{case['id']}.json", case)
    save(OUT / "manifest.json", {"created_utc": datetime.now(timezone.utc).isoformat(),
        "source_sha256": sha(ROOT / "benchmarks/cases.jsonl"), "eligible": len(eligible),
        "selected": [c["id"] for c in chosen], "seeds": SEEDS, "nstart": NSTART,
        "n_pool": NPOOL, "inventory": inventory})
    print(json.dumps({"eligible": len(eligible), "selected": len(chosen)}, ensure_ascii=False), flush=True)


def freeze():
    if (OUT / "freeze.json").exists():
        raise RuntimeError("freeze already exists")
    manifest = json.loads((OUT / "manifest.json").read_text())
    files = ["preregistration.md", "experiment.py", "analyze.py", "manifest.json"]
    files += [f"inputs/{cid}.json" for cid in manifest["selected"]]
    source_files = ["src/geosolver/engine/standard/search/scipy_multistart_backend.py",
                    "src/geosolver/engine/standard/evaluation/snapshots.py", "jssa/difficulty/probe_basins.py",
                    "jssa/difficulty/ghost_scan.py", "benchmarks/cases.jsonl"]
    save(OUT / "freeze.json", {"frozen_utc": datetime.now(timezone.utc).isoformat(),
        "files": {name: sha(OUT / name) for name in files},
        "source_files": {name: sha(ROOT / name) for name in source_files},
        "python": sys.executable, "numpy": np.__version__, "pid": os.getpid()})
    print("Protocol, code and input hashes frozen.", flush=True)


def verify_freeze():
    frozen = json.loads((OUT / "freeze.json").read_text())
    diffs = [name for name, value in frozen["files"].items() if sha(OUT / name) != value]
    diffs += [name for name, value in frozen["source_files"].items() if sha(ROOT / name) != value]
    if diffs:
        raise RuntimeError("frozen files changed: " + repr(diffs))
    return frozen


def selftest():
    toy = {"id": "Q9-TOY", "dsl": {"id": "Q9-TOY", "variables": ["u", "v"],
        "constructions": [{"name": "A", "expression": "Point(0,0)"},
                          {"name": "B", "expression": "Point(1,0)"},
                          {"name": "C", "expression": "Point(u,v)"},
                          {"name": "D", "expression": "Point(u+1,v)"}],
        "conditions": [{"left": "u", "operator": "=", "right": 2},
                       {"left": "v", "operator": "=", "right": 3},
                       {"left": "v", "operator": ">", "right": 0}], "target": "u+v"}}
    states = {m: prepare_method(toy, SEEDS[0], m) for m in METHODS}
    for state in states.values():
        local_start(state, SEEDS[0], 0)
    rows = [s["rows"][0] for s in states.values()]
    assert all(r["status"] == "candidate" and abs(r["answer"] - 5) < 1e-8 for r in rows), rows
    assert all(np.allclose(r["x"], rows[0]["x"], atol=1e-12, rtol=0) for r in rows)
    s = states["G"]["strata"]
    assert all(np.array_equal(s[states[m]["meta"]["indices"]], s[:NSTART]) for m in METHODS)
    # A non-axis-aligned rigid transform and scale preserve all Hamming distances.
    pts = np.array([[0., 0.], [2., 0.], [1., 3.], [4., 2.]])
    tri = triples_for("toy", ["A", "B", "C", "D"])
    rot = np.array([[.6, -.8], [.8, .6]])
    sig = orientation_signature(pts, tri)
    assert np.array_equal(sig, orientation_signature(17 * (pts @ rot) + [5., 7.], tri))
    assert np.array_equal(-sig, orientation_signature(pts * [-1, 1], tri))
    save(OUT / "selftest.json", {"passed": True, "synthetic_only": True, "first_rows": rows,
        "selected_indices": {m: s["meta"]["indices"] for m, s in states.items()},
        "invariance_checks": ["translation_rotation_scaling", "reflection", "same_start", "prefix_strata"]})
    print("Synthetic self-test passed.", flush=True)


def run(jobs):
    verify_freeze()
    if not 1 <= jobs <= 4:
        raise ValueError("jobs must be at most 4")
    (OUT / "raw").mkdir(exist_ok=True)
    manifest = json.loads((OUT / "manifest.json").read_text())
    tasks = [(cid, seed) for cid in manifest["selected"] for seed in SEEDS]
    tasks = [(cid, seed) for cid, seed in tasks if not (OUT / "raw" / f"{cid}__{seed}.json").exists()]
    t0 = time.perf_counter()
    with (OUT / "progress.jsonl").open("a") as log:
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            futures = {pool.submit(run_task, cid, seed): (cid, seed) for cid, seed in tasks}
            for n, future in enumerate(as_completed(futures), 1):
                result = future.result()
                result.update(done=n, total=len(tasks), elapsed_total=round(time.perf_counter()-t0, 3))
                line = json.dumps(result, ensure_ascii=False)
                log.write(line + "\n")
                log.flush()
                print(line, flush=True)
    verify_freeze()
    save(OUT / "execution.json", {"finished_utc": datetime.now(timezone.utc).isoformat(),
        "jobs": jobs, "completed_tasks_this_invocation": len(tasks), "elapsed_sec": time.perf_counter()-t0,
        "frozen_hashes_unchanged": True, "threads_per_worker": 1})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "selftest", "freeze", "run", "verify"))
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    {"prepare": prepare_inputs, "selftest": selftest, "freeze": freeze,
     "run": lambda: run(args.jobs), "verify": lambda: print(verify_freeze()["frozen_utc"])}[args.command]()
