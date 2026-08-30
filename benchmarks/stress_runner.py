"""Explicitly oversubscribed Linux diagnostic runs; not canonical performance runs."""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from queue import Queue

import psutil
import research_runner as runner


def select_cases(records, identifiers):
    requested = set(identifiers)
    chosen = [r for r in records if r.identifier in requested and r.runnable]
    if not requested or {r.identifier for r in chosen} != requested:
        raise runner.CampaignError("a nonempty set of runnable case IDs is required")
    return sorted(chosen, key=lambda r: r.identifier)


def cpu_slots(cpus, jobs):
    if not cpus or jobs < 1:
        raise runner.CampaignError("positive jobs and a nonempty CPU list required")
    return [cpus[index % len(cpus)] for index in range(jobs)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--jobs", type=int, default=16)
    parser.add_argument("--physical-cores", type=int, default=8)
    selection_group = parser.add_mutually_exclusive_group(required=True)
    selection_group.add_argument("--case-id", action="append")
    selection_group.add_argument("--all", action="store_true", help="all verified runnable cases")
    arguments = parser.parse_args()
    destination = arguments.destination.resolve()
    if destination.exists() and any(destination.iterdir()):
        raise runner.CampaignError("refusing to overwrite an existing campaign")
    if sys.platform != "linux":
        raise runner.CampaignError("this diagnostic harness requires Linux affinity")
    if arguments.physical_cores < 1:
        raise runner.CampaignError("physical-cores must be positive")
    cpus = runner._independent_cpus()[: arguments.physical_cores]
    if len(cpus) != arguments.physical_cores or None in cpus:
        raise runner.CampaignError("not enough independently assignable CPUs")
    slots = cpu_slots(cpus, arguments.jobs)
    from geosolver.runtime.integrity import verify_engine_lock

    valid, detail = verify_engine_lock()
    if not valid or runner.runtime_fingerprint()["issues"]:
        raise runner.CampaignError(f"product/runtime verification failed: {detail}")
    validation = runner.validate_corpus()
    if not validation["valid"]:
        raise runner.CampaignError(str(validation))
    records = runner._load_cases()
    if arguments.all:
        identifiers = [r.identifier for r in records if r.runnable and r.truth_status == "verified"]
        selection = "all verified runnable cases, ordered by case ID"
    else:
        identifiers = arguments.case_id
        selection = "explicit case IDs, ordered by case ID; see manifest"
    records = select_cases(records, identifiers)
    psutil.Process().cpu_affinity(cpus)
    manifest = runner._manifest(records, [0])
    manifest["diagnostic_execution"] = {
        "canonical_performance_run": False,
        "selection_rule": selection,
        "population": validation,
        "family_counts": dict(Counter(r.identifier.upper().split("-")[0] for r in records)),
        "variable_counts": dict(sorted(Counter(len(r.dsl["variables"]) for r in records).items())),
        "physical_cores": len(cpus),
        "cpu_ids": cpus,
        "requested_jobs": arguments.jobs,
        "cpu_slots": slots,
        "harness_sha256": runner._sha256_file(Path(__file__)),
        "dirty_changes": runner._git_value("status", "--porcelain"),
        "note": "Product engine lock verified separately; tooling/artifacts may be uncommitted. "
        "180 seconds is wall time, not dedicated CPU time under oversubscription.",
    }
    runner._atomic_json(destination / "campaign-manifest.json", manifest)
    available = Queue()
    for cpu in slots:
        available.put(cpu)
    lock = threading.Lock()
    active = Counter()
    events = []
    started = time.monotonic()

    def run_one(record):
        cpu = available.get()
        with lock:
            active[cpu] += 1
            events.append(
                {
                    "event": "start",
                    "case": record.identifier,
                    "cpu": cpu,
                    "seconds": time.monotonic() - started,
                    "active": sum(active.values()),
                }
            )
        try:
            return runner._run_one(record, 0, destination, cpu)
        finally:
            with lock:
                active[cpu] -= 1
                events.append(
                    {
                        "event": "finish",
                        "case": record.identifier,
                        "cpu": cpu,
                        "seconds": time.monotonic() - started,
                        "active": sum(active.values()),
                    }
                )
            available.put(cpu)

    errors = []
    print(json.dumps(manifest["diagnostic_execution"], ensure_ascii=False), flush=True)
    with ThreadPoolExecutor(max_workers=arguments.jobs) as executor:
        futures = {executor.submit(run_one, record): record.identifier for record in records}
        for index, future in enumerate(as_completed(futures), 1):
            try:
                path = future.result()
                raw = json.loads(path.read_text())
                result = raw.get("solver_result") or {}
                print(
                    f"{index}/{len(records)} {futures[future]} {result.get('status')} "
                    f"{result.get('termination_reason')} "
                    f"{raw['process']['elapsed_seconds']:.2f}s",
                    flush=True,
                )
            except Exception as error:
                errors.append({"case": futures[future], "error": repr(error)})
                print(f"ERROR {futures[future]} {error}", flush=True)
    runner._atomic_json(
        destination / "scheduling.json",
        {
            "elapsed_seconds": time.monotonic() - started,
            "events": events,
            "errors": errors,
            "peak_active_runs": max(event["active"] for event in events),
        },
    )
    runner.write_checksums(destination)
    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
