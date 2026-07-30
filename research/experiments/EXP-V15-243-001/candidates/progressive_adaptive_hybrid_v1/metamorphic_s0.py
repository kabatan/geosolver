#!/usr/bin/env python3
"""Generated truth-free S0 for the adaptive progressive/deep hybrid."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np


HERE = Path(__file__).resolve().parent
BASE_S0_PATH = HERE.parent / "progressive_local_budget_v1" / "metamorphic_s0.py"
BASE_S0_SHA256 = "f55683bebc95b54b5f90a4e028f564ad708bfc0d9c9a05d0d5417002df532ad8"


def _load(name: str, path: Path, expected_sha256: str | None = None):
    payload = path.read_bytes()
    if expected_sha256 is not None and hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise RuntimeError(f"hash-bound S0 dependency changed: {path}")
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


CANDIDATE = _load("geotarget_adaptive_hybrid_s0_candidate", HERE / "candidate.py")
BASE_S0 = _load(
    "geotarget_adaptive_hybrid_base_metamorphic_s0",
    BASE_S0_PATH,
    BASE_S0_SHA256,
)
BASE_S0.CANDIDATE = CANDIDATE
BASE_S0.PROFILES = (CANDIDATE.PROFILE,)
PROFILES = BASE_S0.PROFILES


def equivalent_run(profile: str, variant: str):
    """Run an equivalent narrow basin with block-interleaved handoffs."""

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

    proposals = BASE_S0.starts(count, transform)
    clock = BASE_S0.Clock()

    def runner(spec, allowance, deadline, checkpoint):
        del deadline, checkpoint
        clock.now += 0.001
        canonical = np.asarray(inverse(np.asarray(spec.point, dtype=float)))
        residual = residual_scale * (canonical - target)
        residual = residual[residual_permutation]
        distance = float(np.linalg.norm(residual, ord=np.inf))
        residual_inf = (
            1.0e-20
            if distance <= BASE_S0.NARROW_BASIN_RADIUS
            else BASE_S0.OFF_BASIN_RESIDUAL_FLOOR + distance
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
    trace = BASE_S0._decision_trace(result)
    first = [
        record
        for record in result.records
        if record.phase == "ORDINAL_FIRST_SERVICE"
    ]
    assert tuple(record.start_ordinal for record in first) == tuple(range(count))
    assert result.activation["minimum_service_complete"] is True
    assert any(
        record.start_ordinal == 31
        and record.rung_callback_cap == CANDIDATE.RUNG_CALLBACK_CAPS[-1]
        for record in result.records
    )
    assert result.callbacks_used == sum(
        record.callbacks_used for record in result.records
    )
    assert result.activation["counter_cauchy_service_floor_holds"] is True
    return result, trace


BASE_S0.equivalent_run = equivalent_run


def demonstrated_starvation_handoff_run() -> dict[str, object]:
    """A useful preempted probe is deepened, but keeps its demonstrated cap."""

    proposals = BASE_S0.starts(8)
    clock = BASE_S0.Clock()
    calls = {ordinal: 0 for ordinal in range(8)}

    def runner(spec, allowance, deadline, checkpoint):
        del checkpoint
        calls[spec.ordinal] += 1
        if spec.ordinal == 7 and calls[7] == 1:
            clock.now = deadline
            return CANDIDATE.RungOutcome(
                spec.point.copy(),
                CANDIDATE.Assessment(True, True, 1.0e-20, 0.0),
                min(allowance, 1),
                "PREEMPTED_WITH_USEFUL_ENDPOINT",
                completed_before_deadline=False,
                endpoint_observed_before_deadline=True,
            )
        clock.now += 0.001
        return CANDIDATE.RungOutcome(
            spec.point.copy(),
            CANDIDATE.Assessment(
                True,
                True,
                1.0e-20 if spec.ordinal == 7 else float(100 + spec.ordinal),
                0.0,
            ),
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
    assert [record.rung_callback_cap for record in lane] == [64, 600]
    assert lane[0].status.startswith("INCOMPLETE_PREDEADLINE_EVIDENCE:")
    assert lane[-1].attempt_wall_cap_seconds <= 4.0
    return {
        "start_ordinal": 7,
        "rungs": [record.rung_callback_cap for record in lane],
        "deep_handoff_wall_cap_seconds": lane[-1].attempt_wall_cap_seconds,
        "demonstrated_starvation_remains_capped": True,
        "useful_preempted_probe_not_discarded": True,
    }


def build_evidence() -> dict[str, object]:
    evidence = BASE_S0.build_evidence()
    evidence["schema_version"] = (
        "geotarget.progressive-adaptive-hybrid-metamorphic-s0/v1"
    )
    evidence["candidate_sha256"] = hashlib.sha256(
        (HERE / "candidate.py").read_bytes()
    ).hexdigest()
    evidence["base_metamorphic_harness_sha256"] = BASE_S0_SHA256
    evidence["formal_or_benchmark_truth_used"] = False
    for profile in PROFILES:
        result, _trace = BASE_S0.equivalent_run(profile, "base")
        deep = [
            record
            for record in result.records
            if record.phase == "ADAPTIVE_HANDOFF"
        ]
        target_lane = [
            record for record in result.records if record.start_ordinal == 31
        ]
        probe_by_start = {
            record.start_ordinal: record
            for record in result.records
            if record.phase == "ORDINAL_FIRST_SERVICE"
        }
        row = evidence["profiles"][profile]
        first_probes = [
            record
            for record in result.records
            if record.phase == "ORDINAL_FIRST_SERVICE"
        ]
        row["iid_regular_first_service_complete"] = all(
            record.phase == "ORDINAL_FIRST_SERVICE"
            for record in first_probes
            if not record.insurance
        )
        row["hybrid_reopen_gate"] = {
            "target_direct_rungs": [
                record.rung_callback_cap for record in target_lane
            ],
            "target_handoff_reason": result.activation[
                "ambiguous_or_improving_selected"
            ]
            > 0,
            "target_deep_service_not_limited_to_probe_wall_cap": (
                target_lane[-1].attempt_wall_cap_seconds > 4.0
            ),
            "completed_probe_handoffs_uncapped": all(
                record.attempt_wall_cap_seconds > 4.0
                for record in deep
                if probe_by_start[record.start_ordinal].completed_before_deadline
            ),
            "handoff_selected_count": result.activation[
                "handoff_selected_count"
            ],
            "baseline_handoff_selected": result.activation[
                "baseline_handoff_selected"
            ],
            "insurance_handoff_selected": result.activation[
                "insurance_handoff_selected"
            ],
            "counter_cauchy_service_floor_holds": result.activation[
                "counter_cauchy_service_floor_holds"
            ],
        }
        assert row["hybrid_reopen_gate"]["target_direct_rungs"] == [64, 600]
        assert row["hybrid_reopen_gate"][
            "target_deep_service_not_limited_to_probe_wall_cap"
        ]
        assert row["hybrid_reopen_gate"]["completed_probe_handoffs_uncapped"]
    evidence["demonstrated_starvation_handoff"] = (
        demonstrated_starvation_handoff_run()
    )
    evidence["status"] = "PASS"
    return evidence


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
