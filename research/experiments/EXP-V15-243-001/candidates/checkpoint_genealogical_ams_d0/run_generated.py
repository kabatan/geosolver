#!/usr/bin/env python3
"""Candidate-private equal-callback D0 generated experiment.

This file intentionally uses no repository scorer, truth manifest, or common
checkpoint/scheduler framework.  Generated-family root metadata is consulted
only after a fresh source replay, for reporting the D0 mechanism check.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Callable, Sequence

import numpy as np

import candidate
from generated_cases import (
    PANEL,
    GeneratedSource,
    cluster_replayed,
    runtime_factory,
)


SCHEMA = "geotarget.exp-v15-243.checkpoint-genealogical-ams-generated/v1"


@dataclass(frozen=True)
class PoolResult:
    callbacks: int
    endpoints: tuple[np.ndarray, ...]
    safe: tuple[np.ndarray, ...]
    starts_created: int
    callback_free_terminal_notices: int


def _capture(
    trajectory: candidate.Trajectory,
    replay: Callable[[Sequence[float]], bool],
    endpoints: list[np.ndarray],
    safe: list[np.ndarray],
) -> None:
    state = trajectory.state
    seen: set[bytes] = set()
    for endpoint in (state.current, state.best):
        if endpoint is None:
            continue
        point = np.asarray(endpoint.x, dtype=float).copy()
        key = point.tobytes()
        if key in seen:
            continue
        seen.add(key)
        endpoints.append(point)
        try:
            accepted = bool(replay(point))
        except Exception:
            accepted = False
        if accepted:
            safe.append(point)


def run_independent_pool(
    make_runtime: candidate.RuntimeFactory,
    *,
    replay: candidate.Replay,
    callback_budget: int,
    seed: int,
    population: int,
) -> PoolResult:
    """Spend exactly ``callback_budget`` source calls without cloning."""

    if callback_budget <= 0 or population <= 0:
        raise ValueError("positive callback budget and population required")
    trajectories = [
        candidate._new_trajectory(
            ordinal,
            make_runtime(ordinal),
            max_callbacks=max(64, callback_budget),
            rng_seed=seed * 1009 + ordinal,
        )
        for ordinal in range(population)
    ]
    next_id = population
    callbacks = 0
    terminal_notices = 0
    cursor = 0
    endpoints: list[np.ndarray] = []
    safe: list[np.ndarray] = []
    free_transition_guard = 0
    while callbacks < callback_budget:
        slot = cursor % population
        cursor += 1
        trajectory = trajectories[slot]
        if trajectory.state.terminal:
            trajectory = candidate._new_trajectory(
                next_id,
                make_runtime(next_id),
                max_callbacks=max(64, callback_budget),
                rng_seed=seed * 1009 + next_id,
            )
            next_id += 1
            trajectories[slot] = trajectory
        did_charge, _new_passage = candidate._advance_charged(trajectory)
        if did_charge:
            callbacks += 1
            free_transition_guard = 0
            _capture(trajectory, replay, endpoints, safe)
        else:
            terminal_notices += 1
            free_transition_guard += 1
            _capture(trajectory, replay, endpoints, safe)
            if free_transition_guard > population * 3:
                raise RuntimeError("independent pool made no charged progress")
    return PoolResult(
        callbacks,
        tuple(endpoints),
        tuple(safe),
        next_id,
        terminal_notices,
    )


def _physical_points(
    source: GeneratedSource, points: Sequence[np.ndarray]
) -> list[list[float]]:
    return [source.physical(point).tolist() for point in cluster_replayed(source, points)]


def _unmatched(
    left: Sequence[Sequence[float]],
    right: Sequence[Sequence[float]],
    *,
    tolerance: float = 2.0e-4,
) -> list[list[float]]:
    right_arrays = [np.asarray(item, dtype=float) for item in right]
    return [
        list(map(float, item))
        for item in left
        if all(
            float(np.linalg.norm(np.asarray(item, dtype=float) - other)) > tolerance
            for other in right_arrays
        )
    ]


def run_arm_pair(
    spec,
    seed: int,
    *,
    total_callbacks: int,
    coordinate_signed_permutation: bool = False,
    residual_swap_sign: bool = False,
) -> dict[str, object]:
    baseline_budget, side_budget = candidate.split_budget(total_callbacks)

    # Control and candidate get distinct evaluator objects but identical
    # source transforms, starts, kernel, seed, and charged callback budgets.
    control_source = GeneratedSource(
        spec,
        seed,
        coordinate_signed_permutation=coordinate_signed_permutation,
        residual_swap_sign=residual_swap_sign,
    )
    candidate_source = GeneratedSource(
        spec,
        seed,
        coordinate_signed_permutation=coordinate_signed_permutation,
        residual_swap_sign=residual_swap_sign,
    )
    control_baseline = run_independent_pool(
        runtime_factory(control_source, baseline=True),
        replay=control_source.replay,
        callback_budget=baseline_budget,
        seed=seed,
        population=12,
    )
    candidate_baseline = run_independent_pool(
        runtime_factory(candidate_source, baseline=True),
        replay=candidate_source.replay,
        callback_budget=baseline_budget,
        seed=seed,
        population=12,
    )
    control_side = run_independent_pool(
        runtime_factory(control_source, baseline=False),
        replay=control_source.replay,
        callback_budget=side_budget,
        seed=seed + 400_009,
        population=4,
    )
    ams_side = candidate.run_ams_side(
        runtime_factory(candidate_source, baseline=False),
        replay=candidate_source.replay,
        callback_budget=side_budget,
        seed=seed + 400_009,
        population=4,
        breadth_callbacks=5,
        branch_quantum=3,
    )
    if control_source.callbacks != total_callbacks:
        raise AssertionError(
            f"control callbacks {control_source.callbacks} != {total_callbacks}"
        )
    if candidate_source.callbacks != total_callbacks:
        raise AssertionError(
            f"candidate callbacks {candidate_source.callbacks} != {total_callbacks}"
        )
    if ams_side.charged_callbacks != side_budget:
        raise AssertionError("AMS used a non-exact callback budget")

    control_points = _physical_points(
        control_source, control_baseline.safe + control_side.safe
    )
    candidate_points = _physical_points(
        candidate_source,
        candidate_baseline.safe + ams_side.replayed_safe_endpoints,
    )
    gains = _unmatched(candidate_points, control_points)
    losses = _unmatched(control_points, candidate_points)
    genealogy = [
        {
            **asdict(event),
            "level": asdict(event.level),
        }
        for event in ams_side.genealogy
    ]
    return {
        "family": spec.name,
        "category": spec.category,
        "seed": seed,
        "transform": {
            "coordinate_signed_permutation": coordinate_signed_permutation,
            "residual_swap_sign": residual_swap_sign,
        },
        "budget": {
            "total": total_callbacks,
            "baseline": baseline_budget,
            "side": side_budget,
            "baseline_fraction": baseline_budget / total_callbacks,
            "side_fraction": side_budget / total_callbacks,
        },
        "callbacks": {
            "control": control_source.callbacks,
            "candidate": candidate_source.callbacks,
            "candidate_ams": ams_side.charged_callbacks,
        },
        "control_safe_roots": control_points,
        "candidate_safe_roots": candidate_points,
        "unique_safe_root_gains": gains,
        "safe_root_losses": losses,
        "genealogy": genealogy,
        "genealogy_events": len(genealogy),
        "first_passage_count": ams_side.first_passage_count,
        "tangent_branches": sum(
            event.tangent_source == "weak-right-singular-vector"
            for event in ams_side.genealogy
        ),
        "positive_perturbations": sum(
            event.perturbation_norm_z > 0.0 for event in ams_side.genealogy
        ),
        "branch_fail_closed_events": ams_side.invalid_or_opaque_events,
        "source_replay_rejections": ams_side.source_replay_rejections,
    }


def _point_sets_equal(
    left: Sequence[Sequence[float]], right: Sequence[Sequence[float]]
) -> bool:
    return not _unmatched(left, right) and not _unmatched(right, left)


def summarize(runs: Sequence[dict[str, object]]) -> dict[str, object]:
    ordinary = [item for item in runs if not any(item["transform"].values())]
    metamorphic = [item for item in runs if any(item["transform"].values())]
    transformed_by_key = {
        (item["family"], item["seed"]): item for item in metamorphic
    }
    meta_checks = []
    for original in ordinary:
        transformed = transformed_by_key.get((original["family"], original["seed"]))
        if transformed is None:
            continue
        meta_checks.append(
            {
                "family": original["family"],
                "seed": original["seed"],
                "control_invariant": _point_sets_equal(
                    original["control_safe_roots"], transformed["control_safe_roots"]
                ),
                "candidate_invariant": _point_sets_equal(
                    original["candidate_safe_roots"],
                    transformed["candidate_safe_roots"],
                ),
            }
        )

    positive = [item for item in ordinary if item["category"] == "positive"]
    negative = [item for item in ordinary if item["category"] != "positive"]
    family_gain_counts = {
        family: sum(
            bool(item["unique_safe_root_gains"])
            for item in positive
            if item["family"] == family
        )
        for family in sorted({item["family"] for item in positive})
    }
    unique_gain_families = [
        family for family, count in family_gain_counts.items() if count > 0
    ]
    zero_losses = all(not item["safe_root_losses"] for item in ordinary)
    zero_false = all(
        not item["control_safe_roots"] and not item["candidate_safe_roots"]
        for item in negative
    )
    equal_callbacks = all(
        item["callbacks"]["control"] == item["callbacks"]["candidate"]
        for item in runs
    )
    genealogy_activation = sum(item["genealogy_events"] for item in ordinary)
    metamorphic_pass = bool(meta_checks) and all(
        item["control_invariant"] and item["candidate_invariant"]
        for item in meta_checks
    )
    gates = {
        "at_least_three_positive_families": len(family_gain_counts) >= 3,
        "at_least_two_unique_gain_families": len(unique_gain_families) >= 2,
        "zero_safe_root_loss": zero_losses,
        "zero_false_safe_root": zero_false,
        "equal_charged_callbacks": equal_callbacks,
        "genealogy_activated": genealogy_activation > 0,
        "metamorphic_invariance": metamorphic_pass,
    }
    return {
        "family_gain_seed_counts": family_gain_counts,
        "unique_gain_families": unique_gain_families,
        "total_unique_safe_root_gains": sum(
            len(item["unique_safe_root_gains"]) for item in positive
        ),
        "total_safe_root_losses": sum(
            len(item["safe_root_losses"]) for item in ordinary
        ),
        "false_safe_roots": sum(
            len(item["candidate_safe_roots"]) for item in negative
        ),
        "genealogy_events": genealogy_activation,
        "tangent_branches": sum(item["tangent_branches"] for item in ordinary),
        "branch_fail_closed_events": sum(
            item["branch_fail_closed_events"] for item in ordinary
        ),
        "metamorphic_checks": meta_checks,
        "gates": gates,
        "d0_pass": all(gates.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=8)
    parser.add_argument("--callbacks", type=int, default=384)
    parser.add_argument("--metamorphic-seeds", type=int, default=2)
    parser.add_argument(
        "--output", type=Path, default=Path(__file__).with_name("GENERATED_RESULT.json")
    )
    args = parser.parse_args()
    runs: list[dict[str, object]] = []
    for spec in PANEL:
        for seed in range(args.seeds):
            runs.append(run_arm_pair(spec, seed, total_callbacks=args.callbacks))
        if spec.category == "positive":
            for seed in range(min(args.seeds, args.metamorphic_seeds)):
                runs.append(
                    run_arm_pair(
                        spec,
                        seed,
                        total_callbacks=args.callbacks,
                        coordinate_signed_permutation=True,
                        residual_swap_sign=True,
                    )
                )
    payload = {
        "schema_version": SCHEMA,
        "mechanism": candidate.configuration_manifest(),
        "policy": {
            "candidate_private": True,
            "formal_cpus_0_through_6_used": False,
            "real_cases_or_truth_used": False,
            "common_checkpoint_framework_used": False,
        },
        "arguments": vars(args) | {"output": str(args.output)},
        "runs": runs,
        "summary": summarize(runs),
    }
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    return 0 if payload["summary"]["d0_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
