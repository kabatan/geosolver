"""Run one deterministic 64-start extension batch for the optimized champion."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from geotarget.optimized_search import run_parallel_search
from geotarget.parallel import install as install_parallel_hp

ADAPTIVE_BATCH_SIZE = 64
ADAPTIVE_STABILITY_BATCHES = 2
MINIMUM_SAFE_WINDOW_SECONDS = 12.0


def _load_frozen_module(path: Path, name: str) -> Any:
    specification = importlib.util.spec_from_file_location(
        f"geotarget_product_{name}", path
    )
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def _load_frozen(runtime: Path) -> Any:
    entrypoint = (
        runtime
        / "solver/research/experiments/EXP-V15-243-001/repro_20260722/workers"
        / "champion_v2_poc_preloaded.py"
    )
    sys.path.insert(0, str(entrypoint.parent))
    module = _load_frozen_module(entrypoint, "adaptive_frozen")
    return module.CHAMPION.BASE


def extension_batch_end(ordinal_start: int) -> int:
    return ordinal_start + ADAPTIVE_BATCH_SIZE


def has_safe_extension_window(remaining_seconds: float) -> bool:
    return remaining_seconds >= MINIMUM_SAFE_WINDOW_SECONDS


def update_extension_stability(
    *,
    descriptors_before: int,
    descriptors_after: int,
    answer_found: bool,
    consecutive_empty_batches: int,
) -> tuple[bool, int, bool]:
    """Advance the answer-then-empty-batches state without changing policy."""

    if descriptors_after > descriptors_before:
        answer_found = True
        consecutive_empty_batches = 0
    elif answer_found:
        consecutive_empty_batches += 1
    stable = answer_found and consecutive_empty_batches >= ADAPTIVE_STABILITY_BATCHES
    return answer_found, consecutive_empty_batches, stable


def _array_record(value: Any) -> bytes:
    contiguous = value if value.flags.c_contiguous else value.copy(order="C")
    return b"\0".join(
        (
            str(contiguous.dtype).encode("ascii"),
            json.dumps(contiguous.shape, separators=(",", ":")).encode("ascii"),
            contiguous.tobytes(),
        )
    )


def policy_prefix_sha256(policy: Any, count: int) -> str:
    """Hash every proposal field that affects an existing start ordinal."""

    digest = hashlib.sha256()
    for name in ("points", "local_origins", "local_scales"):
        values = getattr(policy, name)
        if len(values) < count:
            raise RuntimeError("proposal policy is shorter than the claimed prefix")
        digest.update(name.encode("ascii") + b"\0")
        for value in values[:count]:
            digest.update(_array_record(value) + b"\0")
    for name in ("sources", "scale_exponents"):
        values = getattr(policy, name)
        if len(values) < count:
            raise RuntimeError("proposal metadata is shorter than the claimed prefix")
        digest.update(name.encode("ascii") + b"\0")
        digest.update(
            json.dumps(
                list(values[:count]),
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        )
    return digest.hexdigest()


def verify_policy_prefix_extension(
    base: Any,
    document: dict[str, Any],
    *,
    source_sha256: str,
    seed: int,
    previous_starts: int,
    extended_starts: int,
) -> str:
    """Fail closed unless increasing starts preserves the complete old prefix."""

    if not 0 < previous_starts < extended_starts:
        raise ValueError("proposal extension bounds are invalid")
    previous = base.materialize_policy(
        document,
        source_sha256=source_sha256,
        starts=previous_starts,
        seed=seed,
    )
    extended = base.materialize_policy(
        document,
        source_sha256=source_sha256,
        starts=extended_starts,
        seed=seed,
    )
    previous_digest = policy_prefix_sha256(previous, previous_starts)
    extended_digest = policy_prefix_sha256(extended, previous_starts)
    if previous_digest != extended_digest:
        raise RuntimeError("adaptive proposal extension changed an existing start ordinal")
    return previous_digest


def _descriptor_key(descriptor: Mapping[str, Any]) -> str:
    return json.dumps(
        [
            descriptor.get("minimal_polynomial_high_to_low"),
            descriptor.get("selected_real_root_index"),
        ],
        separators=(",", ":"),
        sort_keys=True,
    )


def _descriptors(result: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    values = result.get("distinct_exact_target_descriptors") or result.get(
        "distinct_exact_targets"
    )
    found: dict[str, dict[str, Any]] = {}
    if isinstance(values, list):
        for value in values:
            if isinstance(value, Mapping):
                descriptor = dict(value)
                found.setdefault(_descriptor_key(descriptor), descriptor)
    return found


def run_batch(
    *,
    runtime: Path,
    source: Path,
    source_sha256: str,
    initial_output: Path,
    output: Path,
    seconds: float,
    cpus: tuple[int, ...],
    seed: int,
    ordinal_start: int,
    ordinal_end: int,
) -> dict[str, Any]:
    if not 1 <= ordinal_end - ordinal_start <= ADAPTIVE_BATCH_SIZE:
        raise ValueError("an adaptive continuation window must stay within one 64-start batch")
    base = _load_frozen(runtime)
    base.HP_BRIDGE = Path(__file__).with_name("hp_slot_entrypoint.py")
    install_parallel_hp(base, cpus)
    _source_payload, source_document = base._source_contract(source, source_sha256)
    search_worker = _load_frozen_module(Path(base.SEARCH_WORKER), "adaptive_search_worker")
    prefix_sha256 = verify_policy_prefix_extension(
        search_worker.BASE,
        source_document,
        source_sha256=source_sha256,
        seed=seed,
        previous_starts=ordinal_start,
        extended_starts=ordinal_end,
    )
    previous = json.loads((initial_output / "RESULT.json").read_text(encoding="utf-8"))
    before = _descriptors(previous)
    started = time.monotonic()
    deadline = started + seconds
    search_seconds = min(146.0, max(1.0, seconds * 146.0 / 180.0))
    search_status, search = run_parallel_search(
        base=base,
        cpus=cpus,
        source=source,
        source_sha256=source_sha256,
        search_seconds=search_seconds,
        starts=ordinal_end,
        callbacks_per_start=600,
        aggregate_callback_cap=(ordinal_end - ordinal_start) * 600,
        seed=seed,
        output=output,
        ordinal_start=ordinal_start,
        ordinal_end=ordinal_end,
    )
    endpoints = search.get("endpoints", ()) if isinstance(search, Mapping) else ()
    candidates = base._fresh_replay_candidates(
        source_document,
        endpoints if isinstance(endpoints, list) else (),
        hard_deadline=min(
            deadline - base.FINALIZE_RESERVE_SECONDS,
            time.monotonic() + base.SELECTION_RESERVE_SECONDS,
        ),
    )
    if candidates and time.monotonic() < deadline - base.FINALIZE_RESERVE_SECONDS:
        attempts, new_descriptors, schedule = base._service_candidates(
            source=source,
            source_sha256=source_sha256,
            candidates=candidates,
            cpu=cpus[0],
            output=output / "adaptive-hp",
            hard_deadline=deadline,
        )
    else:
        attempts, new_descriptors, schedule = [], {}, {
            "deferred_record_ids": [
                str(getattr(candidate, "record_id", "")) for candidate in candidates
            ]
        }
    combined = dict(before)
    for descriptor in new_descriptors.values():
        combined.setdefault(_descriptor_key(descriptor), dict(descriptor))
    ordered = [combined[key] for key in sorted(combined)]
    prior_attempts = previous.get("hp_attempts")
    result = {
        **previous,
        "status": "SEARCH_DEADLINE_REACHED",
        "hp_attempts": (
            list(prior_attempts) if isinstance(prior_attempts, list) else []
        )
        + list(attempts),
        "distinct_exact_targets": ordered,
        "distinct_exact_target_descriptors": ordered,
        "distinct_exact_target_count": len(ordered),
        "hp_schedule": schedule,
        "adaptive_extension": {
            "schema_version": "geotarget.adaptive-extension/v1",
            "ordinal_start": ordinal_start,
            "ordinal_end": ordinal_end,
            "starts_completed": int(
                search.get("work", {}).get("lanes_started", 0)
                if isinstance(search, Mapping)
                else 0
            ),
            "new_descriptor_count": len(combined) - len(before),
            "descriptor_count": len(combined),
            "search_classification": search_status.classification,
            "search_failed_shards": [list(value) for value in search_status.failed_shards],
            "seconds": seconds,
            "elapsed_seconds": time.monotonic() - started,
            "parallel_physical_cpus": list(cpus),
            "proposal_prefix_extended_only": True,
            "preserved_proposal_prefix_sha256": prefix_sha256,
            "callbacks_per_start": 600,
            "completeness_claim": False,
        },
    }
    result["hp_attempt_count"] = len(result["hp_attempts"])
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--initial-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=float, required=True)
    parser.add_argument("--cpus", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--ordinal-start", type=int, required=True)
    parser.add_argument("--ordinal-end", type=int, required=True)
    arguments = parser.parse_args()
    cpus = tuple(int(value) for value in arguments.cpus.split(","))
    if (
        not 12.0 <= arguments.seconds <= 180.0
        or not cpus
        or len(set(cpus)) != len(cpus)
        or any(cpu not in range(16) for cpu in cpus)
    ):
        raise SystemExit("invalid adaptive continuation resources")
    arguments.output.mkdir(parents=True, exist_ok=True)
    result = run_batch(
        runtime=arguments.runtime.resolve(),
        source=arguments.source.resolve(),
        source_sha256=arguments.source_sha256,
        initial_output=arguments.initial_output.resolve(),
        output=arguments.output.resolve(),
        seconds=arguments.seconds,
        cpus=cpus,
        seed=arguments.seed,
        ordinal_start=arguments.ordinal_start,
        ordinal_end=arguments.ordinal_end,
    )
    destination = arguments.output / "RESULT.json"
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(destination)


if __name__ == "__main__":
    main()
