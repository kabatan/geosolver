"""Preregistration 6, experiment 2: component ablation on the 34 unseen problems (Q30), same machine, interleaved.

7 arms x 34 problems x seeds 311-313 = 714 runs, 180 s, 1 core each. Arm order is rotated per (problem, seed) so
load and time of day are shared. Each run spawns the CLI of the checked-out worktree (jssa-ablation 67ad79a =
frozen 60db4b6 + GEOSOLVER_ABLATE_* switches) pinned to one CPU, and scores it with research_runner's own answer
keys (exact-set match), like jssa/difficulty/full-solver-redraw-cloud/campaign.py. Resumable.
Usage: ablation34_driver.py OUT_DIR JOBS CPU_LIST(comma) CASES_DIR_A CASES_DIR_B
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from queue import Queue

import psutil

ROOT = Path(os.environ.get("ABLATION_ROOT", str(Path.home() / "work/geosolver-ablation")))
sys.path.insert(0, str(ROOT))
from benchmarks.research_runner import (  # noqa: E402
    THREAD_ENVIRONMENT, _answer_keys, _canonical_json, _load_cases, read_run_outcome, reference_expressions,
)
from geosolver.exact import describe_exact  # noqa: E402

SEEDS = (311, 312, 313)
ARMS = {
    "BASE": {},
    "NO_SECOND_ATTEMPT": {"GEOSOLVER_ABLATE_NO_SECOND_ATTEMPT": "1"},
    "NO_NOMAD": {"GEOSOLVER_ABLATE_NO_NOMAD": "1"},
    "NO_ALGEBRAIC": {"GEOSOLVER_ABLATE_NO_ALGEBRAIC": "1"},
    "NO_SCALE_CHART": {"GEOSOLVER_ABLATE_NO_SCALE_CHART": "1"},
    "NO_RESCUE": {"GEOSOLVER_ABLATE_NO_RESCUE": "1"},
    "NO_ANALYTIC_JAC": {"GEOSOLVER_ABLATE_NO_ANALYTIC_JAC": "1"},
}
ORDER = list(ARMS)


def expected_keys(record):
    return sorted({_canonical_json(describe_exact(v).canonical_key())
                   for ref in record.references for v in reference_expressions(ref)})


def run(record, seed, arm, out: Path, cpu: int):
    dest = out / "runs" / arm / record.identifier / f"{seed}.json"
    if dest.is_file():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".solver.tmp")
    env = os.environ.copy() | THREAD_ENVIRONMENT | ARMS[arm]
    env.pop("GEOSOLVER_ABLATE_SEARCH_MODE", None)
    cmd = [sys.executable, "-m", "geosolver.application.cli", "solve", str(record.dsl_path),
           "--time-limit-seconds", "180", "--cores", "1", "--seed", str(seed), "--output", str(tmp)]
    load = os.getloadavg()[0]
    t0 = time.monotonic()
    p = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                         encoding="utf-8", errors="replace")
    try:  # pin before the solver spawns its worker (children inherit the affinity)
        psutil.Process(p.pid).cpu_affinity([cpu])
    except (psutil.Error, AttributeError):
        pass
    timed_out = False
    try:
        so, se = p.communicate(timeout=188)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            procs = psutil.Process(p.pid).children(recursive=True) + [psutil.Process(p.pid)]
        except psutil.Error:
            procs = []
        for q in procs:
            try:
                q.kill()
            except psutil.Error:
                pass
        so, se = p.communicate()
    elapsed = time.monotonic() - t0
    result = None
    if tmp.is_file():
        try:
            result = json.loads(tmp.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
        tmp.unlink()
    raw = {"case_id": record.identifier, "seed": seed, "arm": arm, "cpu": cpu, "loadavg_start": load,
           "process": {"returncode": p.returncode, "timed_out": timed_out, "elapsed_seconds": elapsed,
                       "stderr": se[-2000:]},
           "solver_result": result}
    outcome = read_run_outcome(raw)
    matched = bool(result is not None and outcome["normal_completion"] and _answer_keys(result) == expected_keys(record))
    diag = (result or {}).get("diagnostics", {}) or {}
    compact = {"case_id": record.identifier, "seed": seed, "arm": arm, "cpu": cpu, "loadavg_start": load,
               "elapsed_seconds": elapsed, "timed_out": timed_out, "returncode": p.returncode,
               "status": outcome["status"], "normal_completion": outcome["normal_completion"],
               "failure_stage": outcome["failure_stage"], "termination_reason": outcome["termination_reason"],
               "wall_seconds": outcome["wall_seconds"], "cpu_seconds": outcome["cpu_seconds"],
               "phase_timings": outcome["phase_timings"], "rejection_tags": outcome["rejection_tags"],
               "ablations": (diag.get("config_snapshot") or {}).get("ablations"),
               "matched": matched, "answer_keys": _answer_keys(result) if result else None,
               "stderr_tail": se[-500:]}
    dest.write_text(json.dumps(compact))


def main():
    out, jobs, cpus_arg = Path(sys.argv[1]).resolve(), int(sys.argv[2]), [int(c) for c in sys.argv[3].split(",")]
    records = []
    for d in sys.argv[4:6]:
        records += [r for r in _load_cases(Path(d) / "cases.jsonl")]
    assert len(records) == 34, len(records)
    tasks = []
    for s in SEEDS:
        for r in records:
            k = (zlib.crc32(r.identifier.encode()) + s) % len(ORDER)
            for arm in ORDER[k:] + ORDER[:k]:
                tasks.append((r, s, arm))
    cpus: Queue = Queue()
    for c in cpus_arg[:jobs]:
        cpus.put(c)

    def go(t):
        cpu = cpus.get()
        try:
            run(*t, out, cpu)
        except Exception as e:  # noqa: BLE001
            print("ERR", t[0].identifier, t[1], t[2], e, flush=True)
        finally:
            cpus.put(cpu)
        print(time.strftime("%H:%M:%S"), t[0].identifier, t[1], t[2], flush=True)

    print("tasks", len(tasks), flush=True)
    with ThreadPoolExecutor(jobs) as ex:
        list(ex.map(go, tasks))


if __name__ == "__main__":
    main()
