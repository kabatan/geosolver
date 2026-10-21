"""Select adaptive rescue boxes from guard-feasible ledger."""

from __future__ import annotations

from typing import TYPE_CHECKING

from geosolver.engine.standard.contracts.branch_box import BranchBox
from geosolver.engine.standard.contracts.candidate_record import FloatCandidate

from .coordinate_distance import normalized_distance

if TYPE_CHECKING:
    from geosolver.engine.standard.contracts.external_pipeline_config import (
        ExternalPipelineConfig,
    )


def _nearest_representative_distance(
    *,
    candidate: FloatCandidate,
    representatives: tuple[FloatCandidate, ...],
    bounds: list[tuple[float, float]],
) -> float:
    distances = [
        normalized_distance(
            first=candidate.x_float,
            second=other.x_float,
            bounds=bounds,
        )
        for other in representatives
        if other.candidate_key != candidate.candidate_key
    ]
    if not distances:
        return 1.0
    return min(distances)


def _axis_radius_from_neighbor_distance(
    *,
    global_width: float,
    neighbor_distance: float,
    pipeline_config: ExternalPipelineConfig,
) -> float:
    base_radius = (
        float(global_width)
        * float(neighbor_distance)
        * float(pipeline_config.rescue_radius_fraction)
    )
    min_radius = float(global_width) * float(pipeline_config.rescue_radius_min_ratio)
    max_radius = float(global_width) * float(pipeline_config.rescue_radius_max_ratio)
    return max(min_radius, min(base_radius, max_radius))


def _clamp_box_to_global_bounds(
    *,
    center: tuple[float, ...],
    axis_radii: tuple[float, ...],
    bounds: list[tuple[float, float]],
) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]:
    clamped_center: list[float] = []
    lower_bounds: list[float] = []
    upper_bounds: list[float] = []
    for index, (global_low, global_high) in enumerate(bounds):
        radius = axis_radii[index]
        center_value = min(max(float(center[index]), float(global_low)), float(global_high))
        clamped_center.append(center_value)
        lower_bounds.append(max(float(global_low), center_value - radius))
        upper_bounds.append(min(float(global_high), center_value + radius))
    return tuple(clamped_center), tuple(lower_bounds), tuple(upper_bounds)


def select_rescue_boxes(
    guard_feasible_ledger: tuple[FloatCandidate, ...],
    bounds: list[tuple[float, float]],
    pipeline_config: ExternalPipelineConfig,
) -> tuple[BranchBox, ...]:
    """Select adaptive rescue boxes from guard-feasible ledger only."""
    if not guard_feasible_ledger:
        return ()
    max_boxes = max(1, int(pipeline_config.max_rescue_boxes))
    selected: list[FloatCandidate] = [guard_feasible_ledger[0]]
    remaining = list(guard_feasible_ledger[1:])
    while remaining and len(selected) < max_boxes:
        best_index = 0
        best_distance = -1.0
        for index, candidate in enumerate(remaining):
            min_distance = min(
                normalized_distance(
                    first=candidate.x_float,
                    second=selected_candidate.x_float,
                    bounds=bounds,
                )
                for selected_candidate in selected
            )
            if min_distance > best_distance:
                best_distance = min_distance
                best_index = index
        selected.append(remaining.pop(best_index))
    representatives = tuple(selected)
    boxes: list[BranchBox] = []
    for box_id, candidate in enumerate(representatives, start=1):
        neighbor_distance = _nearest_representative_distance(
            candidate=candidate,
            representatives=representatives,
            bounds=bounds,
        )
        axis_radii = tuple(
            _axis_radius_from_neighbor_distance(
                global_width=(high - low),
                neighbor_distance=neighbor_distance,
                pipeline_config=pipeline_config,
            )
            for low, high in bounds
        )
        clamped_center, lower_bounds, upper_bounds = _clamp_box_to_global_bounds(
            center=candidate.x_float,
            axis_radii=axis_radii,
            bounds=bounds,
        )
        boxes.append(
            BranchBox(
                box_id=box_id,
                center=clamped_center,
                lower_bounds=lower_bounds,
                upper_bounds=upper_bounds,
                source_candidate_ids=(int(candidate.candidate_id),),
                priority=float(candidate.score),
                stage="search_rescue",
            )
        )
        if len(boxes) >= max_boxes:
            break
    return tuple(boxes)
