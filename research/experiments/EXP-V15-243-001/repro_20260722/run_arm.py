#!/usr/bin/env python3
"""Run one frozen solver arm, then score exact-set equality offline.

This is intentionally only a selector around the existing dataset runner and
scorer.  The worker sees materialized ``formulation`` objects; the scorer reads
the outer answer field only after the dataset runner has returned.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
DEFAULT_PYTHON = ROOT / "python/.venv/bin/python"
DEFAULT_DATASET = Path("/home/kabatan/ダウンロード/omc_v15_merged_5files.jsonl")
BASE_RUNNER = ROOT / "research/experiments/EXP-OMC-G-PART01-V15-EVAL-001/run_dataset.py"
SCORER = ROOT / "research/experiments/EXP-OMC-G-PART01-V15-EVAL-001/score_dataset.py"
BENCHMARK = HERE.parent / "benchmark/formal_baseline.py"
WORKERS = {
    "baseline": ROOT / "research/experiments/EXP-REAL61-008/finalist_numeric_worker_v15/worker.py",
    "champion_v1": HERE.parent / "champion_v1/worker.py",
    "baseline_preloaded": HERE / "workers/baseline_preloaded.py",
    "champion_v1_preloaded": HERE / "workers/champion_v1_preloaded.py",
    "champion_v2_preloaded": HERE / "workers/champion_v2_preloaded.py",
    "champion_v2_branch_diverse_preloaded": (
        HERE / "workers/champion_v2_branch_diverse_preloaded.py"
    ),
    "champion_v2_poc_preloaded": HERE / "workers/champion_v2_poc_preloaded.py",
    "champion_v2_poc_bounded_wave1_preloaded": (
        HERE / "workers/champion_v2_poc_bounded_wave1_preloaded.py"
    ),
    "champion_v2_poc_guard_stratum_preloaded": (
        HERE / "workers/champion_v2_poc_guard_stratum_preloaded.py"
    ),
    "champion_v2_poc_direct_exact_preloaded": (
        HERE / "workers/champion_v2_poc_direct_exact_preloaded.py"
    ),
    "champion_v2_poc_hp_scheduler": (
        HERE.parent / "candidates/repro_hp_scheduler_poc_binding/worker.py"
    ),
    "champion_v2_poc_callback_ledger_v4": (
        HERE.parent / "candidates/repro_champion_v2_poc_callback_ledger_v4/worker.py"
    ),
    "champion_v2_poc_archive_levy_tail": (
        HERE.parent / "candidates/repro_champion_v2_poc_archive_levy_tail/worker.py"
    ),
    "champion_v2_poc_bounded_wave1_archive_levy_tail": (
        HERE.parent
        / "candidates/repro_champion_v2_poc_bounded_wave1_archive_levy_tail/worker.py"
    ),
    "champion_v2_poc_archive_levy_branch_diverse": (
        HERE.parent
        / "candidates/repro_champion_v2_poc_archive_levy_branch_diverse/worker.py"
    ),
}
THREAD_ENVIRONMENT = {
    "PYTHONDONTWRITEBYTECODE": "1",
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
}


def _sha256(path_or_payload: Path | bytes) -> str:
    payload = path_or_payload.read_bytes() if isinstance(path_or_payload, Path) else path_or_payload
    return hashlib.sha256(payload).hexdigest()


def _load(path: Path, name: str):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _runtime_preflight(python: Path) -> dict[str, str]:
    if not python.is_file() or not os.access(python, os.X_OK):
        raise SystemExit(f"Python interpreter is unavailable: {python}")
    code = (
        "import json,numpy,scipy,mpmath,sympy;"
        "print(json.dumps({'numpy':numpy.__version__,'scipy':scipy.__version__,"
        "'mpmath':mpmath.__version__,'sympy':sympy.__version__},sort_keys=True))"
    )
    completed = subprocess.run(
        [str(python), "-c", code],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, **THREAD_ENVIRONMENT},
    )
    return json.loads(completed.stdout)


def _invoke(module, arguments: list[str]) -> None:
    previous = sys.argv
    try:
        sys.argv = [str(module.__file__), *arguments]
        module.main()
    finally:
        sys.argv = previous


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", required=True, choices=tuple(WORKERS))
    parser.add_argument("--partition", default="development", choices=("development", "screen24"))
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--python", type=Path, default=DEFAULT_PYTHON)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=7)
    parser.add_argument("--cpus", default="8,9,10,11,12,13,14")
    parser.add_argument("--total-seconds", type=float, default=180.0)
    parser.add_argument("--search-seconds", type=float, default=146.0)
    parser.add_argument("--starts", type=int, default=256)
    parser.add_argument("--callbacks-per-start", type=int, default=600)
    parser.add_argument("--aggregate-callback-cap", type=int, default=153600)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--execute", action="store_true")
    arguments = parser.parse_args()

    output = arguments.output.resolve()
    if output.exists():
        raise SystemExit(f"refusing existing output path: {output}")
    # Keep a venv launcher symlink intact.  Resolving it selects the base
    # interpreter and silently drops the venv's site-packages.
    python = arguments.python.expanduser().absolute()
    worker = WORKERS[arguments.arm].resolve()
    for required in (worker, BASE_RUNNER, SCORER, BENCHMARK):
        if not required.is_file():
            raise SystemExit(f"required frozen input is unavailable: {required}")
    versions = _runtime_preflight(python)

    benchmark = _load(BENCHMARK, "geotarget_repro_20260722_benchmark")
    dataset = arguments.dataset.resolve()
    rows, _ = benchmark._load_rows(dataset)
    documents = benchmark.build_documents(dataset)
    benchmark._check_documents(documents)
    selected_ids = benchmark._selection(arguments.partition, documents)
    subset_payload = benchmark._subset_payload(rows, selected_ids)

    common = [
        "--dataset", "<temporary-truth-isolated-subset>",
        "--jobs", str(arguments.jobs),
        "--cpus", arguments.cpus,
        "--total-seconds", str(arguments.total_seconds),
        "--search-seconds", str(arguments.search_seconds),
        "--starts", str(arguments.starts),
        "--callbacks-per-start", str(arguments.callbacks_per_start),
        "--aggregate-callback-cap", str(arguments.aggregate_callback_cap),
        "--seed", str(arguments.seed),
        "--output", str(output),
    ]
    plan = {
        "arm": arguments.arm,
        "execute": arguments.execute,
        "partition": arguments.partition,
        "case_count": len(selected_ids),
        "selected_dataset_sha256": _sha256(subset_payload),
        "python": str(python),
        "runtime_versions": versions,
        "worker": str(worker),
        "worker_sha256": _sha256(worker),
        "runner_sha256": _sha256(BASE_RUNNER),
        "scorer_sha256": _sha256(SCORER),
        "truth_passed_to_worker": False,
        "score_rule": "accepted AND no duplicates AND returned exact descriptor set == expected set",
        "arguments": common,
    }
    if not arguments.execute:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    environment = {**os.environ, **THREAD_ENVIRONMENT}
    with tempfile.TemporaryDirectory(prefix=f".{output.name}.subset-", dir=output.parent) as temporary:
        subset = Path(temporary) / f"{arguments.partition}.jsonl"
        subset.write_bytes(subset_payload)

        runner = _load(BASE_RUNNER, f"geotarget_repro_runner_{arguments.arm}")
        runner.PYTHON = python
        runner.WORKER = worker
        runner.THREAD_ENVIRONMENT = {**runner.THREAD_ENVIRONMENT, **THREAD_ENVIRONMENT}
        run_arguments = [value if value != "<temporary-truth-isolated-subset>" else str(subset) for value in common]
        _invoke(runner, ["--execute", *run_arguments])

        subprocess.run(
            [str(python), str(SCORER), "--dataset", str(subset), "--run", str(output)],
            check=True,
            cwd=ROOT,
            env=environment,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
