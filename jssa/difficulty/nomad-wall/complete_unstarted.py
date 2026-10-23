"""Account for all initial slots, then separately execute only unstarted pairs."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import resource
import subprocess
import sys
import tempfile
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from queue import Queue

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks import research_runner as research


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def account():
    path = HERE / "initial-attempt-inventory.json"
    if path.exists():
        return json.loads(path.read_text())
    cases = list(csv.DictReader((HERE / "selected-cases.csv").open()))
    retained, missing = {}, []
    for case in cases:
        for seed in (0, 1, 2):
            for mode in ("B", "N"):
                folder = HERE / "runs" / mode / "runs" / case["id"]
                raw = folder / f"{seed}.json"
                if raw.exists():
                    retained[str(raw.relative_to(HERE))] = sha(raw)
                else:
                    audit = raw.with_suffix(".audit.jsonl")
                    log = HERE / "pair-logs" / f"{case['id']}.{seed}.log"
                    text = log.read_text() if log.exists() else ""
                    if not audit.exists():
                        assert "No such file or directory" in text and (
                            "campaign.py" in text or "selected-cases.csv" in text)
                    missing.append({"id": case["id"], "seed": seed, "mode": mode,
                        "solver_started": audit.exists(), "log_path": str(log.relative_to(HERE)),
                        "log_sha256": sha(log) if log.exists() else None,
                        "reason": "final_result_missing" if audit.exists() else "launcher_file_unavailable"})
    assert len(retained) == 121 and len(missing) == 23
    assert sum(not row["solver_started"] for row in missing) == 22
    result = {"created_unix": time.time(), "retained_raw_sha256": retained, "missing_slots": missing,
              "plan_sha256": sha(HERE / "recovery-plan.md"),
              "completion_script_sha256": sha(Path(__file__))}
    research._atomic_json(path, result)
    return result


def materialize_failures(inventory):
    for row in inventory["missing_slots"]:
        folder = HERE / "runs" / row["mode"] / "runs" / row["id"]
        raw = folder / f"{row['seed']}.json"
        if raw.exists():
            assert json.loads(raw.read_text()).get("failure_accounting_record")
            continue
        log = (HERE / row["log_path"]).read_text()
        research._atomic_json(raw, {
            "schema_version": 2, "case_id": row["id"], "seed": row["seed"],
            "failure_accounting_record": True, "observed_solver_result": False,
            "failure_reason": row["reason"], "solver_started": row["solver_started"],
            "execution_contract_issues": [row["reason"]],
            "config": {"time_limit_seconds": 180, "cores": 1,
                       "thread_environment": research.THREAD_ENVIRONMENT},
            "process": {"returncode": None, "timed_out": False, "elapsed_seconds": None,
                        "stderr": log, "stdout": ""}, "solver_result": None,
        })
        research._atomic_json(raw.with_suffix(".receipt.json"), {
            "case_id": row["id"], "seed": row["seed"], "mode": row["mode"],
            "cpu": None, "started_unix": None, "finished_unix": None,
            "runner_error": row["reason"], "failure_accounting_record": True,
            "recorded_unix": time.time(),
        })


def pair(identifier, seed, cpu):
    inventory = json.loads((HERE / "initial-attempt-inventory.json").read_text())
    pending = [row for row in inventory["missing_slots"]
               if row["id"] == identifier and row["seed"] == seed and not row["solver_started"]]
    assert {row["mode"] for row in pending} == {"B", "N"}
    record = next(c for c in research._load_cases() if c.identifier == identifier)
    order_hash = hashlib.sha256(("Q14-nomad-wall-20261023|" + identifier).encode()).hexdigest()
    modes = ("B", "N") if (int(order_hash, 16) + seed) % 2 == 0 else ("N", "B")
    resource.setrlimit(resource.RLIMIT_FSIZE, (20 * 1024**2, 20 * 1024**2))
    for mode in modes:
        campaign = HERE / "completion" / mode
        folder = campaign / "runs" / identifier
        raw = folder / f"{seed}.json"
        if raw.exists():
            continue
        temp = folder / f"{seed}.temp"
        audit = folder / f"{seed}.audit.jsonl"
        assert temp.is_dir() and not audit.exists()
        os.environ.update(NOMAD_WALL_MODE=mode, NOMAD_WALL_AUDIT=str(audit),
            PYTHONPATH=os.pathsep.join([str(HERE / "patch"), str(ROOT / "src"), str(ROOT)]),
            PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(temp), TMP=str(temp), TEMP=str(temp))
        tempfile.tempdir = str(temp)
        start, load = time.time(), os.getloadavg()
        error = None
        try:
            research._run_one(record, seed, campaign, cpu)
        except Exception:
            error = traceback.format_exc()
            if not raw.exists():
                research._atomic_json(raw, {
                    "schema_version": 2, "case_id": identifier, "seed": seed,
                    "execution_contract_issues": ["completion_runner_exception"],
                    "process": {"returncode": -1, "timed_out": False,
                                "elapsed_seconds": time.time() - start, "stderr": error},
                    "solver_result": None,
                })
        research._atomic_json(raw.with_suffix(".receipt.json"), {
            "case_id": identifier, "seed": seed, "mode": mode, "cpu": cpu,
            "started_unix": start, "finished_unix": time.time(), "load_start": load,
            "load_finish": os.getloadavg(), "runner_error": error, "post_hoc_completion": True,
        })
        print(f"completion {identifier} {seed} {mode}", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair", nargs=3)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if args.pair:
        pair(args.pair[0], int(args.pair[1]), int(args.pair[2]))
        return
    inventory = account()
    assert all(sha(HERE / p) == h for p, h in inventory["retained_raw_sha256"].items())
    materialize_failures(inventory)
    pending = [row for row in inventory["missing_slots"] if not row["solver_started"]]
    for row in pending:
        (HERE / "completion" / row["mode"] / "runs" / row["id"] / f"{row['seed']}.temp").mkdir(parents=True, exist_ok=True)
    if args.prepare:
        print(json.dumps({"initial_slots": 144, "observed_raw": 121, "failure_records": 23,
                          "supplemental_runs": len(pending)}))
        return
    assert args.run
    slots = Queue()
    for cpu in research._independent_cpus()[:2]:
        slots.put(cpu)
    pairs = list(dict.fromkeys((row["id"], row["seed"]) for row in pending))

    def go(task):
        cpu = slots.get()
        identifier, seed = task
        path = HERE / "completion" / f"{identifier}.{seed}.log"
        try:
            with path.open("a") as stream:
                process = subprocess.run([sys.executable, "-B", str(Path(__file__)), "--pair",
                    identifier, str(seed), str(cpu)], cwd=ROOT, env=os.environ.copy(),
                    stdout=stream, stderr=subprocess.STDOUT, timeout=420)
            assert process.returncode == 0, f"completion helper error: {task}"
            print(f"completion-pair {identifier} {seed}", flush=True)
        finally:
            slots.put(cpu)

    with ThreadPoolExecutor(max_workers=2) as pool:
        for future in as_completed([pool.submit(go, task) for task in pairs]):
            future.result()


if __name__ == "__main__":
    main()
