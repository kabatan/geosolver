#!/usr/bin/env python3
"""Truth-blind soft reservoir for expensive high-precision endpoint service.

The policy consumes only a provisional scalar target, an original-evaluator
residual, a configuration (only through pairwise distance), and a discovery
ordinal.  Bucketing is deliberately soft: every deferred record remains in a
deterministic aging schedule, so a Float64 merge can delay but never delete a
close distinct root.  A later high-precision descriptor mismatch splits the
bucket and promotes one unserved member from every new descriptor partition.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from statistics import median
from typing import Hashable, Mapping, Sequence


@dataclass(frozen=True)
class Candidate:
    record_id: str
    target: float
    residual: float
    configuration: tuple[float, ...]
    discovery_ordinal: int

    def __post_init__(self) -> None:
        if not self.record_id:
            raise ValueError("record_id must be nonempty")
        if not math.isfinite(self.target):
            raise ValueError("target must be finite")
        if not math.isfinite(self.residual) or self.residual < 0.0:
            raise ValueError("residual must be finite and nonnegative")
        if self.discovery_ordinal < 0:
            raise ValueError("discovery_ordinal must be nonnegative")
        if any(not math.isfinite(value) for value in self.configuration):
            raise ValueError("configuration must be finite")


@dataclass(frozen=True)
class SoftBucket:
    bucket_id: str
    member_ids: tuple[str, ...]
    champion_id: str
    service_order: tuple[str, ...]
    uncertainty_by_id: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class DescriptorSplit:
    mismatch: bool
    descriptor_groups: tuple[tuple[Hashable, tuple[str, ...]], ...]
    promoted_record_ids: tuple[str, ...]


def policy_document() -> dict[str, object]:
    """Return the frozen, truth-blind policy in hashable JSON form."""

    return {
        "schema_version": "geotarget.exp008-hp-soft-reservoir-policy/v1",
        "runtime_inputs": [
            "provisional_scalar_target",
            "original_evaluator_residual_inf",
            "scale_normalized_configuration_distance",
            "discovery_ordinal",
        ],
        "forbidden_runtime_inputs": [
            "truth",
            "known_target_count",
            "case_id",
            "family",
            "source_series",
        ],
        "target_scale": "max(median(abs(t)), median(abs(t-median(t))), Float64 ulp)",
        "base_uncertainty": "target_scale * sqrt(max(residual, Float64 epsilon)) + ulp(t)",
        "empirical_uncertainty": (
            "nearest configuration neighbour target gap, divided between the pair "
            "in proportion to sqrt(residual)"
        ),
        "soft_bucket": "connected components of overlapping target uncertainty intervals",
        "first_service": "minimum residual, then oldest discovery ordinal",
        "deferred_service": (
            "round-robin aging waves; within a bucket use scale-free target/configuration "
            "maximin diversity; every record is eventually serviced"
        ),
        "hp_feedback": (
            "different confirmed descriptors split a bucket; promote the best unserved "
            "record in every resulting descriptor partition"
        ),
        "tuned_numeric_thresholds": [],
        "source_or_problem_modification": False,
        "bounds_or_gauge_added": False,
    }


def policy_sha256() -> str:
    payload = json.dumps(
        policy_document(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _configuration_distance(left: Candidate, right: Candidate) -> float:
    if len(left.configuration) != len(right.configuration):
        raise ValueError("configuration dimensions differ")
    difference = math.sqrt(
        sum((a - b) * (a - b) for a, b in zip(left.configuration, right.configuration))
    )
    left_norm = math.sqrt(sum(value * value for value in left.configuration))
    right_norm = math.sqrt(sum(value * value for value in right.configuration))
    denominator = left_norm + right_norm
    if denominator == 0.0:
        return 0.0 if difference == 0.0 else math.inf
    return difference / denominator


def _target_scale(candidates: Sequence[Candidate]) -> float:
    values = [candidate.target for candidate in candidates]
    center = median(values)
    return max(
        median(abs(value) for value in values),
        median(abs(value - center) for value in values),
        max(math.ulp(value) for value in values),
    )


def _uncertainties(candidates: Sequence[Candidate]) -> dict[str, float]:
    scale = _target_scale(candidates)
    machine_epsilon = math.ulp(1.0)
    result: dict[str, float] = {}
    for index, candidate in enumerate(candidates):
        root_residual = math.sqrt(max(candidate.residual, machine_epsilon))
        uncertainty = scale * root_residual + math.ulp(candidate.target)
        if len(candidates) > 1:
            neighbour = min(
                (
                    other
                    for other_index, other in enumerate(candidates)
                    if other_index != index
                ),
                key=lambda other: (
                    _configuration_distance(candidate, other),
                    abs(candidate.target - other.target),
                    other.residual,
                    other.discovery_ordinal,
                    other.record_id,
                ),
            )
            neighbour_root_residual = math.sqrt(
                max(neighbour.residual, machine_epsilon)
            )
            denominator = root_residual + neighbour_root_residual
            local_share = (
                abs(candidate.target - neighbour.target)
                * root_residual
                / denominator
            )
            uncertainty = max(uncertainty, local_share)
        result[candidate.record_id] = uncertainty
    return result


def _pair_novelty(
    left: Candidate,
    right: Candidate,
    uncertainties: Mapping[str, float],
) -> float:
    target_denominator = max(
        uncertainties[left.record_id] + uncertainties[right.record_id],
        math.ulp(left.target),
        math.ulp(right.target),
    )
    target_separation = abs(left.target - right.target) / target_denominator
    return max(target_separation, _configuration_distance(left, right))


def _service_order(
    members: Sequence[Candidate], uncertainties: Mapping[str, float]
) -> tuple[str, ...]:
    champion = min(
        members,
        key=lambda item: (item.residual, item.discovery_ordinal, item.record_id),
    )
    serviced = [champion]
    unserved = {member.record_id: member for member in members if member != champion}
    while unserved:
        selected = min(
            unserved.values(),
            key=lambda candidate: (
                -min(
                    _pair_novelty(candidate, prior, uncertainties)
                    for prior in serviced
                ),
                candidate.discovery_ordinal,
                candidate.residual,
                candidate.record_id,
            ),
        )
        serviced.append(selected)
        del unserved[selected.record_id]
    return tuple(candidate.record_id for candidate in serviced)


def build_soft_buckets(candidates: Sequence[Candidate]) -> tuple[SoftBucket, ...]:
    """Build target-uncertainty buckets for one problem instance."""

    if not candidates:
        return ()
    if len({candidate.record_id for candidate in candidates}) != len(candidates):
        raise ValueError("record_id values must be unique")
    dimensions = {len(candidate.configuration) for candidate in candidates}
    if len(dimensions) != 1:
        raise ValueError("configuration dimensions differ")

    uncertainties = _uncertainties(candidates)
    intervals = sorted(
        (
            (
                candidate.target - uncertainties[candidate.record_id],
                candidate.target + uncertainties[candidate.record_id],
                candidate,
            )
            for candidate in candidates
        ),
        key=lambda row: (
            row[0],
            row[1],
            row[2].discovery_ordinal,
            row[2].record_id,
        ),
    )
    components: list[list[Candidate]] = []
    component_upper = -math.inf
    for lower, upper, candidate in intervals:
        if not components or lower > component_upper:
            components.append([candidate])
            component_upper = upper
        else:
            components[-1].append(candidate)
            component_upper = max(component_upper, upper)

    buckets = []
    for members in components:
        member_ids = tuple(sorted(member.record_id for member in members))
        digest = hashlib.sha256("\0".join(member_ids).encode("utf-8")).hexdigest()
        order = _service_order(members, uncertainties)
        buckets.append(
            SoftBucket(
                bucket_id=digest,
                member_ids=member_ids,
                champion_id=order[0],
                service_order=order,
                uncertainty_by_id=tuple(
                    sorted((record_id, uncertainties[record_id]) for record_id in member_ids)
                ),
            )
        )
    by_id = {candidate.record_id: candidate for candidate in candidates}
    return tuple(
        sorted(
            buckets,
            key=lambda bucket: (
                by_id[bucket.champion_id].discovery_ordinal,
                by_id[bucket.champion_id].residual,
                bucket.bucket_id,
            ),
        )
    )


def aging_waves(buckets: Sequence[SoftBucket]) -> tuple[tuple[str, ...], ...]:
    """Return fair service waves; their concatenation contains every record once."""

    if not buckets:
        return ()
    return tuple(
        tuple(
            bucket.service_order[depth]
            for bucket in buckets
            if depth < len(bucket.service_order)
        )
        for depth in range(max(len(bucket.service_order) for bucket in buckets))
    )


def split_on_descriptor_mismatch(
    bucket: SoftBucket,
    candidates: Mapping[str, Candidate],
    observations: Mapping[str, Hashable | None],
) -> DescriptorSplit:
    """Partition a bucket after HP feedback and promote each new partition.

    ``None`` is an HP failure/unknown, not a descriptor.  Such records and all
    unserved records are assigned to their closest confirmed descriptor anchor;
    if fewer than two descriptors exist, the original bucket remains intact.
    """

    confirmed: dict[Hashable, list[str]] = {}
    for record_id, descriptor in observations.items():
        if record_id not in bucket.member_ids:
            raise ValueError("observation is outside the bucket")
        if descriptor is not None:
            confirmed.setdefault(descriptor, []).append(record_id)
    if len(confirmed) < 2:
        descriptor = next(iter(confirmed), "UNRESOLVED")
        return DescriptorSplit(
            mismatch=False,
            descriptor_groups=((descriptor, bucket.member_ids),),
            promoted_record_ids=(),
        )

    uncertainty = dict(bucket.uncertainty_by_id)
    groups = {descriptor: list(record_ids) for descriptor, record_ids in confirmed.items()}
    assigned = {record_id for record_ids in groups.values() for record_id in record_ids}
    for record_id in bucket.member_ids:
        if record_id in assigned:
            continue
        candidate = candidates[record_id]
        descriptor = min(
            groups,
            key=lambda value: (
                min(
                    _pair_novelty(candidate, candidates[anchor], uncertainty)
                    for anchor in confirmed[value]
                ),
                repr(value),
            ),
        )
        groups[descriptor].append(record_id)

    promoted = []
    observed_ids = set(observations)
    for descriptor in sorted(groups, key=repr):
        deferred = [
            candidates[record_id]
            for record_id in groups[descriptor]
            if record_id not in observed_ids
        ]
        if deferred:
            promoted.append(
                min(
                    deferred,
                    key=lambda item: (
                        item.residual,
                        item.discovery_ordinal,
                        item.record_id,
                    ),
                ).record_id
            )
    return DescriptorSplit(
        mismatch=True,
        descriptor_groups=tuple(
            (descriptor, tuple(sorted(groups[descriptor])))
            for descriptor in sorted(groups, key=repr)
        ),
        promoted_record_ids=tuple(promoted),
    )
