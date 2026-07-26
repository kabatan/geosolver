"""Resume only the frozen champion's explicitly deferred reservoir records."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from geotarget.parallel import install as install_parallel


def _load_frozen(runtime: Path):
    entrypoint = (
        runtime
        / "solver/research/experiments/EXP-V15-243-001/repro_20260722/workers"
        / "champion_v2_poc_preloaded.py"
    )
    sys.path.insert(0, str(entrypoint.parent))
    specification = importlib.util.spec_from_file_location(
        "geotarget_product_continuation_frozen", entrypoint
    )
    if specification is None or specification.loader is None:
        raise ImportError(entrypoint)
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module.CHAMPION.BASE


def _descriptor_key(descriptor: Mapping[str, Any]) -> str:
    polynomial = descriptor.get("minimal_polynomial_high_to_low")
    root = descriptor.get("selected_real_root_index")
    return json.dumps([polynomial, root], separators=(",", ":"), sort_keys=True)


def _existing_descriptors(result: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    values = result.get("distinct_exact_target_descriptors") or result.get("distinct_exact_targets")
    descriptors: dict[str, dict[str, Any]] = {}
    if isinstance(values, list):
        for value in values:
            if isinstance(value, Mapping):
                descriptor = dict(value)
                descriptors.setdefault(_descriptor_key(descriptor), descriptor)
    return descriptors


def _pending_candidates(
    base: Any,
    source_document: dict[str, Any],
    search: Mapping[str, Any],
    result: Mapping[str, Any],
    deadline: float,
    new_endpoints: set[tuple[float, ...]] | None = None,
):
    endpoints = search.get("endpoints")
    if not isinstance(endpoints, list):
        return ()
    all_candidates = base._fresh_replay_candidates(
        source_document,
        endpoints,
        hard_deadline=min(deadline, time.monotonic() + base.SELECTION_RESERVE_SECONDS),
    )
    schedule = result.get("hp_schedule")
    deferred = schedule.get("deferred_record_ids") if isinstance(schedule, Mapping) else ()
    deferred_ids = {str(value) for value in deferred} if isinstance(deferred, list) else set()
    def wanted(candidate: Any) -> bool:
        if candidate.record_id in deferred_ids:
            return True
        endpoint = getattr(candidate, "endpoint", None)
        return new_endpoints is not None and tuple(endpoint or ()) in new_endpoints

    verified = tuple(candidate for candidate in all_candidates if wanted(candidate))
    backlog = tuple(
        candidate
        for candidate in getattr(all_candidates, "deadline_backlog", ())
        if wanted(candidate)
    )
    reservoir_type = type(all_candidates)
    try:
        return reservoir_type(verified, backlog)
    except TypeError:
        return verified + backlog


def continue_result(
    *,
    runtime: Path,
    source: Path,
    source_sha256: str,
    initial_output: Path,
    output: Path,
    seconds: float,
    cpu: int,
    cpus: tuple[int, ...],
    seed: int,
) -> dict[str, Any]:
    base = _load_frozen(runtime)
    if len(cpus) > 1:
        install_parallel(base, cpus)
    source_payload, source_document = base._source_contract(source, source_sha256)
    del source_payload
    result = json.loads((initial_output / "RESULT.json").read_text(encoding="utf-8"))
    search_path = initial_output / "search.json"
    if not search_path.is_file():
        return result
    search = json.loads(search_path.read_text(encoding="utf-8"))
    deadline = time.monotonic() + seconds
    previous_work = search.get("work") if isinstance(search.get("work"), Mapping) else {}
    start_offset = min(256, int(previous_work.get("lanes_started", 0)))
    callbacks_used = min(153600, int(previous_work.get("callbacks", 0)))
    new_endpoint_points: set[tuple[float, ...]] = set()
    if start_offset < 256 and callbacks_used < 153600:
        search_seconds = min(146.0, seconds * 146.0 / 180.0)
        resumed_path = output / "resumed-search.json"
        worker = (
            runtime
            / "solver/research/experiments/EXP-V15-243-001/champion_v0/search_worker.py"
        )
        search_environment = os.environ.copy()
        for name in (
            "OMP_NUM_THREADS",
            "OMP_THREAD_LIMIT",
            "OPENBLAS_NUM_THREADS",
            "MKL_NUM_THREADS",
            "NUMEXPR_NUM_THREADS",
        ):
            search_environment[name] = "1"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "geotarget.resume_search_entrypoint",
                "--worker",
                str(worker),
                "--source",
                str(source),
                "--source-sha256",
                source_sha256,
                "--seconds",
                str(search_seconds),
                "--start-offset",
                str(start_offset),
                "--callbacks-remaining",
                str(153600 - callbacks_used),
                "--seed",
                str(seed),
                "--output",
                str(resumed_path),
            ],
            check=True,
            timeout=search_seconds + 10.0,
            env=search_environment,
        )
        resumed = json.loads(resumed_path.read_text(encoding="utf-8"))
        resumed_endpoints = list(resumed.get("endpoints", ()))
        new_endpoint_points = {
            tuple(float(value) for value in endpoint.get("point", ()))
            for endpoint in resumed_endpoints
            if isinstance(endpoint, Mapping)
        }
        merged_endpoints = list(search.get("endpoints", ())) + resumed_endpoints
        merged_work = dict(previous_work)
        resumed_work = resumed.get("work") if isinstance(resumed.get("work"), Mapping) else {}
        merged_work["lanes_started"] = min(
            256, start_offset + int(resumed_work.get("lanes_started", 0))
        )
        for key in ("callbacks", "finite_callbacks", "invalid_callbacks", "guard_failed_callbacks"):
            merged_work[key] = int(previous_work.get(key, 0)) + int(resumed_work.get(key, 0))
        search = {**search, "endpoints": merged_endpoints, "work": merged_work}
        (output / "search.json").write_text(
            json.dumps(search, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    candidates = _pending_candidates(
        base,
        source_document,
        search,
        result,
        deadline,
        new_endpoints=new_endpoint_points,
    )
    if not candidates:
        result["continuation"] = {
            "schema_version": "geotarget.product-continuation/v1",
            "fixed_work_graph_only": True,
            "new_starts": max(
                0, int(search.get("work", {}).get("lanes_started", 0)) - start_offset
            ),
            "new_seeds": 0,
            "seconds": seconds,
            "cpu": cpu,
            "pending_start_ordinals": list(
                range(int(search.get("work", {}).get("lanes_started", 0)), 256)
            ),
        }
        return result

    attempts, new_descriptors, schedule = base._service_candidates(
        source=source,
        source_sha256=source_sha256,
        candidates=candidates,
        cpu=cpu,
        output=output,
        hard_deadline=deadline,
    )
    descriptors = _existing_descriptors(result)
    for descriptor in new_descriptors.values():
        descriptors.setdefault(_descriptor_key(descriptor), dict(descriptor))
    ordered = [descriptors[key] for key in sorted(descriptors)]
    prior_attempts = result.get("hp_attempts")
    result["hp_attempts"] = (
        list(prior_attempts) if isinstance(prior_attempts, list) else []
    ) + list(attempts)
    result["hp_attempt_count"] = len(result["hp_attempts"])
    result["distinct_exact_targets"] = ordered
    result["distinct_exact_target_descriptors"] = ordered
    result["distinct_exact_target_count"] = len(ordered)
    result["hp_schedule"] = schedule
    result["continuation"] = {
        "schema_version": "geotarget.product-continuation/v1",
        "fixed_work_graph_only": True,
        "new_starts": max(
            0, int(search.get("work", {}).get("lanes_started", 0)) - start_offset
        ),
        "new_seeds": 0,
        "seconds": seconds,
        "cpu": cpu,
        "deferred_record_ids": list(schedule.get("deferred_record_ids", ())),
        "pending_start_ordinals": list(
            range(int(search.get("work", {}).get("lanes_started", 0)), 256)
        ),
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--initial-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=float, required=True)
    parser.add_argument("--cpu", type=int, required=True)
    parser.add_argument("--cpus", required=True)
    parser.add_argument("--seed", type=int, required=True)
    arguments = parser.parse_args()
    cpus = tuple(int(value) for value in arguments.cpus.split(","))
    if (
        not 0 < arguments.seconds <= 180
        or arguments.cpu not in range(16)
        or not cpus
        or cpus[0] != arguments.cpu
        or len(set(cpus)) != len(cpus)
        or any(cpu not in range(16) for cpu in cpus)
    ):
        raise SystemExit("invalid continuation window")
    if sorted(os.sched_getaffinity(0)) != [arguments.cpu]:
        raise SystemExit("continuation must be pinned to its declared CPU")
    arguments.output.mkdir(parents=True, exist_ok=True)
    result = continue_result(
        runtime=arguments.runtime.resolve(),
        source=arguments.source.resolve(),
        source_sha256=arguments.source_sha256,
        initial_output=arguments.initial_output.resolve(),
        output=arguments.output.resolve(),
        seconds=arguments.seconds,
        cpu=arguments.cpu,
        cpus=cpus,
        seed=arguments.seed,
    )
    destination = arguments.output / "RESULT.json"
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, destination)


if __name__ == "__main__":
    main()
