#!/usr/bin/env python3
"""Run the frozen v15 numeric worker on the supplied canonical JSONL corpus.

The outer JSONL contains offline truth beside a standalone v15 formulation.
Only the formulation is materialized and passed to the solver.  Truth is never
placed in a worker input, environment variable, path, or command line.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
from queue import Queue
import re
import sys
import time
import traceback
from typing import Mapping


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
WORKER = (
    ROOT
    / "research/experiments/EXP-REAL61-008/finalist_numeric_worker_v15/worker.py"
)
PYTHON = ROOT / "python/.venv/bin/python"
DEFAULT_DATASET = Path(
    "/home/kabatan/ダウンロード/omc_dataset_field_G_part_01_v15_canonical.jsonl"
)
ONE_MIB = 1024**2
ONE_GIB = 1024**3
MAX_JOBS = 7

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.infrastructure.memory_safety.safe_subprocess import (  # noqa: E402
    Limits,
    atomic_write_json,
    run_guarded,
)


THREAD_ENVIRONMENT = {
    "PYTHONHASHSEED": "0",
    "OMP_NUM_THREADS": "1",
    "OMP_THREAD_LIMIT": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "BLIS_NUM_THREADS": "1",
    "GOTO_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "JULIA_NUM_THREADS": "1",
    "RAYON_NUM_THREADS": "1",
    "MALLOC_ARENA_MAX": "2",
    "GEOTARGET_GLOBAL_RSS_RESERVATION_BYTES": str(8 * ONE_GIB),
}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _slug(index: int, problem_id: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", problem_id).strip("_")
    return f"{index:03d}-{clean}"


def _canonical_formulation_bytes(formulation: Mapping[str, object]) -> bytes:
    return (
        json.dumps(
            formulation,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


def _load_dataset(path: Path) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        outer = json.loads(line)
        if not isinstance(outer, Mapping):
            raise ValueError(f"row {index}: outer record must be an object")
        problem_id = outer.get("problem_id")
        formulation = outer.get("formulation")
        if not isinstance(problem_id, str) or not isinstance(formulation, Mapping):
            raise ValueError(f"row {index}: missing problem_id/formulation")
        if formulation.get("id") != problem_id or formulation.get("task") != "solve":
            raise ValueError(f"row {index}: formulation identity/task mismatch")
        variables = formulation.get("variables")
        names = variables.get("names") if isinstance(variables, Mapping) else None
        if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
            raise ValueError(f"row {index}: malformed variables.names")
        rows.append(
            {
                "index": len(rows) + 1,
                "problem_id": problem_id,
                "slug": _slug(len(rows) + 1, problem_id),
                "variable_count": len(names),
                "formulation": dict(formulation),
            }
        )
    if not rows:
        raise ValueError("dataset is empty")
    if len({str(row["problem_id"]) for row in rows}) != len(rows):
        raise ValueError("duplicate problem_id")
    return tuple(rows)


def _cpus(text: str, jobs: int) -> tuple[int, ...]:
    values = tuple(int(item.strip()) for item in text.split(",") if item.strip())
    if len(values) < jobs or len(set(values[:jobs])) != jobs:
        raise ValueError("--cpus must provide one distinct physical CPU per job")
    selected = values[:jobs]
    if any(cpu < 0 or cpu >= 16 for cpu in selected):
        raise ValueError("use first-sibling physical CPU ids 0..15")
    return selected


def _accepted(result: object, digest: str, total_seconds: float) -> bool:
    return bool(
        isinstance(result, Mapping)
        and result.get("schema_version")
        == "geotarget.exp008-finalist-numeric-worker-v15/v1"
        and result.get("completed") is True
        and result.get("source_sha256") == digest
        and result.get("source_bytes_unchanged") is True
        and result.get("within_total_wall_budget") is True
        and float(result.get("elapsed_wall_seconds", total_seconds + 1.0))
        <= total_seconds
        and isinstance(result.get("distinct_exact_targets"), list)
        and result.get("truth_case_family_known_target_count_read") is False
        and result.get("source_or_problem_modified") is False
        and result.get("variables_or_equations_removed") is False
        and result.get("bounds_added_or_inferred") is False
        and result.get("gauge_or_symmetry_reduction") is False
        and result.get("coordinate_reparameterization") is False
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--jobs", type=int, default=7)
    parser.add_argument("--cpus", default="1,2,3,5,6,7,9")
    parser.add_argument("--total-seconds", type=float, default=180.0)
    parser.add_argument("--search-seconds", type=float, default=146.0)
    parser.add_argument("--starts", type=int, default=256)
    parser.add_argument("--callbacks-per-start", type=int, default=600)
    parser.add_argument("--aggregate-callback-cap", type=int, default=153600)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--output",
        type=Path,
        default=HERE / "results/formal-180s-seed0-jobs7-v1",
    )
    arguments = parser.parse_args()

    try:
        if not 1 <= arguments.jobs <= MAX_JOBS:
            raise ValueError(
                f"--jobs must lie in [1,{MAX_JOBS}] for nested HP admission"
            )
        cpus = _cpus(arguments.cpus, arguments.jobs)
        dataset = arguments.dataset.resolve()
        dataset_bytes = dataset.read_bytes()
        bindings = _load_dataset(dataset)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error

    plan = {
        "execute": arguments.execute,
        "dataset": str(dataset),
        "dataset_sha256": _sha256(dataset_bytes),
        "case_count": len(bindings),
        "jobs": arguments.jobs,
        "cpus": list(cpus),
        "total_seconds": arguments.total_seconds,
        "search_seconds": arguments.search_seconds,
        "starts": arguments.starts,
        "callbacks_per_start": arguments.callbacks_per_start,
        "aggregate_callback_cap": arguments.aggregate_callback_cap,
        "seed": arguments.seed,
        "worker": str(WORKER),
        "worker_sha256": _sha256(WORKER.read_bytes()) if WORKER.is_file() else None,
        "fresh_process_per_case": True,
        "one_pinned_physical_core_per_case": True,
        "truth_or_known_target_count_passed_to_solver": False,
        "formulation_content_modified": False,
        "bounds_added_or_inferred": False,
        "gauge_or_symmetry_reduction": False,
    }
    if not arguments.execute:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return
    if not PYTHON.is_file() or not WORKER.is_file():
        raise SystemExit("integrated Python/worker is unavailable")

    output = arguments.output.resolve()
    if output.exists():
        raise SystemExit(f"refusing existing output directory: {output}")
    output.mkdir(parents=True)
    atomic_write_json(output / "RUN_PLAN.json", plan)

    materialized: list[dict[str, object]] = []
    for binding in bindings:
        source = output / "inputs" / f"{binding['slug']}.json"
        source.parent.mkdir(parents=True, exist_ok=True)
        payload = _canonical_formulation_bytes(binding["formulation"])
        source.write_bytes(payload)
        materialized.append(
            {
                **binding,
                "source": source,
                "digest": _sha256(payload),
            }
        )
    atomic_write_json(
        output / "INPUT_MANIFEST.json",
        {
            "dataset_sha256": plan["dataset_sha256"],
            "truth_fields_materialized_into_solver_inputs": False,
            "rows": [
                {
                    "index": row["index"],
                    "problem_id": row["problem_id"],
                    "slug": row["slug"],
                    "variable_count": row["variable_count"],
                    "source": str(row["source"]),
                    "source_sha256": row["digest"],
                }
                for row in materialized
            ],
        },
    )

    cpu_queue: Queue[int] = Queue()
    for cpu in cpus:
        cpu_queue.put(cpu)
    dry_limits = Limits(
        timeout_seconds=8.0,
        rss_bytes=256 * ONE_MIB,
        address_space_bytes=2 * ONE_GIB,
        data_bytes=1536 * ONE_MIB,
        output_bytes=256 * 1024,
        tail_bytes=8 * 1024,
    )
    run_limits = Limits(
        timeout_seconds=arguments.total_seconds + 3.0,
        rss_bytes=256 * ONE_MIB,
        address_space_bytes=3 * ONE_GIB,
        data_bytes=2 * ONE_GIB,
        output_bytes=256 * 1024,
        tail_bytes=8 * 1024,
    )

    def run_one(binding: Mapping[str, object]) -> dict[str, object]:
        cpu = cpu_queue.get()
        problem_id = str(binding["problem_id"])
        slug = str(binding["slug"])
        digest = str(binding["digest"])
        source = Path(binding["source"])
        case_output = output / "artifacts" / slug
        command = [
            "taskset",
            "-c",
            str(cpu),
            str(PYTHON),
            str(WORKER),
            "--source",
            str(source),
            "--source-sha256",
            digest,
            "--total-seconds",
            str(arguments.total_seconds),
            "--search-seconds",
            str(arguments.search_seconds),
            "--starts",
            str(arguments.starts),
            "--callbacks-per-start",
            str(arguments.callbacks_per_start),
            "--aggregate-callback-cap",
            str(arguments.aggregate_callback_cap),
            "--seed",
            str(arguments.seed),
            "--cpu",
            str(cpu),
            "--output",
            str(case_output),
        ]
        started = time.monotonic()
        try:
            dry = run_guarded(
                command,
                limits=dry_limits,
                environment=THREAD_ENVIRONMENT,
                cwd=ROOT,
                status_path=output / "process-status" / slug / "dry.json",
            )
            plan_path = case_output / "PLAN.json"
            if not dry.accepted_output or not plan_path.is_file():
                return {
                    "index": binding["index"],
                    "problem_id": problem_id,
                    "slug": slug,
                    "variable_count": binding["variable_count"],
                    "accepted": False,
                    "process_classification": "DRY_PLAN_FAILED",
                    "outer_elapsed_seconds": time.monotonic() - started,
                    "exact_target_count": 0,
                    "cpu": cpu,
                }
            plan_sha256 = _sha256(plan_path.read_bytes())
            executed = run_guarded(
                command + ["--execute", "--plan-sha256", plan_sha256],
                limits=run_limits,
                environment=THREAD_ENVIRONMENT,
                cwd=ROOT,
                status_path=output / "process-status" / slug / "execute.json",
            )
            result = None
            result_path = case_output / "RESULT.json"
            if executed.accepted_output and result_path.is_file():
                try:
                    result = json.loads(result_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    pass
            targets = (
                result.get("distinct_exact_targets", [])
                if isinstance(result, Mapping)
                else []
            )
            return {
                "index": binding["index"],
                "problem_id": problem_id,
                "slug": slug,
                "variable_count": binding["variable_count"],
                "accepted": executed.accepted_output
                and _accepted(result, digest, arguments.total_seconds),
                "process_classification": executed.classification,
                "elapsed_wall_seconds": (
                    result.get("elapsed_wall_seconds")
                    if isinstance(result, Mapping)
                    else None
                ),
                "outer_elapsed_seconds": time.monotonic() - started,
                "exact_target_count": len(targets) if isinstance(targets, list) else 0,
                "peak_outer_worker_rss_bytes": executed.peak_process_group_rss_bytes,
                "cpu": cpu,
            }
        except Exception as error:  # preserve the rest of a long formal run
            return {
                "index": binding["index"],
                "problem_id": problem_id,
                "slug": slug,
                "variable_count": binding["variable_count"],
                "accepted": False,
                "process_classification": "LAUNCHER_EXCEPTION",
                "outer_elapsed_seconds": time.monotonic() - started,
                "exact_target_count": 0,
                "cpu": cpu,
                "error": f"{type(error).__name__}: {error}",
                "traceback": traceback.format_exc(),
            }
        finally:
            cpu_queue.put(cpu)

    rows: list[dict[str, object]] = []
    run_started = time.monotonic()
    with ThreadPoolExecutor(max_workers=arguments.jobs) as executor:
        futures = [executor.submit(run_one, binding) for binding in materialized]
        for future in as_completed(futures):
            row = future.result()
            rows.append(row)
            print(
                f"[{len(rows):02d}/{len(materialized)}] "
                f"{row['problem_id']} vars={row['variable_count']} "
                f"accepted={row['accepted']} exact={row['exact_target_count']} "
                f"class={row['process_classification']} "
                f"elapsed={float(row['outer_elapsed_seconds']):.1f}s",
                flush=True,
            )
            atomic_write_json(
                output / "CHECKPOINT.json",
                {
                    "completed_count": len(rows),
                    "total_count": len(materialized),
                    "elapsed_seconds": time.monotonic() - run_started,
                    "rows": sorted(rows, key=lambda item: int(item["index"])),
                },
            )
    rows.sort(key=lambda item: int(item["index"]))
    atomic_write_json(
        output / "RESULT.json",
        {
            "status": "COMPLETE" if all(row["accepted"] for row in rows) else "PARTIAL",
            "plan": plan,
            "elapsed_seconds": time.monotonic() - run_started,
            "accepted_case_count": sum(int(bool(row["accepted"])) for row in rows),
            "cases_with_exact_target_count": sum(
                int(int(row["exact_target_count"]) > 0) for row in rows
            ),
            "rows": rows,
        },
    )
    print(output / "RESULT.json", flush=True)


if __name__ == "__main__":
    main()
