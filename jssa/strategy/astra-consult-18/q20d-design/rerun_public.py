"""Correct the rejected CLI budget, preserving all originally registered inputs."""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

import run_experiment as base

OUT, ROOT = base.OUT, base.ROOT


def freeze():
    base.verify_lock()
    lock = OUT / "correction-lock.json"
    if lock.exists():
        raise RuntimeError("Correction already registered")
    logs = list((OUT / "runs").glob("*/process.log"))
    assert len(logs) == 20 and all("time_limit_seconds must be between 180 and 900" in p.read_text() for p in logs)
    assert not list((OUT / "runs").glob("*/result.json"))
    names = ["execution-correction.md", "rerun_public.py", "registration-lock.json"]
    base.dump(lock, {"utc": base.utc(), "full_solver_results_seen": 0,
                     "local_results_seen": 128,
                     "files": {n: base.sha(OUT / n) for n in names},
                     "initial_failure_log_hashes": {str(p.relative_to(OUT)): base.sha(p) for p in logs}})
    print(lock.read_text(), flush=True)


def verify():
    base.verify_lock()
    data = json.loads((OUT / "correction-lock.json").read_text())
    assert all(base.sha(OUT / n) == h for n, h in data["files"].items())
    assert all(base.sha(OUT / n) == h for n, h in data["initial_failure_log_hashes"].items())


def identify_worker(mode):
    from mpmath import mp
    from geosolver.engine.standard.exact_assembly.identify_answer import identify_answer
    from geosolver.runtime.deadline import runtime_session
    data = json.loads((OUT / "identification-input-180.json").read_text())
    candidate = data["candidate"]
    precision = min(250, int(candidate["answer_precision_dps"]))
    with mp.workdps(max(precision+50, 550)), runtime_session(time.monotonic()+30):
        started = time.monotonic()
        result = identify_answer(
            answer_hp=mp.mpf(candidate["answer_hp"]), tier="strict",
            input_precision_dps=precision, answer_uncertainty=mp.mpf(candidate["answer_uncertainty"]),
            geometry_hint=data["geometry_hint"] if mode == "hint" else None,
        )
        output = asdict(result)
        output.update(seconds=time.monotonic()-started, mode=mode,
                      saved_candidate_precision=candidate["answer_precision_dps"])
        base.dump(OUT / "identification-180" / mode / "result.json", output)


def identification():
    chosen = None
    for seed in base.SEEDS:
        path = OUT / "runs-180" / f"R4-{seed}" / "result.json"
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
    base.dump(OUT / "identification-input-180.json", chosen or {"status": "no_saved_candidate"})
    if chosen is None:
        print("identify: no saved candidate", flush=True)
        return
    (OUT / "identification-180").mkdir(exist_ok=True)
    for mode in ("plain", "hint"):
        folder = OUT / "identification-180" / mode
        base.bounded_process([sys.executable, str(Path(__file__).resolve()), "identify-worker", "--mode", mode], folder, 38)
        print("identify", mode, flush=True)


def run():
    verify()
    base.prepare_env()
    (OUT / "runs-180").mkdir(exist_ok=True)
    for index, seed in enumerate(base.SEEDS):
        for case_id in (base.IDS if index == 0 else list(reversed(base.IDS))):
            folder = OUT / "runs-180" / f"{case_id}-{seed}"
            if folder.exists():
                raise RuntimeError("Refusing to overwrite a measured run")
            command = [sys.executable, "-m", "geosolver.application.cli", "solve",
                       str(OUT / "inputs" / f"{case_id}.json"), "--time-limit-seconds", "180",
                       "--cores", "1", "--seed", str(seed), "--output", str(folder / "result.json")]
            run = base.bounded_process(command, folder, 188)
            result = json.loads((folder / "result.json").read_text()) if (folder / "result.json").exists() else {}
            print("full180", case_id, seed, result.get("status", "no_artifact"),
                  round(run["elapsed_seconds"], 3), flush=True)
    identification()
    verify()
    base.dump(OUT / "execution-audit-180.json", {"ended_utc": base.utc(), "registered_files_unchanged": True,
                                               "correction_files_unchanged": True, "src": base.source_hash()})


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
        identify_worker(args.mode)
