"""Stage-2 outer orchestration; the committed solver/runner/scorer stay unchanged."""
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

sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[4]
WORK = BASE / "supplement-work"
DEST = WORK / "campaign"
COMMIT = "b83ad623aa6b8cbf38741a0f553ba6d02ab6ce66"
LOCK_SHA = "9605e836be325ef6ede021be07c0e56dc29fb86e6c8995b37100e50b235a7531"
RUNNER_SHA = "02071060658c98f5e6ccfeed0133d24249d4f0ba366469960d37a3238a52504d"
LIMIT = 4_999_999
sys.path.insert(0, str(BASE))
import run_campaign_supplement as runner


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def read(path):
    return json.loads(Path(path).read_text())


def save_new(path, data):
    payload = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()
    assert len(payload) < 5_000_000
    with Path(path).open("xb") as stream:
        stream.write(payload)


def file_limits():
    # Enforce the user's per-file ceiling, including temporary solver output.
    resource.setrlimit(resource.RLIMIT_FSIZE, (LIMIT, LIMIT))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def verify_gate():
    lock_path = BASE / "prediction-supplement.lock.json"
    assert sha(lock_path) == LOCK_SHA
    lock = read(lock_path)
    checked = {}
    for rel in [str(lock_path.relative_to(ROOT)), *lock["files_sha256"]]:
        expected = LOCK_SHA if rel == str(lock_path.relative_to(ROOT)) else lock["files_sha256"][rel]
        actual = sha(ROOT / rel)
        committed = hashlib.sha256(git("show", f"{COMMIT}:{rel}")).hexdigest()
        assert actual == committed == expected, rel
        checked[rel] = actual
    assert sha(BASE / "run_campaign_supplement.py") == RUNNER_SHA
    for rel, expected in lock["evidence_files_sha256"].items():
        assert sha(ROOT / rel) == expected, rel
    original = read(BASE / "prediction.lock.json")
    for rel, expected in original["files_sha256"].items():
        path = ROOT / "benchmarks/research_runner.py" if rel == "@research_runner.py" else BASE / rel
        assert sha(path) == expected, rel
    original_bytes = (BASE / "run_campaign.py").read_bytes()
    expected_bytes = original_bytes.replace(b'assert len(payload.encode())<90_000,',
                                            b'assert len(payload.encode())<4_900_000,')
    assert expected_bytes == (BASE / "run_campaign_supplement.py").read_bytes()
    branches = git("branch", "-r", "--contains", COMMIT).decode().splitlines()
    branches = [line.strip() for line in branches if line.strip()]
    assert branches, "no local remote-tracking ref contains the user-confirmed commit"
    plan = lock["execution_plan"]
    assert len(plan["tasks"]) == 31
    assert [t["task_number"] for t in plan["tasks"]] == list(range(1, 32))
    assert [n for b in plan["batches"] for n in b["task_numbers"]] == list(range(1, 32))
    assert (plan["main_runs"], plan["diagnostic_runs"], plan["max_parallel"]) == (25, 6, 4)
    for task in plan["tasks"]:
        assert sha(ROOT / task["dsl_path"]) == task["dsl_sha256"]
        assert sha(ROOT / task["prior_missing_receipt_path"]) == task["prior_missing_receipt_sha256"]
        expected = DEST / task["group"] / "runs" / task["id"] / f'{task["seed"]}.json'
        assert ROOT / task["output_path"] == expected
    return lock, {
        "verified_at_utc": now(), "prediction_commit": COMMIT,
        "commit_committer_time": git("show", "-s", "--format=%cI", COMMIT).decode().strip(),
        "prediction_lock_sha256": LOCK_SHA, "prediction_sha256": lock["prediction_sha256"],
        "revised_run_campaign_sha256": RUNNER_SHA,
        "committed_and_working_files_sha256": checked,
        "evidence_files_verified": len(lock["evidence_files_sha256"]),
        "original_lock_files_verified": len(original["files_sha256"]),
        "remote_tracking_refs_containing_commit": branches,
        "push_confirmation_source": "explicit user statement; local remote-tracking ancestry also checked; no server-side timestamp inferred",
        "user_reported_push_at_utc": "2026-10-23T15:49:21Z",
        "separate_task_execution_authorization": "【段階2・実行許可】Q29d補遺。これが明示的な実行許可である。25+6=31実行、凍結src・180秒・1コア・最大並列4。",
        "user_authorization_received": True,
    }


def verify_runtime(lock, prepare=False):
    import psutil
    plan = lock["execution_plan"]
    assert sys.executable == plan["python_executable"]
    if prepare:
        runner.prepare_runtime()
    fingerprint = runner.bootstrap()
    runner.verify_inputs()  # HERE still points at the original, locked inputs.
    pf = read(BASE / "preflight.json")
    assert fingerprint["runtime_dependencies"] == plan["runtime_dependencies"] == pf["runtime"]["runtime_dependencies"]
    assert fingerprint["source_hash"] == lock["source_hash"]
    assert sha(runner.RUNTIME / "uv.lock") == lock["dependency_lock_sha256"]
    assert git("rev-parse", lock["frozen_commit"] + ":src").decode().strip() == lock["source_git_tree"]
    assert runner.rr.CANONICAL_TIME_LIMIT_SECONDS == plan["time_limit_seconds"] == 180
    assert runner.rr.CANONICAL_CORES == plan["cores_per_run"] == 1
    assert runner.rr.THREAD_ENVIRONMENT == plan["thread_environment"]
    assert sys.getrecursionlimit() == plan["recursion_limit"] == 10000
    assert all(os.environ[k] == v for k, v in plan["thread_environment"].items())
    assert plan["cpus"] == pf["cpus"] == [7, 15, 10, 14]
    allowed = psutil.Process().cpu_affinity()
    assert set(plan["cpus"]) <= set(allowed)
    topology = {}
    for cpu in plan["cpus"]:
        p = Path(f"/sys/devices/system/cpu/cpu{cpu}/topology")
        topology[str(cpu)] = {k: (p / k).read_text().strip()
                              for k in ("physical_package_id", "core_id", "thread_siblings_list")}
    assert len({(v["physical_package_id"], v["core_id"]) for v in topology.values()}) == 4
    from score import validate_conversions
    return {"checked_at_utc": now(), "runtime": fingerprint,
            "frozen_commit": runner.FROZEN, "runtime_root": str(runner.RUNTIME),
            "dependency_lock_sha256": sha(runner.RUNTIME / "uv.lock"),
            "python_executable": sys.executable, "cpu_topology": topology,
            "allowed_cpu_affinity": allowed, "score_checks": validate_conversions(),
            "time_limit_seconds": 180, "cores_per_run": 1, "max_parallel": 4,
            "external_watchdog_seconds": 188, "recursion_limit": 10000,
            "thread_environment": plan["thread_environment"],
            "per_file_rlimit_fsize_bytes": LIMIT, "core_dumps_disabled": True}


def prepare():
    assert not WORK.exists(), "do not overwrite or automatically resume preparation"
    lock, gate = verify_gate()
    runtime = verify_runtime(lock, prepare=True)
    WORK.mkdir()
    (WORK / "dsl").mkdir()
    for source in sorted((BASE / "dsl").glob("*.json")):
        target = WORK / "dsl" / source.name
        with target.open("xb") as stream:
            stream.write(source.read_bytes())
        assert sha(target) == sha(source)
    DEST.mkdir()
    (DEST / "batches").mkdir()
    save_new(WORK / "stage2-verification.json", {
        "schema": "q29d-supplement-stage2-verification-v1", **gate,
        "runtime_verification": runtime, "outer_orchestrator_sha256": sha(__file__),
        "solver_search_executed_during_preparation": False, "sealed_raw_accessed": False,
        "tasks": lock["execution_plan"]["tasks"],
        "dsl_copies_sha256": {p.name: sha(p) for p in sorted((WORK / "dsl").glob("*.json"))},
    })
    print(json.dumps({"prepared_at_utc": now(), "runtime": runtime, "lock_sha256": LOCK_SHA}), flush=True)


def initialize(queue):
    file_limits()
    runner.HERE = WORK
    runner.initialize_worker(queue)


def run_task(task):
    import psutil
    assert runner.HERE == WORK
    dsl = (WORK if task["group"] == "main" else runner.CORPUS) / "dsl" / (task["id"] + ".json")
    assert sha(dsl) == task["dsl_sha256"]
    assert psutil.Process().cpu_affinity() == [runner.CPU]
    result = runner.worker({k: task[k] for k in ("group", "id", "seed")})
    path = ROOT / task["output_path"]
    assert path.stat().st_size < 5_000_000
    record = read(path)
    return {"task_number": task["task_number"], **result,
            "worker_pid": os.getpid(), "worker_cpu_affinity": psutil.Process().cpu_affinity(),
            "output_path": task["output_path"], "output_sha256": sha(path),
            "output_bytes": path.stat().st_size,
            "started_at_utc": record["started_at_utc"], "finished_at_utc": record["finished_at_utc"]}


def batch(number):
    lock, gate = verify_gate()
    preparation = read(WORK / "stage2-verification.json")
    assert preparation["outer_orchestrator_sha256"] == sha(__file__)
    runtime = verify_runtime(lock)
    plan = lock["execution_plan"]
    b = plan["batches"][number - 1]
    assert b["batch"] == number
    for prior in range(1, number):
        assert read(DEST / "batches" / f"{prior:02d}-complete.json")["all_workers_joined"]
    for later in range(number, 9):
        assert not (DEST / "batches" / f"{later:02d}-start.json").exists(), "no retry or out-of-order batch"
    tasks = [plan["tasks"][n - 1] for n in b["task_numbers"]]
    assert 1 <= len(tasks) <= 4
    for task in tasks:
        assert not (ROOT / task["output_path"]).exists()
        if task["group"] == "main":
            assert sha(WORK / "dsl" / (task["id"] + ".json")) == task["dsl_sha256"]
    started = now()
    if number == 1:
        save_new(DEST / "execution-manifest.json", {
            "schema": "q29d-supplement-execution-manifest-v1", **gate,
            "started_at_utc": started, "runtime_verification": runtime,
            "stage2_verification_sha256": sha(WORK / "stage2-verification.json"),
            "outer_orchestrator_sha256": sha(__file__), "execution_plan": plan,
            "sealed_raw_accessed": False, "automatic_retry": False,
        })
    start = {"batch": number, "started_at_utc": started, "tasks": tasks,
             "gate_verified_at_utc": gate["verified_at_utc"], "runtime_verification": runtime,
             "prediction_lock_sha256": LOCK_SHA, "outer_orchestrator_sha256": sha(__file__)}
    save_new(DEST / "batches" / f"{number:02d}-start.json", start)
    print(json.dumps({"batch": number, "started_at_utc": started, "task_numbers": b["task_numbers"]}), flush=True)
    ctx = multiprocessing.get_context("spawn")
    queue = ctx.Queue()
    for cpu in plan["cpus"]:
        queue.put(cpu)
    results = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=len(tasks), mp_context=ctx,
            initializer=initialize, initargs=(queue,)) as pool:
        futures = [pool.submit(run_task, task) for task in tasks]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
    queue.close()
    queue.join_thread()
    assert len(results) == len(tasks)
    save_new(DEST / "batches" / f"{number:02d}-complete.json", {
        "batch": number, "started_at_utc": started, "completed_at_utc": now(),
        "all_workers_joined": True, "completed_runs": len(results),
        "results": sorted(results, key=lambda r: r["task_number"]),
    })
    print(json.dumps({"batch": number, "all_workers_joined": True, "completed_runs": len(results)}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "batch"])
    parser.add_argument("number", nargs="?", type=int, choices=range(1, 9))
    args = parser.parse_args()
    file_limits()
    with (BASE / "supplement-execution.guard").open("a") as guard:
        fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.action == "prepare":
            assert args.number is None
            prepare()
        else:
            assert args.number is not None
            batch(args.number)


if __name__ == "__main__":
    main()
