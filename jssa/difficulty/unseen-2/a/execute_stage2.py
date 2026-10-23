"""Q30a authorized execution; frozen inputs/product/scoring, bounded batches.

Only research_runner's final storage callback is replaced. Solver execution,
resource budgets, answer keys, completion rules and score.py remain unchanged.
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
COMMIT = "f5747643c634137d3414e854d20cac2b2c9b4bc9"
LOCK_SHA = "691cc47559053448b3d975a5c0173f6cf4971679d82b83645d30ec3acef4c884"
FILE_LIMIT = 4_999_999
SUMMARY_LIMIT = 4_900_000
CPU = None
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT / "src"), str(ROOT), str(BASE)]
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PYTHONPATH"] = os.pathsep.join([str(ROOT / "src"), str(ROOT)])
for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[key] = "1"
from benchmarks import research_runner as rr
from score import assess


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha(path):
    return rr._sha256_file(Path(path))


def read(path):
    return json.loads(Path(path).read_text())


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def encoded_parts(value):
    encoder = json.JSONEncoder(ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
    for part in encoder.iterencode(value):
        yield part.encode("utf-8")


def encoded_identity(value):
    digest = hashlib.sha256()
    count = 0
    for part in encoded_parts(value):
        digest.update(part)
        count += len(part)
    return {"sha256": digest.hexdigest(), "bytes": count}


def save(path, value, *, new=False):
    """Bound the serialized buffer before writing; atomically retain every receipt."""
    payload = bytearray()
    for part in encoded_parts(value):
        if len(payload) + len(part) + 1 > FILE_LIMIT:
            raise ValueError("summary exceeds 4,999,999-byte file ceiling")
        payload.extend(part)
    payload.extend(b"\n")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if new and path.exists():
        raise FileExistsError(path)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".q30a-", delete=False) as stream:
        tmp = Path(stream.name)
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)


def verify_gate():
    lock_path = BASE / "prediction.lock.json"
    if sha(lock_path) != LOCK_SHA:
        raise RuntimeError("prediction lock changed; do not execute")
    if git("show", f"{COMMIT}:{lock_path.relative_to(ROOT)}") != lock_path.read_bytes():
        raise RuntimeError("committed lock differs")
    lock = read(lock_path)
    checked = {}
    for key, root in (("artifact_sha256", BASE), ("external_reference_sha256", ROOT)):
        for rel, expected in lock[key].items():
            path = root / rel
            actual = sha(path)
            committed = hashlib.sha256(git("show", f"{COMMIT}:{path.relative_to(ROOT)}")).hexdigest()
            if actual != expected or committed != expected:
                raise RuntimeError("locked bytes changed: " + str(path))
            checked[str(path.relative_to(ROOT))] = actual
    frozen = lock["execution"]["frozen_commit"]
    source = {}
    for rel in git("ls-tree", "-r", "--name-only", frozen, "src").decode().splitlines():
        content = (ROOT / rel).read_bytes()
        if content != git("show", f"{frozen}:{rel}"):
            raise RuntimeError("src differs from frozen commit: " + rel)
        source[rel] = hashlib.sha256(content).hexdigest()
    if git("ls-files", "--others", "--exclude-standard", "src").strip():
        raise RuntimeError("untracked source files")
    fp = rr.runtime_fingerprint()
    from geosolver.runtime.integrity import verify_engine_lock
    if fp["issues"] or not verify_engine_lock()[0] or fp["source_hash"] != lock["execution"]["source_tree_hash"]:
        raise RuntimeError("frozen runtime identity failed: " + str(fp))
    if (rr.CANONICAL_TIME_LIMIT_SECONDS, rr.CANONICAL_CORES) != (180, 1):
        raise RuntimeError("runner execution contract differs")
    remote_refs = git("for-each-ref", "--contains", COMMIT, "--format=%(refname) %(objectname)", "refs/remotes").decode().splitlines()
    if not remote_refs:
        raise RuntimeError("no remote-tracking ref contains prediction commit")
    return lock, {
        "verified_at_utc": now(), "prediction_commit": COMMIT,
        "prediction_commit_time": git("show", "-s", "--format=%cI", COMMIT).decode().strip(),
        "prediction_lock_sha256": LOCK_SHA, "prediction_sha256": lock["prediction_sha256"],
        "checked_artifacts": len(lock["artifact_sha256"]), "checked_external_references": len(lock["external_reference_sha256"]),
        "files_sha256": checked, "source_files_sha256": source,
        "frozen_commit": frozen, "source_git_tree": git("rev-parse", frozen + ":src").decode().strip(),
        "runtime": fp, "python_executable": sys.executable, "python_version": sys.version,
        "remote_tracking_refs": remote_refs,
        "push_evidence": "User reports push around 2026-10-23T16:13:15Z; local remote-tracking ref contains f574764. No remote server timestamp inferred.",
        "authorization": "Explicit user stage-2 authorization for Q30a, seeds 301..305, 180 seconds, one core, maximum four parallel runs.",
        "file_limit_bytes": FILE_LIMIT, "summary_limit_bytes": SUMMARY_LIMIT,
        "missing_policy": "Missing evidence is neither correct nor observed solver failure. Keep fixed 85/17 denominators and report lower/upper bounds if needed.",
    }


def compact(value, depth=0):
    if isinstance(value, dict):
        if depth >= 9:
            return {"omitted_mapping_keys": list(value)[:60], "original_count": len(value)}
        items = list(value.items())
        result = {k: compact(v, depth + 1) for k, v in items[:60]}
        if len(items) > 60:
            result["omitted_key_count"] = len(items) - 60
        return result
    if isinstance(value, list):
        if len(value) > 8:
            return {"original_count": len(value), "first_6": [compact(v, depth + 1) for v in value[:6]],
                    "last_2": [compact(v, depth + 1) for v in value[-2:]]}
        return [compact(v, depth + 1) for v in value]
    if isinstance(value, str) and len(value) > 1800:
        return value[:1800] + f" [truncated; original_chars={len(value)}]"
    return value


def compact_raw(raw):
    result = raw.get("solver_result")
    diagnostics = (result or {}).get("diagnostics") or {}
    pipeline = diagnostics.get("pipeline_summary") or {}
    assembly = pipeline.get("exact_assembly") or {}
    retained = {k: diagnostics[k] for k in ("process_info", "phase_timings", "counters", "rejection_tags", "numeric_feasible", "exact_identified") if k in diagnostics}
    retained["pipeline_summary"] = {
        "exact_assembly": {k: assembly[k] for k in ("numeric_feasible_count", "rejection_tags") if k in assembly},
        "verification_records": [True] if pipeline.get("verification_records") else [],
    }
    stored = {k: v for k, v in raw.items() if k not in {"process", "solver_result"}}
    stored["process"] = {k: v for k, v in raw.get("process", {}).items() if k not in {"stdout", "stderr"}}
    for stream in ("stdout", "stderr"):
        value = raw.get("process", {}).get(stream, "")
        stored["process"][stream + "_excerpt"] = value[:3000]
        stored["process"][stream + "_characters"] = len(value)
        stored["process"][stream + "_sha256"] = hashlib.sha256(value.encode()).hexdigest()
    stored["solver_result"] = ({**{k: v for k, v in result.items() if k != "diagnostics"}, "diagnostics": retained} if result else None)
    # These checks prove that compaction preserves every input used by the fixed scorer.
    before = assess(raw)
    after = assess(stored)
    if before != after or rr.read_run_outcome(raw) != rr.read_run_outcome(stored):
        raise RuntimeError("storage compaction changed assessment or outcome")
    stored["assessment"] = before
    stored["storage"] = {"schema": "q30a-summary-v1", "recorded_at_utc": now(), "raw_full_record_saved": False,
                         "raw_canonical": encoded_identity(raw), "assessment_preserved": True,
                         "all_answer_descriptors_retained": True}
    stored["diagnostic_evidence"] = compact(diagnostics)
    if encoded_identity(stored)["bytes"] > SUMMARY_LIMIT:
        stored["diagnostic_evidence"] = {"omitted_due_to_size": True, "original_keys": list(diagnostics)}
    return stored


def write_summary(path, raw):
    try:
        save(path, compact_raw(raw), new=True)
    except BaseException:
        error = traceback.format_exc()[-6000:]
        # Keep scoring evidence independently of richer summary construction.
        result = raw.get("solver_result") or {}
        fallback = {"case_id": raw["case_id"], "seed": raw["seed"], "storage_error": error,
                    "outcome_before_storage": rr.read_run_outcome(raw),
                    "all_answer_descriptors": result.get("answers", [])}
        try:
            fallback["assessment"] = assess(raw)
        except BaseException:
            fallback.update(assessment_unavailable=True, missing_reason="scoring_and_storage_error",
                            assessment_error=traceback.format_exc()[-6000:])
        try:
            save(path, fallback, new=not Path(path).exists())
        except BaseException:
            # Final minimal receipt cannot accidentally turn missing records into failures.
            save(path, {"case_id": raw["case_id"], "seed": raw["seed"], "assessment_unavailable": True,
                        "missing_reason": "essential_summary_storage_error", "storage_error": error,
                        "final_storage_error": traceback.format_exc()[-6000:]}, new=not Path(path).exists())


def prepare():
    lock, verification = verify_gate()
    if DEST.exists():
        raise RuntimeError("execution directory already exists; never reset automatically")
    from verify_bundle import verify
    validation = verify()
    records = rr._load_cases(BASE / "cases.jsonl")
    if [r.identifier for r in records] != [p["id"] for p in lock["adopted_problems"]]:
        raise RuntimeError("case ordering mismatch")
    import psutil
    loads = psutil.cpu_percent(interval=2, percpu=True)
    peer = BASE.parent / "b/execution/preflight.json"
    peer_cpus = read(peer).get("cpus", []) if peer.exists() else []
    def siblings(cpu):
        return [int(c) for c in Path(f"/sys/devices/system/cpu/cpu{cpu}/topology/thread_siblings_list").read_text().strip().split(",")]
    candidates = [cpu for cpu in rr._independent_cpus() if not set(siblings(cpu)).intersection(peer_cpus)]
    cpus = sorted(candidates, key=lambda cpu: (sum(loads[c] for c in siblings(cpu)), cpu))[:4]
    if len(cpus) != 4:
        raise RuntimeError("four independent non-peer physical cores unavailable")
    # Constructed storage-only data: a >Q29d-90KB mandatory answer payload.
    # Never invoke search, optimization, PSLQ or the solver for this check.
    sample = {"case_id": records[0].identifier, "seed": 0, "process": {"returncode": 0},
              "solver_result": {"status": "no_answer_found", "answers": [], "diagnostics": {"synthetic": "x" * 250000}}}
    reduced = compact_raw(sample)
    tasks = [{"case_id": r.identifier, "seed": seed} for seed in lock["execution"]["seeds"] for r in records]
    batches = [tasks[i:i + 4] for i in range(0, len(tasks), 4)]
    DEST.mkdir()
    synthetic_path = DEST / "storage-check.json"
    save(synthetic_path, {"synthetic": "x" * 200000}, new=True)
    storage_check = {"large_receipt_bytes": synthetic_path.stat().st_size, "large_receipt_roundtrip": len(read(synthetic_path)["synthetic"]) == 200000,
                     "diagnostics_compaction_bytes": encoded_identity(reduced)["bytes"], "score_preserved": True}
    synthetic_path.unlink()
    save(DEST / "preflight.json", {**verification, "validation": validation, "cpus": cpus,
         "peer_campaign_cpus_avoided": peer_cpus, "load_average": os.getloadavg(),
         "cpu_load_percent": {str(c): loads[c] for cpu in cpus for c in siblings(cpu)},
         "available_memory_bytes": psutil.virtual_memory().available,
         "orchestrator_sha256": sha(__file__), "storage_check": storage_check,
         "solver_runs_during_preparation": 0, "batches": batches, "total_runs": len(tasks),
         "time_limit_seconds": 180, "outer_watchdog_seconds": 188, "max_parallel": 4,
         "cores_per_run": 1, "automatic_retry": False}, new=True)
    save(DEST / "campaign-manifest.json", rr._manifest(records, lock["execution"]["seeds"]), new=True)
    print(json.dumps({"prepared_at_utc": now(), "cpus": cpus, "peer_cpus_avoided": peer_cpus,
                      "total_runs": len(tasks), "batches": len(batches), "storage_check": storage_check,
                      "runtime": verification["runtime"]}), flush=True)


def initialize(queue):
    global CPU
    CPU = queue.get()
    os.sched_setaffinity(0, {CPU})
    resource.setrlimit(resource.RLIMIT_FSIZE, (FILE_LIMIT, FILE_LIMIT))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    rr._atomic_json = write_summary


def worker(task):
    cid, seed = task["case_id"], task["seed"]
    path = DEST / "runs" / cid / f"{seed}.json"
    life = DEST / "lifecycle" / cid / f"{seed}.json"
    if path.exists() or life.exists():
        raise RuntimeError("never retry or replace an attempted run")
    started = now()
    save(life, {**task, "started_at_utc": started, "cpu": CPU}, new=True)
    record = next(r for r in rr._load_cases(BASE / "cases.jsonl") if r.identifier == cid)
    error = None
    with tempfile.TemporaryDirectory(prefix="q30a-") as temp:
        os.environ.update(TMPDIR=temp, TMP=temp, TEMP=temp)
        tempfile.tempdir = temp
        try:
            rr._run_one(record, seed, DEST, CPU)
        except BaseException:
            error = traceback.format_exc()[-6000:]
        finally:
            tempfile.tempdir = None
    status = {**task, "started_at_utc": started, "finished_at_utc": now(), "cpu": CPU,
              "runner_exception": error, "record_present": path.is_file()}
    if path.is_file():
        raw = read(path)
        status.update(record_sha256=sha(path), record_bytes=path.stat().st_size,
                      assessment_unavailable=raw.get("assessment_unavailable", "assessment" not in raw),
                      assessment=raw.get("assessment"))
    else:
        status.update(assessment_unavailable=True, missing_reason="runner_produced_no_saved_record")
    save(life, status)
    return status


def batch(number):
    _, verification = verify_gate()
    preflight = read(DEST / "preflight.json")
    if preflight["orchestrator_sha256"] != sha(__file__):
        raise RuntimeError("orchestrator changed after preparation")
    if not 1 <= number <= len(preflight["batches"]):
        raise ValueError("invalid batch number")
    with (DEST / "batch.guard").open("a") as guard:
        fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for prior in range(1, number):
            if not read(DEST / "batches" / f"{prior:02d}-complete.json")["all_workers_joined"]:
                raise RuntimeError("prior batch incomplete")
        start_path = DEST / "batches" / f"{number:02d}-start.json"
        if start_path.exists():
            raise RuntimeError("batch already attempted; never retry")
        started = now()
        tasks = [dict(t, batch=number) for t in preflight["batches"][number - 1]]
        if number == 1:
            save(DEST / "execution-start.json", {"started_at_utc": started, "verification": verification,
                 "preflight_sha256": sha(DEST / "preflight.json"), "orchestrator_sha256": sha(__file__),
                 "max_parallel": 4, "automatic_retry": False}, new=True)
        save(start_path, {"batch": number, "started_at_utc": started, "tasks": tasks,
                         "gate_verified_at_utc": verification["verified_at_utc"], "load_average": os.getloadavg(),
                         "cpus": preflight["cpus"]}, new=True)
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
                assessment = result.get("assessment") or {}
                print(json.dumps({"case_id": result["case_id"], "seed": result["seed"], "matched": assessment.get("matched"),
                                  "status": assessment.get("status"), "failure_stage": assessment.get("failure_stage"),
                                  "missing": result.get("assessment_unavailable"), "bytes": result.get("record_bytes"),
                                  "wall_seconds": assessment.get("wall_seconds")}), flush=True)
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
        _, receipt = verify_gate()
        print(json.dumps(receipt, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
