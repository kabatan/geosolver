#!/usr/bin/env python3
"""Truth-free generated and metamorphic S0 for progressive scheduling."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Callable, Mapping, Sequence

import numpy as np


HERE = Path(__file__).resolve().parent


def _load_candidate():
    name = "geotarget_progressive_local_budget_metamorphic_candidate"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    path = HERE / "candidate.py"
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


CANDIDATE = _load_candidate()
PROFILES = ("64-192-600", "96-300-600")
NARROW_BASIN_RADIUS = 1.0e-12
OFF_BASIN_RESIDUAL_FLOOR = 1.0e6


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _sources() -> tuple[str, ...]:
    return (
        CANDIDATE.INSURANCE_SOURCE,
        "source_literal_product_cauchy",
        "source_literal_log_symmetric",
        "source_literal_asinh_rational",
    )


def starts(
    count: int,
    transform: Callable[[np.ndarray], np.ndarray] | None = None,
):
    transform = transform or (lambda point: point)
    sources = _sources()
    result = []
    for ordinal in range(count):
        canonical = np.asarray(
            [float(ordinal), 2.0 * ordinal + 1.0, 0.25 * ordinal - 3.0]
        )
        result.append(
            CANDIDATE.StartSpec(
                ordinal,
                sources[ordinal % 4],
                np.asarray(transform(canonical), dtype=float),
                ordinal % 4 == 0,
            )
        )
    return tuple(result)


def _decision_trace(result) -> tuple[tuple[int, int], ...]:
    return tuple(
        (record.start_ordinal, record.rung_callback_cap)
        for record in result.records
    )


def _trace_sha256(trace: Sequence[tuple[int, int]]) -> str:
    payload = json.dumps(trace, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def equivalent_run(profile: str, variant: str):
    """Solve one synthetic narrow basin under equivalent representations."""

    CANDIDATE.set_active_profile(profile)
    count = 32
    target = np.asarray([31.0, 63.0, 4.75])
    if variant == "variable_permutation":
        def transform(point):
            return point[[2, 0, 1]]

        def inverse(point):
            return point[[1, 2, 0]]

        residual_permutation = np.asarray([0, 1, 2])
        residual_scale = 1.0
    elif variant == "residual_permutation":
        def transform(point):
            return point

        def inverse(point):
            return point

        residual_permutation = np.asarray([2, 0, 1])
        residual_scale = 1.0
    elif variant == "affine_scale":
        scale = np.asarray([7.0, 0.25, 3.0])
        shift = np.asarray([-11.0, 5.0, 2.0])

        def transform(point):
            return scale * point + shift

        def inverse(point):
            return (point - shift) / scale

        residual_permutation = np.asarray([0, 1, 2])
        residual_scale = 9.0
    elif variant == "base":
        def transform(point):
            return point

        def inverse(point):
            return point

        residual_permutation = np.asarray([0, 1, 2])
        residual_scale = 1.0
    else:
        raise ValueError(f"unknown metamorphic variant: {variant}")

    proposals = starts(count, transform)
    clock = Clock()

    def runner(spec, allowance, deadline, checkpoint):
        del deadline, checkpoint
        clock.now += 0.001
        canonical = np.asarray(inverse(np.asarray(spec.point, dtype=float)))
        residual = residual_scale * (canonical - target)
        residual = residual[residual_permutation]
        distance = float(np.linalg.norm(residual, ord=np.inf))
        residual_inf = (
            1.0e-20
            if distance <= NARROW_BASIN_RADIUS
            else OFF_BASIN_RESIDUAL_FLOOR + distance
        )
        return CANDIDATE.RungOutcome(
            np.asarray(spec.point, dtype=float).copy(),
            CANDIDATE.Assessment(True, True, residual_inf, 0.0),
            min(allowance, 1),
            "GENERATED_EQUIVALENT",
            promotion_signals={"model_ratio": 0.75, "rank_stability": 1.0},
        )

    result = CANDIDATE.run_rung_scheduler(
        proposals,
        callback_cap=100_000,
        hard_deadline=100.0,
        finalize_reserve_seconds=0.0,
        run_rung=runner,
        clock=clock,
    )
    trace = _decision_trace(result)
    first = result.records[:count]
    assert tuple(record.start_ordinal for record in first) == tuple(range(count))
    assert result.activation["minimum_service_complete"] is True
    assert any(
        record.start_ordinal == 31
        and record.rung_callback_cap == CANDIDATE.RUNG_CALLBACK_CAPS[-1]
        for record in result.records
    )
    assert result.callbacks_used == sum(record.callbacks_used for record in result.records)
    running = 0
    for record in result.records:
        running += record.callbacks_used
        assert record.aggregate_callbacks_after == running
    assert result.activation["counter_cauchy_service_floor_holds"] is True
    return result, trace


def starvation_run(profile: str) -> Mapping[str, object]:
    """A deadline-consuming first callback cannot monopolize later starts."""

    CANDIDATE.set_active_profile(profile)
    proposals = starts(16)
    clock = Clock()
    invoked: list[int] = []

    def runner(spec, allowance, deadline, checkpoint):
        del checkpoint
        invoked.append(spec.ordinal)
        if spec.ordinal == 0 and len(invoked) == 1:
            clock.now = deadline
            return CANDIDATE.RungOutcome(
                spec.point.copy(),
                CANDIDATE.Assessment(False, False, float("inf"), 1.0e300),
                min(allowance, 1),
                "LONG_CALLBACK_PREEMPTED",
                completed_before_deadline=False,
                endpoint_observed_before_deadline=False,
            )
        clock.now += 0.001
        return CANDIDATE.RungOutcome(
            spec.point.copy(),
            CANDIDATE.Assessment(True, True, float(spec.ordinal + 1), 0.0),
            min(allowance, 1),
            "FAST_CALLBACK",
        )

    result = CANDIDATE.run_rung_scheduler(
        proposals,
        callback_cap=100_000,
        hard_deadline=30.0,
        finalize_reserve_seconds=0.0,
        run_rung=runner,
        clock=clock,
    )
    assert invoked[:3] == [0, 1, 2]
    assert result.activation["minimum_service_complete"] is True
    assert result.records[0].status.startswith("DEADLINE_REJECTED:")
    assert result.records[0].attempt_wall_cap_seconds < 4.0
    return {
        "first_service_count": result.activation["first_service_count"],
        "start_count": result.activation["start_count"],
        "deadline_rejected_services": result.activation[
            "deadline_rejected_services"
        ],
        "first_attempt_wall_cap_seconds": result.records[
            0
        ].attempt_wall_cap_seconds,
        "later_start_serviced": 1 in invoked,
    }


def preemption_repromotion_run(profile: str) -> Mapping[str, object]:
    """Useful pre-deadline evidence remains eligible after a partial service."""

    CANDIDATE.set_active_profile(profile)
    proposals = starts(8)
    clock = Clock()
    calls: dict[int, int] = {ordinal: 0 for ordinal in range(8)}

    def runner(spec, allowance, deadline, checkpoint):
        del deadline, checkpoint
        clock.now += 0.001
        calls[spec.ordinal] += 1
        residual = 1.0e-20 if spec.ordinal == 7 else float(100 + spec.ordinal)
        if spec.ordinal == 7 and calls[7] == 1:
            return CANDIDATE.RungOutcome(
                spec.point.copy(),
                CANDIDATE.Assessment(True, True, residual, 0.0),
                min(allowance, 1),
                "PREEMPTED_WITH_ENDPOINT_EVIDENCE",
                completed_before_deadline=False,
                endpoint_observed_before_deadline=True,
            )
        return CANDIDATE.RungOutcome(
            spec.point.copy(),
            CANDIDATE.Assessment(True, True, residual, 0.0),
            min(allowance, 1),
            "COMPLETED",
        )

    result = CANDIDATE.run_rung_scheduler(
        proposals,
        callback_cap=100_000,
        hard_deadline=30.0,
        finalize_reserve_seconds=0.0,
        run_rung=runner,
        clock=clock,
    )
    lane = [record for record in result.records if record.start_ordinal == 7]
    assert lane[0].status.startswith("INCOMPLETE_PREDEADLINE_EVIDENCE:")
    assert tuple(record.rung_callback_cap for record in lane) == tuple(
        CANDIDATE.RUNG_CALLBACK_CAPS
    )
    return {
        "preempted_start_ordinal": 7,
        "services_after_partial_evidence": len(lane) - 1,
        "rungs": [record.rung_callback_cap for record in lane],
        "partial_evidence_repromoted": len(lane) == len(CANDIDATE.RUNG_CALLBACK_CAPS),
    }


def work_accounting_failure_taxonomy(profile: str) -> Mapping[str, str]:
    """Exercise each scheduler-owned accounting failure as a fail-closed row."""

    CANDIDATE.set_active_profile(profile)

    def assessment():
        return CANDIDATE.Assessment(True, True, 1.0, 0.0)

    def run_fault(label: str, runner) -> str:
        try:
            CANDIDATE.run_rung_scheduler(
                starts(4),
                callback_cap=10_000,
                hard_deadline=10.0,
                finalize_reserve_seconds=0.0,
                run_rung=runner,
                clock=Clock(),
            )
        except (AssertionError, ValueError) as error:
            return f"{type(error).__name__}:{error}"
        raise AssertionError(f"accounting fault was accepted: {label}")

    def overcharge(spec, allowance, deadline, checkpoint):
        del deadline, checkpoint
        return CANDIDATE.RungOutcome(
            spec.point.copy(), assessment(), allowance + 1, "OVERCHARGE"
        )

    def negative(spec, allowance, deadline, checkpoint):
        del allowance, deadline, checkpoint
        return CANDIDATE.RungOutcome(
            spec.point.copy(), assessment(), -1, "NEGATIVE_CHARGE"
        )

    def zero_completed(spec, allowance, deadline, checkpoint):
        del allowance, deadline, checkpoint
        return CANDIDATE.RungOutcome(
            spec.point.copy(), assessment(), 0, "ZERO_COMPLETED"
        )

    def malformed_endpoint(spec, allowance, deadline, checkpoint):
        del deadline, checkpoint
        return CANDIDATE.RungOutcome(
            np.append(spec.point, 0.0),
            assessment(),
            min(allowance, 1),
            "MALFORMED_ENDPOINT",
        )

    def mutate_prefix(spec, allowance, deadline, checkpoint):
        del deadline, checkpoint
        spec.point[0] += 1.0
        return CANDIDATE.RungOutcome(
            spec.point.copy(), assessment(), min(allowance, 1), "MUTATED_PREFIX"
        )

    taxonomy = {
        "callback_overcharge": run_fault("callback_overcharge", overcharge),
        "negative_callback_charge": run_fault("negative_callback_charge", negative),
        "zero_charge_completed_service": run_fault(
            "zero_charge_completed_service", zero_completed
        ),
        "malformed_endpoint": run_fault("malformed_endpoint", malformed_endpoint),
        "proposal_prefix_mutation": run_fault(
            "proposal_prefix_mutation", mutate_prefix
        ),
    }
    malformed = list(starts(4))
    malformed[0] = CANDIDATE.StartSpec(
        0, "not-counter-cauchy", malformed[0].point, True
    )
    try:
        CANDIDATE.run_rung_scheduler(
            malformed,
            callback_cap=10,
            hard_deadline=10.0,
            run_rung=lambda *_args: None,
        )
    except ValueError as error:
        taxonomy["insurance_prefix_mismatch"] = f"ValueError:{error}"
    else:
        raise AssertionError("malformed insurance prefix was accepted")
    return taxonomy


def build_evidence() -> dict[str, object]:
    profiles: dict[str, object] = {}
    for profile in PROFILES:
        base_result, base_trace = equivalent_run(profile, "base")
        equivalent: dict[str, object] = {}
        for variant in (
            "variable_permutation",
            "residual_permutation",
            "affine_scale",
        ):
            _result, trace = equivalent_run(profile, variant)
            equivalent[variant] = {
                "decision_trace_equal": trace == base_trace,
                "decision_trace_sha256": _trace_sha256(trace),
            }
            assert trace == base_trace
        insurance_services = sum(record.insurance for record in base_result.records)
        first_services = base_result.records[: base_result.activation["start_count"]]
        regular_sources = {
            record.source for record in first_services if not record.insurance
        }
        deep_regular_sources = {
            record.source
            for record in base_result.records
            if not record.insurance
            and record.rung_callback_cap == CANDIDATE.RUNG_CALLBACK_CAPS[-1]
        }
        profiles[profile] = {
            "rungs": list(CANDIDATE.RUNG_PROFILES[profile]),
            "narrow_basin_radius": NARROW_BASIN_RADIUS,
            "off_basin_residual_floor": OFF_BASIN_RESIDUAL_FLOOR,
            "narrow_basin_start_ordinal": 31,
            "service_count": len(base_result.records),
            "first_service_count": base_result.activation["first_service_count"],
            "start_count": base_result.activation["start_count"],
            "all_start_first_service": base_result.activation[
                "minimum_service_complete"
            ],
            "narrow_basin_start_reached_deepest_rung": True,
            "callbacks_used": base_result.callbacks_used,
            "callbacks_reconciled": base_result.callbacks_used
            == sum(record.callbacks_used for record in base_result.records),
            "insurance_services": insurance_services,
            "insurance_service_fraction": insurance_services
            / len(base_result.records),
            "insurance_prefix_floor_holds": base_result.activation[
                "counter_cauchy_service_floor_holds"
            ],
            "iid_regular_first_service_count": sum(
                not record.insurance for record in first_services
            ),
            "iid_regular_first_service_complete": all(
                record.phase == "ORDINAL_FIRST_SERVICE"
                for record in first_services
                if not record.insurance
            ),
            "iid_regular_source_stream_count": len(regular_sources),
            "iid_regular_source_streams_with_deep_solve": len(
                deep_regular_sources
            ),
            "each_iid_regular_source_stream_has_deep_solve": (
                deep_regular_sources == regular_sources
            ),
            "base_decision_trace_sha256": _trace_sha256(base_trace),
            "metamorphic": equivalent,
            "starvation": dict(starvation_run(profile)),
            "preemption_repromotion": dict(preemption_repromotion_run(profile)),
            "work_accounting_failure_taxonomy": dict(
                work_accounting_failure_taxonomy(profile)
            ),
        }
    return {
        "schema_version": "geotarget.progressive-local-budget-metamorphic-s0/v1",
        "status": "PASS",
        "candidate_sha256": hashlib.sha256(
            (HERE / "candidate.py").read_bytes()
        ).hexdigest(),
        "truth_used": False,
        "benchmark_truth_used": False,
        "external_case_family_problem_id_or_target_inputs": False,
        "synthetic_target_generated_in_harness": True,
        "generated_only": True,
        "profiles": profiles,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compact", action="store_true")
    arguments = parser.parse_args()
    print(
        json.dumps(
            build_evidence(),
            ensure_ascii=False,
            sort_keys=True,
            indent=None if arguments.compact else 2,
        )
    )


if __name__ == "__main__":
    main()
