"""Join partial coordinate descriptors only behind a fresh same-root proof.

This is a disposable proposal gate.  It is deliberately not a descriptor or
release authority: the existing QQBar source/guard/branch/raw-target replay
must still accept every proposal emitted here.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from functools import reduce
from math import gcd
from typing import Callable, Mapping, Sequence


Q = Fraction


@dataclass(frozen=True, order=True, slots=True)
class Interval:
    lower: Q
    upper: Q

    def __post_init__(self) -> None:
        if self.lower > self.upper:
            raise ValueError("reversed interval")

    @classmethod
    def point(cls, value: Q | int) -> "Interval":
        value = Q(value)
        return cls(value, value)

    @property
    def midpoint(self) -> Q:
        return (self.lower + self.upper) / 2

    def contains(self, other: "Interval") -> bool:
        return self.lower <= other.lower and other.upper <= self.upper

    def strictly_contains(self, other: "Interval") -> bool:
        return self.lower < other.lower and other.upper < self.upper

    def __add__(self, other: "Interval") -> "Interval":
        return Interval(self.lower + other.lower, self.upper + other.upper)

    def __neg__(self) -> "Interval":
        return Interval(-self.upper, -self.lower)

    def __sub__(self, other: "Interval") -> "Interval":
        return self + (-other)

    def __mul__(self, other: "Interval") -> "Interval":
        values = (
            self.lower * other.lower,
            self.lower * other.upper,
            self.upper * other.lower,
            self.upper * other.upper,
        )
        return Interval(min(values), max(values))


Box = tuple[Interval, ...]
PointResidual = Callable[[tuple[Q, ...]], tuple[Q, ...]]
IntervalJacobian = Callable[[Box], tuple[tuple[Interval, ...], ...]]


@dataclass(frozen=True, order=True, slots=True)
class ReplayBinding:
    source_sha256: str
    guard_sha256: str
    branch_sha256: str
    raw_target_sha256: str


@dataclass(frozen=True, order=True, slots=True)
class Descriptor:
    # Primitive integer coefficients, highest power first.
    minpoly: tuple[int, ...]
    real_root_ordinal: int
    isolator: Interval


@dataclass(frozen=True, order=True, slots=True)
class PartialCoordinateFact:
    coordinate: int
    refinement: Interval
    minpoly: tuple[int, ...] | None = None
    real_root_ordinal: int | None = None
    isolator: Interval | None = None


@dataclass(frozen=True, slots=True)
class ExactifierAttempt:
    endpoint_ordinal: int
    rung_ordinal: int
    binding: ReplayBinding
    root_box: Box
    facts: tuple[PartialCoordinateFact, ...]
    finalized: bool = True


@dataclass(frozen=True, slots=True)
class SourceSystem:
    dimension: int
    source_sha256: str
    point_residual: PointResidual
    interval_jacobian: IntervalJacobian


@dataclass(frozen=True, slots=True)
class KrawczykCertificate:
    source_hull: Box
    krawczyk_image: Box
    strict_inclusion: bool


@dataclass(frozen=True, slots=True)
class JoinProposal:
    binding: ReplayBinding
    descriptors: tuple[Descriptor, ...]
    certificate: KrawczykCertificate
    consumed_attempts: tuple[tuple[int, int], ...]
    proposal_authority: bool = False
    release: bool = False
    existing_qqbar_source_guard_branch_raw_target_replay_required: bool = True


@dataclass(frozen=True, slots=True)
class JoinBatch:
    proposals: tuple[JoinProposal, ...]
    work: Mapping[str, int]
    proposal_authority: bool = False
    release: bool = False


def _scale(interval: Interval, scalar: Q) -> Interval:
    return Interval.point(scalar) * interval


def _hull(boxes: Sequence[Box]) -> Box:
    return tuple(
        Interval(min(box[index].lower for box in boxes), max(box[index].upper for box in boxes))
        for index in range(len(boxes[0]))
    )


def _invert(matrix: Sequence[Sequence[Q]]) -> tuple[tuple[Q, ...], ...] | None:
    size = len(matrix)
    if size == 0 or any(len(row) != size for row in matrix):
        return None
    rows = [list(map(Q, row)) + [Q(int(i == j)) for j in range(size)] for i, row in enumerate(matrix)]
    for column in range(size):
        pivot = next((row for row in range(column, size) if rows[row][column]), None)
        if pivot is None:
            return None
        rows[column], rows[pivot] = rows[pivot], rows[column]
        divisor = rows[column][column]
        rows[column] = [value / divisor for value in rows[column]]
        for row in range(size):
            if row == column:
                continue
            multiplier = rows[row][column]
            if multiplier:
                rows[row] = [
                    left - multiplier * right
                    for left, right in zip(rows[row], rows[column], strict=True)
                ]
    return tuple(tuple(row[size:]) for row in rows)


def _fresh_krawczyk(system: SourceSystem, box: Box) -> KrawczykCertificate | None:
    """Recompute K(X)=x-CF(x)+(I-CJ(X))(X-x), accepting strict inclusion."""

    size = system.dimension
    if len(box) != size or any(interval.lower == interval.upper for interval in box):
        return None
    midpoint = tuple(interval.midpoint for interval in box)
    residual = system.point_residual(midpoint)
    jacobian = system.interval_jacobian(box)
    if len(residual) != size or len(jacobian) != size or any(len(row) != size for row in jacobian):
        return None
    midpoint_jacobian = tuple(
        tuple(jacobian[row][column].midpoint for column in range(size))
        for row in range(size)
    )
    inverse = _invert(midpoint_jacobian)
    if inverse is None:
        return None

    center = tuple(
        midpoint[row] - sum(inverse[row][column] * residual[column] for column in range(size))
        for row in range(size)
    )
    remainder = tuple(
        tuple(
            Interval.point(int(row == column))
            - reduce(
                Interval.__add__,
                (_scale(jacobian[k][column], inverse[row][k]) for k in range(size)),
                Interval.point(0),
            )
            for column in range(size)
        )
        for row in range(size)
    )
    delta = tuple(interval - Interval.point(value) for interval, value in zip(box, midpoint, strict=True))
    image = tuple(
        Interval.point(center[row])
        + reduce(
            Interval.__add__,
            (remainder[row][column] * delta[column] for column in range(size)),
            Interval.point(0),
        )
        for row in range(size)
    )
    if not all(parent.strictly_contains(child) for parent, child in zip(box, image, strict=True)):
        return None
    return KrawczykCertificate(box, image, True)


def _descriptor_well_formed(descriptor: Descriptor) -> bool:
    coefficients = descriptor.minpoly
    if len(coefficients) < 2 or coefficients[0] <= 0 or descriptor.real_root_ordinal < 0:
        return False
    if coefficients[-1] == 0 and descriptor.isolator.lower > 0:
        return False
    common = reduce(gcd, (abs(value) for value in coefficients), 0)
    if common != 1:
        return False
    # Cheap necessary check only.  QQBar replay remains the isolator authority.
    value = Interval.point(coefficients[0])
    for coefficient in coefficients[1:]:
        value = value * descriptor.isolator + Interval.point(coefficient)
    return value.lower <= 0 <= value.upper


def join_partial_coordinates(
    system: SourceSystem,
    attempts: Sequence[ExactifierAttempt],
) -> JoinBatch:
    work = {
        "attempt_count": len(attempts),
        "binding_group_count": 0,
        "fresh_krawczyk_count": 0,
        "fresh_krawczyk_pass_count": 0,
        "conflict_count": 0,
        "missing_coordinate_count": 0,
        "missing_descriptor_component_count": 0,
        "root_membership_reject_count": 0,
        "proposal_count": 0,
    }
    grouped: dict[ReplayBinding, list[ExactifierAttempt]] = {}
    for attempt in attempts:
        if attempt.finalized:
            grouped.setdefault(attempt.binding, []).append(attempt)
    work["binding_group_count"] = len(grouped)
    proposals: list[JoinProposal] = []

    for binding in sorted(grouped):
        group = grouped[binding]
        if binding.source_sha256 != system.source_sha256:
            continue
        if any(len(attempt.root_box) != system.dimension for attempt in group):
            continue
        facts: dict[int, list[PartialCoordinateFact]] = {}
        malformed = False
        for attempt in group:
            for fact in attempt.facts:
                if (
                    not 0 <= fact.coordinate < system.dimension
                    or not attempt.root_box[fact.coordinate].contains(fact.refinement)
                ):
                    malformed = True
                    break
                facts.setdefault(fact.coordinate, []).append(fact)
            if malformed:
                break
        if malformed:
            continue
        if set(facts) != set(range(system.dimension)):
            work["missing_coordinate_count"] += 1
            continue
        descriptors: list[Descriptor] = []
        conflict = False
        for coordinate in range(system.dimension):
            minpolys = {fact.minpoly for fact in facts[coordinate] if fact.minpoly is not None}
            ordinals = {
                fact.real_root_ordinal
                for fact in facts[coordinate]
                if fact.real_root_ordinal is not None
            }
            isolators = {fact.isolator for fact in facts[coordinate] if fact.isolator is not None}
            if any(len(values) > 1 for values in (minpolys, ordinals, isolators)):
                work["conflict_count"] += 1
                conflict = True
                break
            if any(len(values) != 1 for values in (minpolys, ordinals, isolators)):
                work["missing_descriptor_component_count"] += 1
                conflict = True
                break
            descriptor = Descriptor(
                next(iter(minpolys)),
                next(iter(ordinals)),
                next(iter(isolators)),
            )
            if not _descriptor_well_formed(descriptor):
                conflict = True
                break
            descriptors.append(descriptor)
        if conflict:
            continue

        source_hull = _hull(tuple(attempt.root_box for attempt in group))
        work["fresh_krawczyk_count"] += 1
        certificate = _fresh_krawczyk(system, source_hull)
        if certificate is None:
            continue
        work["fresh_krawczyk_pass_count"] += 1

        # Hull uniqueness alone is insufficient: the certified root enclosure
        # must be present in every joined attempt and every partial refinement.
        if any(
            not all(
                attempt.root_box[index].contains(certificate.krawczyk_image[index])
                for index in range(system.dimension)
            )
            for attempt in group
        ):
            work["root_membership_reject_count"] += 1
            continue
        if any(
            not fact.refinement.contains(certificate.krawczyk_image[coordinate])
            or (
                fact.isolator is not None
                and not fact.isolator.contains(certificate.krawczyk_image[coordinate])
            )
            for coordinate in range(system.dimension)
            for fact in facts[coordinate]
        ):
            work["root_membership_reject_count"] += 1
            continue

        proposals.append(
            JoinProposal(
                binding=binding,
                descriptors=tuple(descriptors),
                certificate=certificate,
                consumed_attempts=tuple(
                    sorted((attempt.endpoint_ordinal, attempt.rung_ordinal) for attempt in group)
                ),
            )
        )

    proposals.sort(key=lambda proposal: (proposal.binding, proposal.consumed_attempts))
    work["proposal_count"] = len(proposals)
    return JoinBatch(tuple(proposals), work)


def boundary_manifest() -> dict[str, object]:
    return {
        "candidate_private_ephemeral_partial_facts": True,
        "group_key": ["source", "guard", "branch", "raw_target"],
        "fresh_krawczyk_hull_recomputed": True,
        "strict_unique_root_inclusion_required": True,
        "certified_root_inside_every_attempt_and_refinement": True,
        "coordinate_conflict_fail_closed": True,
        "minpoly_ordinal_isolator_components_union": True,
        "missing_coordinate_fail_closed": True,
        "proposal_authority": False,
        "release": False,
        "sole_final_authority": "unchanged QQBar source/guard/branch/raw-target replay",
        "truth_or_outcome_input": False,
        "case_routing": False,
    }


__all__ = [
    "Descriptor",
    "ExactifierAttempt",
    "Interval",
    "JoinBatch",
    "JoinProposal",
    "PartialCoordinateFact",
    "ReplayBinding",
    "SourceSystem",
    "boundary_manifest",
    "join_partial_coordinates",
]
