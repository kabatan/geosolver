"""Backtracking line search for high-precision refinement."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from mpmath import mp

from geosolver.engine.standard.precision.type_guards.mp_types import MPFloat


def _vector_norm(values: Sequence[MPFloat]) -> MPFloat:
    return mp.sqrt(mp.fsum(value * value for value in values))


def _point_within_bounds(
    point: Sequence[MPFloat],
    bounds: Sequence[tuple[MPFloat | None, MPFloat | None]] | None,
) -> bool:
    if bounds is None:
        return True
    if len(point) != len(bounds):
        raise ValueError("line-search bounds must match point dimension")
    for value, (lower, upper) in zip(point, bounds, strict=True):
        if lower is not None and value < lower:
            return False
        if upper is not None and value > upper:
            return False
    return True


def run_line_search(
    *,
    point: Sequence[MPFloat],
    current_norm: MPFloat,
    step: Sequence[MPFloat],
    dps: int,
    max_steps: int,
    residual_fn: Callable[[list[MPFloat], int], list[MPFloat] | None],
    bounds: Sequence[tuple[MPFloat | None, MPFloat | None]] | None = None,
    trial_filter: Callable[[list[MPFloat], int], bool] | None = None,
) -> tuple[list[MPFloat], list[MPFloat] | None, bool]:
    """Run backtracking line search."""
    _ = dps
    alpha = mp.mpf("1")
    for _ in range(max_steps):
        trial = [value + (alpha * delta) for value, delta in zip(point, step)]
        if not _point_within_bounds(trial, bounds):
            alpha /= mp.mpf("2")
            continue
        if trial_filter is not None and not trial_filter(trial, int(dps)):
            alpha /= mp.mpf("2")
            continue
        trial_vec = residual_fn(trial, int(dps))
        if trial_vec is not None:
            trial_norm = _vector_norm(trial_vec)
            if mp.isfinite(trial_norm) and trial_norm < current_norm:
                return trial, trial_vec, True
        alpha /= mp.mpf("2")
    return [mp.mpf(value) for value in point], None, False

