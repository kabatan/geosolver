"""Select NOMAD start points from phase-0 probe candidates."""

from __future__ import annotations

import math

from geosolver.engine.standard.contracts.candidate_record import FloatCandidate


def _normalized_distance(
    x: tuple[float, ...],
    y: tuple[float, ...],
    bounds: list[tuple[float, float]],
) -> float:
    total = 0.0
    for index, (low, high) in enumerate(bounds):
        width = max(high - low, 1e-12)
        delta = (x[index] - y[index]) / width
        total += delta * delta
    return math.sqrt(total)


def _build_fallback_start_points(
    bounds: list[tuple[float, float]],
    required_count: int,
) -> list[list[float]]:
    points: list[list[float]] = []
    denominator = float(required_count + 1)
    for index in range(required_count):
        ratio = float(index + 1) / denominator
        points.append(
            [low + ((high - low) * ratio) for low, high in bounds]
        )
    return points


def select_search_start_points(
    *,
    probe_candidates: tuple[FloatCandidate, ...],
    bounds: list[tuple[float, float]],
    required_count: int,
    dedup_distance_threshold: float,
) -> list[list[float]]:
    """Select diverse start points from phase-0 probe outputs."""
    if required_count <= 0:
        raise ValueError("required_count must be positive")
    ordered = sorted(
        probe_candidates,
        key=lambda candidate: (
            not candidate.guard_ok,
            candidate.residual_norm_float,
        ),
    )
    selected: list[FloatCandidate] = []
    for candidate in ordered:
        if any(
            _normalized_distance(candidate.x_float, existing.x_float, bounds)
            < dedup_distance_threshold
            for existing in selected
        ):
            continue
        selected.append(candidate)
        if len(selected) >= required_count:
            break
    if not selected:
        return _build_fallback_start_points(bounds, required_count)
    return [list(candidate.x_float) for candidate in selected]

