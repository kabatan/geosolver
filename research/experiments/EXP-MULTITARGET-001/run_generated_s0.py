#!/usr/bin/env python3
"""Deterministic generated multi-target S0 for the tail scheduler."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import time

import candidate


@dataclass(frozen=True)
class Endpoint:
    endpoint: tuple[float, ...]
    endpoint_sha256: str
    residual_inf: float
    provisional_target: float
    cluster_ordinal: int
    cluster_rank: int


def endpoint(
    panel: int,
    ordinal: int,
    *,
    target: float,
    cluster: int,
    rank: int,
) -> Endpoint:
    point = (float(panel), float(ordinal), target)
    digest = hashlib.sha256(repr(point).encode()).hexdigest()
    return Endpoint(
        point,
        digest,
        1.0e-12 * (ordinal + 1),
        target,
        cluster,
        rank,
    )


def authority(root: int) -> dict[str, object]:
    return {
        "authority_pass": True,
        "descriptor": {
            "minimal_polynomial_high_to_low": [1, -root],
            "selected_real_root_index": 0,
        },
    }


class SyntheticAuthorityBase:
    FINALIZE_RESERVE_SECONDS = 2.0
    MIN_HP_ATTEMPT_SECONDS = 3.0
    MAX_HP_ATTEMPT_SECONDS = 18.0
    MAX_RESTORATION_ATTEMPT_SECONDS = 12.0

    def __init__(self, outcomes: dict[str, dict[str, object]]) -> None:
        self.outcomes = outcomes

    @staticmethod
    def _normalized_target_distance(left: Endpoint, right: Endpoint) -> float:
        scale = max(abs(left.provisional_target), abs(right.provisional_target), 1.0)
        return abs(left.provisional_target - right.provisional_target) / scale

    @staticmethod
    def _configuration_distance(left: Endpoint, right: Endpoint) -> float:
        difference = sum(
            (a - b) ** 2 for a, b in zip(left.endpoint, right.endpoint, strict=True)
        ) ** 0.5
        scale = sum(value * value for value in left.endpoint) ** 0.5
        scale += sum(value * value for value in right.endpoint) ** 0.5
        return difference / max(scale, 1.0)

    @staticmethod
    def _primary_tranche_capacity(remaining: float, count: int) -> int:
        return candidate._tranche_capacity(remaining, count, 18.0, 3.0)

    @staticmethod
    def _select_primary_tranche(items, capacity):
        ordered = tuple(sorted(items, key=lambda item: item[1].residual_inf))
        return ordered[:capacity], ordered[capacity:]

    @staticmethod
    def _wave_attempt_seconds(remaining: float, count: int, maximum: float) -> float:
        admitted = min(maximum, remaining - 3.0 * (count - 1))
        return admitted if admitted >= 3.0 else 0.0

    @staticmethod
    def _descriptor_key(descriptor):
        return json.dumps(descriptor, sort_keys=True, separators=(",", ":"))

    def _run_hp_candidate(self, **kwargs):
        return self.outcomes[kwargs["candidate"].endpoint_sha256]

    @staticmethod
    def _run_restoration_candidate(**_kwargs):
        return {"authority_pass": False, "descriptor": None}


def main() -> None:
    family_counts = {
        "distinct_primary_clusters": 0,
        "same_provisional_cluster": 0,
        "exact_descriptor_duplicate": 0,
    }
    control_descriptors = 0
    candidate_descriptors = 0
    candidate_false_descriptors = 0
    post_first_attempt_panels = 0
    same_cluster_alternate_panels = 0

    for panel in range(100):
        if panel < 40:
            family = "distinct_primary_clusters"
            items = (
                endpoint(panel, 0, target=0.0, cluster=0, rank=0),
                endpoint(panel, 1, target=100.0, cluster=1, rank=0),
            )
            roots = (panel * 2 + 1, panel * 2 + 2)
        elif panel < 80:
            family = "same_provisional_cluster"
            items = (
                endpoint(panel, 0, target=10.0, cluster=0, rank=0),
                endpoint(panel, 1, target=10.0 + 1.0e-10, cluster=0, rank=1),
            )
            roots = (panel * 2 + 1, panel * 2 + 2)
        else:
            family = "exact_descriptor_duplicate"
            items = (
                endpoint(panel, 0, target=10.0, cluster=0, rank=0),
                endpoint(panel, 1, target=10.0 + 1.0e-10, cluster=0, rank=1),
            )
            roots = (panel + 1, panel + 1)
        family_counts[family] += 1
        outcomes = {
            item.endpoint_sha256: authority(root)
            for item, root in zip(items, roots, strict=True)
        }
        base = SyntheticAuthorityBase(outcomes)
        attempts, descriptors, schedule = candidate.service_candidates(
            base,
            source=Path("generated-source.json"),
            source_sha256=hashlib.sha256(f"panel-{panel}".encode()).hexdigest(),
            candidates=items,
            cpu=0,
            output=Path("generated-output") / str(panel),
            hard_deadline=time.monotonic() + 40.0,
        )
        expected = len(set(roots))
        candidate_descriptors += len(descriptors)
        candidate_false_descriptors += max(0, len(descriptors) - expected)
        # The S0 control models the failure being corrected: stop after the
        # first authority, or suppress a same-cluster alternate after success.
        control_descriptors += 1
        post_first_attempt_panels += int(schedule["attempts_after_first_authority"] > 0)
        same_cluster_alternate_panels += int(
            family != "distinct_primary_clusters" and len(attempts) == 2
        )

    result = {
        "schema": "geotarget.exp-multitarget-001-generated-s0/v1",
        "panel_count": 100,
        "family_counts": family_counts,
        "control_model": "stop-after-first-or-same-cluster-success-suppression",
        "control_distinct_exact_descriptors": control_descriptors,
        "candidate_distinct_exact_descriptors": candidate_descriptors,
        "candidate_gain": candidate_descriptors - control_descriptors,
        "candidate_false_descriptors": candidate_false_descriptors,
        "panels_with_attempt_after_first_authority": post_first_attempt_panels,
        "same_cluster_panels_serving_alternate": same_cluster_alternate_panels,
        "canonical_authority_replaced": False,
        "truth_case_family_known_target_count_runtime_input": False,
    }
    if result != {
        "schema": "geotarget.exp-multitarget-001-generated-s0/v1",
        "panel_count": 100,
        "family_counts": {
            "distinct_primary_clusters": 40,
            "same_provisional_cluster": 40,
            "exact_descriptor_duplicate": 20,
        },
        "control_model": "stop-after-first-or-same-cluster-success-suppression",
        "control_distinct_exact_descriptors": 100,
        "candidate_distinct_exact_descriptors": 180,
        "candidate_gain": 80,
        "candidate_false_descriptors": 0,
        "panels_with_attempt_after_first_authority": 100,
        "same_cluster_panels_serving_alternate": 60,
        "canonical_authority_replaced": False,
        "truth_case_family_known_target_count_runtime_input": False,
    }:
        raise AssertionError(result)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
