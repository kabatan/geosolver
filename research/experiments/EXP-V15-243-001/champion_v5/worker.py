#!/usr/bin/env python3
"""Champion v5: v3 plus failure-only exact-coordinate source replay.

The ordinary champion_v2 target-only HP authority is always attempted first.
If it fails early and at least seven seconds remain in that endpoint's
anonymous HP allocation, one generic fallback independently refines every
source coordinate and requires exact QQBar replay of the untouched source.
Case execution remains fresh-process, one physical core, and at most sixteen
cases in parallel under the champion_v3 resource scheduler.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
from fractions import Fraction
from pathlib import Path
import sys
import time
from typing import Mapping


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SCHEDULER_ROOT = HERE.parent / "candidates/hp_lock_scheduler"
SCHEDULER_WORKER = SCHEDULER_ROOT / "worker.py"
CHAMPION_V2_WORKER = HERE.parent / "champion_v2/worker.py"
EXACT_ROOT = HERE.parent / "candidates/exact_coordinate_replay"
EXACT_WORKER = EXACT_ROOT / "fallback_worker.py"
EXACT_CANDIDATE = EXACT_ROOT / "candidate.py"
EXACT_REFINER = (
    ROOT / "research/experiments/EXP-REAL61-001/refine_proposals_worker.py"
)
EXACT_DAG = (
    ROOT / "research/experiments/EXP-REAL61-004/qqbar_exact_replay/dag_compile.py"
)
EXACT_QQBAR = (
    ROOT
    / "research/experiments/EXP-REAL61-004/qqbar_exact_replay/qqbar_worker.jl"
)
MAX_JOBS = 16
GLOBAL_RESERVATION_BYTES = 20 * 1024**3
RESERVATION_TOKEN_BYTES = 256 * 1024**2
MINIMUM_FALLBACK_REMAINING_SECONDS = 7.0
MAXIMUM_FALLBACK_SECONDS = 12.0

os.environ["GEOTARGET_HP_MAX_JOBS"] = str(MAX_JOBS)
os.environ["GEOTARGET_GLOBAL_RSS_RESERVATION_BYTES"] = str(
    GLOBAL_RESERVATION_BYTES
)
os.environ["GEOTARGET_MEMORY_RESERVATION_TOKEN_BYTES"] = str(
    RESERVATION_TOKEN_BYTES
)
os.environ["GEOTARGET_HP_CHAMPION_WORKER"] = str(
    CHAMPION_V2_WORKER.resolve()
)

if str(SCHEDULER_ROOT) not in sys.path:
    sys.path.insert(0, str(SCHEDULER_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _matches_sha256(path: Path, expected: str) -> bool:
    try:
        return _sha256(path) == expected
    except OSError:
        return False


def _load_scheduler():
    name = "geotarget_exp_v15_243_champion_v5_scheduler_worker"
    specification = importlib.util.spec_from_file_location(
        name,
        SCHEDULER_WORKER,
    )
    if specification is None or specification.loader is None:
        raise ImportError(SCHEDULER_WORKER)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


SCHEDULER = _load_scheduler()
BASE = SCHEDULER.CHAMPION.BASE
_SCHEDULER_PLAN = BASE._plan
_SCHEDULED_HP = BASE._run_hp_candidate


def _isolator_metadata(value: object) -> dict[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    left = value.get("left")
    right = value.get("right")
    multiplicity = value.get("multiplicity")
    root_index = value.get("real_root_index")
    if (
        not isinstance(left, str)
        or not isinstance(right, str)
        or not isinstance(multiplicity, int)
        or isinstance(multiplicity, bool)
        or multiplicity != 1
        or not isinstance(root_index, int)
        or isinstance(root_index, bool)
        or root_index < 0
    ):
        return None
    try:
        if Fraction(left) > Fraction(right):
            return None
    except (ValueError, ZeroDivisionError):
        return None
    return dict(value)


def _coordinate_descriptor_metadata(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    polynomial = value.get("coefficients_high_to_low")
    metadata = value.get("polynomial_metadata")
    return bool(
        value.get("status") == "ALGEBRAIC_PROPOSAL"
        and value.get("numeric_lanes_used_only_for_proposal") is True
        and isinstance(polynomial, list)
        and len(polynomial) >= 2
        and all(
            isinstance(coefficient, int)
            and not isinstance(coefficient, bool)
            for coefficient in polynomial
        )
        and isinstance(metadata, Mapping)
        and metadata.get("square_free") is True
        and metadata.get("irreducible_over_Q") is True
        and _isolator_metadata(metadata.get("isolating_interval")) is not None
    )


def _exact_descriptor(value: object) -> dict[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    polynomial = value.get("minimal_polynomial_high_to_low")
    root_index = value.get("selected_real_root_index")
    isolator = value.get("isolating_interval")
    if (
        not isinstance(polynomial, list)
        or len(polynomial) < 2
        or not all(
            isinstance(coefficient, int)
            and not isinstance(coefficient, bool)
            for coefficient in polynomial
        )
        or not isinstance(root_index, int)
        or isinstance(root_index, bool)
        or root_index < 0
        or _isolator_metadata(isolator) is None
        or isolator.get("real_root_index") != root_index
        or value.get("proposal_relation_low_to_high")
        != list(reversed(polynomial))
        or value.get("confirmation_relation_low_to_high")
        != list(reversed(polynomial))
        or not isinstance(value.get("target_768"), str)
        or not isinstance(value.get("target_1024"), str)
    ):
        return None
    return dict(value)


def _root_attestation_matches(value: object, root_index: object) -> bool:
    return bool(
        isinstance(root_index, int)
        and not isinstance(root_index, bool)
        and root_index >= 0
        and isinstance(value, Mapping)
        and isinstance(value.get("claimed_real_root_index"), int)
        and not isinstance(value.get("claimed_real_root_index"), bool)
        and value.get("claimed_real_root_index") == root_index
        and isinstance(value.get("attested_real_root_index"), int)
        and not isinstance(value.get("attested_real_root_index"), bool)
        and value.get("attested_real_root_index") == root_index
        and isinstance(value.get("real_root_count"), int)
        and not isinstance(value.get("real_root_count"), bool)
        and value.get("real_root_count") > root_index
        and isinstance(value.get("multiplicity"), int)
        and not isinstance(value.get("multiplicity"), bool)
        and value.get("multiplicity") == 1
        and value.get("interval_unique") is True
        and value.get("index_match") is True
    )


def _nested_exact_authority_matches_source(
    fallback: Mapping[str, object],
    descriptor: Mapping[str, object],
    source_document: Mapping[str, object],
    source_sha256: str,
) -> bool:
    """Recheck the child authority ledger at the integration seam."""

    exact = fallback.get("exact_coordinate_authority")
    numeric = fallback.get("numeric_source_replay")
    variables = source_document.get("variables")
    names = variables.get("names") if isinstance(variables, Mapping) else None
    constraints = source_document.get("constraints")
    guards = source_document.get("guards") or []
    bounds = source_document.get("bounds")
    if (
        not isinstance(exact, Mapping)
        or not isinstance(names, list)
        or not isinstance(constraints, list)
        or not isinstance(guards, list)
        or fallback.get("independent_coordinate_lanes") != [768, 1024]
        or fallback.get("exact_replay_backend") != "FLINT_QQBAR_VIA_NEMO"
        or fallback.get("numeric_guard_branch_replay_is_authority") is not True
        or fallback.get("numeric_target_nearness_is_authority") is not False
        or fallback.get("numeric_float_residual_is_authority") is not False
        or not isinstance(numeric, Mapping)
        or numeric.get("schema_version")
        != "geotarget.v15-243-frozen-numeric-source-replay/v1"
        or numeric.get("refiner_sha256") != _sha256(EXACT_REFINER)
        or numeric.get("source_sha256") != source_sha256
        or numeric.get("proposal_status") != "PSLQ_PROPOSAL"
        or not isinstance(numeric.get("float_source_replay"), Mapping)
        or numeric.get("float_source_replay").get("evaluation_defined") is not True
        or numeric.get("float_source_replay").get("guard_ok") is not True
        or numeric.get("float_source_replay").get("hard_feasible") is not True
        or numeric.get("float_source_replay").get("residual_is_authority") is not False
        or not isinstance(
            numeric.get("float_source_replay").get("residual_inf"),
            (int, float),
        )
        or isinstance(
            numeric.get("float_source_replay").get("residual_inf"),
            bool,
        )
        or not math.isfinite(
            float(numeric.get("float_source_replay").get("residual_inf"))
        )
        or float(numeric.get("float_source_replay").get("residual_inf")) < 0.0
        or numeric.get("precision_lanes_decimal_digits") != [155, 232, 320]
        or not isinstance(numeric.get("lane_methods"), Mapping)
        or set(numeric.get("lane_methods")) != {"155", "232", "320"}
        or not isinstance(numeric.get("lane_working_decimal_digits"), Mapping)
        or set(numeric.get("lane_working_decimal_digits"))
        != {"155", "232", "320"}
        or any(
            not isinstance(numeric.get("lane_working_decimal_digits")[key], int)
            or isinstance(numeric.get("lane_working_decimal_digits")[key], bool)
            or numeric.get("lane_working_decimal_digits")[key] < int(key)
            for key in ("155", "232", "320")
        )
        or not isinstance(numeric.get("lane_source_replay"), Mapping)
        or set(numeric.get("lane_source_replay")) != {"155", "232", "320"}
        or any(
            not isinstance(numeric.get("lane_source_replay")[key], Mapping)
            or numeric.get("lane_source_replay")[key]
            != {
                "replay_decimal_digits": int(key),
                "guard_replay_decimal_digits": int(key),
                "hard_feasibility_replay_decimal_digits": int(key),
                "residual_replay_decimal_digits": int(key),
                "answer_replay_decimal_digits": int(key),
                "residual_threshold": {
                    "155": "1e-100",
                    "232": "1e-150",
                    "320": "1e-200",
                }[key],
                "guard_ok": True,
                "hard_feasible": True,
                "residual_reached": True,
                "answer_defined": True,
            }
            for key in ("155", "232", "320")
        )
        or numeric.get("float_endpoint_source_replay_required") is not True
        or numeric.get("all_precision_lanes_guard_and_hard_feasible")
        is not True
        or numeric.get("all_precision_lanes_source_residual_reached")
        is not True
        or numeric.get("coordinates_linked_to_exact_roots_by_independent_lanes")
        is not True
        or numeric.get("branch_and_guard_parity_is_not_inferred_from_qqbar")
        is not True
        or exact.get("schema_version")
        != "geotarget.v15-243-exact-coordinate-replay/v1"
        or exact.get("backend") != "FLINT_QQBAR_VIA_NEMO"
        or exact.get("status") != "EXACT_TARGET_AUTHORITY_READY"
        or exact.get("authority_pass") is not True
        or exact.get("truth_used") is not False
        or exact.get("case_family_or_target_count_routing") is not False
        or exact.get("numeric_nearness_is_authority") is not False
        or exact.get("source_replay_required") is not True
        or exact.get("source_raw_answer_exact") is not True
        or exact.get("target_link_exact") is not True
        or exact.get("post_process_used") is not False
        or exact.get("target_set_completeness_claim") is not False
        or exact.get("root_ordinal_attestation_complete") is not True
        or exact.get("root_ordinal_policy")
        != "ZERO_BASED_STRICTLY_INCREASING_REAL_QQBAR_V1"
        or exact.get("root_ordinal_attestation_backend")
        != "NEMO_QQBAR_SORTED_REAL_ROOTS"
        or exact.get("source_guard_margin_policy")
        != (
            "exact algebraic guard leg; frozen numeric parity separately "
            "required"
        )
        or exact.get("combined_numeric_and_exact_authority_required") is not True
        or exact.get("standalone_operational_v15_parity_claim") is not False
        or exact.get("source_guard_default_margin_exact_rational")
        != "1/10^40"
        or exact.get("source_guard_logical_not_fails_closed") is not True
        or exact.get("source_hard_feasibility_exact_subset") is not True
        or exact.get("source_hard_margin_exact_rationals")
        != {
            "line_distinct": "1/10^12",
            "triangle_nondegenerate": "1/10^14",
            "intersection_exclude_distinct": "1/10^12",
        }
        or exact.get("source_constraints_exact") != len(constraints)
        or exact.get("source_guards_exact") != len(guards)
        or exact.get("source_bounds_exact")
        != (0 if bounds is None else len(names))
    ):
        return False
    coordinate_descriptors = exact.get("coordinate_descriptors")
    coordinate_attestations = exact.get("coordinate_root_attestations")
    target = exact.get("exact_target_descriptor")
    target_attestation = exact.get("target_root_attestation")
    target_isolator = (
        target.get("isolating_interval")
        if isinstance(target, Mapping)
        else None
    )
    if (
        not isinstance(coordinate_descriptors, list)
        or len(coordinate_descriptors) != len(names)
        or not isinstance(coordinate_attestations, list)
        or len(coordinate_attestations) != len(names)
        or not all(
            _coordinate_descriptor_metadata(item)
            for item in coordinate_descriptors
        )
        or any(
            not isinstance(item.get("polynomial_metadata"), Mapping)
            or not isinstance(
                item.get("polynomial_metadata").get("isolating_interval"),
                Mapping,
            )
            or not _root_attestation_matches(
                attestation,
                item.get("polynomial_metadata")
                .get("isolating_interval")
                .get("real_root_index"),
            )
            for item, attestation in zip(
                coordinate_descriptors,
                coordinate_attestations,
                strict=True,
            )
        )
        or not isinstance(target, Mapping)
        or not isinstance(target_isolator, Mapping)
        or not _root_attestation_matches(
            target_attestation,
            target_isolator.get("real_root_index"),
        )
        or target_isolator.get("real_root_index")
        != descriptor.get("selected_real_root_index")
        or target.get("coefficients_high_to_low")
        != descriptor.get("minimal_polynomial_high_to_low")
        or target.get("isolating_interval")
        != descriptor.get("isolating_interval")
    ):
        return False
    return True


def _run_exact_fallback(**kwargs) -> dict[str, object] | None:
    timeout_seconds = float(kwargs["timeout_seconds"])
    started = time.monotonic()
    ordinary = _SCHEDULED_HP(**kwargs)
    if ordinary.get("authority_pass") is True:
        return ordinary
    if (
        ordinary.get("resource_busy_deferred") is True
        or ordinary.get("status")
        in SCHEDULER.RESOURCE_BUSY_STATUSES
    ):
        # Resource contention is not a numerical failure.  Preserve the
        # scheduler-visible terminal so this endpoint can be retried instead
        # of spending a second resource acquisition on the fallback lane.
        return ordinary
    remaining = timeout_seconds - (time.monotonic() - started)
    if remaining < MINIMUM_FALLBACK_REMAINING_SECONDS:
        result = dict(ordinary)
        result["exact_coordinate_fallback"] = {
            "status": "NOT_RUN_INSUFFICIENT_ENDPOINT_ALLOCATION",
            "minimum_remaining_seconds": (
                MINIMUM_FALLBACK_REMAINING_SECONDS
            ),
            "observed_remaining_seconds": max(0.0, remaining),
        }
        return result

    source = Path(kwargs["source"])
    source_sha256 = str(kwargs["source_sha256"])
    candidate = kwargs["candidate"]
    cpu = int(kwargs["cpu"])
    root = Path(kwargs["output"]) / "exact-coordinate-fallback"
    artifact = root / "RESULT.json"
    artifact.unlink(missing_ok=True)
    fallback_seconds = min(
        MAXIMUM_FALLBACK_SECONDS,
        max(0.5, remaining - 0.5),
    )
    command = [
        "taskset",
        "-c",
        str(cpu),
        str(BASE.PYTHON),
        str(EXACT_WORKER),
        "--source",
        str(source.resolve()),
        "--source-sha256",
        source_sha256,
        "--endpoint",
        json.dumps(
            candidate.endpoint,
            separators=(",", ":"),
            allow_nan=False,
        ),
        "--endpoint-sha256",
        candidate.endpoint_sha256,
        "--timeout-seconds",
        str(max(0.5, fallback_seconds - 0.5)),
        "--output",
        str(artifact.resolve()),
    ]
    guarded = None
    lease_status = "ACQUIRED"
    try:
        with SCHEDULER.adapter.per_core_lease(
            cpu,
            wait_seconds=min(
                SCHEDULER.adapter.DEFAULT_POLICY.maximum_core_lease_wait_seconds,
                max(0.0, fallback_seconds - 1.0),
            ),
        ):
            root.mkdir(parents=True, exist_ok=True)
            guarded = BASE.run_guarded(
                command,
                limits=BASE.Limits(
                    timeout_seconds=fallback_seconds,
                    rss_bytes=768 * 1024**2,
                    address_space_bytes=3072 * 1024**2,
                    data_bytes=2048 * 1024**2,
                    output_bytes=1024**2,
                    tail_bytes=16 * 1024,
                ),
                environment=BASE.THREAD_ENVIRONMENT,
                cwd=ROOT,
                status_path=root / "process-status.json",
            )
            if guarded.classification == "MEMORY_RESERVATION_TIMEOUT":
                lease_status = "MEMORY_BUSY_DEFERRED"
    except SCHEDULER.adapter.LeaseUnavailable:
        lease_status = "LOCK_BUSY_DEFERRED"

    fallback = None
    try:
        loaded = json.loads(artifact.read_text(encoding="utf-8"))
        if isinstance(loaded, Mapping):
            fallback = loaded
    except (OSError, json.JSONDecodeError):
        pass
    descriptor = (
        _exact_descriptor(fallback.get("descriptor"))
        if isinstance(fallback, Mapping)
        else None
    )
    try:
        source_document = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        source_document = None
    accepted = bool(
        guarded is not None
        and guarded.accepted_output
        and guarded.descendant_leak is not True
        and isinstance(fallback, Mapping)
        and fallback.get("schema_version")
        == "geotarget.v15-243-exact-coordinate-fallback/v1"
        and fallback.get("completed") is True
        and fallback.get("status")
        == "EXACT_COORDINATE_TARGET_AUTHORITY_READY"
        and fallback.get("authority_pass") is True
        and _matches_sha256(source, source_sha256)
        and fallback.get("source_sha256") == source_sha256
        and fallback.get("endpoint_float64_sha256")
        == candidate.endpoint_sha256
        and fallback.get("truth_used") is False
        and fallback.get("case_family_known_target_count_routing") is False
        and fallback.get("source_or_problem_modified") is False
        and fallback.get("bounds_added_or_inferred") is False
        and fallback.get("coordinate_reparameterization") is False
        and fallback.get("target_set_completeness_claim") is False
        and fallback.get("within_fallback_wall_budget") is True
        and descriptor is not None
        and isinstance(source_document, Mapping)
        and _nested_exact_authority_matches_source(
            fallback,
            descriptor,
            source_document,
            source_sha256,
        )
    )
    fallback_evidence = {
        "status": (
            "TARGET_AUTHORITY_READY"
            if accepted
            else (
                lease_status
                if lease_status in SCHEDULER.RESOURCE_BUSY_STATUSES
                else (
                    fallback.get("status")
                    if isinstance(fallback, Mapping)
                    else lease_status
                )
            )
        ),
        "authority_pass": accepted,
        "lease_status": lease_status,
        "allocated_seconds": fallback_seconds,
        "result_sha256": _sha256(artifact) if artifact.is_file() else None,
        "process": guarded.to_dict() if guarded is not None else None,
        "truth_used": False,
        "target_set_completeness_claim": False,
    }
    if not accepted:
        result = dict(ordinary)
        result["exact_coordinate_fallback"] = fallback_evidence
        if lease_status in SCHEDULER.RESOURCE_BUSY_STATUSES:
            # The outer scheduler requeues only top-level resource terminals.
            # Do not hide a fallback lease deferral beneath an ordinary HP
            # numerical failure.
            result.update(
                {
                    "status": lease_status,
                    "authority_pass": False,
                    "descriptor": None,
                    "resource_busy_deferred": True,
                }
            )
        return result
    return {
        "attempt_kind": "FAILURE_ONLY_EXACT_COORDINATE_QQBAR_REPLAY",
        "endpoint_float64_sha256": candidate.endpoint_sha256,
        "residual_inf": candidate.residual_inf,
        "provisional_target": candidate.provisional_target,
        "cluster_ordinal": candidate.cluster_ordinal,
        "cluster_rank": candidate.cluster_rank,
        "status": "TARGET_AUTHORITY_READY",
        "authority_pass": True,
        "descriptor": descriptor,
        "ordinary_hp_attempt": ordinary,
        "exact_coordinate_fallback": fallback_evidence,
        "case_family_truth_target_count_routing": False,
    }


BASE._run_hp_candidate = _run_exact_fallback


def _plan(**kwargs) -> dict[str, object]:
    plan = _SCHEDULER_PLAN(**kwargs)
    policy = plan.get("hp_resource_policy")
    expected = {
        "max_jobs": MAX_JOBS,
        "global_reservation_bytes": GLOBAL_RESERVATION_BYTES,
        "reservation_token_bytes": RESERVATION_TOKEN_BYTES,
        "worst_case_token_reserved_bytes": 16 * 1024**3,
        "reservation_headroom_bytes": 4 * 1024**3,
    }
    observed = (
        {key: policy.get(key) for key in expected}
        if isinstance(policy, Mapping)
        else None
    )
    if observed != expected:
        raise RuntimeError(
            "champion_v5 resource profile mismatch: "
            + json.dumps(observed, sort_keys=True)
        )
    closure = {
        "fallback_worker_sha256": _sha256(EXACT_WORKER),
        "candidate_sha256": _sha256(EXACT_CANDIDATE),
        "independent_refiner_sha256": _sha256(EXACT_REFINER),
        "dag_compiler_sha256": _sha256(EXACT_DAG),
        "qqbar_worker_sha256": _sha256(EXACT_QQBAR),
    }
    plan.update(
        {
            "schema_version": "geotarget.exp-v15-243-champion-v5-plan/v1",
            "champion_v5_worker_sha256": _sha256(Path(__file__)),
            "champion_v5_underlying_solver": str(
                CHAMPION_V2_WORKER.resolve()
            ),
            "champion_v5_underlying_solver_sha256": _sha256(
                CHAMPION_V2_WORKER
            ),
            "exact_coordinate_fallback": {
                "policy": (
                    "failure-only after ordinary HP; frozen v15 Float "
                    "evaluation-defined/guard/branch/hard admission with no "
                    "Float residual authority; nominal 155/232/320-digit "
                    "source guard, branch, hard-feasibility and residual "
                    "replay; independent 768/1024 coordinate proposals; "
                    "exact untouched-source QQBar replay"
                ),
                "minimum_remaining_seconds": (
                    MINIMUM_FALLBACK_REMAINING_SECONDS
                ),
                "maximum_seconds": MAXIMUM_FALLBACK_SECONDS,
                "numeric_guard_branch_replay_is_authority": True,
                "combined_numeric_and_exact_source_authority": True,
                "float_residual_is_authority": False,
                "numeric_coordinate_nearness_is_authority": False,
                "post_process_supported": False,
                "target_set_completeness_claim": False,
                "spurious_pslq_continues_bounded_degree_search": True,
                "closure": closure,
            },
            "case_parallelism_is_resource_only": True,
            "fresh_process_per_case": True,
            "one_first_sibling_physical_cpu_per_case": True,
            "maximum_concurrent_cases": MAX_JOBS,
            "logical_smt_siblings_used_by_formal_cases": False,
            "case_family_truth_target_count_routing": False,
        }
    )
    return plan


BASE._plan = _plan


def main() -> None:
    SCHEDULER.main()


if __name__ == "__main__":
    main()
