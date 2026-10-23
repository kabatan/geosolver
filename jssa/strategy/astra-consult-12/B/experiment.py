"""astra-B: one-step diagnostics and monotone radial residual interventions.

Run with /home/kabatan/work/solver/.venv/bin/python -B experiment.py features
then the same command with `intervene`. All writes are inside this directory.
The production solver and DSL inputs are imported/read without changes.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import sys
import time
from pathlib import Path

for _key in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
    os.environ[_key] = "1"
sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "jssa/difficulty")]

import numpy as np
import scipy
from scipy.optimize import least_squares
from geosolver import GeometryProblem
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.search import scipy_multistart_backend as smb
from geosolver.engine.standard.contracts.external_pipeline_config import ExternalPipelineConfig
from probe_basins import answer_float, reference_values


def dump(path, value):
    def clean(x):
        if isinstance(x, (float, np.floating)):
            return float(x) if math.isfinite(x) else None
        if isinstance(x, (int, np.integer)):
            return int(x)
        if isinstance(x, np.ndarray):
            return clean(x.tolist())
        if isinstance(x, dict):
            return {str(k): clean(v) for k, v in x.items()}
        if isinstance(x, (tuple, list)):
            return [clean(v) for v in x]
        return x
    path.write_text(json.dumps(clean(value), ensure_ascii=False, indent=2) + "\n")


def all_cases():
    return {c["id"]: c for c in map(json.loads, (ROOT / "benchmarks/cases.jsonl").open())}


def context(case):
    bundle = load_problem_bundle(GeometryProblem.model_validate(case["dsl"]).engine_document())
    ev = build_ir_evaluator(bundle)
    box = np.array(infer_problem_bounds(bundle), dtype=float)
    return bundle, ev, box


def vector_function(bundle, ev, deadline=None):
    tel = smb._SearchTelemetry()
    fn = smb._AugmentedResidualVectorFn(
        bundle=bundle, evaluator=ev, n_constraints=len(bundle.spec.constraints),
        deadline_monotonic=deadline, telemetry=tel, constraint_scales=None)
    return fn, tel


def norm(v):
    return math.hypot(*map(float, v))


def valid_call(fn, tel, x):
    before = tel.failure_count
    try:
        r = fn(x)
        ok = tel.failure_count == before and np.all(np.isfinite(r))
        return r, bool(ok)
    except Exception:
        return None, False


def features():
    cases = all_cases()
    entries = list(csv.DictReader((ROOT / "jssa/difficulty/minima/basins-323.csv").open()))
    eligible = sorted(r["id"] for r in entries if int(r["n_vars"]) >= 1)
    case_dir = OUT / "features"
    case_dir.mkdir(exist_ok=True)
    results = []
    for i, cid in enumerate(eligible):
        path = case_dir / f"{cid}.json"
        if path.exists():
            results.append(json.loads(path.read_text()))
            continue
        started = time.monotonic()
        try:
            b, ev, box = context(cases[cid])
            n, m = len(b.var_names), len(b.spec.constraints)
            result = {"id": cid, "index": i, "n": n, "m": m, "box": box}
            if n > m:
                result.update(status="powell_excluded", rows=[])
            else:
                fn, tel = vector_function(b, ev)
                rng = np.random.default_rng([102312, i])
                rows = []
                for k in range(16):
                    x = box[:, 0] + rng.random(n) * (box[:, 1] - box[:, 0])
                    r, ok = valid_call(fn, tel, x)
                    row = {"k": k, "start": x, "valid_start": ok}
                    if not ok:
                        rows.append(row)
                        continue
                    rn = norm(r)
                    row["residual_norm"] = rn
                    row["guard_hard_penalties"] = r[-2:]
                    cols = []
                    for j in range(n):
                        h = 1e-5 * max(1.0, abs(x[j]))
                        xp, xm = x.copy(), x.copy()
                        xp[j] += h
                        xm[j] -= h
                        rp, op = valid_call(fn, tel, xp)
                        rm, om = valid_call(fn, tel, xm)
                        if not (op and om):
                            break
                        cols.append((rp - rm) / (2 * h))
                    row["valid_jacobian"] = len(cols) == n
                    if len(cols) != n:
                        rows.append(row)
                        continue
                    J = np.column_stack(cols)
                    delta, _, rank, sv = np.linalg.lstsq(J, -r, rcond=1e-10)
                    trial, trial_ok = valid_call(fn, tel, x + delta)
                    q = norm(trial - r - J @ delta) / max(rn, 1e-12) if trial_ok else 1e12
                    ratio = norm(trial) / max(rn, 1e-12) if trial_ok else 1e12
                    row.update(q=q, log1p_q=math.log1p(q), trial_ratio=ratio,
                               trial_valid=trial_ok, half_step=int(ratio <= 0.5),
                               step_box_norm=norm(delta / (box[:, 1] - box[:, 0])),
                               linear_remaining=norm(r + J @ delta) / max(rn, 1e-12),
                               rank=rank, svals=sv)
                    rows.append(row)
                good = [r for r in rows if "q" in r and math.isfinite(r["q"])]
                norms = [r["residual_norm"] for r in rows if r["valid_start"]]
                result.update(status="ok", rows=rows, n_valid=len(good),
                              Q=float(np.median([r["log1p_q"] for r in good])) if good else None,
                              good_step_fraction=float(np.mean([r["half_step"] for r in good])) if good else None,
                              step_box_norm=float(np.median([r["step_box_norm"] for r in good])) if good else None,
                              linear_remaining=float(np.median([r["linear_remaining"] for r in good])) if good else None,
                              a=max(1e-6, float(np.median(norms))) if norms else None,
                              evaluations=tel.evaluation_count)
        except Exception as exc:
            result = {"id": cid, "index": i, "status": "error", "error": repr(exc)}
        result["seconds"] = time.monotonic() - started
        dump(path, result)
        results.append(json.loads(path.read_text()))
        print(f"feature {i+1}/{len(eligible)} {cid} {result['status']} Q={result.get('Q')} {result['seconds']:.2f}s", flush=True)
    fields = ["id", "index", "status", "n", "m", "n_valid", "Q", "good_step_fraction", "step_box_norm", "linear_remaining", "a", "evaluations", "seconds", "error"]
    with (OUT / "features.csv").open("w") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    valid = [r for r in results if r.get("status") == "ok" and r.get("n") == 2 and r.get("n_valid", 0) >= 8]
    ordered = sorted(valid, key=lambda r: (-r["Q"], r["id"]))
    top = ordered[:6]
    bottom = sorted(valid, key=lambda r: (r["Q"], r["id"]))[:6]
    selected = [{"id": r["id"], "index": r["index"], "group": group, "Q": r["Q"], "a": r["a"]}
                for group, subset in [("high_Q", top), ("low_Q", bottom)] for r in subset]
    dump(OUT / "selected.json", selected)
    dump(OUT / "environment.json", {
        "python": sys.version, "executable": sys.executable, "numpy": np.__version__,
        "scipy": scipy.__version__, "platform": platform.platform(),
        "case_file_sha256": hashlib.sha256((ROOT / "benchmarks/cases.jsonl").read_bytes()).hexdigest(),
        "backend_sha256": hashlib.sha256(Path(smb.__file__).read_bytes()).hexdigest(),
        "protocol_sha256": hashlib.sha256((OUT / "protocol.md").read_bytes()).hexdigest(),
        "original_lm_cap": smb._LM_MAX_NFEV, "features_seed": 102312, "solve_seed": 102313})
    print("SELECTED", json.dumps(selected, ensure_ascii=False), flush=True)


def radial(r, a, mode):
    if mode == "base":
        return r
    if mode == "nohard":
        # Post-hoc diagnostic only. Candidate classification remains unchanged.
        out = r.copy()
        out[-1] = 0.0
        return out
    t = norm(r) / a
    if mode == "sharpen":
        return (1.0 + t*t) * r
    if mode == "flatten":
        return (math.asinh(t) / t if t else 1.0) * r
    if mode == "scale10":
        return 10.0 * r
    raise ValueError(mode)


def solve(b, ev, box, refs, start, a, mode, cap, k, timeout=30.0):
    started = time.monotonic()
    fn, tel = vector_function(b, ev, started + timeout)
    config = ExternalPipelineConfig.production_baseline_tier(seed=0, total_time_budget_sec=180.0).search
    rec = {"mode": mode, "cap": cap}
    try:
        opt = least_squares(lambda x: radial(fn(x), a, mode), start, method="lm",
                            max_nfev=cap, ftol=1e-14, xtol=1e-14, gtol=1e-14)
        rec.update(status=int(opt.status), scipy_nfev=int(opt.nfev), x=opt.x,
                   message=str(opt.message))
        cand = smb._build_candidate(
            evaluator=ev, config=config, bounds=[tuple(row) for row in box],
            values=np.array(opt.x, dtype=float), origin_seed=0,
            family_code=smb._LM_FAMILY_CODE, origin_start_point_index=k, telemetry=tel)
        rec.update(res=cand.residual_norm_float, guard_ok=bool(cand.guard_ok),
                   hard_feasible=cand.hard_feasible, hard_tags=list(cand.hard_violation_tags))
        if "out_of_bounds" in tuple(cand.hard_violation_tags):
            cls = "left_box"
        elif not math.isfinite(cand.residual_norm_float):
            cls = "nonfinite"
        elif cand.residual_norm_float > 1e-8:
            cls = "stuck"
        elif not (bool(cand.guard_ok) and cand.hard_feasible is not False):
            cls = "wrong_branch"
        else:
            value = answer_float(ev, opt.x)
            rec["answer"] = value
            cls = "hit" if value is not None and any(abs(value-ref) <= 1e-6*max(1.0, abs(ref)) for ref in refs) else "wrong_answer"
        rec["cls"] = cls
        # Report whether the augmented residual is near zero at successful ends.
        raw, _ = vector_function(b, ev)
        end_r = raw(opt.x)
        rec["augmented_residual_norm"] = norm(end_r)
        rec["guard_hard_penalties"] = end_r[-2:]
    except (smb._SearchDeadlineExceeded, TimeoutError):
        rec.update(cls="timeout", status=-9)
    except Exception as exc:
        rec.update(cls="error", status=-8, error=repr(exc))
    rec.update(seconds=time.monotonic()-started, evaluations=tel.evaluation_count,
               evaluation_failures=tel.failure_count)
    return rec


def intervene():
    cases = all_cases()
    selected = json.loads((OUT / "selected.json").read_text())
    case_dir = OUT / "interventions"
    case_dir.mkdir(exist_ok=True)
    for sel in selected:
        cid = sel["id"]
        path = case_dir / f"{cid}.json"
        if path.exists():
            continue
        started = time.monotonic()
        b, ev, box = context(cases[cid])
        refs = reference_values(cases[cid]["answer"])
        rng = np.random.default_rng([102313, sel["index"]])
        rows = []
        for k in range(40):
            start = box[:, 0] + rng.random(len(box)) * (box[:, 1] - box[:, 0])
            row = {"k": k, "start": start}
            for mode in ("base", "sharpen", "flatten"):
                r80 = solve(b, ev, box, refs, start, sel["a"], mode, 80, k)
                r320 = (solve(b, ev, box, refs, start, sel["a"], mode, 320, k)
                        if r80["status"] == 0 else dict(r80, cap=320, reused_terminated=True))
                row[mode] = {"80": r80, "320": r320}
            rows.append(row)
            if (k+1) % 10 == 0:
                counts = {mode: sum(r[mode]["80"]["cls"] == "hit" for r in rows) for mode in ("base", "sharpen", "flatten")}
                print(f"intervene {cid} {k+1}/40 {counts} {time.monotonic()-started:.1f}s", flush=True)
        result = dict(sel, references=refs, rows=rows, elapsed=time.monotonic()-started)
        dump(path, result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["features", "intervene"])
    args = parser.parse_args()
    {"features": features, "intervene": intervene}[args.mode]()
