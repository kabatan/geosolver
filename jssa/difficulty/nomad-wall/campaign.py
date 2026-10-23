"""Q14 fixed 24 x 3 x 2 full-solver campaign using the production runner."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import resource
import socket
import subprocess
import sys
import tempfile
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks import research_runner as research


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selected():
    with (HERE / "selected-cases.csv").open() as stream:
        return list(csv.DictReader(stream))


def write_json(path, value):
    research._atomic_json(path, value)


def freeze():
    base = json.loads((HERE / "selection-manifest.json").read_text())
    assert sha(HERE / "preregistration.md") == base["preregistration_sha256"]
    assert sha(HERE / "selected-cases.csv") == base["selected_cases_sha256"]
    assert all(sha(ROOT / p) == h for p, h in base["src_file_sha256"].items())
    records = {c.identifier: c for c in research._load_cases()}
    inputs = {}
    for row in selected():
        case = records[row["id"]]
        assert case.runnable and json.loads(case.dsl_path.read_text()) == case.dsl
        inputs[case.identifier] = {"path": str(case.dsl_path.relative_to(ROOT)), "sha256": sha(case.dsl_path)}
    code_files = ["preregistration.md", "implementation.md", "selected-cases.csv",
                  "select_cases.py", "campaign.py", "check_patch.py", "aggregate.py",
                  "patch/sitecustomize.py", "patch/nomad_wall_patch.py"]
    identity = {
        "code_sha256": {p: sha(HERE / p) for p in code_files},
        "inputs": inputs,
        "research_runner_sha256": sha(ROOT / "benchmarks/research_runner.py"),
        "python": sys.executable,
        "runtime": research.runtime_fingerprint(),
        "host": socket.gethostname(),
        "cpus": research._independent_cpus()[:4],
        "seeds": [0, 1, 2], "modes": ["B", "N"],
        "time_limit_seconds": 180, "outer_timeout_seconds": 188,
        "jobs": 4, "timing_is_reference_only": True,
    }
    path = HERE / "campaign-manifest.json"
    if path.exists():
        previous = json.loads(path.read_text())
        assert previous["identity"] == identity, "campaign identity changed"
        return previous
    result = {"created_utc": datetime.now(timezone.utc).isoformat(), "identity": identity}
    write_json(path, result)
    return result


def run_pair(identifier, seed, cpu):
    row = next(row for row in selected() if row["id"] == identifier)
    record = next(c for c in research._load_cases() if c.identifier == identifier)
    order = ("B", "N") if (int(row["selection_hash"], 16) + seed) % 2 == 0 else ("N", "B")
    resource.setrlimit(resource.RLIMIT_FSIZE, (20 * 1024**2, 20 * 1024**2))
    for mode in order:
        campaign = HERE / "runs" / mode
        folder = campaign / "runs" / identifier
        folder.mkdir(parents=True, exist_ok=True)
        raw_path = folder / f"{seed}.json"
        receipt_path = folder / f"{seed}.receipt.json"
        audit = folder / f"{seed}.audit.jsonl"
        if raw_path.exists():
            print(f"skip {identifier} {seed} {mode}", flush=True)
            continue
        if audit.exists():
            raise RuntimeError(f"interrupted attempt requires explicit accounting: {audit}")
        temp = folder / f"{seed}.temp"
        temp.mkdir(exist_ok=True)
        os.environ.update(
            NOMAD_WALL_MODE=mode, NOMAD_WALL_AUDIT=str(audit),
            PYTHONPATH=os.pathsep.join([str(HERE / "patch"), str(ROOT / "src"), str(ROOT)]),
            PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(temp), TMP=str(temp), TEMP=str(temp),
        )
        tempfile.tempdir = str(temp)
        started = time.time()
        load_start = os.getloadavg()
        error = None
        try:
            research._run_one(record, seed, campaign, cpu)
        except Exception:
            error = traceback.format_exc()
            if not raw_path.exists():
                write_json(raw_path, {
                    "schema_version": 2, "case_id": identifier, "seed": seed,
                    "execution_contract_issues": ["runner_exception"],
                    "process": {"returncode": -1, "timed_out": False,
                                "elapsed_seconds": time.time() - started, "stderr": error},
                    "solver_result": None,
                })
        write_json(receipt_path, {
            "case_id": identifier, "seed": seed, "mode": mode, "cpu": cpu,
            "started_unix": started, "finished_unix": time.time(),
            "load_start": load_start, "load_finish": os.getloadavg(), "runner_error": error,
        })
        print(f"done {identifier} {seed} {mode} {time.time() - started:.1f}s", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair", nargs=3, metavar=("ID", "SEED", "CPU"))
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--first-pair", action="store_true")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if args.pair:
        run_pair(args.pair[0], int(args.pair[1]), int(args.pair[2]))
        return
    manifest = freeze()
    if args.prepare:
        print(json.dumps({"prepared": True, "tasks": 144, "cpus": manifest["identity"]["cpus"]}))
        return
    assert args.first_pair or args.run
    slots = Queue()
    for cpu in manifest["identity"]["cpus"]:
        slots.put(cpu)
    tasks = [(row["id"], seed) for seed in (0, 1, 2) for row in selected()]
    if args.first_pair:
        tasks = tasks[:1]

    def go(task):
        identifier, seed = task
        cpu = slots.get()
        log = HERE / "pair-logs" / f"{identifier}.{seed}.log"
        log.parent.mkdir(exist_ok=True)
        try:
            with log.open("a") as stream:
                result = subprocess.run(
                    [sys.executable, "-B", str(HERE / "campaign.py"), "--pair", identifier, str(seed), str(cpu)],
                    cwd=ROOT, env=os.environ.copy(), stdout=stream, stderr=subprocess.STDOUT,
                    timeout=420, check=False,
                )
            if result.returncode:
                raise RuntimeError(f"pair helper failed: {identifier}/{seed}; see {log}")
            print(f"pair-complete {identifier} {seed}", flush=True)
        finally:
            slots.put(cpu)

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(go, task) for task in tasks]
        for future in as_completed(futures):
            future.result()


if __name__ == "__main__":
    main()
