"""Disposable exact anchored-EDM reconstruction after a numerical endpoint."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
from typing import Callable, Mapping, Sequence


SCHEMA = "geotarget.post-endpoint-edm-gram-exact-reopen/v1"


class Inapplicable(ValueError):
    pass


def _qq(value: object) -> Fraction:
    if isinstance(value, bool):
        raise Inapplicable("BOOLEAN_EXACT_VALUE")
    try:
        return value if isinstance(value, Fraction) else Fraction(str(value))
    except (ValueError, ZeroDivisionError) as error:
        raise Inapplicable("NONRATIONAL_EXACT_VALUE") from error


@dataclass(frozen=True)
class Quadratic:
    rational: Fraction
    radical_coefficient: Fraction
    radicand: Fraction

    def __post_init__(self) -> None:
        if self.radicand <= 0:
            raise Inapplicable("NONPOSITIVE_COMMON_RADICAND")

    def reflected(self) -> "Quadratic":
        return Quadratic(self.rational, -self.radical_coefficient, self.radicand)

    def difference(self, other: "Quadratic") -> tuple[Fraction, Fraction]:
        if self.radicand != other.radicand:
            raise Inapplicable("MIXED_QUADRATIC_FIELDS")
        return self.rational - other.rational, self.radical_coefficient - other.radical_coefficient

    def as_float(self) -> float:
        return float(self.rational) + float(self.radical_coefficient) * float(self.radicand) ** 0.5

    def record(self) -> dict[str, str]:
        return {
            "rational": str(self.rational),
            "sqrt_coefficient": str(self.radical_coefficient),
            "sqrt_radicand": str(self.radicand),
        }


@dataclass(frozen=True)
class ExactPoint:
    x: Quadratic
    y: Quadratic

    def reflected(self) -> "ExactPoint":
        return ExactPoint(self.x.reflected(), self.y.reflected())

    def record(self) -> dict[str, object]:
        return {"x": self.x.record(), "y": self.y.record()}


@dataclass(frozen=True)
class Reconstruction:
    labels: tuple[str, ...]
    anchor_labels: tuple[str, str]
    common_radicand: Fraction
    branches: tuple[Mapping[str, ExactPoint], Mapping[str, ExactPoint]]
    exact_rank: int


def _distance_key(left: str, right: str) -> frozenset[str]:
    if left == right:
        raise Inapplicable("REPEATED_DISTANCE_VERTEX")
    return frozenset((left, right))


def squared_distance(left: ExactPoint, right: ExactPoint) -> Fraction:
    dx_r, dx_s = left.x.difference(right.x)
    dy_r, dy_s = left.y.difference(right.y)
    radical_part = 2 * (dx_r * dx_s + dy_r * dy_s)
    if radical_part != 0:
        raise Inapplicable("DISTANCE_NOT_RATIONAL_IN_COMMON_FIELD")
    return dx_r * dx_r + dy_r * dy_r + (dx_s * dx_s + dy_s * dy_s) * left.x.radicand


def reconstruct_anchored_edm(
    *,
    labels: Sequence[str],
    squared_distances: Mapping[frozenset[str], object],
    anchor_left: str,
    anchor_right: str,
    anchor_left_xy: Sequence[object],
    anchor_right_xy: Sequence[object],
) -> Reconstruction:
    """Factor an exact 2D EDM and align both reflections to two fixed anchors."""

    ordered = tuple(labels)
    if len(ordered) < 3 or len(set(ordered)) != len(ordered):
        raise Inapplicable("EDM_NEEDS_THREE_DISTINCT_LABELS")
    if anchor_left not in ordered or anchor_right not in ordered or anchor_left == anchor_right:
        raise Inapplicable("ANCHORS_NOT_DISTINCT_MEMBERS")
    ax, ay = map(_qq, anchor_left_xy)
    bx, by = map(_qq, anchor_right_xy)
    vx, vy = bx - ax, by - ay
    anchor_square = vx * vx + vy * vy
    if anchor_square <= 0:
        raise Inapplicable("COINCIDENT_FIXED_ANCHORS")

    distances: dict[frozenset[str], Fraction] = {}
    for left_index, left in enumerate(ordered):
        for right in ordered[left_index + 1 :]:
            key = _distance_key(left, right)
            if key not in squared_distances:
                raise Inapplicable("INCOMPLETE_EDM")
            value = _qq(squared_distances[key])
            if value <= 0:
                raise Inapplicable("NONPOSITIVE_OFF_DIAGONAL_EDM")
            distances[key] = value
    if distances[_distance_key(anchor_left, anchor_right)] != anchor_square:
        raise Inapplicable("FIXED_ANCHOR_DISTANCE_MISMATCH")

    projection: dict[str, Fraction] = {}
    height_gram: dict[tuple[str, str], Fraction] = {}
    for label in ordered:
        if label == anchor_left:
            projection[label] = Fraction(0)
        elif label == anchor_right:
            projection[label] = Fraction(1)
        else:
            d_left = distances[_distance_key(anchor_left, label)]
            d_right = distances[_distance_key(anchor_right, label)]
            projection[label] = (d_left + anchor_square - d_right) / (2 * anchor_square)
    for left in ordered:
        for right in ordered:
            if left == anchor_left or right == anchor_left:
                gram = Fraction(0)
            else:
                d_left = Fraction(0) if left == anchor_left else distances[_distance_key(anchor_left, left)]
                d_right = Fraction(0) if right == anchor_left else distances[_distance_key(anchor_left, right)]
                mutual = Fraction(0) if left == right else distances[_distance_key(left, right)]
                gram = (d_left + d_right - mutual) / (2 * anchor_square)
            height_gram[left, right] = gram - projection[left] * projection[right]

    if any(height_gram[label, label] < 0 for label in ordered):
        raise Inapplicable("EDM_GRAM_NOT_PSD")
    pivots = [label for label in ordered if height_gram[label, label] > 0]
    if not pivots:
        raise Inapplicable("COLLINEAR_EDM_HAS_NO_REFLECTION_GAIN")
    pivot = pivots[0]
    radicand = height_gram[pivot, pivot]
    coefficient = {label: height_gram[pivot, label] / radicand for label in ordered}
    for left in ordered:
        for right in ordered:
            if height_gram[left, right] != coefficient[left] * coefficient[right] * radicand:
                raise Inapplicable("EDM_GRAM_RANK_EXCEEDS_TWO")

    positive: dict[str, ExactPoint] = {}
    for label in ordered:
        u = projection[label]
        q = coefficient[label]
        positive[label] = ExactPoint(
            Quadratic(ax + u * vx, -q * vy, radicand),
            Quadratic(ay + u * vy, q * vx, radicand),
        )
    negative = {label: point.reflected() for label, point in positive.items()}
    for branch in (positive, negative):
        for left_index, left in enumerate(ordered):
            for right in ordered[left_index + 1 :]:
                if squared_distance(branch[left], branch[right]) != distances[_distance_key(left, right)]:
                    raise Inapplicable("RECONSTRUCTED_EDM_MISMATCH")
    return Reconstruction(
        labels=ordered,
        anchor_labels=(anchor_left, anchor_right),
        common_radicand=radicand,
        branches=(positive, negative),
        exact_rank=2,
    )


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")
    ).hexdigest()


def replay_branches(
    reconstruction: Reconstruction,
    *,
    source_sha256: str,
    endpoint_sha256: str,
    replay: Callable[[Mapping[str, object]], Mapping[str, object]],
) -> dict[str, object]:
    if len(source_sha256) != 64 or len(endpoint_sha256) != 64:
        raise Inapplicable("SOURCE_OR_ENDPOINT_DIGEST_MALFORMED")
    accepted = []
    for ordinal, branch in enumerate(reconstruction.branches):
        request = {
            "schema_version": SCHEMA,
            "source_sha256": source_sha256,
            "endpoint_float64_sha256": endpoint_sha256,
            "reflection_ordinal": ordinal,
            "exact_rank": reconstruction.exact_rank,
            "exact_points": {label: branch[label].record() for label in reconstruction.labels},
            "source_parser_or_compiler_modified": False,
        }
        response = replay(request)
        valid = bool(
            isinstance(response, Mapping)
            and response.get("source_sha256") == source_sha256
            and response.get("endpoint_float64_sha256") == endpoint_sha256
            and response.get("reflection_ordinal") == ordinal
            and response.get("construction_exact") is True
            and response.get("constraints_exact") is True
            and response.get("guards_and_definedness_exact") is True
            and response.get("raw_target_link_exact") is True
            and response.get("untouched_source_replay") is True
            and response.get("source_parser_or_compiler_modified") is False
        )
        if valid:
            accepted.append({"reflection_ordinal": ordinal, "replay_sha256": _digest(dict(response))})
    return {
        "schema_version": SCHEMA,
        "status": "PROOF_READY_PREJOIN" if accepted else "NO_REPLAYED_BRANCH",
        "accepted_reflection_count": len(accepted),
        "accepted": accepted,
        "both_reflections_enumerated": True,
        "authority_pass": False,
        "target_release": False,
        "target_set_completeness_claim": False,
        "source_parser_or_compiler_modified": False,
        "truth_case_family_target_count_outcome_routing": False,
    }
