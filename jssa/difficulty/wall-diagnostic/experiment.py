"""Q3 frozen, input-only one-step diagnostic and paired development experiment.

Never runs the unseen set. All writes stay beneath HERE. Run with -B.
"""
from __future__ import annotations

import os
for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
              "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "1"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import signal
import sys
import time

import numpy as np
import scipy

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "jssa/difficulty"))
from probe_basins import (GeometryProblem, load_problem_bundle, build_ir_evaluator,
                         infer_problem_bounds, reference_values, answer_float, smb,
                         ExternalPipelineConfig)

RAW = ROOT / "jssa/difficulty/minima/raw-323"
SEED = 17030
POINTS = 256
MIN_DENOM = 32
PER_GROUP = 30
LOCAL_SECONDS = 5.0


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def object_sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode()).hexdigest()


def clean(obj):
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, np.ndarray)):
        return [clean(v) for v in obj]
    if isinstance(obj, np.generic):
        return clean(obj.item())
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj


def write_json(path, data):
    path = Path(path).resolve()
    assert path.is_relative_to(HERE)
    text = json.dumps(clean(data), ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    assert len(text.encode()) < 20_000_000
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def write_csv(path, rows):
    path = Path(path).resolve()
    assert path.is_relative_to(HERE)
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(clean(rows))
    assert path.stat().st_size < 20_000_000


def read_case(cid, scoring=False):
    for line in (ROOT / "benchmarks/cases.jsonl").open():
        case = json.loads(line)
        if case["id"] == cid:
            return case if scoring else {"id": cid, "dsl": case["dsl"]}
    raise KeyError(cid)


def context(cid, scoring=False):
    case = read_case(cid, scoring=scoring)
    bundle = load_problem_bundle(GeometryProblem.model_validate(case["dsl"]).engine_document())
    ev = build_ir_evaluator(bundle)
    bounds = np.asarray(infer_problem_bounds(bundle), dtype=float)
    return case, bundle, ev, bounds


def hard(ev, x):
    try:
        return bool(ev.evaluate_float_hard_feasibility(list(x), include_margins=False).hard_feasible)
    except Exception:
        return None


def finite_residual(bundle, ev, x):
    """Finite equations plus the unchanged guard row; NEVER the 1e10 fallback."""
    try:
        result = ev.evaluate_float_residual(list(x))
        r = np.asarray(result.residual_vector, dtype=float)
        if (result.evaluation_status is not smb.EvaluationStatus.OK or not result.is_finite
                or r.shape != (len(bundle.spec.constraints),) or not np.isfinite(r).all()):
            return None
        g = 10.0 * smb._evaluate_guard_penalty(bundle=bundle, evaluator=ev, values=np.asarray(x))
        v = np.append(r, g)
        return v if np.isfinite(v).all() else None
    except Exception:
        return None


def one_step(x, lo, hi, residual, feasibility):
    """One damped direction, first sufficient-decrease trial, no iteration."""
    counts = Counter()

    def r_at(z):
        counts["residual_calls"] += 1
        return residual(z)

    def f_at(z):
        counts["hard_calls"] += 1
        return feasibility(z)

    out = {"start": np.asarray(x).tolist(), "status": None}
    F = f_at(x)
    out["start_F"] = F
    if F is None:
        out["status"] = "start_hard_error"
    elif not F:
        out["status"] = "start_I"
    else:
        r = r_at(x)
        if r is None:
            out["status"] = "start_residual_invalid"
        else:
            ss = float(r @ r)
            out.update(start_ss=ss, start_eq_ss=float(r[:-1] @ r[:-1]))
            if not math.isfinite(ss) or ss <= 0:
                out["status"] = "zero_or_nonfinite_ss"
            else:
                cols = []
                for j in range(len(x)):
                    h = 1e-6 * max(1.0, hi[j] - lo[j])
                    dx = np.zeros_like(x)
                    dx[j] = h
                    rp, rm = r_at(x + dx), r_at(x - dx)
                    if rp is None or rm is None or rp.shape != r.shape or rm.shape != r.shape:
                        out["status"] = "difference_invalid"
                        break
                    cols.append((rp - rm) / (2.0 * h))
                if out["status"] is None:
                    J = np.column_stack(cols)
                    D = np.maximum(np.linalg.norm(J, axis=0), 1e-8)
                    try:
                        A = np.vstack((J / D, np.sqrt(1e-3) * np.eye(len(x))))
                        b = np.concatenate((-r, np.zeros(len(x))))
                        delta = np.linalg.lstsq(A, b, rcond=None)[0] / D
                    except (ValueError, np.linalg.LinAlgError, FloatingPointError):
                        delta = np.full_like(x, np.nan)
                    if not np.isfinite(delta).all():
                        out["status"] = "linear_solve_invalid"
                    else:
                        out["delta"] = delta.tolist()
                        for exponent in range(9):
                            alpha = 2.0 ** (-exponent)
                            xx = x + alpha * delta
                            if not np.isfinite(xx).all() or np.any(xx < lo) or np.any(xx > hi):
                                counts["trial_outside_box"] += 1
                                continue
                            rr = r_at(xx)
                            if rr is None:
                                counts["trial_residual_invalid"] += 1
                                continue
                            s2 = float(rr @ rr)
                            if math.isfinite(s2) and s2 <= .99 * ss:
                                FF = f_at(xx)
                                out.update(alpha=alpha, trial=xx.tolist(), trial_F=FF,
                                           trial_ss=s2, trial_eq_ss=float(rr[:-1] @ rr[:-1]))
                                out["status"] = "trial_hard_error" if FF is None else "decrease"
                                break
                        if out["status"] is None:
                            out["status"] = "no_decrease"
    out.update(counts)
    return out


def diagnostic(task):
    index, cid = task
    t0 = time.monotonic()
    _, bundle, ev, bounds = context(cid)
    lower, upper = bounds.T
    starts = lower + (upper - lower) * np.random.default_rng([SEED, index]).random((POINTS, len(lower)))
    compile_seconds = time.monotonic() - t0
    rows = []
    for k, x in enumerate(starts):
        t1 = time.monotonic()
        row = one_step(x, lower, upper, lambda z: finite_residual(bundle, ev, z), lambda z: hard(ev, z))
        row.update(k=k, seconds=time.monotonic() - t1)
        rows.append(row)
    den = sum(r["status"] == "decrease" for r in rows)
    crosses = sum(r["status"] == "decrease" and r["trial_F"] is False for r in rows)
    W_raw = crosses / den if den else None
    W = W_raw if den >= MIN_DENOM else None
    group = "undetermined" if W is None else "high" if W >= .25 else "low" if W <= .05 else "middle"
    n = len(bundle.var_names)
    m = len(bundle.spec.constraints)
    return {"id": cid, "index": index, "n_vars": n, "n_eq": m,
            "method": "LM" if n <= m else "Powell", "bounds": bounds.tolist(),
            "seed": [SEED, index], "points": POINTS, "n_F": sum(r["start_F"] is True for r in rows),
            "denominator": den, "crossings": crosses, "W_raw": W_raw, "W": W, "group": group,
            "reasons": dict(Counter(r["status"] for r in rows)),
            "compile_seconds": compile_seconds, "seconds": time.monotonic() - t0,
            "residual_calls": sum(r.get("residual_calls", 0) for r in rows), "records": rows}


def classify(ev, cand, refs):
    if cand is None:
        return {"cls": "error"}
    out = {"x": list(map(float, cand.x_float)), "hard": cand.hard_feasible,
           "guard_ok": cand.guard_ok, "tags": list(cand.hard_violation_tags)}
    if "out_of_bounds" in cand.hard_violation_tags:
        out["cls"] = "left_box"
    elif not math.isfinite(cand.residual_norm_float):
        out["cls"] = "error"
    else:
        out["res"] = float(cand.residual_norm_float)
        if cand.residual_norm_float > 1e-8:
            out["cls"] = "stuck"
        elif not cand.guard_ok or cand.hard_feasible is False:
            out["cls"] = "wrong_branch"
        else:
            val = answer_float(ev, cand.x_float)
            out["ans"] = val
            out["cls"] = "hit" if val is not None and any(
                abs(val - ref) <= 1e-6 * max(1.0, abs(ref)) for ref in refs) else "wrong_answer"
    return out


def alarm_handler(signum, frame):
    raise TimeoutError("Q3 per-start 5 second limit")


def solve(bundle, ev, bounds, start, k, refs, arm):
    old_hard, old_ls, old_minimize = smb._evaluate_hard_feasibility_penalty, smb.least_squares, smb.minimize
    status = {}
    hard_calls = 0

    def no_hard(**kw):
        nonlocal hard_calls
        hard_calls += 1
        return 0.0

    def logged(fun):
        def call(*args, **kwargs):
            ans = fun(*args, **kwargs)
            status.update(status=int(ans.status), message=str(ans.message), nfev=int(ans.nfev))
            return ans
        return call

    if arm == "N":
        smb._evaluate_hard_feasibility_penalty = no_hard
    smb.least_squares, smb.minimize = logged(old_ls), logged(old_minimize)
    telemetry = smb._SearchTelemetry()
    config = ExternalPipelineConfig.production_baseline_tier(seed=0, total_time_budget_sec=180.0).search
    previous_handler = signal.signal(signal.SIGALRM, alarm_handler)
    t0 = time.monotonic()
    try:
        signal.setitimer(signal.ITIMER_REAL, LOCAL_SECONDS)
        cand = smb._collect_local_start_record(bundle=bundle, evaluator=ev, bounds=bounds.tolist(),
            config=config, seed=0, start_index=k, start=np.asarray(start, dtype=float),
            deadline_monotonic=t0 + LOCAL_SECONDS, telemetry=telemetry)
        signal.setitimer(signal.ITIMER_REAL, 0)
        # Restore the hard function before original final scoring, too.
        smb._evaluate_hard_feasibility_penalty = old_hard
        result = classify(ev, cand, refs)
    except (smb._SearchDeadlineExceeded, TimeoutError):
        result = {"cls": "timeout"}
    except Exception as exc:
        result = {"cls": "error", "error": repr(exc)}
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        smb._evaluate_hard_feasibility_penalty = old_hard
        smb.least_squares, smb.minimize = old_ls, old_minimize
    result.update(seconds=time.monotonic() - t0, evaluations=telemetry.evaluation_count,
                  optimizer=status, no_hard_calls=hard_calls)
    return result


def paired(task):
    index, cid = task
    t0 = time.monotonic()
    case, bundle, ev, bounds = context(cid, scoring=True)
    raw = json.loads((RAW / f"{cid}.json").read_text())
    if not np.array_equal(bounds, np.asarray(raw["box"])):
        raise ValueError(f"box mismatch {cid}")
    refs = reference_values(case["answer"])
    counts, hits, selected = Counter(), Counter(), []
    hard_errors = 0
    for r in sorted(raw["records"], key=lambda r: r["k"]):
        F = hard(ev, r["start"])
        hard_errors += F is None
        # Same conservative classification as the saved probe and G; report exceptions.
        F = F is True
        counts[F] += 1
        hits[F] += r["cls"] == "hit"
        if counts[F] <= PER_GROUP:
            selected.append((r, F))
    records = []
    for saved, F in selected:
        k = saved["k"]
        out = {"k": k, "F": F, "start": saved["start"], "saved_cls": saved["cls"],
               "saved_seconds": saved.get("sec"), "saved_x": saved.get("x")}
        order = ["B", "N"] if k % 2 == 0 else ["N", "B"]
        for arm in order:
            out[arm] = solve(bundle, ev, bounds, saved["start"], k, refs, arm)
        records.append(out)
    return {"id": cid, "index": index, "n_vars": len(bundle.var_names),
            "n_eq": len(bundle.spec.constraints), "saved_n_F": counts[True], "saved_n_I": counts[False],
            "saved_hit_F": hits[True], "saved_hit_I": hits[False], "start_hard_errors": hard_errors,
            "records": records, "seconds": time.monotonic() - t0}


def code_inventory():
    paths = sorted((ROOT / "src").rglob("*.py"))
    paths += [ROOT / "jssa/difficulty/probe_basins.py", HERE / "experiment.py",
              HERE / "preregistration.md"]
    return {str(p.relative_to(ROOT)): sha(p) for p in paths}


def freeze():
    if (HERE / "freeze.json").exists():
        raise RuntimeError("freeze.json already exists; do not overwrite a registration")
    rows = list(csv.DictReader((ROOT / "jssa/difficulty/minima/basins-323.csv").open()))
    ids = sorted(r["id"] for r in rows if int(r["n_vars"]) >= 1)
    assert len(ids) == len(set(ids)) == 292
    manifest = []
    for i, cid in enumerate(ids):
        raw_path = RAW / f"{cid}.json"
        raw = json.loads(raw_path.read_text())
        manifest.append({"index": i, "id": cid, "dsl_sha256": object_sha(read_case(cid)["dsl"]),
                         "raw_sha256": sha(raw_path), "n_vars": raw["n_vars"],
                         "n_eq": raw["n_constraints"], "saved_starts": len(raw["records"])})
    write_json(HERE / "manifest.json", manifest)
    write_json(HERE / "freeze.json", {"frozen_utc": now(), "manifest_sha256": sha(HERE / "manifest.json"),
        "files": code_inventory(), "python": sys.version, "executable": sys.executable,
        "numpy": np.__version__, "scipy": scipy.__version__, "workers_max": 4,
        "q2_exists_at_freeze": (ROOT / "jssa/difficulty/unseen-1983").exists(),
        "q1_exists_at_freeze": (ROOT / "jssa/difficulty/wall-292").exists()})
    print("Frozen", len(ids), "cases", now(), flush=True)


def verify_freeze():
    f = json.loads((HERE / "freeze.json").read_text())
    assert f["manifest_sha256"] == sha(HERE / "manifest.json")
    assert f["files"] == code_inventory(), "Code or preregistration changed after freezing"
    manifest = json.loads((HERE / "manifest.json").read_text())
    for row in manifest:
        assert row["raw_sha256"] == sha(RAW / f"{row['id']}.json")
        assert row["dsl_sha256"] == object_sha(read_case(row["id"])["dsl"])
    return manifest


def run(phase, workers):
    manifest = verify_freeze()
    assert 1 <= workers <= 4
    out = HERE / ("diagnostics" if phase == "diagnose" else "paired")
    out.mkdir(exist_ok=True)
    fn = diagnostic if phase == "diagnose" else paired
    tasks = [(r["index"], r["id"]) for r in manifest if not (out / f"{r['id']}.json").exists()]
    started = now()
    t0 = time.monotonic()
    errors = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fn, task): task for task in tasks}
        for n, fut in enumerate(as_completed(futures), 1):
            task = futures[fut]
            try:
                result = fut.result()
                write_json(out / f"{task[1]}.json", result)
                print(phase, n, "/", len(tasks), task[1], "seconds", round(result["seconds"], 3), flush=True)
            except Exception as exc:
                errors.append({"id": task[1], "exception": repr(exc)})
                print("ERROR", task[1], repr(exc), flush=True)
    write_json(HERE / f"{phase}-run.json", {"started_utc": started, "finished_utc": now(),
        "wall_seconds": time.monotonic() - t0, "workers": workers, "tasks": len(tasks), "errors": errors})
    if errors:
        raise RuntimeError(errors)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("phase", choices=["freeze", "diagnose", "paired", "verify"])
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    if args.phase == "freeze":
        freeze()
    elif args.phase == "verify":
        print("Frozen inputs/code verified", len(verify_freeze()))
    else:
        run(args.phase, args.workers)


if __name__ == "__main__":
    main()
