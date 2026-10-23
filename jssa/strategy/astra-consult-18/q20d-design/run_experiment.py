"""Registered, serial pilot using the unchanged local and public solver paths."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import resource
import signal
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
MAIN = ["R1", "R2", "R3", "R4", "DEP", "S5", "S13", "S17"]
IDS = MAIN + ["FIXED4", "CUBIC"]
SEEDS = [202610231, 202610232]


def dump(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n")


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_hash():
    digest = hashlib.sha256()
    count = 0
    for path in sorted((ROOT / "src").rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            digest.update(str(path.relative_to(ROOT)).encode() + b"\0" + path.read_bytes() + b"\0")
            count += 1
    return {"sha256": digest.hexdigest(), "files": count}


def verify_lock():
    lock = json.loads((OUT / "registration-lock.json").read_text())
    for name, value in lock["files"].items():
        if sha(OUT / name) != value:
            raise RuntimeError(f"Registered file changed: {name}")
    if source_hash() != lock["src"]:
        raise RuntimeError("src changed")
    return lock


def freeze():
    path = OUT / "registration-lock.json"
    if path.exists():
        raise SystemExit("Already registered")
    filenames = ["preregistration.md", "build_inputs.py", "run_experiment.py", "input-manifest.json", "references.json"]
    filenames += [f"inputs/{i}.json" for i in IDS]
    value = {
        "frozen_utc": utc(), "first_solver_run_has_occurred": False,
        "files": {n: sha(OUT / n) for n in filenames}, "src": source_hash(),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "src_diff_from_60db4b6": subprocess.check_output(["git", "diff", "--name-only", "60db4b6", "--", "src"], cwd=ROOT, text=True),
        "python": sys.executable,
    }
    dump(path, value)
    print(json.dumps(value, ensure_ascii=False), flush=True)


def local():
    import numpy as np
    from mpmath import mp
    from geosolver import GeometryProblem
    from geosolver.engine.standard.contracts.external_pipeline_config import ExternalPipelineConfig
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
    from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    from geosolver.engine.standard.search import scipy_multistart_backend as smb

    references = json.loads((OUT / "references.json").read_text())
    starts = None
    first_bounds = None
    shared_document = None
    all_results = {}
    for case_id in MAIN:
        dsl = json.loads((OUT / "inputs" / f"{case_id}.json").read_text())
        common = {k: v for k, v in dsl.items() if k not in {"id", "target"}}
        if shared_document is None:
            shared_document = common
        assert common == shared_document
        bundle = load_problem_bundle(GeometryProblem.model_validate(dsl).engine_document())
        evaluator = build_ir_evaluator(bundle)
        bounds = infer_problem_bounds(bundle)
        if starts is None:
            first_bounds = bounds
            lower = np.array([b[0] for b in bounds], dtype=float)
            upper = np.array([b[1] for b in bounds], dtype=float)
            starts = lower + np.random.default_rng(20261023).random((16, len(bounds))) * (upper - lower)
        assert bounds == first_bounds
        telemetry = smb._SearchTelemetry()
        config = ExternalPipelineConfig.production_baseline_tier(seed=20261023, total_time_budget_sec=180).search
        begun = time.monotonic()
        deadline = begun + 20
        rows = []
        for k, start in enumerate(starts):
            if time.monotonic() >= deadline:
                break
            n0 = telemetry.evaluation_count
            row = {"k": k, "start": start.tolist()}
            try:
                candidate = smb._collect_local_start_record(
                    bundle=bundle, evaluator=evaluator, bounds=bounds, config=config,
                    seed=20261023, start_index=k, start=start.copy(),
                    deadline_monotonic=deadline, telemetry=telemetry,
                )
                if candidate is None:
                    row["class"] = "no_candidate"
                else:
                    row.update(x=list(candidate.x_float), residual=candidate.residual_norm_float,
                               guard_ok=candidate.guard_ok, hard_feasible=candidate.hard_feasible,
                               hard_violation_tags=list(candidate.hard_violation_tags))
                    with mp.workdps(50), high_precision_mode():
                        evaluation = evaluator.evaluate_answer_hp(
                            [mp.mpf(repr(float(v))) for v in candidate.x_float], precision=50)
                        value = getattr(evaluation, "answer_hp", None)
                        ref = mp.mpf(references[case_id]["decimal_100"])
                        row["answer"] = None if value is None else mp.nstr(value, 50)
                        numeric_match = value is not None and abs(value-ref) <= mp.mpf("1e-6")*max(1, abs(ref))
                    in_bounds = all(a <= x <= b for (a,b), x in zip(bounds, candidate.x_float))
                    success = (candidate.residual_norm_float <= 1e-8 and candidate.guard_ok
                               and candidate.hard_feasible is not False and in_bounds and numeric_match)
                    row["class"] = "hit" if success else "miss"
            except Exception as exc:
                row.update({"class": "error", "error": repr(exc)})
            row["evaluations"] = telemetry.evaluation_count - n0
            rows.append(row)
        all_results[case_id] = {"bounds": bounds, "elapsed": time.monotonic()-begun, "rows": rows}
        dump(OUT / "local-results.json", all_results)
        print("local", case_id, sum(r["class"] == "hit" for r in rows), "/", len(rows), flush=True)


def prepare_env():
    for name in ("tmp", "cache", "runs", "identification"):
        (OUT / name).mkdir(exist_ok=True)
    env = os.environ.copy()
    env.update({
        "PYTHONPATH": "src", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0",
        "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1", "TMPDIR": str(OUT / "tmp"),
        "XDG_CACHE_HOME": str(OUT / "cache"), "GEOSOLVER_MEMORY_LIMIT_BYTES": str(2*1024**3),
    })
    return env


def child_limits():
    eligible = os.sched_getaffinity(0)
    os.sched_setaffinity(0, {min(eligible)})
    resource.setrlimit(resource.RLIMIT_AS, (2*1024**3, 2*1024**3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (20*1024**2, 20*1024**2))


def bounded_process(command, folder, limit):
    import psutil
    folder.mkdir(exist_ok=True)
    started = time.monotonic()
    with (folder / "process.log").open("w") as log:
        process = subprocess.Popen(command, cwd=ROOT, env=prepare_env(), stdout=log, stderr=log,
                                   start_new_session=True, preexec_fn=child_limits)
        record = {"command": command, "started_utc": utc(), "outer_timeout": False}
        try:
            code = process.wait(timeout=limit)
        except subprocess.TimeoutExpired:
            record["outer_timeout"] = True
            try:
                children = psutil.Process(process.pid).children(recursive=True)
            except psutil.NoSuchProcess:
                children = []
            for child in children:
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            code = process.wait(timeout=5)
        record.update(returncode=code, elapsed_seconds=time.monotonic()-started, ended_utc=utc())
    dump(folder / "execution.json", record)
    return record


def full():
    for seed_index, seed in enumerate(SEEDS):
        order = IDS if seed_index == 0 else list(reversed(IDS))
        for case_id in order:
            folder = OUT / "runs" / f"{case_id}-{seed}"
            if folder.exists():
                raise RuntimeError(f"Refusing to overwrite {folder}")
            command = [sys.executable, "-m", "geosolver.application.cli", "solve",
                       str(OUT / "inputs" / f"{case_id}.json"), "--time-limit-seconds", "60",
                       "--cores", "1", "--seed", str(seed), "--output", str(folder / "result.json")]
            run = bounded_process(command, folder, 68)
            result = json.loads((folder / "result.json").read_text()) if (folder / "result.json").exists() else {}
            print("full", case_id, seed, result.get("status", "no_artifact"),
                  round(run["elapsed_seconds"], 3), flush=True)


def identification_worker(mode):
    from mpmath import mp
    from geosolver.engine.standard.exact_assembly.identify_answer import identify_answer
    from geosolver.runtime.deadline import runtime_session

    record = json.loads((OUT / "identification-input.json").read_text())
    precision = min(250, int(record["candidate"]["answer_precision_dps"]))
    with mp.workdps(max(precision+50, 550)), runtime_session(time.monotonic()+30):
        candidate = record["candidate"]
        value = mp.mpf(candidate["answer_hp"])
        uncertainty = mp.mpf(candidate["answer_uncertainty"])
        begin = time.monotonic()
        result = identify_answer(
            answer_hp=value, tier="strict", input_precision_dps=precision,
            answer_uncertainty=uncertainty,
            geometry_hint=record["geometry_hint"] if mode == "hint" else None,
        )
        output = asdict(result)
        output["seconds"] = time.monotonic()-begin
        output["mode"] = mode
        output["saved_candidate_precision"] = candidate["answer_precision_dps"]
        dump(OUT / "identification" / mode / "result.json", output)


def identification():
    # The hint is the exact expression derived when authoring the problem, not an inferred new solver capability.
    chosen = None
    for seed in SEEDS:
        path = OUT / "runs" / f"R4-{seed}" / "result.json"
        if not path.exists():
            continue
        result = json.loads(path.read_text())
        for candidate in result.get("diagnostics", {}).get("candidate_records", []):
            if candidate.get("answer_hp") is not None and candidate.get("answer_uncertainty") is not None:
                chosen = {"source": str(path.relative_to(OUT)), "candidate": candidate,
                          "geometry_hint": "sqrt(2)+sqrt(5)+sqrt(13)+sqrt(17)"}
                break
        if chosen:
            break
    if chosen is None:
        dump(OUT / "identification-input.json", {"status": "no_saved_candidate"})
        print("identify: no saved candidate", flush=True)
        return
    dump(OUT / "identification-input.json", chosen)
    for mode in ("plain", "hint"):
        bounded_process([sys.executable, str(Path(__file__).resolve()), "identify-worker", "--mode", mode],
                        OUT / "identification" / mode, 38)
        print("identify", mode, flush=True)


def run():
    verify_lock()
    if (OUT / "started.json").exists():
        raise RuntimeError("This registered experiment already started; do not repeat it silently")
    prepare_env()
    dump(OUT / "started.json", {"utc": utc(), "registration_sha256": sha(OUT / "registration-lock.json")})
    local()
    full()
    identification()
    verify_lock()
    dump(OUT / "execution-audit.json", {"ended_utc": utc(), "registered_files_unchanged": True,
                                       "src_unchanged": True, "src": source_hash()})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["freeze", "run", "identify-worker"])
    parser.add_argument("--mode", choices=["plain", "hint"])
    args = parser.parse_args()
    if args.action == "freeze":
        freeze()
    elif args.action == "run":
        run()
    else:
        identification_worker(args.mode)
