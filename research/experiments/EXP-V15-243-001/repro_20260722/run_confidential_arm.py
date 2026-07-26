#!/usr/bin/env python3
"""Run one frozen arm on validation/sealed without publishing case results."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
RUN_ARM = HERE / "run_arm.py"
BENCHMARK = HERE.parent / "benchmark/formal_baseline.py"


def main() -> int:
    run_arm = _load(RUN_ARM, "geotarget_confidential_run_arm")
    benchmark = _load(BENCHMARK, "geotarget_confidential_benchmark")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", required=True, choices=tuple(run_arm.WORKERS))
    parser.add_argument("--partition", required=True, choices=("validation", "sealed"))
    parser.add_argument("--dataset", type=Path, default=run_arm.DEFAULT_DATASET)
    parser.add_argument("--python", type=Path, default=run_arm.DEFAULT_PYTHON)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--public-summary", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=7)
    parser.add_argument("--cpus", default="1,2,3,5,6,7,9")
    parser.add_argument("--total-seconds", type=float, default=180.0)
    parser.add_argument("--search-seconds", type=float, default=146.0)
    parser.add_argument("--starts", type=int, default=256)
    parser.add_argument("--callbacks-per-start", type=int, default=600)
    parser.add_argument("--aggregate-callback-cap", type=int, default=153600)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--execute", action="store_true")
    arguments = parser.parse_args()

    try:
        dataset = arguments.dataset.resolve()
        rows, _ = benchmark._load_rows(dataset)
        documents = benchmark.build_documents(dataset)
        benchmark._check_documents(documents)
        selected_ids = benchmark._selection(arguments.partition, documents)
        subset_payload = benchmark._subset_payload(rows, selected_ids)
        output = arguments.output.resolve()
        public_summary = arguments.public_summary.resolve()
        python = arguments.python.expanduser().absolute()
        worker = run_arm.WORKERS[arguments.arm].resolve()
        if benchmark._is_within(output, ROOT):
            raise ValueError("confidential output must be outside the repository")
        if output.exists():
            raise ValueError(f"refusing existing output path: {output}")
        for required in (
            worker,
            run_arm.BASE_RUNNER,
            run_arm.SCORER,
            RUN_ARM,
            BENCHMARK,
        ):
            if not required.is_file():
                raise ValueError("a frozen input is unavailable")
        versions = run_arm._runtime_preflight(python)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error

    run_arguments = [
        "--dataset", "<private-temporary-subset>",
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
    selected_digest = benchmark._sha256(subset_payload)
    plan = {
        "schema_version": "geotarget.exp-v15-243-confidential-arm-plan/v1",
        "execute": arguments.execute,
        "arm": arguments.arm,
        "partition": arguments.partition,
        "confidential_partition": True,
        "case_count": len(selected_ids),
        "dataset_sha256": benchmark.EXPECTED_DATASET_SHA256,
        "selected_dataset_sha256": selected_digest,
        "worker_sha256": run_arm._sha256(worker),
        "runner_sha256": run_arm._sha256(run_arm.BASE_RUNNER),
        "scorer_sha256": run_arm._sha256(run_arm.SCORER),
        "runtime_versions": versions,
        "truth_passed_to_worker": False,
        "individual_confidential_results_published": False,
        "score_rule": "accepted AND no duplicates AND returned exact descriptor set == expected set",
        "arguments": run_arguments,
    }
    if not arguments.execute:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    output.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    if stat.S_IMODE(output.parent.stat().st_mode) & 0o077:
        raise SystemExit("confidential output parent must be mode 0700")
    temporary_log_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=f".{output.name}.log-",
            dir=output.parent,
            delete=False,
        ) as log, tempfile.TemporaryDirectory(
            prefix=f".{output.name}.dataset-", dir=output.parent
        ) as temporary:
            temporary_log_path = Path(log.name)
            os.chmod(temporary_log_path, 0o600)
            temporary_root = Path(temporary)
            os.chmod(temporary_root, 0o700)
            subset = temporary_root / "selected.jsonl"
            subset.write_bytes(subset_payload)
            os.chmod(subset, 0o600)

            runner = run_arm._load(
                run_arm.BASE_RUNNER,
                f"geotarget_confidential_runner_{arguments.arm}",
            )
            runner.PYTHON = python
            runner.WORKER = worker
            runner.THREAD_ENVIRONMENT = {
                **runner.THREAD_ENVIRONMENT,
                **run_arm.THREAD_ENVIRONMENT,
            }
            concrete_arguments = [
                str(subset) if value == "<private-temporary-subset>" else value
                for value in run_arguments
            ]
            with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                run_arm._invoke(runner, ["--execute", *concrete_arguments])
            scored = subprocess.run(
                [str(python), str(run_arm.SCORER), "--dataset", str(subset), "--run", str(output)],
                cwd=ROOT,
                env={**os.environ, **run_arm.THREAD_ENVIRONMENT},
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
            if scored.returncode != 0:
                raise RuntimeError("offline scorer failed")
    except BaseException as error:
        if isinstance(error, KeyboardInterrupt):
            raise
        raise SystemExit("confidential run failed; inspect the private log") from None

    assert temporary_log_path is not None
    os.chmod(output, 0o700)
    private_log = output / "CUSTODIAN_RUN_LOG.txt"
    os.replace(temporary_log_path, private_log)
    os.chmod(private_log, 0o600)
    raw_score = output / "OFFLINE_SCORE.json"
    private_score = output / "CUSTODIAN_OFFLINE_SCORE.json"
    os.replace(raw_score, private_score)
    os.chmod(private_score, 0o600)
    score = json.loads(private_score.read_text(encoding="utf-8"))
    summary = benchmark._public_summary(
        partition=arguments.partition,
        selected_dataset_sha256=selected_digest,
        seed=arguments.seed,
        score=score,
    )
    summary["solver_arm"] = arguments.arm
    summary["worker_sha256"] = run_arm._sha256(worker)
    benchmark.atomic_write_json(output / "CUSTODIAN_WRAPPER_PLAN.json", plan, mode=0o600)
    benchmark.atomic_write_json(public_summary, summary, mode=0o644)
    print(public_summary)
    return 0


def _load(path: Path, name: str):
    import importlib.util
    import sys

    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


if __name__ == "__main__":
    raise SystemExit(main())
