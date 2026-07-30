#!/usr/bin/env python3
"""Generated D0 evaluator; never imports the formal execute/scorer/truth stack."""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import time

import numpy as np

from candidate import (
    Config,
    portfolio_trace,
    run_branching_svgd,
    run_count_matched_immigration,
    run_deterministic_svgd,
)
from generated_cases import descriptors_from_points, make_problem


FAMILIES = ("axial", "elbow", "simplex")


def _lane_initial(problem, case_seed: int, lane: int) -> np.ndarray:
    return problem.initial_points(100_000 * case_seed + 997 * lane + 31)


def _join(results) -> np.ndarray:
    return np.concatenate([result.points for result in results], axis=0)


def evaluate_case(family: str, category: str, seed: int, presentation: str, scale: float):
    problem = make_problem(family, category, presentation=presentation, affine_scale=scale)
    config = Config()
    trace = portfolio_trace(4)
    assert trace.count("baseline") == 3 and trace.count("side") == 1
    common = [
        run_deterministic_svgd(
            _lane_initial(problem, seed, lane), problem.score, problem.source_valid,
            origin=problem.origin, scale=problem.scale, config=config,
        )
        for lane in range(3)
    ]
    side_initial = _lane_initial(problem, seed, 3)
    old_side = run_deterministic_svgd(
        side_initial, problem.score, problem.source_valid,
        origin=problem.origin, scale=problem.scale, config=config,
    )
    branching = run_branching_svgd(
        side_initial, problem.score, problem.source_valid,
        origin=problem.origin, scale=problem.scale,
        seed=200_000 * seed + 8191, config=config,
    )
    immigration = run_count_matched_immigration(
        side_initial, branching.telemetry.additions_by_generation,
        problem.score, problem.source_valid,
        origin=problem.origin, scale=problem.scale,
        seed=200_000 * seed + 104_729, config=config,
    )
    if branching.telemetry.population_counts != immigration.telemetry.population_counts:
        raise AssertionError("immigration control is not population-count matched")
    if branching.telemetry.score_calls != immigration.telemetry.score_calls:
        raise AssertionError("immigration control is not score-work matched")

    arm_results = {
        "old_deterministic": common + [old_side],
        "count_matched_immigration": common + [immigration],
        "branching_svgd": common + [branching],
    }
    descriptors = {}
    semantic_rejections = {}
    for arm, results in arm_results.items():
        found, rejected = descriptors_from_points(problem, _join(results))
        descriptors[arm] = found
        semantic_rejections[arm] = rejected
        if not found.issubset(problem.expected_descriptors):
            raise AssertionError("canonical replay emitted an invalid descriptor")

    return {
        "family": problem.public_family,
        "category": category,
        "seed": seed,
        "presentation": presentation,
        "affine_scale": scale,
        "scores": {arm: len(found) for arm, found in descriptors.items()},
        "descriptors": {arm: sorted(found) for arm, found in descriptors.items()},
        "semantic_rejections_before_emission": semantic_rejections,
        "expected_descriptors": sorted(problem.expected_descriptors),
        "invalid_emitted": 0,
        "crash": False,
        "branching_telemetry": asdict(branching.telemetry),
        "immigration_telemetry": asdict(immigration.telemetry),
        "quota": {"baseline": 0.75, "side": 0.25},
    }


def _aggregate_identity(rows):
    by_family = defaultdict(list)
    for row in rows:
        if row["category"] == "positive" and row["presentation"] == "identity" and row["affine_scale"] == 1.0:
            by_family[row["family"]].append(row)
    family_summary = {}
    qualifying = []
    for family, family_rows in sorted(by_family.items()):
        control_stats = {}
        family_ok = True
        for control in ("old_deterministic", "count_matched_immigration"):
            gains = sum(r["scores"]["branching_svgd"] > r["scores"][control] for r in family_rows)
            losses = sum(r["scores"]["branching_svgd"] < r["scores"][control] for r in family_rows)
            ties = len(family_rows) - gains - losses
            root_delta = sum(r["scores"]["branching_svgd"] - r["scores"][control] for r in family_rows)
            control_stats[control] = {
                "case_gains": gains,
                "case_losses": losses,
                "case_ties": ties,
                "root_count_delta": root_delta,
            }
            family_ok &= gains > 0 and losses == 0 and root_delta > 0
        family_summary[family] = {
            "cases": len(family_rows),
            "comparisons": control_stats,
            "qualifies": bool(family_ok),
        }
        if family_ok:
            qualifying.append(family)
    return family_summary, qualifying


def _metamorphic_summary(rows):
    positive = [r for r in rows if r["category"] == "positive"]
    grouped = defaultdict(lambda: defaultdict(list))
    for row in positive:
        grouped[row["family"]][(row["presentation"], row["affine_scale"])].append(
            row["scores"]["branching_svgd"]
        )
    summary = {}
    pass_all = True
    for family, variants in sorted(grouped.items()):
        baseline = float(np.mean(variants[("identity", 1.0)]))
        deltas = {}
        for variant, values in sorted(variants.items()):
            delta = float(np.mean(values) - baseline)
            deltas[f"{variant[0]}@{variant[1]:g}"] = delta
            pass_all &= abs(delta) <= 1.0
        summary[family] = {"identity_mean": baseline, "mean_root_count_deltas": deltas}
    return summary, bool(pass_all)


def run_suite():
    started = time.perf_counter()
    rows = []
    # Fixed before execution: this D0 performs no parameter/configuration search.
    for family in FAMILIES:
        for seed in range(16):
            rows.append(evaluate_case(family, "positive", seed, "identity", 1.0))
        for category in ("negative", "near_miss"):
            for seed in range(6):
                rows.append(evaluate_case(family, category, seed, "identity", 1.0))
        for presentation, affine_scale in (
            ("permutation", 1.0), ("reflection", 1.0), ("rotation", 1.0),
            ("identity", 0.2), ("identity", 7.0),
        ):
            for seed in range(8):
                rows.append(evaluate_case(family, "positive", seed, presentation, affine_scale))

    family_summary, qualifying = _aggregate_identity(rows)
    metamorphic, metamorphic_pass = _metamorphic_summary(rows)
    safety_pass = all(
        row["invalid_emitted"] == 0 and not row["crash"]
        and set(row["descriptors"]["branching_svgd"]).issubset(set(row["expected_descriptors"]))
        for row in rows
    )
    activation_pass = all(
        row["branching_telemetry"]["offspring_accepted"]["S"] > 0
        and row["branching_telemetry"]["offspring_attempted"]["O"] == 0
        and row["branching_telemetry"]["deaths"] == 0
        and row["branching_telemetry"]["unique_spine_checks"] == Config().generations + 1
        and row["branching_telemetry"]["population_counts"][-1] > row["branching_telemetry"]["population_counts"][0]
        for row in rows
    )
    go = len(qualifying) >= 2 and safety_pass and activation_pass and metamorphic_pass
    totals = {
        arm: sum(row["scores"][arm] for row in rows if row["category"] == "positive")
        for arm in ("old_deterministic", "count_matched_immigration", "branching_svgd")
    }
    return {
        "schema": "branching-svgd-cleanroom-d0-result-v1",
        "decision": "GO" if go else "STOP",
        "go_rule": "gain vs both controls and loss=0 in >=2 anonymous positive families; safety, activation, metamorphic pass",
        "formal_harness_used": False,
        "truth_boundary": "generated_cases.py only; candidate receives score and source-validity callables",
        "configuration_search_performed": False,
        "portfolio_quota": {"baseline": 0.75, "side": 0.25},
        "case_count": len(rows),
        "positive_descriptor_totals_all_presentations": totals,
        "family_summary_identity": family_summary,
        "qualifying_anonymous_families": qualifying,
        "safety": {
            "pass": safety_pass,
            "invalid_emitted": sum(r["invalid_emitted"] for r in rows),
            "crashes": sum(bool(r["crash"]) for r in rows),
            "negative_cases": sum(r["category"] == "negative" for r in rows),
            "near_miss_cases": sum(r["category"] == "near_miss" for r in rows),
            "semantic_rejections_before_emission": sum(r["semantic_rejections_before_emission"]["branching_svgd"] for r in rows),
        },
        "activation": {
            "pass": activation_pass,
            "branching_cases": len(rows),
            "spine_offspring": sum(r["branching_telemetry"]["offspring_accepted"]["S"] for r in rows),
            "explorer_offspring": sum(r["branching_telemetry"]["offspring_accepted"]["E"] for r in rows),
            "optimizer_offspring_attempted": sum(r["branching_telemetry"]["offspring_attempted"]["O"] for r in rows),
            "deaths": sum(r["branching_telemetry"]["deaths"] for r in rows),
            "old_particles_retained": sum(r["branching_telemetry"]["old_particles_retained"] for r in rows),
            "all_count_and_score_work_matched_to_immigration": all(
                r["branching_telemetry"]["population_counts"] == r["immigration_telemetry"]["population_counts"]
                and r["branching_telemetry"]["score_calls"] == r["immigration_telemetry"]["score_calls"]
                for r in rows
            ),
        },
        "metamorphic": {"pass": metamorphic_pass, "families": metamorphic},
        "runtime_seconds": time.perf_counter() - started,
        "environment": {
            "python": platform.python_version(), "numpy": np.__version__,
            "cpu_affinity_expected": "15",
        },
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--raw-output", type=Path)
    args = parser.parse_args()
    result = run_suite()
    rows = result.pop("rows")
    raw_payload = json.dumps(rows, indent=2, sort_keys=True) + "\n"
    result["raw_rows_sha256"] = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()
    if args.raw_output is not None:
        args.raw_output.parent.mkdir(parents=True, exist_ok=True)
        args.raw_output.write_text(raw_payload, encoding="utf-8")
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("decision", "case_count", "qualifying_anonymous_families", "runtime_seconds")}, indent=2))


if __name__ == "__main__":
    main()
