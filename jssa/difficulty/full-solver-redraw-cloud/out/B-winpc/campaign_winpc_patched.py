"""Paired full-solver campaign for preregistration-4: plain vs redraw, same machine, alternating.

Each run spawns the frozen CLI (solve DSL --time-limit-seconds 180 --cores 1 --seed S) pinned to one
CPU with one thread, like benchmarks/research_runner._run_one, and scores it at once with the runner's
own answer keys (set match). The redraw arm sets REDRAW_MODE=redraw and puts patch/ on PYTHONPATH, so
the search worker subprocess loads patch/sitecustomize.py -> redraw_patch.py. Usage: campaign.py OUT_DIR JOBS [ids...]; resumable (skips finished runs).
"""
from __future__ import annotations

import csv
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

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from benchmarks.research_runner import (  # noqa: E402
    THREAD_ENVIRONMENT, _answer_keys, _canonical_json, _load_cases, read_run_outcome, reference_expressions,
)
from geosolver.exact import describe_exact  # noqa: E402

HERE = Path(__file__).resolve().parent
SEEDS = tuple(int(s) for s in os.environ.get("SEEDS", "101,102,103").split(","))
MODES = ("plain", "redraw")


def expected_keys(record):
    return sorted({_canonical_json(describe_exact(v).canonical_key())
                   for ref in record.references for v in reference_expressions(ref)})


def run(record, seed, mode, out: Path, cpu: int):
    dest = out / "runs" / mode / record.identifier / f"{seed}.json"
    if dest.is_file():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp, stats = dest.with_suffix(".solver.tmp"), dest.with_suffix(".stats.json")
    env = os.environ.copy() | THREAD_ENVIRONMENT | {"REDRAW_STATS": str(stats), "REDRAW_MODE": mode,
                                                  "PYTHONPATH": str(HERE / "patch"),
                                                  "LM_FIRST": os.environ.get("LM_FIRST", "0")}
    cmd = [sys.executable, "-m", "geosolver.application.cli", "solve",
           str(record.dsl_path), "--time-limit-seconds", "180", "--cores", "1", "--seed", str(seed),
           "--output", str(tmp)]
    load = os.getloadavg()[0] if hasattr(os, "getloadavg") else psutil.cpu_percent(0.1)
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
    raw = {"case_id": record.identifier, "seed": seed, "mode": mode, "lm_first": env["LM_FIRST"], "cpu": cpu, "loadavg_start": load,
           "process": {"returncode": p.returncode, "timed_out": timed_out, "elapsed_seconds": elapsed,
                       "stderr": se[-4000:]},
           "redraw_stats": json.loads(stats.read_text()) if stats.is_file() else None,
           "solver_result": result}
    stats.unlink(missing_ok=True)
    if result is None:  # timed out or killed before the CLI wrote its output: record as unsolved (no solver_result)
        raw["score"] = {"matched": False, "wall_seconds": elapsed, "status": "no_result"}
        dest.write_text(json.dumps(raw))
        return
    try:
        outcome = read_run_outcome(raw)
    except Exception as exc:  # solver_result without diagnostics (e.g. status error): record as unsolved, keep the raw result
        raw["score"] = {"matched": False, "wall_seconds": elapsed, "status": str((result or {}).get("status", "unreadable")), "note": f"read_run_outcome failed: {exc}"}
        dest.write_text(json.dumps(raw))
        return
    matched = bool(outcome["normal_completion"] and _answer_keys(result) == expected_keys(record))
    raw["score"] = {"matched": matched, "wall_seconds": outcome["wall_seconds"], "status": outcome["status"]}
    dest.write_text(json.dumps(raw))


def main():
    out, jobs = Path(sys.argv[1]), int(sys.argv[2])
    ids = sys.argv[3:] or [r["id"] for r in csv.DictReader(open(ROOT / "jssa/difficulty/start-feasibility-1023/predictions.csv"))]
    cases = {c.identifier: c for c in _load_cases()}
    tasks = [(cases[i], s, m) for s in SEEDS for i in ids for m in (MODES if (zlib.crc32(i.encode()) + s) % 2 else MODES[::-1])]
    cpus: Queue = Queue()
    for c in range(jobs):
        cpus.put(c * int(os.environ.get("CPU_STRIDE", "1")))  # CPU_STRIDE=2 skips SMT siblings (logical CPUs 0,2,4,... = distinct physical cores on Windows)

    def go(t):
        cpu = cpus.get()
        try:
            run(*t, out, cpu)
        except Exception as e:  # noqa: BLE001
            print("ERR", t[0].identifier, t[1], t[2], e, flush=True)
        finally:
            cpus.put(cpu)
        print(time.strftime("%H:%M:%S"), t[0].identifier, t[1], t[2], flush=True)

    with ThreadPoolExecutor(jobs) as ex:
        list(ex.map(go, tasks))


if __name__ == "__main__":
    main()
