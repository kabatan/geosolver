"""Preregistration 7: global comparison of BASE / NO_ALGEBRAIC / NO_SECOND_ATTEMPT on the fixed 72-problem set.

72 problems (problem-set.json) x 3 arms x seeds 401-403, 180 s, 1 core each, jobs fixed. Arm order is rotated per
(problem, seed). Frozen solver 60db4b6 via the jssa-ablation worktree (switches only). Hashes of the inputs and the
code are written to out/HASHES.json before the first run. Resumable (finished runs are skipped).
Usage: prereg7_driver.py OUT_DIR JOBS CPU_LIST PROBLEM_SET_JSON
"""
from __future__ import annotations

import hashlib
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
    DEFAULT_CASES, THREAD_ENVIRONMENT, _answer_keys, _canonical_json, _load_cases, read_run_outcome, reference_expressions,
)
from geosolver.exact import describe_exact  # noqa: E402
from geosolver.runtime.integrity import source_tree_hash  # noqa: E402

SEEDS = (401, 402, 403)
ARMS = {
    "BASE": {},
    "NO_ALGEBRAIC": {"GEOSOLVER_ABLATE_NO_ALGEBRAIC": "1"},
    "NO_SECOND_ATTEMPT": {"GEOSOLVER_ABLATE_NO_SECOND_ATTEMPT": "1"},
}
ORDER = list(ARMS)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


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
    try:
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
           "process": {"returncode": p.returncode, "timed_out": timed_out, "elapsed_seconds": elapsed, "stderr": se[-2000:]},
           "solver_result": result}
    try:
        outcome = read_run_outcome(raw)
    except Exception:  # noqa: BLE001
        outcome = {"status": str((result or {}).get("status", "unreadable")), "normal_completion": False,
                   "failure_stage": "outcome_unreadable", "termination_reason": None, "rejection_tags": [],
                   "wall_seconds": elapsed, "cpu_seconds": None, "phase_timings": {}}
    matched = bool(result is not None and outcome["normal_completion"] and _answer_keys(result) == expected_keys(record))
    diag = (result or {}).get("diagnostics", {}) or {}
    ps = diag.get("pipeline_summary") or {}
    sf = ps.get("search_staged_fallback") or {}
    pr = ps.get("phase_rescue") or {}
    ea = ps.get("exact_assembly") or {}
    rf = ps.get("refinement") or {}
    compact = {"case_id": record.identifier, "seed": seed, "arm": arm, "cpu": cpu, "loadavg_start": load,
               "elapsed_seconds": elapsed, "timed_out": timed_out, "returncode": p.returncode,
               "status": outcome["status"], "normal_completion": outcome["normal_completion"],
               "failure_stage": outcome["failure_stage"], "termination_reason": outcome["termination_reason"],
               "wall_seconds": outcome["wall_seconds"], "cpu_seconds": outcome["cpu_seconds"],
               "phase_timings": outcome["phase_timings"], "rejection_tags": outcome["rejection_tags"],
               "ablations": (diag.get("config_snapshot") or {}).get("ablations"),
               "second_attempt_triggered": sf.get("triggered"), "second_attempt_selected": sf.get("selected_stage"),
               "rescue_triggered": pr.get("triggered"), "answer_source_candidate_id": ps.get("answer_source_candidate_id"),
               "refine_attempted": rf.get("attempted_count"), "refine_converged": rf.get("converged_count"),
               "exact_numeric_feasible": ea.get("numeric_feasible_count"), "exact_accepted": ea.get("accepted_count"),
               "exact_rejected_false": ea.get("rejected_false_positive_count"),
               "matched": matched, "answer_keys": _answer_keys(result) if result else None, "stderr_tail": se[-500:]}
    dest.write_text(json.dumps(compact))


def main():
    out, jobs = Path(sys.argv[1]).resolve(), int(sys.argv[2])
    cpus_arg, pset = [int(c) for c in sys.argv[3].split(",")], Path(sys.argv[4])
    out.mkdir(parents=True, exist_ok=True)
    ps = json.loads(pset.read_text())
    ids = list(ps["hard"]) + list(ps["fast_algebraic"]) + list(ps["fast_search"]) + list(ps["multivalued"])
    assert len(ids) == 72 and len(set(ids)) == 72, (len(ids), len(set(ids)))
    cases = {c.identifier: c for c in _load_cases(DEFAULT_CASES)}
    missing = [i for i in ids if i not in cases]
    assert not missing, missing
    hashes = {"started": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "problem_set_json_sha256": sha(pset),
              "cases_jsonl_sha256": sha(DEFAULT_CASES), "dsl_sha256": {i: sha(cases[i].dsl_path) for i in ids},
              "source_tree_hash": source_tree_hash(),
              "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "git_dirty": bool(subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"],
                                                        cwd=ROOT, text=True).strip()),
              "jobs": jobs, "cpus": cpus_arg[:jobs], "thread_environment": THREAD_ENVIRONMENT, "arms": ARMS,
              "seeds": list(SEEDS)}
    hp = out / "HASHES.json"
    if not hp.exists():
        hp.write_text(json.dumps(hashes, indent=1, sort_keys=True))
    tasks = []
    for s in SEEDS:
        for i in ids:
            k = (zlib.crc32(i.encode()) + s) % len(ORDER)
            for arm in ORDER[k:] + ORDER[:k]:
                tasks.append((cases[i], s, arm))
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
