"""Single-GPU cumulative wall-time accounting across preparation/train/evaluation."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import signal
import subprocess
import time
from contextlib import suppress
from pathlib import Path

from .common import now, write_json


def initialize(path, hours=40, preparation_hours=2):
    path = Path(path)
    if path.exists():
        state = json.loads(path.read_text())
        if (
            state["limit_seconds"] != hours * 3600
            or state["preparation_limit_seconds"] != preparation_hours * 3600
        ):
            raise ValueError("Existing budget limits are immutable")
        return state
    state = {
        "limit_seconds": hours * 3600,
        "preparation_limit_seconds": preparation_hours * 3600,
        "created_utc": now(),
        "jobs": [],
    }
    write_json(path, state)
    return state


def remaining(state, category=None):
    if any(j["status"] == "running" for j in state["jobs"]):
        raise ValueError("Unfinished budget entry: inspect/reconcile the worker before resuming")
    total = state["limit_seconds"] - sum(j["charged_seconds"] for j in state["jobs"])
    if category == "preparation":
        total = min(
            total,
            state["preparation_limit_seconds"]
            - sum(j["charged_seconds"] for j in state["jobs"] if j["category"] == "preparation"),
        )
    return total


def run_budgeted(command, log, ledger, category, timeout=None, reserve_seconds=0):
    ledger = Path(ledger)
    lock_path = ledger.with_suffix(".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another GPU job owns this budget") from exc
        state = json.loads(ledger.read_text())
        allowance = remaining(state, category) - reserve_seconds
        if timeout is not None:
            allowance = min(allowance, timeout)
        # Leave time for process-group teardown inside the booked allowance.
        grace = min(20.0, max(0.1, allowance / 10))
        if allowance <= grace:
            raise TimeoutError("Cumulative GPU budget exhausted or reserved for evaluation")
        job = {
            "command": list(command),
            "category": category,
            "log": str(log),
            "started_utc": now(),
            "status": "running",
            "allowance_seconds": allowance,
            "charged_seconds": 0.0,
            "owner_pid": os.getpid(),
        }
        state["jobs"].append(job)
        write_json(ledger, state)
        started = time.monotonic()
        process = None
        previous_term = signal.getsignal(signal.SIGTERM)

        def terminate_worker(signum, frame):
            raise KeyboardInterrupt("Budget owner received SIGTERM")

        signal.signal(signal.SIGTERM, terminate_worker)
        try:
            Path(log).parent.mkdir(parents=True, exist_ok=True)
            with Path(log).open("a") as stream:
                process = subprocess.Popen(
                    command, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True
                )
                job["process_group"] = process.pid
                write_json(ledger, state)
                code = process.wait(timeout=allowance - grace)
            job["exit_code"] = code
            if code:
                raise RuntimeError(f"Worker exited {code}; inspect {log}")
            job["status"] = "complete"
        except BaseException as exc:
            job["status"] = "failed"
            job["error"] = repr(exc)
            raise
        finally:
            signal.signal(signal.SIGTERM, previous_term)
            if process is not None:
                # Also stop descendants if the main worker exited unexpectedly.
                with suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=grace)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                # The leader may already have exited while a GPU descendant
                # remains. Kill only this worker's isolated process group.
                with suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
            job["charged_seconds"] = time.monotonic() - started
            job["ended_utc"] = now()
            write_json(ledger, state)


def main():
    ap = argparse.ArgumentParser(__doc__)
    ap.add_argument("mode", choices=["init", "run", "status"])
    ap.add_argument("--ledger", required=True)
    ap.add_argument(
        "--category", choices=["preparation", "training", "evaluation"], default="preparation"
    )
    ap.add_argument("--log")
    ap.add_argument("--seconds", type=float)
    args, command = ap.parse_known_args()
    if args.mode == "init":
        initialize(args.ledger)
    elif args.mode == "run":
        command = command[1:] if command[:1] == ["--"] else command
        if not command or not args.log:
            ap.error("run needs --log and a worker command")
        run_budgeted(command, args.log, args.ledger, args.category, args.seconds)
    state = json.loads(Path(args.ledger).read_text())
    print(
        json.dumps(
            {
                "remaining_seconds": remaining(state),
                "preparation_remaining_seconds": remaining(state, "preparation"),
                "jobs": len(state["jobs"]),
            }
        )
    )


if __name__ == "__main__":
    main()
