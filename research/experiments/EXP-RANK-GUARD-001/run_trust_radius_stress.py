#!/usr/bin/env python3
"""Generated-only ablation of weak-direction trust-radius policies."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Mapping, Sequence

import numpy as np


HERE = Path(__file__).resolve().parent
ADAPTER_PATH = HERE / "arms/shared/charted_search_adapter.py"
TRUST_ADAPTER_PATH = HERE / "arms/shared/trusted_search_adapter.py"
V2_ARM_MANIFEST = HERE / "arms/charted-weak-trust-v2/arm.json"
AFFINE_WIDTHS = (1.0e-9, 1.0, 1.0e9)
RANK_RATIOS = (1.0e-7, 1.0e-4, 1.0e-2, 8.0e-2)
CONTROL_RADII = (0.25, 0.0625)
POLICY_NAMES = (
    "fixed_control",
    "fixed_conservative",
    "rank_scaled",
    "bound_slack_scaled",
    "bound_slack_times_rank",
    "near_boundary_guard_rank",
)
BASIN_RELATIVE_TOLERANCE = 0.22
BASIN_ABSOLUTE_TOLERANCE = 0.006


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


ADAPTER = _load("stress_exp_rank_guard_001_adapter", ADAPTER_PATH)
TRUST = _load("stress_exp_rank_guard_001_trusted_adapter", TRUST_ADAPTER_PATH)


@dataclass(frozen=True)
class Observation:
    residual: np.ndarray
    finite: bool
    semantics_valid: bool
    violation_vector: np.ndarray


@dataclass(frozen=True)
class StressSpecification:
    family: str
    width: float
    anchor_fraction: float
    rank_ratio: float
    semantic_guard_radius: float
    basin_radius: float


class StressCase:
    dimension = 3

    def __init__(self, specification: StressSpecification):
        self.specification = specification
        width = float(specification.width)
        self.lower = np.array([-2.0 * width, -0.5 * width, 4.0 * width])
        self.upper = np.array([3.0 * width, 2.5 * width, 9.0 * width])
        fractions = np.array([0.43, 0.58, specification.anchor_fraction])
        self.anchor = self.lower + (self.upper - self.lower) * fractions
        self.anchor_chart = ADAPTER._to_chart(
            self.anchor, self.lower, self.upper
        )
        self.callbacks = 0

    def displacement(self, point: Sequence[float]) -> np.ndarray:
        return (
            ADAPTER._to_chart(np.asarray(point, dtype=float), self.lower, self.upper)
            - self.anchor_chart
        )

    def evaluate(self, point: Sequence[float]) -> Observation:
        self.callbacks += 1
        values = np.asarray(point, dtype=float)
        displacement = self.displacement(values)
        guard_violation = max(
            0.0,
            abs(float(displacement[2]))
            - self.specification.semantic_guard_radius,
        )
        strict = bool(
            np.all(np.isfinite(values))
            and np.all(values > self.lower)
            and np.all(values < self.upper)
        )
        residual = np.array(
            [
                2.0 * displacement[0],
                displacement[1],
                self.specification.rank_ratio * displacement[2],
            ],
            dtype=float,
        )
        return Observation(
            residual=residual,
            finite=bool(np.all(np.isfinite(residual))),
            semantics_valid=bool(strict and guard_violation == 0.0),
            violation_vector=np.array([guard_violation]),
        )


def _rank_confidence(ratio: float) -> float:
    normalized = min(1.0, max(0.0, ratio / ADAPTER.WEAK_STRONG_RATIO_MAX))
    return math.sqrt(max(0.05, 1.0 - normalized))


def _bound_headroom(
    anchor: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    direction: np.ndarray,
) -> float:
    coordinate_headroom = np.ones(anchor.size, dtype=float)
    two_sided = np.isfinite(lower) & np.isfinite(upper)
    if np.any(two_sided):
        fraction = (anchor[two_sided] - lower[two_sided]) / (
            upper[two_sided] - lower[two_sided]
        )
        coordinate_headroom[two_sided] = np.clip(
            2.0 * np.minimum(fraction, 1.0 - fraction), 0.0, 1.0
        )
    # One-sided intervals have no source-independent affine scale, so they
    # conservatively retain the fixed-control radius.
    weights = np.square(np.asarray(direction, dtype=float))
    return float(np.clip(np.dot(weights, coordinate_headroom), 0.0, 1.0))


def _policy_radii(name: str, *, rank_ratio: float, bound_headroom: float):
    confidence = _rank_confidence(rank_ratio)
    if name == "fixed_control":
        return CONTROL_RADII
    if name == "fixed_conservative":
        return (0.125, 0.03125)
    if name == "rank_scaled":
        outer = float(np.clip(0.25 * confidence, 0.03125, 0.25))
    elif name == "bound_slack_scaled":
        outer = float(np.clip(0.25 * math.sqrt(bound_headroom), 0.03125, 0.25))
    elif name == "bound_slack_times_rank":
        outer = float(
            np.clip(
                0.25 * math.sqrt(bound_headroom) * confidence,
                0.03125,
                0.25,
            )
        )
    elif name == "near_boundary_guard_rank":
        if bound_headroom >= 0.1:
            return CONTROL_RADII
        outer = float(
            np.clip(
                0.25 * math.sqrt(bound_headroom) * confidence,
                0.03125,
                0.25,
            )
        )
    else:
        raise ValueError(f"unknown radius policy: {name}")
    return (outer, outer / 4.0)


def _proposals(
    case: StressCase, policy_name: str
) -> tuple[tuple[np.ndarray, ...], Mapping[str, float]]:
    evidence = ADAPTER._jacobian_pair(
        case, case.anchor, case.lower, case.upper
    )
    if evidence is None:
        return (), {
            "rank_ratio": math.inf,
            "bound_headroom": 0.0,
            "outer_radius": 0.0,
            "inner_radius": 0.0,
        }
    _residual, coarse, fine = evidence
    direction = ADAPTER._stable_weak_direction(coarse, fine)
    if direction is None:
        return (), {
            "rank_ratio": math.inf,
            "bound_headroom": 0.0,
            "outer_radius": 0.0,
            "inner_radius": 0.0,
        }
    singular_values = np.linalg.svd(fine, compute_uv=False)
    rank_ratio = float(singular_values[-1] / singular_values[-2])
    headroom = _bound_headroom(
        case.anchor, case.lower, case.upper, direction
    )
    radii = _policy_radii(
        policy_name, rank_ratio=rank_ratio, bound_headroom=headroom
    )
    chart = ADAPTER._to_chart(case.anchor, case.lower, case.upper)
    proposals: list[np.ndarray] = []
    for radius in radii:
        pair = (
            ADAPTER._from_chart(
                chart + radius * direction, case.lower, case.upper
            ),
            ADAPTER._from_chart(
                chart - radius * direction, case.lower, case.upper
            ),
        )
        observations = [case.evaluate(point) for point in pair]
        if all(observation.semantics_valid for observation in observations):
            proposals.extend(np.asarray(point, dtype=float).copy() for point in pair)
    return tuple(proposals), {
        "rank_ratio": rank_ratio,
        "bound_headroom": headroom,
        "outer_radius": radii[0],
        "inner_radius": radii[1],
    }


def _covered(case: StressCase, proposals: Sequence[np.ndarray]) -> bool:
    target = case.specification.basin_radius
    tolerance = max(BASIN_ABSOLUTE_TOLERANCE, BASIN_RELATIVE_TOLERANCE * target)
    return any(
        abs(abs(float(case.displacement(point)[2])) - target) <= tolerance
        for point in proposals
    )


def _specifications() -> list[StressSpecification]:
    specifications: list[StressSpecification] = []
    for width in AFFINE_WIDTHS:
        for ratio in RANK_RATIOS:
            confidence = _rank_confidence(ratio)
            for fraction in (1.0e-6, 0.02, 0.15, 0.5):
                headroom = 2.0 * min(fraction, 1.0 - fraction)
                coupled = float(
                    np.clip(
                        0.25 * math.sqrt(headroom) * confidence,
                        0.015625,
                        0.25,
                    )
                )
                specifications.append(
                    StressSpecification(
                        family="guard_rank_coupled",
                        width=width,
                        anchor_fraction=fraction,
                        rank_ratio=ratio,
                        semantic_guard_radius=max(0.03, 1.5 * coupled),
                        basin_radius=coupled,
                    )
                )
            for target in (0.025, 0.045, 0.08, 0.14, 0.23):
                specifications.append(
                    StressSpecification(
                        family="basin_scale_independent",
                        width=width,
                        anchor_fraction=0.5,
                        rank_ratio=ratio,
                        semantic_guard_radius=0.3,
                        basin_radius=target,
                    )
                )
            for guard in (0.035, 0.055, 0.09, 0.15):
                specifications.append(
                    StressSpecification(
                        family="narrow_semantic_guard",
                        width=width,
                        anchor_fraction=0.35,
                        rank_ratio=ratio,
                        semantic_guard_radius=guard,
                        basin_radius=0.72 * guard,
                    )
                )
    return specifications


def run_stress() -> dict[str, object]:
    specifications = _specifications()
    aggregate: dict[str, Counter[str]] = {
        name: Counter() for name in POLICY_NAMES
    }
    by_family: dict[str, dict[str, Counter[str]]] = {
        name: defaultdict(Counter) for name in POLICY_NAMES
    }
    radius_ranges: dict[str, list[float]] = {name: [] for name in POLICY_NAMES}
    implementation_policy_parity = 0
    for specification in specifications:
        for policy_name in POLICY_NAMES:
            case = StressCase(specification)
            proposals, diagnostics = _proposals(case, policy_name)
            expected_callbacks = 1 + 4 * case.dimension + 2 * len(
                _policy_radii(
                    policy_name,
                    rank_ratio=specification.rank_ratio,
                    bound_headroom=1.0,
                )
            )
            strict = all(
                np.all(point > case.lower) and np.all(point < case.upper)
                for point in proposals
            )
            covered = _covered(case, proposals)
            counters = aggregate[policy_name]
            family = by_family[policy_name][specification.family]
            for target in (counters, family):
                target["cases"] += 1
                target["basin_covered"] += int(covered)
                target["strict_bound_safe"] += int(strict)
                target["work_exact"] += int(case.callbacks == expected_callbacks)
                target["proposal_count"] += len(proposals)
                target["tail_quota_ok"] += int(len(proposals) <= 4)
            radius_ranges[policy_name].append(diagnostics["outer_radius"])
            if policy_name == "near_boundary_guard_rank":
                actual = TRUST._trust_radii(
                    diagnostics["rank_ratio"], diagnostics["bound_headroom"]
                )
                expected = _policy_radii(
                    policy_name,
                    rank_ratio=diagnostics["rank_ratio"],
                    bound_headroom=diagnostics["bound_headroom"],
                )
                implementation_policy_parity += int(actual == expected)

    def records(source: Mapping[str, Counter[str]]):
        return {
            key: {
                "cases": values["cases"],
                "basin_covered": values["basin_covered"],
                "coverage_rate": values["basin_covered"] / values["cases"],
                "strict_bound_safe_cases": values["strict_bound_safe"],
                "exact_work_cases": values["work_exact"],
                "proposal_count": values["proposal_count"],
                "tail_quota_ok_cases": values["tail_quota_ok"],
            }
            for key, values in sorted(source.items())
        }

    aggregate_records = records(aggregate)
    family_records = {
        name: records(families) for name, families in sorted(by_family.items())
    }
    control = aggregate_records["fixed_control"]
    promotions: dict[str, dict[str, object]] = {}
    for name in POLICY_NAMES:
        if name == "fixed_control":
            continue
        candidate = aggregate_records[name]
        family_nonregression = all(
            family_records[name][family]["basin_covered"]
            >= family_records["fixed_control"][family]["basin_covered"]
            for family in family_records["fixed_control"]
        )
        safety_and_work = bool(
            candidate["strict_bound_safe_cases"] == candidate["cases"]
            and candidate["exact_work_cases"] == candidate["cases"]
            and candidate["tail_quota_ok_cases"] == candidate["cases"]
        )
        requested_mechanism = name in {
            "bound_slack_times_rank",
            "near_boundary_guard_rank",
        }
        promotions[name] = {
            "aggregate_coverage_delta": (
                candidate["basin_covered"] - control["basin_covered"]
            ),
            "all_generated_families_nonregressing": family_nonregression,
            "strict_safety_work_and_quota_nonregression": safety_and_work,
            "uses_requested_guard_slack_times_rank_scale": requested_mechanism,
            "eligible_for_v2_arm": bool(
                candidate["basin_covered"] > control["basin_covered"]
                and family_nonregression
                and safety_and_work
                and requested_mechanism
            ),
        }
    eligible_winners = [
        name for name, row in promotions.items() if row["eligible_for_v2_arm"]
    ]
    winner = (
        max(
            eligible_winners,
            key=lambda name: int(promotions[name]["aggregate_coverage_delta"]),
        )
        if eligible_winners
        else None
    )
    manifest = json.loads(V2_ARM_MANIFEST.read_text(encoding="utf-8"))
    entrypoint = V2_ARM_MANIFEST.parent / manifest["entrypoint"]
    actual_mechanism_hash = hashlib.sha256(entrypoint.read_bytes()).hexdigest()
    arm_hash_valid = actual_mechanism_hash == manifest["mechanism_hash"]
    implementation_parity_valid = implementation_policy_parity == len(
        specifications
    )
    v2_arm_created = bool(
        winner == "near_boundary_guard_rank"
        and arm_hash_valid
        and implementation_parity_valid
    )
    payload: dict[str, object] = {
        "schema_version": "geotarget.exp-rank-guard-001-trust-radius-stress/v1",
        "status": "PASS",
        "generated_only": True,
        "formal_case_result_scorer_truth_or_id_used": False,
        "formal_aggregate_used_only_as_motivation": {
            "score_relation": "tie",
            "safety": "clean",
            "activation_fraction": "5/24",
            "proposal_count": 20,
            "case_ids_received": False,
        },
        "stress_design": {
            "case_count": len(specifications),
            "families": sorted({item.family for item in specifications}),
            "affine_widths": list(AFFINE_WIDTHS),
            "rank_ratios": list(RANK_RATIOS),
            "candidate_observables": [
                "finite source bounds",
                "anchor position",
                "h/h2 Jacobian singular ratio",
                "semantic validity of each complete symmetric pair",
            ],
            "unavailable_positive_guard_margin": True,
            "radii_per_policy": 2,
            "maximum_generated_proposals_per_case": 4,
            "tail_replacement_fraction_unchanged": 0.25,
        },
        "aggregate": aggregate_records,
        "by_family": family_records,
        "outer_radius_ranges": {
            name: {
                "minimum": min(values),
                "maximum": max(values),
            }
            for name, values in radius_ranges.items()
        },
        "promotion_gates": promotions,
        "implementation_policy_parity_cases": implementation_policy_parity,
        "implementation_policy_parity_expected": len(specifications),
        "v2_arm": {
            "id": manifest["id"],
            "entrypoint": str(entrypoint.relative_to(HERE)),
            "mechanism_hash": actual_mechanism_hash,
            "manifest_hash_matches": arm_hash_valid,
            "selected_policy_matches_implementation": implementation_parity_valid,
        },
        "v2_arm_created": v2_arm_created,
        "selected_policy": winner,
        "disposition": (
            "PROMOTE_GENERATED_WINNER"
            if v2_arm_created
            else "CLOSE_NO_FAMILY_NONREGRESSING_GENERATED_WINNER"
        ),
        "blockers": [
            "the frozen observation exposes zero violation for a valid guard, not positive guard headroom",
            "bound headroom is not a substitute for unrelated semantic-guard slack",
            "rank singular ratio alone does not identify an unknown basin distance",
        ],
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    payload["evidence_sha256"] = hashlib.sha256(canonical).hexdigest()
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = run_stress()
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(text, end="")
    else:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
