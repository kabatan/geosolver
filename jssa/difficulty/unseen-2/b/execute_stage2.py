"""Q30b stage 2: unchanged inputs, solver, runner and exact-set scoring.

Only the runner's final storage callback is adapted to retain compact receipts.
One invocation runs one preregistered batch (at most four 188-second watchdogs).
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import fcntl
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import traceback

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[3]
DEST = BASE / "execution"
COMMIT = "b23f338a639a773bef2ae7ecbacebffc5b0ae1d5"
LOCK_SHA = "472bff87309f31d9a1de6e73e7767a234b43df9111f9ef36bf590e69b3be9113"
FILE_LIMIT = 4_999_999
SUMMARY_LIMIT = 4_900_000
CPU = None
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PYTHONPATH"] = os.pathsep.join([str(ROOT / "src"), str(ROOT)])
for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[key] = "1"
from benchmarks import research_runner as rr


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return digest(Path(path).read_bytes())


def read(path):
    return json.loads(Path(path).read_text())


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def save(path, data, *, new=False):
    path = Path(path)
    payload = (json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode()
    if len(payload) > FILE_LIMIT:
        raise ValueError(f"metadata exceeds file ceiling: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if new:
        with path.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    else:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".q30b-", delete=False) as stream:
            tmp = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)


def verify_gate():
    lock_path = BASE / "prediction.lock.json"
    if sha(lock_path) != LOCK_SHA:
        raise RuntimeError("prediction lock changed; do not execute")
    lock = read(lock_path)
    if git("show", f"{COMMIT}:{lock_path.relative_to(ROOT)}") != lock_path.read_bytes():
        raise RuntimeError("committed lock mismatch")
    checked = {}
    for rel, expected in lock["artifacts_sha256"].items():
        path = BASE / rel
        actual = sha(path)
        if actual != expected or digest(git("show", f"{COMMIT}:{path.relative_to(ROOT)}")) != expected:
            raise RuntimeError("locked artifact mismatch: " + rel)
        checked[str(path.relative_to(ROOT))] = actual
    for rel, expected in lock["control_file_sha256"].items():
        if sha(ROOT / rel) != expected:
            raise RuntimeError("control mismatch: " + rel)
        checked[rel] = expected
    source = {}
    frozen = lock["frozen_source"]["commit"]
    for rel in git("ls-tree", "-r", "--name-only", frozen, "src").decode().splitlines():
        content = (ROOT / rel).read_bytes()
        if content != git("show", f"{frozen}:{rel}"):
            raise RuntimeError("frozen src mismatch: " + rel)
        source[rel] = digest(content)
    source_hash = digest(json.dumps(source, sort_keys=True, separators=(",", ":")).encode())
    if source_hash != lock["frozen_source"]["sha256"]:
        raise RuntimeError("source manifest mismatch")
    refs = git("for-each-ref", "--contains", COMMIT, "--format=%(refname) %(objectname)", "refs/remotes").decode().splitlines()
    if not refs:
        raise RuntimeError("no remote-tracking reference contains the authorized commit")
    fp = rr.runtime_fingerprint()
    from geosolver.runtime.integrity import verify_engine_lock
    if fp["issues"] or not verify_engine_lock()[0]:
        raise RuntimeError("runtime verification failed")
    if (rr.CANONICAL_TIME_LIMIT_SECONDS, rr.CANONICAL_CORES) != (180, 1):
        raise RuntimeError("runner resource contract changed")
    return lock, {
        "verified_at_utc": now(), "prediction_commit": COMMIT,
        "commit_time": git("show", "-s", "--format=%cI", COMMIT).decode().strip(),
        "prediction_lock_sha256": LOCK_SHA, "prediction_sha256": lock["prediction_sha256"],
        "checked_artifacts": len(lock["artifacts_sha256"]), "checked_controls": len(lock["control_file_sha256"]),
        "checked_source_files": len(source), "source_manifest_sha256": source_hash,
        "frozen_commit": frozen, "runtime": fp, "python_executable": sys.executable,
        "source_git_tree": git("rev-parse", frozen + ":src").decode().strip(),
        "files_sha256": checked, "remote_tracking_refs": refs,
        "push_evidence": "User explicitly reports push around 2026-10-23T16:08:19Z; local remote-tracking ref agrees. No remote server timestamp inferred.",
        "explicit_stage2_execution_authorization": True,
        "storage_limit_bytes": FILE_LIMIT, "summary_limit_bytes": SUMMARY_LIMIT,
        "missing_record_policy": "Report separately, neither correct nor observed solver failure; preserve fixed denominators 85 and 17 for prediction thresholds.",
    }


def compact(value, depth=0):
    if isinstance(value, dict):
        if depth >= 10:
            return {"omitted_mapping_keys": list(value)[:80], "key_count": len(value)}
        items = list(value.items())
        out = {k: compact(v, depth + 1) for k, v in items[:80]}
        if len(items) > 80:
            out["omitted_key_count"] = len(items) - 80
        return out
    if isinstance(value, list):
        if len(value) > 8:
            return {"original_count": len(value), "first_6": [compact(v, depth + 1) for v in value[:6]],
                    "last_2": [compact(v, depth + 1) for v in value[-2:]]}
        return [compact(v, depth + 1) for v in value]
    if isinstance(value, str) and len(value) > 1500:
        return value[:1500] + f" [truncated: {len(value)} chars]"
    return value


def compact_raw(raw):
    result = raw.get("solver_result")
    diagnostics = (result or {}).get("diagnostics") or {}
    pipeline = diagnostics.get("pipeline_summary") or {}
    assembly = pipeline.get("exact_assembly") or {}
    # Preserve every field used by unmodified read_run_outcome and _answer_keys.
    retained = {k: diagnostics[k] for k in ("process_info", "phase_timings", "counters", "rejection_tags", "numeric_feasible", "exact_identified") if k in diagnostics}
    retained["pipeline_summary"] = {
        "exact_assembly": {k: assembly[k] for k in ("numeric_feasible_count", "rejection_tags") if k in assembly},
        "verification_records": [True] if pipeline.get("verification_records") else [],
    }
    stored = {k: v for k, v in raw.items() if k not in {"process", "solver_result"}}
    stored["process"] = {k: v for k, v in raw.get("process", {}).items() if k not in {"stdout", "stderr"}}
    for stream in ("stdout", "stderr"):
        text = raw.get("process", {}).get(stream, "")
        stored["process"][stream + "_excerpt"] = text[:2000]
        stored["process"][stream + "_characters"] = len(text)
        stored["process"][stream + "_sha256"] = digest(text.encode())
    stored["solver_result"] = ({**{k: v for k, v in result.items() if k != "diagnostics"}, "diagnostics": retained} if result else None)
    stored["storage"] = {"schema": "q30b-compact-receipt-v1", "raw_full_record_saved": False,
                         "recorded_at_utc": now(), "raw_canonical_sha256": digest(rr._canonical_json(raw).encode()),
                         "raw_canonical_bytes": len(rr._canonical_json(raw).encode()),
                         "read_run_outcome_preserved": rr.read_run_outcome(raw) == rr.read_run_outcome(stored),
                         "answer_keys_preserved": rr._answer_keys(result) == rr._answer_keys(stored["solver_result"])}
    stored["diagnostic_evidence"] = compact(diagnostics)
    if len(json.dumps(stored, ensure_ascii=False).encode()) > SUMMARY_LIMIT:
        stored["diagnostic_evidence"] = {"omitted_due_to_size": True, "original_keys": list(diagnostics)}
    return stored


def write_summary(path, raw):
    # No small-size assertion can discard the run. Save an essential receipt first
    # if richer compaction fails, and retain a distinct missing-record receipt if
    # even the public result cannot be serialized under the hard file ceiling.
    try:
        stored = compact_raw(raw)
        save(path, stored, new=True)
    except Exception:
        error = traceback.format_exc()[-6000:]
        essential = {k: v for k, v in raw.items() if k not in {"process", "solver_result"}}
        result = raw.get("solver_result") or {}
        essential.update(solver_result={k: v for k, v in result.items() if k != "diagnostics"},
                         outcome_before_storage=rr.read_run_outcome(raw), storage_error=error,
                         assessment_unavailable=True, missing_reason="summary_storage_error")
        save(path, essential, new=not Path(path).exists())


def prepare():
    lock, verification = verify_gate()
    if DEST.exists():
        raise RuntimeError("execution directory already exists; no automatic reset")
    validation = rr.validate_corpus(BASE / "cases.jsonl")
    if not validation["valid"]:
        raise RuntimeError(validation)
    import psutil
    loads = psutil.cpu_percent(interval=1, percpu=True)
    cpus = sorted(rr._independent_cpus(), key=lambda cpu: (loads[cpu], cpu))[:4]
    records = rr._load_cases(BASE / "cases.jsonl")
    if [r.identifier for r in records] != lock["adopted_problem_ids"]:
        raise RuntimeError("case ordering differs from prediction lock")
    # Storage stress check uses constructed data, never solver/local search/PSLQ.
    sample = {"case_id": "STORAGE-ONLY", "seed": 0, "process": {"returncode": 0},
              "solver_result": {"status": "no_answer_found", "answers": [], "diagnostics": {
                  "pipeline_summary": {"exact_assembly": {"numeric_feasible_count": 1}, "verification_records": [{"x": 1}]},
                  "large_synthetic_diagnostic": "x" * 6_000_000}}}
    reduced = compact_raw(sample)
    if rr.read_run_outcome(sample) != rr.read_run_outcome(reduced):
        raise RuntimeError("storage adapter changes outcome")
    DEST.mkdir()
    save(DEST / "preflight.json", {**verification, "cpus": cpus, "cpu_load_percent": {str(c): loads[c] for c in cpus},
         "outer_orchestrator_sha256": sha(__file__), "validation": validation,
         "solver_executions_during_preparation": 0, "storage_stress_check": {"synthetic_diagnostic_bytes": 6_000_000,
         "summary_bytes": len(json.dumps(reduced).encode()), "outcome_preserved": True},
         "plan": lock["run_conditions"]}, new=True)
    save(DEST / "campaign-manifest.json", rr._manifest(records, list(range(301, 306))), new=True)
    print(json.dumps({"prepared_at_utc": now(), "cpus": cpus, "runtime": verification["runtime"], "storage_stress_passed": True}), flush=True)


def initialize(queue):
    global CPU
    import psutil
    CPU = queue.get()
    psutil.Process().cpu_affinity([CPU])
    resource.setrlimit(resource.RLIMIT_FSIZE, (FILE_LIMIT, FILE_LIMIT))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    rr._atomic_json = write_summary


def worker(task):
    cid, seed = task["case_id"], task["seed"]
    path = DEST / "runs" / cid / f"{seed}.json"
    receipt = DEST / "run-lifecycle" / cid / f"{seed}.json"
    started = now()
    save(receipt, {**task, "started_at_utc": started, "cpu": CPU, "worker_pid": os.getpid()}, new=True)
    if path.exists():
        raise RuntimeError("no retry or overwrite")
    dsl_path = BASE / "dsl" / f"{cid}.json"
    record = rr.CaseRecord(cid, dsl_path, read(dsl_path), "Q30b", (), "runnable", "verified", cid)
    error = None
    with tempfile.TemporaryDirectory(prefix="q30b-") as tmp:
        os.environ.update(TMPDIR=tmp, TMP=tmp, TEMP=tmp)
        tempfile.tempdir = tmp
        try:
            rr._run_one(record, seed, DEST, CPU)
        except BaseException:
            error = traceback.format_exc()[-6000:]
        finally:
            tempfile.tempdir = None
    status = {**task, "started_at_utc": started, "finished_at_utc": now(), "cpu": CPU,
              "worker_pid": os.getpid(), "runner_exception": error, "record_present": path.is_file()}
    if path.is_file():
        raw = read(path)
        status.update(record_sha256=sha(path), record_bytes=path.stat().st_size,
                      outcome=rr.read_run_outcome(raw), assessment_unavailable=raw.get("assessment_unavailable", False))
    else:
        status.update(assessment_unavailable=True, missing_reason="runner_produced_no_saved_record")
    save(receipt, status)
    return status


def batch(number):
    lock, verification = verify_gate()
    preflight = read(DEST / "preflight.json")
    if preflight["outer_orchestrator_sha256"] != sha(__file__):
        raise RuntimeError("orchestrator changed after preflight")
    if not 1 <= number <= 25:
        raise ValueError("batch must be 1..25")
    with (DEST / "batch.guard").open("a") as guard:
        fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for prior in range(1, number):
            if not read(DEST / "batches" / f"{prior:02d}-complete.json")["all_workers_joined"]:
                raise RuntimeError("prior batch incomplete")
        if (DEST / "batches" / f"{number:02d}-start.json").exists():
            raise RuntimeError("batch already attempted; never retry")
        plan = lock["run_conditions"]["batches"][number - 1]
        tasks = [{"case_id": cid, "seed": plan["seed"], "batch": number} for cid in plan["case_ids"]]
        started = now()
        if number == 1:
            save(DEST / "execution-start.json", {"started_at_utc": started, "verification": verification,
                 "preflight_sha256": sha(DEST / "preflight.json"), "orchestrator_sha256": sha(__file__),
                 "max_parallel": 4, "automatic_retry": False}, new=True)
        save(DEST / "batches" / f"{number:02d}-start.json", {"batch": number, "started_at_utc": started,
             "tasks": tasks, "gate_verified_at_utc": verification["verified_at_utc"], "cpus": preflight["cpus"]}, new=True)
        print(json.dumps({"batch": number, "started_at_utc": started, "tasks": tasks}), flush=True)
        ctx = multiprocessing.get_context("spawn")
        queue = ctx.Queue()
        for cpu in preflight["cpus"]:
            queue.put(cpu)
        results = []
        with concurrent.futures.ProcessPoolExecutor(max_workers=len(tasks), mp_context=ctx, initializer=initialize, initargs=(queue,)) as pool:
            futures = {pool.submit(worker, task): task for task in tasks}
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                except BaseException:
                    result = {**futures[future], "assessment_unavailable": True, "missing_reason": "orchestrator_worker_error",
                              "error": traceback.format_exc()[-6000:]}
                    save(DEST / "missing" / f'{result["case_id"]}-{result["seed"]}.json', result, new=True)
                results.append(result)
                print(json.dumps(result, ensure_ascii=False), flush=True)
        queue.close()
        queue.join_thread()
        save(DEST / "batches" / f"{number:02d}-complete.json", {"batch": number, "started_at_utc": started,
             "completed_at_utc": now(), "all_workers_joined": True, "results": results}, new=True)
        print(json.dumps({"batch": number, "all_workers_joined": True, "completed": len(results)}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "batch", "verify"])
    parser.add_argument("number", type=int, nargs="?")
    args = parser.parse_args()
    if args.action == "prepare":
        prepare()
    elif args.action == "batch":
        batch(args.number)
    else:
        _, verification = verify_gate()
        print(json.dumps(verification, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
