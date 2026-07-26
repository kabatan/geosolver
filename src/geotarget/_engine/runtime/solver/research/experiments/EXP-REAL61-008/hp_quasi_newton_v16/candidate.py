"""D0 kernel for a high-precision event-refreshed direct-Broyden refiner.

This module deliberately contains only the mechanism that differs from the
current numerical-v3 refiner: an arbitrary-precision direct good-Broyden
update and an identity-free refresh policy.  A later experiment can insert it
inside each *independently initialized* 512- and 768-bit lane.  It does not
compile or transform a problem, add bounds, alter coordinates, inspect case
metadata, or weaken the final numerical-v3/PSLQ gates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from mpmath import mp


@dataclass(frozen=True)
class UpdateResult:
    matrix: tuple[tuple[object, ...], ...]
    normalized_secant_defect: object | None
    usable: bool


@dataclass(frozen=True)
class RefreshObservation:
    """Only general numerical events may request a fresh dense Jacobian."""

    linear_solve_failed: bool = False
    rank_changed: bool = False
    semantic_branch_changed: bool = False
    accepted_step: bool = True
    actual_to_predicted_ratio: object | None = None
    normalized_secant_defect: object | None = None
    consecutive_poor_ratios: int = 0
    accepted_updates_since_refresh: int = 0


@dataclass(frozen=True)
class RefreshPolicy:
    # Reference values are inherited from the successful Float64 direct-
    # Broyden mechanism.  D0 compares event-only and Shamanskii-m4 variants;
    # no case-dependent value is permitted.
    poor_ratio_threshold: object = "0.05"
    poor_ratio_patience: int = 2
    secant_defect_threshold: object = "0.85"
    maximum_updates_without_refresh: int | None = None


def _matrix(values: Sequence[Sequence[object]]) -> list[list[object]]:
    rows = [[mp.mpf(value) for value in row] for row in values]
    if not rows or not rows[0]:
        raise ValueError("Jacobian must be nonempty")
    columns = len(rows[0])
    if any(len(row) != columns for row in rows):
        raise ValueError("Jacobian rows must have equal length")
    return rows


def _norm2(values: Sequence[object]):
    return mp.sqrt(mp.fsum(mp.mpf(value) ** 2 for value in values))


def good_broyden_update(
    jacobian: Sequence[Sequence[object]],
    step: Sequence[object],
    residual_change: Sequence[object],
    *,
    denominator_rtol: object | None = None,
) -> UpdateResult:
    """Apply ``J + ((y-Js)s^T)/(s^Ts)`` without Float64 coercion.

    The relative denominator floor follows the active arbitrary precision
    when it is not supplied explicitly.  Returning ``usable=False`` requests
    a fresh dense/AD Jacobian; it never turns a failed update into authority.
    """

    matrix = _matrix(jacobian)
    delta = [mp.mpf(value) for value in step]
    change = [mp.mpf(value) for value in residual_change]
    if len(delta) != len(matrix[0]):
        raise ValueError("Broyden step dimension disagrees with Jacobian")
    if len(change) != len(matrix):
        raise ValueError("residual-change dimension disagrees with Jacobian")
    if not all(mp.isfinite(value) for row in matrix for value in row):
        raise ValueError("Jacobian must be finite")
    if not all(mp.isfinite(value) for value in delta + change):
        raise ValueError("step and residual change must be finite")

    predicted = [
        mp.fsum(matrix[row][column] * delta[column] for column in range(len(delta)))
        for row in range(len(matrix))
    ]
    defect_vector = [
        change[row] - predicted[row] for row in range(len(change))
    ]
    scale = max(_norm2(change), _norm2(predicted), mp.eps)
    defect = _norm2(defect_vector) / scale
    denominator = mp.fsum(value * value for value in delta)
    relative_floor = (
        mp.sqrt(mp.eps)
        if denominator_rtol is None
        else mp.mpf(denominator_rtol)
    )
    if not (relative_floor > 0 and relative_floor < 1):
        raise ValueError("denominator_rtol must lie in (0, 1)")
    threshold = relative_floor * max(mp.mpf("1"), max(abs(v) for v in delta) ** 2)
    usable = bool(
        mp.isfinite(denominator)
        and denominator > threshold
        and mp.isfinite(defect)
    )
    if not usable:
        return UpdateResult(
            tuple(tuple(value for value in row) for row in matrix),
            defect if mp.isfinite(defect) else None,
            False,
        )

    updated = [
        [
            matrix[row][column]
            + defect_vector[row] * delta[column] / denominator
            for column in range(len(delta))
        ]
        for row in range(len(matrix))
    ]
    if not all(mp.isfinite(value) for row in updated for value in row):
        return UpdateResult(
            tuple(tuple(value for value in row) for row in matrix), defect, False
        )
    return UpdateResult(
        tuple(tuple(value for value in row) for row in updated), defect, True
    )


def refresh_reason(
    observation: RefreshObservation,
    policy: RefreshPolicy = RefreshPolicy(),
) -> str | None:
    """Return an identity-free reason for rebuilding the lane Jacobian."""

    if observation.linear_solve_failed:
        return "LINEAR_SOLVE_FAILURE"
    if observation.rank_changed:
        return "RANK_CHANGE"
    if observation.semantic_branch_changed:
        return "SEMANTIC_BRANCH_CHANGE"
    if not observation.accepted_step:
        return "NO_ACCEPTED_DESCENT"

    defect_gate = mp.mpf(policy.secant_defect_threshold)
    defect = observation.normalized_secant_defect
    if defect is not None and mp.mpf(defect) > defect_gate:
        return "SECANT_DEFECT"

    ratio_gate = mp.mpf(policy.poor_ratio_threshold)
    ratio = observation.actual_to_predicted_ratio
    poor = ratio is not None and mp.mpf(ratio) < ratio_gate
    if poor and observation.consecutive_poor_ratios >= policy.poor_ratio_patience:
        return "PERSISTENT_POOR_MODEL_RATIO"

    maximum = policy.maximum_updates_without_refresh
    if maximum is not None:
        if maximum < 1:
            raise ValueError("maximum_updates_without_refresh must be positive")
        if observation.accepted_updates_since_refresh >= maximum:
            return "SHAMANSKII_REFRESH"
    return None


def mechanism_manifest() -> dict[str, object]:
    return {
        "name": "hp_event_refreshed_direct_good_broyden_d0",
        "independent_512_768_lane_initialization_retained": True,
        "fresh_original_dsl_512_768_1024_replay_retained": True,
        "owned_pslq_768_1024_retained": True,
        "problem_or_source_modified": False,
        "bounds_added_or_inferred": False,
        "gauge_or_symmetry_reduction": False,
        "coordinate_reparameterization": False,
        "case_family_truth_or_known_target_count_read": False,
    }


__all__ = [
    "RefreshObservation",
    "RefreshPolicy",
    "UpdateResult",
    "good_broyden_update",
    "mechanism_manifest",
    "refresh_reason",
]
