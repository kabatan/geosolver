"""Per-start affine scaling; scales are preconditioners, never bounds."""

from __future__ import annotations

from typing import Sequence

import numpy as np

from runtime import SourceCase, with_affine_metadata


SCHEMA = "geotarget.exp-real61-008.per-start-scaling/v1"
EQUILIBRATION_FACTOR_MIN = 0.25
EQUILIBRATION_FACTOR_MAX = 4.0


def base_scales(start: Sequence[float]) -> np.ndarray:
    point = np.asarray(start, dtype=float)
    if point.ndim != 1 or not np.all(np.isfinite(point)):
        raise ValueError("start must be a finite vector")
    return np.maximum(1.0, np.abs(point))


def equilibrate_columns(
    scales: Sequence[float], jacobian_x: np.ndarray
) -> np.ndarray:
    base = np.asarray(scales, dtype=float)
    jacobian = np.asarray(jacobian_x, dtype=float)
    if base.ndim != 1 or jacobian.ndim != 2 or jacobian.shape[1] != base.size:
        raise ValueError("Jacobian/scaling shape mismatch")
    if not np.all(np.isfinite(base)) or np.any(base <= 0.0):
        raise ValueError("base scales must be finite and positive")
    column_norms = np.linalg.norm(jacobian * base[None, :], axis=0)
    positive = column_norms[np.isfinite(column_norms) & (column_norms > 0.0)]
    if positive.size == 0:
        return base.copy()
    target = float(np.exp(np.mean(np.log(positive))))
    factors = np.ones_like(base)
    active = np.isfinite(column_norms) & (column_norms > 0.0)
    factors[active] = np.clip(
        target / column_norms[active],
        EQUILIBRATION_FACTOR_MIN,
        EQUILIBRATION_FACTOR_MAX,
    )
    return base * factors


def case_for_start(
    case: SourceCase,
    start: Sequence[float],
    *,
    jacobian_x: np.ndarray | None = None,
) -> SourceCase:
    point = np.asarray(start, dtype=float)
    if point.shape != (case.dimension,) or not np.all(np.isfinite(point)):
        raise ValueError("start shape mismatch or non-finite start")
    if np.any(point < case.lower) or np.any(point > case.upper):
        raise ValueError("start violates an explicit source bound")
    scales = base_scales(point)
    if jacobian_x is not None:
        scales = equilibrate_columns(scales, jacobian_x)
    return with_affine_metadata(case, origin=point, scales=scales)


def frozen_configuration() -> dict[str, object]:
    return {
        "schema_version": SCHEMA,
        "origin": "the current start, independently for every local solve",
        "base_scale_j": "max(1, abs(start_j))",
        "jacobian_column_equilibration": False,
        "optional_equilibration_factor_bounds": [
            EQUILIBRATION_FACTOR_MIN,
            EQUILIBRATION_FACTOR_MAX,
        ],
        "scales_are_search_bounds": False,
        "scales_exclude_points": False,
        "case_family_truth_routing": False,
    }


__all__ = [
    "base_scales",
    "case_for_start",
    "equilibrate_columns",
    "frozen_configuration",
]
