"""Q36: one authorized, fixed-seed job per command; never retry or fill gaps.

Preparation imports/validates the frozen product but performs no search.
The only product hooks observe local termination and compact completed output.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
import traceback

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OUT = HERE / "stage2"
COMMIT = "bffba67a5af6591b7f2b547ab3b32a808c4b0a78"
FROZEN = "60db4b679b04167175c51c479c87c22fa663fda0"
LOCK_SHA = "143fc5989ebad6339d46036aaed9e4cc8c1b416e9a96a79fbbdf1c20d861811d"
SOURCE = "sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5"
LIMIT = 4_999_999
THREADS = {k: "1" for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")}
os.environ.update(THREADS)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PYTHONPATH"] = os.pathsep.join([str(ROOT / "src"), str(HERE), str(ROOT)])
sys.path[:0] = [str(ROOT / "src"), str(HERE), str(ROOT)]


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return digest(Path(path).read_bytes())


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value, exclusive=True):
    data = (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode()
    assert len(data) <= LIMIT, (path, len(data))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb" if exclusive else "wb") as stream:
        stream.write(data)


def limits():
    resource.setrlimit(resource.RLIMIT_FSIZE, (LIMIT, LIMIT))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def verify_locked():
    assert sha(HERE / "prediction.lock.json") == LOCK_SHA
    lock = read(HERE / "prediction.lock.json")
    checks = {}
    for name in ["prediction.lock.json", *[x["path"] for x in lock["frozen_artifacts"]]]:
        b = (HERE / name).read_bytes()
        assert b == git("show", f"{COMMIT}:{(HERE / name).relative_to(ROOT)}"), name
        if name != "prediction.lock.json":
            row = next(x for x in lock["frozen_artifacts"] if x["path"] == name)
            assert digest(b) == row["sha256"] and len(b) == row["bytes"], name
        checks[name] = {"sha256": digest(b), "bytes": len(b), "matches_commit": True}
    return checks


def verify_runtime():
    from benchmarks.research_runner import runtime_fingerprint
    from geosolver.runtime.integrity import verify_engine_lock
    assert not git("diff", FROZEN, "--", "src")
    assert not git("ls-files", "--others", "--exclude-standard", "src")
    fp = runtime_fingerprint()
    assert not fp["issues"] and fp["source_hash"] == SOURCE, fp
    assert verify_engine_lock() == (True, SOURCE)
    return fp


def prepare():
    assert not OUT.exists(), "preparation is not repeatable over existing evidence"
    checks = verify_locked()
    fp = verify_runtime()
    manifest = read(HERE / "source-manifest.json")
    source_checks = []
    doc_paths = {"jssa/strategy/codex-tasks-1023.md", "jssa/strategy/gpt-pro-consult-18-answer.md"}
    for row in manifest["sources"]:
        current = sha(ROOT / row["path"])
        match = current == row["sha256"]
        audit = {**row, "working_sha256": current, "matches_registration": match}
        if not match:
            assert row["path"] in doc_paths, row["path"]
            old = git("show", f"3e32bf7:{row['path']}")
            assert digest(old) == row["sha256"] and len(old) == row["bytes"]
            audit.update(original_preserved_in="3e32bf7", role="explanatory_document_not_computational_input")
        source_checks.append(audit)
    selected = sorted(r["case_id"] for r in csv.DictReader((HERE / "input-census.csv").open()) if r["multiple_answers"] == "True")
    assert len(selected) == 8
    cases = {r["id"]: r for r in map(json.loads, (ROOT / "benchmarks/cases.jsonl").read_text().splitlines())}
    import psutil
    from benchmarks.research_runner import _independent_cpus
    load = psutil.cpu_percent(interval=1, percpu=True)
    cpus = sorted(_independent_cpus(), key=lambda c: (load[c], c))[:2]
    from geosolver import GeometryProblem
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds
    sys.path.insert(0, str(ROOT / "jssa/difficulty"))
    from probe_basins import reference_values
    inputs = []
    references = {}
    for cid in selected:
        case = cases[cid]
        archive = read(ROOT / "jssa/difficulty/minima/raw-323" / f"{cid}.json")
        bundle = load_problem_bundle(GeometryProblem.model_validate(case["dsl"]).engine_document())
        bounds = [list(map(float, pair)) for pair in infer_problem_bounds(bundle)]
        assert bounds == archive["box"], cid
        refs = reference_values(case["answer"])
        assert refs == archive["references"], cid
        inputs.append({"case_id": cid, "dsl": case["dsl"], "box": bounds, "var_names": list(bundle.var_names)})
        references[cid] = {"answer": case["answer"], "numeric": refs}
    # Only after all read-only gates pass do we create the execution workspace.
    OUT.mkdir()
    for item in inputs:
        path = OUT / "inputs" / f"{item['case_id']}.json"
        save(path, item["dsl"])
        item["dsl_sha256"] = sha(path)
        del item["dsl"]
    save(OUT / "grading" / "references.json", references)
    tasks = [{"kind": kind, "case_id": cid, "seed": seed}
             for kind, seeds in (("local", range(36001, 36021)), ("full", range(36101, 36131)))
             for seed in seeds for cid in selected]
    for i, task in enumerate(tasks):
        task["job"] = i + 1
    save(OUT / "tasks.json", tasks)
    save(OUT / "source-checks.json", source_checks)
    code = {name: sha(HERE / name) for name in ("stage2.py", "q36_save_worker.py")}
    save(OUT / "preflight.json", {
        "verified_at_utc": now(), "prediction_commit": COMMIT,
        "commit_time_utc": dt.datetime.fromisoformat(git("show", "-s", "--format=%cI", COMMIT).decode().strip()).astimezone(dt.timezone.utc).isoformat(),
        "remote_tracking_refs": git("branch", "-r", "--contains", COMMIT).decode().splitlines(),
        "push_basis": "explicit user confirmation; local remote-tracking ancestry checked, no server timestamp inferred",
        "user_reported_push_utc": "2026-10-23T15:58:18Z approximately",
        "explicit_stage2_authorization_received": True,
        "locked_artifacts": checks, "selection_file": "input-census.csv",
        "source_checks_count": len(source_checks), "source_document_drifts": sorted(doc_paths),
        "computational_sources_match_registration": True,
        "frozen_commit": FROZEN, "src_git_tree": git("rev-parse", FROZEN + ":src").decode().strip(),
        "runtime": fp, "python": sys.executable, "python_version": sys.version,
        "cpus": cpus, "thread_environment": THREADS, "max_parallel": 2,
        "local_deadline_seconds": 120, "local_outer_seconds": 150,
        "full_budget_seconds": 180, "full_outer_seconds": 200,
        "file_size_limit_bytes": LIMIT, "code_sha256": code,
        "inputs": inputs, "tasks_sha256": sha(OUT / "tasks.json"),
        "references_sha256": sha(OUT / "grading/references.json"),
        "search_invocations_during_preparation": 0,
        "storage_design": "Frozen standard worker executes unchanged; completed artifacts retain all answers and per-value exact-candidate origins, while large coordinate/diagnostic arrays are omitted. No numerical hook in full solver. Local optimizer wrappers only record returned status and exceptions.",
    })
    print(json.dumps({"prepared": True, "at_utc": now(), "jobs": len(tasks), "cpus": cpus, "solver_invocations": 0}))


def local_job(task, result_path):
    import numpy as np
    sys.path.insert(0, str(ROOT / "jssa/difficulty"))
    import probe_basins as probe
    from geosolver import GeometryProblem
    from geosolver.engine.standard.contracts.external_pipeline_config import ExternalPipelineConfig
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    from geosolver.engine.standard.search import scipy_multistart_backend as smb
    cid, seed = task["case_id"], task["seed"]
    bundle = load_problem_bundle(GeometryProblem.model_validate(read(OUT / "inputs" / f"{cid}.json")).engine_document())
    evaluator = build_ir_evaluator(bundle)
    bounds = infer_problem_bounds(bundle)
    pf = read(OUT / "preflight.json")
    assert [list(map(float, b)) for b in bounds] == next(x["box"] for x in pf["inputs"] if x["case_id"] == cid)
    refs = read(OUT / "grading/references.json")[cid]["numeric"]
    config = ExternalPipelineConfig.production_baseline_tier(seed=seed, total_time_budget_sec=180.0).search
    lower = np.array([b[0] for b in bounds], dtype=float)
    upper = np.array([b[1] for b in bounds], dtype=float)
    telemetry, rng = smb._SearchTelemetry(), np.random.default_rng(seed)
    optimizer_stop = {}
    def observe(fn, backend):
        def call(*args, **kwargs):
            try:
                result = fn(*args, **kwargs)
            except BaseException as error:
                optimizer_stop.update(backend=backend, exception=type(error).__name__)
                raise
            optimizer_stop.update(backend=backend, status=int(result.status), success=bool(result.success), message=str(result.message))
            return result
        return call
    smb.least_squares = observe(smb.least_squares, "lm")
    smb.minimize = observe(smb.minimize, "powell")
    records, first_hit = [], {}
    out = {**task, "started_at_utc": now(), "box": [list(map(float, b)) for b in bounds],
           "references": refs, "starts_requested": 50, "records": records,
           "interrupted_start": None, "end_reason": "all_starts_completed"}
    started = time.monotonic()
    deadline = started + 120
    for k in range(50):
        if time.monotonic() > deadline:
            out["end_reason"] = "deadline_before_start"
            break
        start = lower + rng.random(lower.size) * (upper - lower)
        optimizer_stop.clear()
        t0, n0 = time.monotonic(), telemetry.evaluation_count
        try:
            cand = smb._collect_local_start_record(bundle=bundle, evaluator=evaluator, bounds=bounds,
                config=config, seed=seed, start_index=k, start=start, deadline_monotonic=deadline, telemetry=telemetry)
        except smb._SearchDeadlineExceeded:
            out["end_reason"] = "deadline_during_start"
            out["interrupted_start"] = {"k": k, "start": start.tolist(), "termination": dict(optimizer_stop)}
            break
        except Exception as error:
            cand, err = None, type(error).__name__
        else:
            err = None
        rec = {"k": k, "sec": time.monotonic() - t0, "nfev": telemetry.evaluation_count - n0,
               "start": start.tolist(), "x": None, "ans": None, "ref": None,
               "termination": dict(optimizer_stop), "start_feasible": probe._hard_feasible(evaluator, start)}
        if cand is not None:
            rec["x"] = [float(v) if math.isfinite(float(v)) else str(float(v)) for v in cand.x_float]
        if cand is None:
            rec.update(cls="error", err=err)
        elif "out_of_bounds" in tuple(cand.hard_violation_tags):
            rec["cls"] = "left_box"
        elif not math.isfinite(cand.residual_norm_float):
            rec.update(cls="error", err="nonfinite")
        else:
            rec["res"] = cand.residual_norm_float
            feasible = bool(cand.guard_ok) and cand.hard_feasible is not False
            if cand.residual_norm_float > probe.RES_TOL:
                rec["cls"] = "stuck"
            elif not feasible:
                rec["cls"] = "wrong_branch"
            else:
                value = probe.answer_float(evaluator, cand.x_float)
                rec["ans"] = value if value is not None and math.isfinite(value) else None
                if value is not None and not math.isfinite(value):
                    rec["ans_nonfinite"] = str(value)
                match = next((j for j, ref in enumerate(refs) if value is not None and abs(value-ref) <= probe.ANS_RTOL * max(1.0, abs(ref))), None)
                rec["cls"], rec["ref"] = ("wrong_answer", None) if match is None else ("hit", match)
                if match is not None and match not in first_hit:
                    svals, n_eq = probe.equality_jacobian_svals(evaluator, cand.x_float)
                    first_hit[match] = {"k": k, "x": list(cand.x_float), "svals": svals, "n_residuals": n_eq}
        records.append(rec)
        # Keep completed starts even if the outer deadline later kills this job.
        out.update(starts_done=len(records), unfinished_starts=50-len(records), elapsed_seconds=time.monotonic()-started)
        save(result_path.with_suffix(".partial.json"), out, exclusive=False)
    out.update(starts_done=len(records), unfinished_starts=50-len(records), elapsed_seconds=time.monotonic()-started,
               finished_at_utc=now(), first_hit=first_hit, complete_receipt=True)
    save(result_path, out)


def full_job(task, result_path):
    from geosolver import solve
    from geosolver.engine import EngineRunner
    cid = task["case_id"]
    # This process reads only the DSL, never the reference-answer file.
    dsl = read(OUT / "inputs" / f"{cid}.json")
    os.environ["Q36_COMPLETED_SET_PATH"] = str(result_path.with_suffix(".worker-final.json"))
    started = now()
    result = solve(dsl, {"seed": task["seed"], "cores": 1, "time_limit_seconds": 180},
                   runner=EngineRunner(worker_module="q36_save_worker"))
    record = result.model_dump(mode="json")
    record.update(task=task, started_at_utc=started, finished_at_utc=now())
    save(result_path, record)


def run_one(number):
    command_started = time.monotonic()
    pf = read(OUT / "preflight.json")
    assert sha(OUT / "tasks.json") == pf["tasks_sha256"]
    task = read(OUT / "tasks.json")[number-1]
    assert task["job"] == number
    verify_locked()
    fp = verify_runtime()
    assert fp == pf["runtime"]
    for name, expected in pf["code_sha256"].items():
        assert sha(HERE / name) == expected, name
    item = next(x for x in pf["inputs"] if x["case_id"] == task["case_id"])
    assert sha(OUT / "inputs" / f"{task['case_id']}.json") == item["dsl_sha256"]
    assert sha(OUT / "grading/references.json") == pf["references_sha256"]
    guard = None
    for slot in range(2):
        candidate = (OUT / f"slot-{slot}.guard").open("a")
        try:
            fcntl.flock(candidate, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            candidate.close()
        else:
            guard = candidate
            break
    assert guard is not None, "maximum two concurrent jobs"
    os.sched_setaffinity(0, {pf["cpus"][slot]})
    directory = OUT / task["kind"] / task["case_id"]
    directory.mkdir(parents=True, exist_ok=True)
    result_path = directory / f"{task['seed']}.json"
    start_path = result_path.with_suffix(".start.json")
    assert not start_path.exists() and not result_path.exists(), "no automatic retry, replacement, or overwrite"
    outer = 150 if task["kind"] == "local" else 200
    receipt = {**task, "started_at_utc": now(), "source_hash": SOURCE, "dsl_sha256": item["dsl_sha256"],
               "lock_sha256": LOCK_SHA, "cpu": pf["cpus"][slot], "outer_seconds": outer,
               "thread_environment": THREADS, "code_sha256": pf["code_sha256"]}
    save(start_path, receipt)
    print(json.dumps({"started": task, "utc": receipt["started_at_utc"]}), flush=True)
    import psutil
    log_path = result_path.with_suffix(".log")
    with log_path.open("xb") as log:
        process = subprocess.Popen([sys.executable, str(HERE / "stage2.py"), "_"+task["kind"], str(number)],
                                   cwd=ROOT, env=os.environ.copy(), stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        timed_out = False
        try:
            process.wait(timeout=max(0.1, outer - (time.monotonic()-command_started) - 0.25))
        except subprocess.TimeoutExpired:
            timed_out = True
            children = psutil.Process(process.pid).children(recursive=True)
            for child in reversed(children):
                try: child.kill()
                except psutil.NoSuchProcess: pass
            process.kill()
            process.wait(timeout=1)
    end = {**receipt, "finished_at_utc": now(), "command_elapsed_seconds": time.monotonic()-command_started,
           "outer_timeout": timed_out, "returncode": process.returncode,
           "result_available": result_path.exists(), "log_bytes": log_path.stat().st_size}
    end["artifacts"] = {p.name: {"sha256": sha(p), "bytes": p.stat().st_size}
                        for p in directory.glob(f"{task['seed']}.*") if p.is_file()}
    assert all(x["bytes"] <= LIMIT for x in end["artifacts"].values())
    save(result_path.with_suffix(".end.json"), end)
    print(json.dumps({"finished": task, "seconds": end["command_elapsed_seconds"],
                      "returncode": process.returncode, "result_available": result_path.exists()}), flush=True)
    guard.close()


def main():
    limits()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "_local", "_full"))
    parser.add_argument("number", type=int, nargs="?")
    args = parser.parse_args()
    if args.action == "prepare":
        assert args.number is None
        prepare()
    elif args.action == "run":
        run_one(args.number)
    else:
        task = read(OUT / "tasks.json")[args.number-1]
        assert args.action == "_" + task["kind"]
        path = OUT / task["kind"] / task["case_id"] / f"{task['seed']}.json"
        try:
            (local_job if task["kind"] == "local" else full_job)(task, path)
        except BaseException:
            save(path.with_suffix(".failure.json"), {"task": task, "at_utc": now(), "traceback": traceback.format_exc()})
            raise


if __name__ == "__main__":
    main()
