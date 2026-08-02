#!/usr/bin/env python3
"""Thin 180-second strict-restart direct-Broyden -> numerical-v3 worker v15.

The worker receives only an untouched solve JSON, its digest, a seed, and a
wall budget.  Discovery is delegated to the frozen
accepted-semantic-invalid-retained direct-Broyden corrective with its one
general near-root strict restart.  Semantic-safe endpoints are replayed by the
same original-source evaluator.  Each provisional scalar target cluster keeps
one residual-best endpoint and one configuration-diverse alternate.  HP work
is scheduled breadth-first over a finite anonymous primary tranche selected by
residual quality and soft target/configuration diversity.  Every selected
primary is attempted before any alternate, and every eligible alternate is
attempted before the existing bounded restoration wave.  Primaries outside
the finite wall-feasible tranche remain explicitly deferred/unknown.

Default operation is a dry run.  Execution requires ``--execute`` and the
SHA-256 of the exact dry plan.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import struct
import sys
import time
from typing import Mapping, Sequence


PROCESS_STARTED = time.monotonic()
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PYTHON = ROOT / "python/.venv/bin/python"
SEARCH_ROOT = (
    HERE.parent
    / "hybrid_direct_broyden_tr_lm_v9/corrective_nearroot_strict_restart_v2"
)
SEARCH_WORKER = SEARCH_ROOT / "worker.py"
SEARCH_ADAPTER = SEARCH_ROOT / "adapter.py"
SEARCH_CANDIDATE = SEARCH_ROOT / "candidate.py"
HP_BRIDGE = HERE.parent / "hp_precision_schedule_v11/bridge.py"
PRECISION_RUNTIME = HERE.parent / "ad_inverse_broyden/precision_runtime.py"
RESTORATION_ROOT = HERE.parent / "roweq180_hp_restoration_integration_v1"
RESTORATION_WORKER = RESTORATION_ROOT / "worker.py"
RESTORATION_ADAPTER = RESTORATION_ROOT / "adapter.py"
RESTORATION_CANDIDATE = HERE.parent / "hp_failure_restoration_rescue_v6/candidate.py"
GLOBAL_HP_LOCK = Path("/tmp/geotarget-one-heavy-hp-process-v1.lock")
SEARCH_ARM = (
    "precision_isolated_retained_then_strict_nearroot_restart_"
    "direct_broyden_ruiz_tr_lm"
)
EXPECTED_SEARCH_CANDIDATE_SHA256 = (
    "d2904af6e1f0f0dbc8432dfb2adf3039e28c502131df45ffdd3bfde42f7acafc"
)

EXPECTED_RESTORATION_WORKER_SHA256 = (
    "3afcaf0b6ce3f363eb7c7f8c9396e20b3a797b31b4a0dc77f225c1f437fbcf5b"
)
EXPECTED_RESTORATION_ADAPTER_SHA256 = (
    "d2190d86cf8ab4c6af3e9ed9623daf81a6549d98430d69304689a8fded262ead"
)
EXPECTED_RESTORATION_CANDIDATE_SHA256 = (
    "00788a8b9dfc46edf20c86d456287c87a86828c4ddfdd18793ce831a96814b00"
)

SCHEMA = "geotarget.exp008-finalist-numeric-worker-v15/v1"
DEFAULT_TOTAL_SECONDS = 180.0
DEFAULT_SEARCH_SECONDS = 146.0
DEFAULT_STARTS = 256
DEFAULT_CALLBACKS_PER_START = 600
DEFAULT_AGGREGATE_CALLBACK_CAP = DEFAULT_STARTS * DEFAULT_CALLBACKS_PER_START
FINALIZE_RESERVE_SECONDS = 2.0
SELECTION_RESERVE_SECONDS = 1.0
MIN_HP_ATTEMPT_SECONDS = 3.0
MAX_HP_ATTEMPT_SECONDS = 18.0
MAX_CANDIDATES_PER_PROVISIONAL_CLUSTER = 2
MAX_RESTORATION_ATTEMPT_SECONDS = 12.0
RESTORATION_CALLBACK_CAP = 600
CLUSTER_RELATIVE_TOLERANCE = 1.0e-8
CLUSTER_ABSOLUTE_TOLERANCE = 1.0e-8
REPLAY_PRECISION_DIGITS = 80

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
    "GEOTARGET_GLOBAL_RSS_RESERVATION_BYTES": str(8 * 1024**3),
}


@dataclass(frozen=True)
class ReplayCandidate:
    endpoint: tuple[float, ...]
    endpoint_sha256: str
    residual_inf: float
    provisional_target: float
    cluster_ordinal: int = 0
    cluster_rank: int = 0


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _endpoint_sha256(endpoint: Sequence[float]) -> str:
    values = tuple(float(value) for value in endpoint)
    payload = struct.pack(">I", len(values)) + b"".join(
        struct.pack(">d", value) for value in values
    )
    return _sha256(payload)


def _load_module(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _source_contract(source: Path, expected_sha256: str) -> tuple[bytes, dict[str, object]]:
    payload = source.read_bytes()
    if _sha256(payload) != expected_sha256:
        raise ValueError("source SHA-256 mismatch")
    document = json.loads(payload)
    names = document.get("variables", {}).get("names") if isinstance(document, Mapping) else None
    if (
        not isinstance(document, dict)
        or document.get("task") != "solve"
        or not isinstance(names, list)
    ):
        raise ValueError("untouched solve JSON with variables.names is required")
    return payload, document


def _configuration_distance(left: ReplayCandidate, right: ReplayCandidate) -> float:
    if len(left.endpoint) != len(right.endpoint):
        return math.inf
    difference = math.sqrt(
        sum((a - b) * (a - b) for a, b in zip(left.endpoint, right.endpoint, strict=True))
    )
    denominator = math.sqrt(sum(value * value for value in left.endpoint)) + math.sqrt(
        sum(value * value for value in right.endpoint)
    )
    if denominator == 0.0:
        return 0.0 if difference == 0.0 else math.inf
    return difference / denominator


def _near_configuration_duplicate(
    candidate: ReplayCandidate, accepted: ReplayCandidate
) -> bool:
    """Residual-scaled soft duplicate predicate; never an answer authority."""

    if len(candidate.endpoint) != len(accepted.endpoint):
        return False
    machine_epsilon = math.ulp(1.0)
    candidate_uncertainty = math.sqrt(max(candidate.residual_inf, machine_epsilon))
    accepted_uncertainty = math.sqrt(max(accepted.residual_inf, machine_epsilon))
    configuration_near = _configuration_distance(candidate, accepted) <= (
        candidate_uncertainty + accepted_uncertainty
    )
    target_scale = max(
        abs(candidate.provisional_target),
        abs(accepted.provisional_target),
        1.0,
    )
    target_near = abs(candidate.provisional_target - accepted.provisional_target) <= (
        target_scale * (candidate_uncertainty + accepted_uncertainty)
        + math.ulp(candidate.provisional_target)
        + math.ulp(accepted.provisional_target)
    )
    return configuration_near and target_near


def _cluster_and_select(candidates: Sequence[ReplayCandidate]) -> tuple[ReplayCandidate, ...]:
    """Keep residual-best plus one configuration-diverse endpoint per cluster."""

    clusters: list[tuple[float, list[ReplayCandidate]]] = []
    for candidate in sorted(
        candidates,
        key=lambda item: (item.provisional_target, item.residual_inf, item.endpoint_sha256),
    ):
        for representative, members in clusters:
            if math.isclose(
                candidate.provisional_target,
                representative,
                rel_tol=CLUSTER_RELATIVE_TOLERANCE,
                abs_tol=CLUSTER_ABSOLUTE_TOLERANCE,
            ):
                members.append(candidate)
                break
        else:
            clusters.append((candidate.provisional_target, [candidate]))
    selected_groups: list[tuple[ReplayCandidate, ReplayCandidate | None]] = []
    for cluster_ordinal, (_target, members) in enumerate(clusters):
        unique_by_sha: dict[str, ReplayCandidate] = {}
        for member in members:
            prior = unique_by_sha.get(member.endpoint_sha256)
            if prior is None or (member.residual_inf, member.endpoint_sha256) < (
                prior.residual_inf,
                prior.endpoint_sha256,
            ):
                unique_by_sha[member.endpoint_sha256] = member
        unique = tuple(unique_by_sha.values())
        primary_source = min(
            unique, key=lambda item: (item.residual_inf, item.endpoint_sha256)
        )
        primary = ReplayCandidate(
            endpoint=primary_source.endpoint,
            endpoint_sha256=primary_source.endpoint_sha256,
            residual_inf=primary_source.residual_inf,
            provisional_target=primary_source.provisional_target,
            cluster_ordinal=cluster_ordinal,
            cluster_rank=0,
        )
        alternate = None
        remaining = [item for item in unique if item.endpoint_sha256 != primary.endpoint_sha256]
        if remaining:
            configuration_diverse = [
                item
                for item in remaining
                if not _near_configuration_duplicate(item, primary)
            ]
            if configuration_diverse:
                # Among genuinely distinct configurations, residual is the
                # best empirical predictor of HP conversion.
                alternate_source = min(
                    configuration_diverse,
                    key=lambda item: (item.residual_inf, item.endpoint_sha256),
                )
            else:
                # If all endpoints are locally indistinguishable, retain the
                # most distant one as failure robustness without adding a
                # problem-specific separation threshold.
                alternate_source = min(
                    remaining,
                    key=lambda item: (
                        -_configuration_distance(primary, item),
                        item.residual_inf,
                        item.endpoint_sha256,
                    ),
                )
            alternate = ReplayCandidate(
                endpoint=alternate_source.endpoint,
                endpoint_sha256=alternate_source.endpoint_sha256,
                residual_inf=alternate_source.residual_inf,
                provisional_target=alternate_source.provisional_target,
                cluster_ordinal=cluster_ordinal,
                cluster_rank=1,
            )
        selected_groups.append((primary, alternate))

    # Residual-best primaries own the order; their diverse alternate follows
    # immediately.  Identity, truth, known target count, and benchmark outcome
    # are unavailable.
    selected_groups.sort(
        key=lambda pair: (pair[0].residual_inf, pair[0].endpoint_sha256)
    )
    return tuple(
        candidate
        for primary, alternate in selected_groups
        for candidate in (primary, alternate)
        if candidate is not None
    )


def _fresh_replay_candidates(
    document: dict[str, object], endpoints: Sequence[object], *, hard_deadline: float
) -> tuple[ReplayCandidate, ...]:
    runtime = _load_module(
        "geotarget_exp008_finalist_v15_precision_runtime", PRECISION_RUNTIME
    )
    _case, _budget, evaluator = runtime.build_source_case(
        document,
        callback_cap=max(1, len(endpoints)),
        deadline=max(time.monotonic() + 0.01, hard_deadline),
    )
    candidates: list[ReplayCandidate] = []
    for row in endpoints:
        if time.monotonic() >= hard_deadline:
            break
        if not isinstance(row, Mapping) or not isinstance(row.get("point"), list):
            continue
        try:
            endpoint = tuple(float(value) for value in row["point"])
        except (TypeError, ValueError, OverflowError):
            continue
        if not all(math.isfinite(value) for value in endpoint):
            continue
        replay = runtime.replay_endpoint(
            evaluator, endpoint, precision=REPLAY_PRECISION_DIGITS
        )
        if replay.get("safe") is not True:
            continue
        try:
            residual = float(replay.get("residual_inf"))
            target = float(str(replay.get("diagnostic_target")))
        except (TypeError, ValueError, OverflowError):
            continue
        if not (math.isfinite(residual) and math.isfinite(target)):
            continue
        candidates.append(
            ReplayCandidate(
                endpoint=endpoint,
                endpoint_sha256=_endpoint_sha256(endpoint),
                residual_inf=residual,
                provisional_target=target,
            )
        )
    return _cluster_and_select(candidates)


def _has_retained_alternate(
    candidate: ReplayCandidate,
    candidates: Sequence[ReplayCandidate],
    ordinal: int,
) -> bool:
    return any(
        later.cluster_ordinal == candidate.cluster_ordinal
        and later.cluster_rank == 1
        for later in candidates[ordinal + 1 :]
    )


def _same_cluster_authority_exists(
    candidate: ReplayCandidate, successful_cluster_ordinals: set[int]
) -> bool:
    """Only a successful endpoint's own provisional cluster may be skipped."""

    return candidate.cluster_ordinal in successful_cluster_ordinals


def _wave_attempt_seconds(
    remaining_seconds: float,
    unserved_including_current: int,
    maximum_seconds: float,
) -> float:
    """Cap one attempt while reserving the minimum for the rest of its wave."""

    if unserved_including_current < 1:
        raise ValueError("wave must contain the current attempt")
    if maximum_seconds < MIN_HP_ATTEMPT_SECONDS:
        raise ValueError("wave maximum must admit a minimum HP attempt")
    reserve = MIN_HP_ATTEMPT_SECONDS * (unserved_including_current - 1)
    admitted = min(maximum_seconds, remaining_seconds - reserve)
    if admitted < MIN_HP_ATTEMPT_SECONDS:
        return 0.0
    return admitted


def _primary_tranche_capacity(
    remaining_seconds: float, primary_count: int
) -> int:
    """Fit one meaningful primary plus minimum-time diversity attempts."""

    if primary_count < 0:
        raise ValueError("primary count cannot be negative")
    if primary_count == 0 or remaining_seconds < MIN_HP_ATTEMPT_SECONDS:
        return 0
    if remaining_seconds < MAX_HP_ATTEMPT_SECONDS:
        return 1
    diversity_slots = math.floor(
        (remaining_seconds - MAX_HP_ATTEMPT_SECONDS)
        / MIN_HP_ATTEMPT_SECONDS
    )
    return min(primary_count, 1 + max(0, diversity_slots))


def _normalized_target_distance(
    left: ReplayCandidate, right: ReplayCandidate
) -> float:
    scale = max(
        abs(left.provisional_target),
        abs(right.provisional_target),
        1.0,
    )
    return abs(left.provisional_target - right.provisional_target) / scale


def _unit_range(values: Mapping[int, float]) -> dict[int, float]:
    if not values:
        return {}
    low = min(values.values())
    high = max(values.values())
    if not (math.isfinite(low) and math.isfinite(high)) or high <= low:
        return {key: 0.0 for key in values}
    return {key: (value - low) / (high - low) for key, value in values.items()}


def _select_primary_tranche(
    primaries: Sequence[tuple[int, ReplayCandidate]], capacity: int
) -> tuple[
    tuple[tuple[int, ReplayCandidate], ...],
    tuple[tuple[int, ReplayCandidate], ...],
]:
    """Select a residual-led, softly diverse tranche without identity inputs."""

    ordered = tuple(primaries)
    if capacity < 0:
        raise ValueError("primary tranche capacity cannot be negative")
    if capacity == 0:
        return (), ordered
    if len(ordered) <= capacity:
        return ordered, ()

    residual_order = sorted(
        ordered,
        key=lambda item: (
            item[1].residual_inf,
            item[1].endpoint_sha256,
        ),
    )
    denominator = max(1, len(residual_order) - 1)
    residual_quality = {
        ordinal: 1.0 - rank / denominator
        for rank, (ordinal, _candidate) in enumerate(residual_order)
    }
    selected = [residual_order[0]]
    remaining = {ordinal: candidate for ordinal, candidate in ordered}
    remaining.pop(selected[0][0])

    while len(selected) < capacity and remaining:
        target_novelty = {
            ordinal: min(
                _normalized_target_distance(candidate, chosen)
                for _chosen_ordinal, chosen in selected
            )
            for ordinal, candidate in remaining.items()
        }
        configuration_novelty = {
            ordinal: min(
                _configuration_distance(candidate, chosen)
                for _chosen_ordinal, chosen in selected
            )
            for ordinal, candidate in remaining.items()
        }
        target_score = _unit_range(target_novelty)
        configuration_score = _unit_range(configuration_novelty)

        # Residual remains the strongest signal.  Novelty terms are soft and
        # scale-free, so they can diversify the finite tranche without
        # suppressing a strong endpoint or asserting target identity.
        def priority(item: tuple[int, ReplayCandidate]) -> tuple[object, ...]:
            ordinal, candidate = item
            score = (
                0.5 * residual_quality[ordinal]
                + 0.25 * target_score[ordinal]
                + 0.25 * configuration_score[ordinal]
            )
            return (
                -score,
                -residual_quality[ordinal],
                -target_score[ordinal],
                -configuration_score[ordinal],
                candidate.residual_inf,
                candidate.endpoint_sha256,
            )

        chosen = min(remaining.items(), key=priority)
        selected.append(chosen)
        remaining.pop(chosen[0])

    selected_ordinals = {ordinal for ordinal, _candidate in selected}
    deferred = tuple(
        item for item in ordered if item[0] not in selected_ordinals
    )
    return tuple(selected), deferred


def _authority_descriptor(authority: object) -> dict[str, object] | None:
    if not isinstance(authority, Mapping) or authority.get("authority_pass") is not True:
        return None
    final = authority.get("final_result")
    if not isinstance(final, Mapping) or final.get("authority_pass") is not True:
        return None
    scope = final.get("authority_scope")
    target = final.get("target_authority")
    if not isinstance(scope, Mapping) or not isinstance(target, Mapping):
        return None
    required_scope = (
        "numerical_configuration_512_768",
        "target_512_768_1024",
        "original_dsl_hp_replay",
        "target_only_owned_pslq",
        "minimal_polynomial_and_isolator",
    )
    if any(scope.get(field) is not True for field in required_scope):
        return None
    polynomial = target.get("minimal_polynomial_high_to_low")
    root_index = target.get("selected_real_root_index")
    isolator = target.get("isolating_interval")
    if (
        target.get("target_relation_confirmed") is not True
        or not isinstance(polynomial, list)
        or not polynomial
        or not isinstance(root_index, int)
        or not isinstance(isolator, Mapping)
    ):
        return None
    return {
        "minimal_polynomial_high_to_low": polynomial,
        "selected_real_root_index": root_index,
        "isolating_interval": dict(isolator),
        "proposal_relation_low_to_high": target.get("proposal_relation_low_to_high"),
        "confirmation_relation_low_to_high": target.get(
            "confirmation_relation_low_to_high"
        ),
        "target_512": target.get("target_512"),
        "target_768": target.get("target_768"),
        "target_1024": target.get("target_1024"),
    }


def _descriptor_key(descriptor: Mapping[str, object]) -> str:
    payload = {
        "minimal_polynomial_high_to_low": descriptor.get(
            "minimal_polynomial_high_to_low"
        ),
        "selected_real_root_index": descriptor.get("selected_real_root_index"),
    }
    return _sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )


def _plan(
    *,
    source: Path,
    source_sha256: str,
    total_seconds: float,
    search_seconds: float,
    starts: int,
    callbacks_per_start: int,
    aggregate_callback_cap: int,
    seed: int,
    cpu: int,
    output: Path,
) -> dict[str, object]:
    return {
        "schema_version": "geotarget.exp008-finalist-numeric-plan-v15/v1",
        "status": "DRY_RUN_NOT_STARTED",
        "source_path": str(source.resolve()),
        "source_sha256": source_sha256,
        "total_seconds": total_seconds,
        "search_seconds": search_seconds,
        "selection_reserve_seconds": SELECTION_RESERVE_SECONDS,
        "hp_and_finalization_seconds": total_seconds - search_seconds,
        "finalize_reserve_seconds": FINALIZE_RESERVE_SECONDS,
        "starts": starts,
        "callbacks_per_start": callbacks_per_start,
        "aggregate_callback_cap": aggregate_callback_cap,
        "seed": seed,
        "cpu": cpu,
        "output": str(output.resolve()),
        "search_arm": SEARCH_ARM,
        "integrated_worker_sha256": _sha256(Path(__file__).read_bytes()),
        "search_worker_sha256": _sha256(SEARCH_WORKER.read_bytes()),
        "search_adapter_sha256": _sha256(SEARCH_ADAPTER.read_bytes()),
        "search_candidate_sha256": _sha256(SEARCH_CANDIDATE.read_bytes()),
        "expected_search_candidate_sha256": EXPECTED_SEARCH_CANDIDATE_SHA256,
        "precision_runtime_sha256": _sha256(PRECISION_RUNTIME.read_bytes()),
        "hp_bridge_sha256": _sha256(HP_BRIDGE.read_bytes()),
        "restoration_worker_sha256": _sha256(RESTORATION_WORKER.read_bytes()),
        "expected_restoration_worker_sha256": EXPECTED_RESTORATION_WORKER_SHA256,
        "restoration_adapter_sha256": _sha256(RESTORATION_ADAPTER.read_bytes()),
        "expected_restoration_adapter_sha256": EXPECTED_RESTORATION_ADAPTER_SHA256,
        "restoration_candidate_sha256": _sha256(RESTORATION_CANDIDATE.read_bytes()),
        "expected_restoration_candidate_sha256": EXPECTED_RESTORATION_CANDIDATE_SHA256,
        "candidate_selection": (
            "residual-best plus one scale-normalized configuration-diverse alternate "
            "per provisional target cluster"
        ),
        "hp_allocation": (
            "anonymous finite residual-plus-soft-novelty primary tranche; then "
            "failed-cluster alternates and restoration breadth-first; each wave "
            "attempt reserves the minimum for every selected unserved member"
        ),
        "unselected_primary_disposition": "DEFERRED_UNKNOWN_NOT_DISCARDED",
        "post_hp_failure_lane": (
            "bounded existing hp_failure_restoration_rescue_v6; leftover-only"
        ),
        "cross_cluster_candidate_suppression": False,
        "final_target_deduplication": (
            "exact minimal polynomial plus selected real-root index only"
        ),
        "proposal_policy": "frozen literal-prefix full-support policy",
        "permanent_iid_insurance": "counter-product Cauchy every fourth proposal",
        "truth_case_family_known_target_count_read": False,
        "source_or_problem_modified": False,
        "variables_or_equations_removed": False,
        "bounds_added_or_inferred": False,
        "gauge_or_symmetry_reduction": False,
        "coordinate_reparameterization": False,
        "hp_children_started": 0,
    }


def _run_search(
    *,
    source: Path,
    source_sha256: str,
    search_seconds: float,
    starts: int,
    callbacks_per_start: int,
    aggregate_callback_cap: int,
    seed: int,
    output: Path,
):
    artifact = output / "search.json"
    status = output / "search-process-status.json"
    artifact.unlink(missing_ok=True)
    command = [
        str(PYTHON),
        str(SEARCH_WORKER),
        "--case",
        str(source.resolve()),
        "--case-sha256",
        source_sha256,
        "--arm",
        SEARCH_ARM,
        "--seconds",
        str(search_seconds),
        "--starts",
        str(starts),
        "--callbacks-per-start",
        str(callbacks_per_start),
        "--aggregate-callback-cap",
        str(aggregate_callback_cap),
        "--seed",
        str(seed),
        "--output",
        str(artifact),
    ]
    guarded = run_guarded(
        command,
        limits=Limits(
            timeout_seconds=search_seconds + 4.0,
            rss_bytes=768 * 1024**2,
            address_space_bytes=3072 * 1024**2,
            data_bytes=2048 * 1024**2,
            output_bytes=1024**2,
            tail_bytes=16 * 1024,
        ),
        environment=THREAD_ENVIRONMENT,
        cwd=ROOT,
        status_path=status,
    )
    document = None
    if guarded.accepted_output and artifact.is_file():
        try:
            candidate = json.loads(artifact.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            candidate = None
        if (
            isinstance(candidate, Mapping)
            and candidate.get("completed") is True
            and candidate.get("arm") == SEARCH_ARM
            and candidate.get("source_sha256") == source_sha256
            and candidate.get("source_bytes_unchanged") is True
            and candidate.get("source_semantics_modified") is False
            and candidate.get("all_source_variables_and_equations_retained") is True
            and candidate.get("explicit_source_bounds_only") is True
            and candidate.get("added_or_inferred_search_bounds") is False
            and candidate.get("gauge_or_symmetry_reduction") is False
            and candidate.get(
                "candidate_received_case_id_family_truth_or_target_count"
            )
            is False
            and candidate.get("truth_used") is False
            and candidate.get("completeness_claim") is False
        ):
            document = candidate
    return guarded, document


def _bridge_command(
    *,
    source: Path,
    source_sha256: str,
    candidate: ReplayCandidate,
    cpu: int,
    output: Path,
    deadline_seconds: float,
    primary_cap_seconds: float,
    process_timeout_seconds: float,
    execute: bool,
    plan_sha256: str | None = None,
) -> list[str]:
    command = [
        str(PYTHON),
        str(HP_BRIDGE),
        "--source",
        str(source.resolve()),
        "--source-sha256",
        source_sha256,
        "--endpoint",
        json.dumps(candidate.endpoint, separators=(",", ":"), allow_nan=False),
        "--endpoint-sha256",
        candidate.endpoint_sha256,
        "--cpu",
        str(cpu),
        "--deadline-seconds",
        str(deadline_seconds),
        "--primary-cap-seconds",
        str(primary_cap_seconds),
        "--process-timeout-seconds",
        str(process_timeout_seconds),
        "--output",
        str(output),
    ]
    if execute:
        command.extend(("--execute", "--plan-sha256", str(plan_sha256)))
    return command


def _run_hp_candidate(
    *,
    source: Path,
    source_sha256: str,
    candidate: ReplayCandidate,
    cpu: int,
    output: Path,
    timeout_seconds: float,
) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    # The inner bridge owns and kills its HP child before the outer guard can
    # expire.  This gap prevents a nested child from surviving an outer timeout.
    deadline_seconds = max(0.1, timeout_seconds - 1.75)
    # The first finalist comparison runs only the reviewed two-prefix/four-stage
    # primary.  With the optional six-stage fallback disabled, the primary owns
    # the complete admitted HP interval.
    primary_cap_seconds = deadline_seconds
    process_timeout_seconds = max(deadline_seconds + 0.25, timeout_seconds - 1.0)
    dry_status = output / "dry-process-status.json"
    dry = run_guarded(
        _bridge_command(
            source=source,
            source_sha256=source_sha256,
            candidate=candidate,
            cpu=cpu,
            output=output,
            deadline_seconds=deadline_seconds,
            primary_cap_seconds=primary_cap_seconds,
            process_timeout_seconds=process_timeout_seconds,
            execute=False,
        ),
        limits=Limits(
            timeout_seconds=min(5.0, max(0.5, timeout_seconds)),
            rss_bytes=256 * 1024**2,
            address_space_bytes=1024 * 1024**2,
            data_bytes=768 * 1024**2,
            output_bytes=256 * 1024,
            tail_bytes=8 * 1024,
        ),
        environment=THREAD_ENVIRONMENT,
        cwd=ROOT,
        status_path=dry_status,
    )
    plan_path = output / "PLAN.json"
    if not dry.accepted_output or not plan_path.is_file():
        return {
            "endpoint_float64_sha256": candidate.endpoint_sha256,
            "status": "HP_DRY_FAILED",
            "authority_pass": False,
            "process": dry.to_dict(),
        }
    plan_sha256 = _sha256(plan_path.read_bytes())
    remaining_timeout = max(0.25, timeout_seconds - dry.elapsed_seconds)
    execute_status = output / "execute-process-status.json"
    executed = run_guarded(
        _bridge_command(
            source=source,
            source_sha256=source_sha256,
            candidate=candidate,
            cpu=cpu,
            output=output,
            deadline_seconds=deadline_seconds,
            primary_cap_seconds=primary_cap_seconds,
            process_timeout_seconds=process_timeout_seconds,
            execute=True,
            plan_sha256=plan_sha256,
        ),
        limits=Limits(
            timeout_seconds=remaining_timeout,
            rss_bytes=768 * 1024**2,
            address_space_bytes=3072 * 1024**2,
            data_bytes=2048 * 1024**2,
            output_bytes=1024**2,
            tail_bytes=16 * 1024,
        ),
        environment=THREAD_ENVIRONMENT,
        cwd=ROOT,
        status_path=execute_status,
    )
    bridge_result = None
    authority = None
    try:
        bridge_result = json.loads((output / "RESULT.json").read_text(encoding="utf-8"))
        authority = json.loads((output / "authority.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    descriptor = _authority_descriptor(authority)
    accepted = bool(
        executed.accepted_output
        and isinstance(bridge_result, Mapping)
        and bridge_result.get("artifact_accepted") is True
        and bridge_result.get("authority_pass") is True
        and bridge_result.get("source_sha256") == source_sha256
        and bridge_result.get("endpoint_float64_sha256") == candidate.endpoint_sha256
        and descriptor is not None
    )
    return {
        "attempt_kind": "PRIMARY_NUMERICAL_V3",
        "endpoint_float64_sha256": candidate.endpoint_sha256,
        "residual_inf": candidate.residual_inf,
        "provisional_target": candidate.provisional_target,
        "cluster_ordinal": candidate.cluster_ordinal,
        "cluster_rank": candidate.cluster_rank,
        "status": "TARGET_AUTHORITY_READY" if accepted else "NO_TARGET_AUTHORITY",
        "authority_pass": accepted,
        "descriptor": descriptor if accepted else None,
        "bridge_result_sha256": (
            _sha256((output / "RESULT.json").read_bytes())
            if (output / "RESULT.json").is_file()
            else None
        ),
        "authority_sha256": (
            _sha256((output / "authority.json").read_bytes())
            if (output / "authority.json").is_file()
            else None
        ),
        "process": executed.to_dict(),
    }


def _run_restoration_candidate(
    *,
    source: Path,
    source_sha256: str,
    candidate: ReplayCandidate,
    cpu: int,
    failed_authority_artifact: Path,
    output: Path,
    timeout_seconds: float,
) -> dict[str, object]:
    """Run the frozen failure-only restoration/HP seam on leftover wall."""

    result_path = output / "RESULT.json"
    output.mkdir(parents=True, exist_ok=True)
    if not failed_authority_artifact.is_file():
        return {
            "attempt_kind": "HP_FAILURE_RESTORATION",
            "endpoint_float64_sha256": candidate.endpoint_sha256,
            "status": "FAILED_AUTHORITY_ARTIFACT_UNAVAILABLE",
            "authority_pass": False,
            "descriptor": None,
        }
    admitted_seconds = min(
        MAX_RESTORATION_ATTEMPT_SECONDS,
        max(0.1, timeout_seconds - 0.75),
    )
    command = [
        "flock",
        "-x",
        str(GLOBAL_HP_LOCK),
        "taskset",
        "-c",
        str(cpu),
        str(PYTHON),
        str(RESTORATION_WORKER),
        "--source",
        str(source.resolve()),
        "--source-sha256",
        source_sha256,
        "--endpoint",
        json.dumps(candidate.endpoint, separators=(",", ":"), allow_nan=False),
        "--endpoint-sha256",
        candidate.endpoint_sha256,
        "--authority-artifact",
        str(failed_authority_artifact.resolve()),
        "--leftover-seconds",
        str(admitted_seconds),
        "--leftover-callbacks",
        str(RESTORATION_CALLBACK_CAP),
        "--output",
        str(result_path.resolve()),
    ]
    guarded = run_guarded(
        command,
        limits=Limits(
            timeout_seconds=max(0.25, timeout_seconds),
            rss_bytes=768 * 1024**2,
            address_space_bytes=3072 * 1024**2,
            data_bytes=2048 * 1024**2,
            output_bytes=1024**2,
            tail_bytes=16 * 1024,
        ),
        environment=THREAD_ENVIRONMENT,
        cwd=ROOT,
        status_path=output / "process-status.json",
    )
    document = None
    try:
        document = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    contract = document.get("problem_contract") if isinstance(document, Mapping) else None
    restored_authority = (
        document.get("restored_authority") if isinstance(document, Mapping) else None
    )
    descriptor = _authority_descriptor(restored_authority)
    accepted = bool(
        guarded.accepted_output
        and isinstance(document, Mapping)
        and document.get("schema_version")
        == "geotarget.exp008-roweq180-hp-restoration-composition/v1"
        and document.get("authority_pass") is True
        and isinstance(contract, Mapping)
        and all(
            contract.get(field) is False
            for field in (
                "source_or_problem_modified",
                "variables_or_equations_changed",
                "bounds_added_or_inferred",
                "gauge_or_symmetry_reduction",
                "coordinate_reparameterization",
                "case_family_source_series_truth_target_count_routing",
            )
        )
        and descriptor is not None
    )
    trigger = document.get("trigger") if isinstance(document, Mapping) else None
    return {
        "attempt_kind": "HP_FAILURE_RESTORATION",
        "endpoint_float64_sha256": candidate.endpoint_sha256,
        "residual_inf": candidate.residual_inf,
        "provisional_target": candidate.provisional_target,
        "cluster_ordinal": candidate.cluster_ordinal,
        "cluster_rank": candidate.cluster_rank,
        "status": "TARGET_AUTHORITY_READY" if accepted else (
            document.get("status") if isinstance(document, Mapping) else "NO_RESTORED_AUTHORITY"
        ),
        "trigger": dict(trigger) if isinstance(trigger, Mapping) else None,
        "authority_pass": accepted,
        "descriptor": descriptor if accepted else None,
        "result_sha256": _sha256(result_path.read_bytes()) if result_path.is_file() else None,
        "process": guarded.to_dict(),
    }


def _service_candidates(
    *,
    source: Path,
    source_sha256: str,
    candidates: Sequence[ReplayCandidate],
    cpu: int,
    output: Path,
    hard_deadline: float,
) -> tuple[
    list[dict[str, object]],
    dict[str, dict[str, object]],
    dict[str, object],
]:
    """Run primary, alternate, and restoration waves under one deadline."""

    indexed = tuple(enumerate(candidates))
    all_primaries = tuple(
        (ordinal, candidate)
        for ordinal, candidate in indexed
        if candidate.cluster_rank == 0
    )
    retained_alternates = tuple(
        (ordinal, candidate)
        for ordinal, candidate in indexed
        if candidate.cluster_rank == 1
    )
    initial_remaining = max(
        0.0,
        hard_deadline - time.monotonic() - FINALIZE_RESERVE_SECONDS,
    )
    primary_tranche_capacity = _primary_tranche_capacity(
        initial_remaining, len(all_primaries)
    )
    primaries, deferred_primaries = _select_primary_tranche(
        all_primaries, primary_tranche_capacity
    )
    attempts: list[dict[str, object]] = []
    descriptors: dict[str, dict[str, object]] = {}
    successful_cluster_ordinals: set[int] = set()
    primary_authority_clusters: set[int] = set()
    failed_primary_by_cluster: dict[int, tuple[int, ReplayCandidate, Path]] = {}
    primary_attempted = 0
    alternate_attempted = 0
    restoration_attempted = 0
    primary_wave_complete = False
    alternate_wave_complete = False
    restoration_wave_complete = False
    eligible_alternate_count = 0
    eligible_restoration_count = 0

    def record_authority(
        candidate: ReplayCandidate, attempt: Mapping[str, object]
    ) -> bool:
        descriptor = attempt.get("descriptor")
        if attempt.get("authority_pass") is not True or not isinstance(
            descriptor, Mapping
        ):
            return False
        descriptors.setdefault(_descriptor_key(descriptor), dict(descriptor))
        successful_cluster_ordinals.add(candidate.cluster_ordinal)
        return True

    def statistics() -> dict[str, object]:
        return {
            "policy": (
                "anonymous finite primary tranche, then breadth-first alternate "
                "and restoration waves"
            ),
            "primary_total": len(all_primaries),
            "primary_tranche_capacity": primary_tranche_capacity,
            "primary_selected_count": len(primaries),
            "primary_deferred_unknown_count": len(deferred_primaries),
            "unselected_primary_disposition": "DEFERRED_UNKNOWN_NOT_DISCARDED",
            "primary_attempted": primary_attempted,
            "primary_wave_complete": primary_wave_complete,
            "all_discovered_primaries_served": bool(
                primary_wave_complete and not deferred_primaries
            ),
            "eligible_alternate_count": eligible_alternate_count,
            "alternate_attempted": alternate_attempted,
            "alternate_wave_complete": alternate_wave_complete,
            "same_cluster_alternates_skipped_after_authority": sum(
                candidate.cluster_ordinal in primary_authority_clusters
                for _ordinal, candidate in retained_alternates
            ),
            "eligible_restoration_count": eligible_restoration_count,
            "restoration_attempted": restoration_attempted,
            "restoration_wave_complete": restoration_wave_complete,
            "minimum_reserved_seconds_per_unserved_wave_candidate": (
                MIN_HP_ATTEMPT_SECONDS
            ),
            "maximum_primary_or_alternate_seconds": MAX_HP_ATTEMPT_SECONDS,
            "maximum_restoration_seconds": MAX_RESTORATION_ATTEMPT_SECONDS,
            "cross_cluster_candidate_suppression": False,
        }

    # Wave 1: every selected tranche primary precedes all alternate and
    # restoration work.  The current cap leaves MIN_HP_ATTEMPT_SECONDS for
    # every selected primary still unserved after it.  Non-selected primaries
    # remain deferred/unknown and are not represented as exhausted or absent.
    for position, (ordinal, candidate) in enumerate(primaries):
        remaining = hard_deadline - time.monotonic() - FINALIZE_RESERVE_SECONDS
        attempt_seconds = _wave_attempt_seconds(
            remaining,
            len(primaries) - position,
            MAX_HP_ATTEMPT_SECONDS,
        )
        if attempt_seconds == 0.0:
            break
        hp_output = output / "hp" / f"{ordinal:04d}-{candidate.endpoint_sha256[:16]}"
        attempt = _run_hp_candidate(
            source=source,
            source_sha256=source_sha256,
            candidate=candidate,
            cpu=cpu,
            output=hp_output,
            timeout_seconds=attempt_seconds,
        )
        attempts.append(attempt)
        primary_attempted += 1
        if record_authority(candidate, attempt):
            primary_authority_clusters.add(candidate.cluster_ordinal)
            continue
        failed_primary_by_cluster[candidate.cluster_ordinal] = (
            ordinal,
            candidate,
            hp_output,
        )
    else:
        primary_wave_complete = True

    if not primary_wave_complete:
        return attempts, descriptors, statistics()

    # Wave 2: only failed primary clusters are eligible.  A primary authority
    # skips its own alternate and nothing from any other provisional cluster.
    eligible_alternates = tuple(
        (ordinal, candidate)
        for ordinal, candidate in retained_alternates
        if candidate.cluster_ordinal in failed_primary_by_cluster
        and not _same_cluster_authority_exists(
            candidate, successful_cluster_ordinals
        )
    )
    eligible_alternate_count = len(eligible_alternates)
    for position, (ordinal, candidate) in enumerate(eligible_alternates):
        remaining = hard_deadline - time.monotonic() - FINALIZE_RESERVE_SECONDS
        attempt_seconds = _wave_attempt_seconds(
            remaining,
            len(eligible_alternates) - position,
            MAX_HP_ATTEMPT_SECONDS,
        )
        if attempt_seconds == 0.0:
            break
        hp_output = output / "hp" / f"{ordinal:04d}-{candidate.endpoint_sha256[:16]}"
        attempt = _run_hp_candidate(
            source=source,
            source_sha256=source_sha256,
            candidate=candidate,
            cpu=cpu,
            output=hp_output,
            timeout_seconds=attempt_seconds,
        )
        attempts.append(attempt)
        alternate_attempted += 1
        if record_authority(candidate, attempt):
            failed_primary_by_cluster.pop(candidate.cluster_ordinal, None)
    else:
        alternate_wave_complete = True

    if not alternate_wave_complete:
        return attempts, descriptors, statistics()

    # Wave 3: at most one existing restoration attempt per still-failed
    # primary, ordered by the frozen primary order and using its failed
    # numerical-v3 artifact as the only trigger evidence.
    restorables = tuple(
        failed_primary_by_cluster[cluster_ordinal]
        for cluster_ordinal in sorted(
            failed_primary_by_cluster,
            key=lambda item: failed_primary_by_cluster[item][0],
        )
    )
    eligible_restoration_count = len(restorables)
    for position, (ordinal, candidate, failed_hp_output) in enumerate(restorables):
        remaining = hard_deadline - time.monotonic() - FINALIZE_RESERVE_SECONDS
        attempt_seconds = _wave_attempt_seconds(
            remaining,
            len(restorables) - position,
            MAX_RESTORATION_ATTEMPT_SECONDS,
        )
        if attempt_seconds == 0.0:
            break
        rescue = _run_restoration_candidate(
            source=source,
            source_sha256=source_sha256,
            candidate=candidate,
            cpu=cpu,
            failed_authority_artifact=failed_hp_output / "authority.json",
            output=output
            / "restoration"
            / f"{ordinal:04d}-{candidate.endpoint_sha256[:16]}",
            timeout_seconds=attempt_seconds,
        )
        attempts.append(rescue)
        restoration_attempted += 1
        if record_authority(candidate, rescue):
            failed_primary_by_cluster.pop(candidate.cluster_ordinal, None)
    else:
        restoration_wave_complete = True

    return attempts, descriptors, statistics()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--total-seconds", type=float, default=DEFAULT_TOTAL_SECONDS)
    parser.add_argument("--search-seconds", type=float, default=DEFAULT_SEARCH_SECONDS)
    parser.add_argument("--starts", type=int, default=DEFAULT_STARTS)
    parser.add_argument(
        "--callbacks-per-start", type=int, default=DEFAULT_CALLBACKS_PER_START
    )
    parser.add_argument(
        "--aggregate-callback-cap", type=int, default=DEFAULT_AGGREGATE_CALLBACK_CAP
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--cpu", type=int, default=13)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--plan-sha256")
    arguments = parser.parse_args()

    if len(arguments.source_sha256) != 64:
        raise SystemExit("source SHA-256 must contain 64 hexadecimal digits")
    try:
        int(arguments.source_sha256, 16)
    except ValueError as error:
        raise SystemExit("source SHA-256 must be hexadecimal") from error
    if arguments.cpu < 0 or arguments.cpu >= 16:
        raise SystemExit("CPU must be a first-sibling physical core in [0,15]")
    if (
        not math.isfinite(arguments.total_seconds)
        or not math.isfinite(arguments.search_seconds)
        or arguments.total_seconds <= 0.0
        or arguments.total_seconds > 180.0
        or arguments.search_seconds <= 0.0
        or arguments.search_seconds
        > arguments.total_seconds
        - SELECTION_RESERVE_SECONDS
        - FINALIZE_RESERVE_SECONDS
        - MIN_HP_ATTEMPT_SECONDS
        or arguments.starts < 1
        or arguments.callbacks_per_start < 2
        or arguments.aggregate_callback_cap < 1
    ):
        raise SystemExit("invalid integrated wall/callback budget")

    source_payload, source_document = _source_contract(
        arguments.source, arguments.source_sha256
    )
    output = arguments.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    plan = _plan(
        source=arguments.source,
        source_sha256=arguments.source_sha256,
        total_seconds=arguments.total_seconds,
        search_seconds=arguments.search_seconds,
        starts=arguments.starts,
        callbacks_per_start=arguments.callbacks_per_start,
        aggregate_callback_cap=arguments.aggregate_callback_cap,
        seed=arguments.seed,
        cpu=arguments.cpu,
        output=output,
    )
    plan_path = output / "PLAN.json"
    atomic_write_json(plan_path, plan)
    plan_sha256 = _sha256(plan_path.read_bytes())
    if not arguments.execute:
        print(json.dumps({"plan_sha256": plan_sha256, **plan}, indent=2))
        return
    if arguments.plan_sha256 != plan_sha256:
        raise SystemExit("execution requires the exact dry-run PLAN SHA-256")
    if sorted(os.sched_getaffinity(0)) != [arguments.cpu]:
        raise SystemExit("execution requires the outer worker pinned to --cpu")
    if not all(
        path.is_file()
        for path in (
            PYTHON,
            SEARCH_WORKER,
            SEARCH_ADAPTER,
            SEARCH_CANDIDATE,
            HP_BRIDGE,
            RESTORATION_WORKER,
            RESTORATION_ADAPTER,
            RESTORATION_CANDIDATE,
        )
    ):
        raise SystemExit("frozen Python, discovery worker, or HP bridge is unavailable")
    if _sha256(SEARCH_CANDIDATE.read_bytes()) != EXPECTED_SEARCH_CANDIDATE_SHA256:
        raise SystemExit("strict-restart direct-Broyden candidate digest changed")
    if (
        _sha256(RESTORATION_WORKER.read_bytes())
        != EXPECTED_RESTORATION_WORKER_SHA256
        or _sha256(RESTORATION_ADAPTER.read_bytes())
        != EXPECTED_RESTORATION_ADAPTER_SHA256
        or _sha256(RESTORATION_CANDIDATE.read_bytes())
        != EXPECTED_RESTORATION_CANDIDATE_SHA256
    ):
        raise SystemExit("frozen HP-failure restoration binding changed")

    hard_deadline = PROCESS_STARTED + arguments.total_seconds
    search_guard, search = _run_search(
        source=arguments.source,
        source_sha256=arguments.source_sha256,
        search_seconds=arguments.search_seconds,
        starts=arguments.starts,
        callbacks_per_start=arguments.callbacks_per_start,
        aggregate_callback_cap=arguments.aggregate_callback_cap,
        seed=arguments.seed,
        output=output,
    )
    endpoints = search.get("endpoints", ()) if isinstance(search, Mapping) else ()
    candidates = _fresh_replay_candidates(
        source_document,
        endpoints if isinstance(endpoints, list) else (),
        hard_deadline=min(
            hard_deadline - FINALIZE_RESERVE_SECONDS,
            time.monotonic() + SELECTION_RESERVE_SECONDS,
        ),
    )

    attempts, descriptors, hp_schedule = _service_candidates(
        source=arguments.source,
        source_sha256=arguments.source_sha256,
        candidates=candidates,
        cpu=arguments.cpu,
        output=output,
        hard_deadline=hard_deadline,
    )

    source_unchanged = arguments.source.read_bytes() == source_payload
    elapsed = time.monotonic() - PROCESS_STARTED
    exact_targets = [descriptors[key] for key in sorted(descriptors)]
    result = {
        "schema_version": SCHEMA,
        "status": "SEARCH_DEADLINE_REACHED",
        "completed": True,
        "source_sha256": arguments.source_sha256,
        "source_bytes_unchanged": source_unchanged,
        "elapsed_wall_seconds": elapsed,
        "within_total_wall_budget": elapsed <= arguments.total_seconds,
        "seed": arguments.seed,
        "search": {
            "arm": SEARCH_ARM,
            "process_classification": search_guard.classification,
            "artifact_accepted": search is not None,
            "endpoint_count": len(endpoints) if isinstance(endpoints, list) else 0,
            "fresh_safe_provisional_cluster_count": len(
                {candidate.cluster_ordinal for candidate in candidates}
            ),
            "fresh_safe_selected_candidate_count": len(candidates),
            "maximum_candidates_per_provisional_cluster": (
                MAX_CANDIDATES_PER_PROVISIONAL_CLUSTER
            ),
        },
        "hp_attempt_count": len(attempts),
        "hp_attempts": attempts,
        "hp_schedule": hp_schedule,
        "distinct_exact_targets": exact_targets,
        "distinct_exact_target_descriptors": exact_targets,
        "distinct_exact_target_count": len(descriptors),
        "exact_descriptor_novelty_key": (
            "minimal polynomial high-to-low plus selected real-root index"
        ),
        "cross_cluster_candidate_suppression": False,
        "hp_failure_restoration_lane": "bounded leftover-only existing v6",
        "target_image_completeness_claim": False,
        "truth_case_family_known_target_count_read": False,
        "source_or_problem_modified": False,
        "variables_or_equations_removed": False,
        "bounds_added_or_inferred": False,
        "gauge_or_symmetry_reduction": False,
        "coordinate_reparameterization": False,
    }
    if not source_unchanged:
        raise RuntimeError("source bytes changed during integrated run")
    atomic_write_json(output / "RESULT.json", result)


if __name__ == "__main__":
    main()
