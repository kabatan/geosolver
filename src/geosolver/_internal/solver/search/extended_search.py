"""Extended candidate ranking/search helpers for optimization orchestration."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import math
from typing import Any

from mpmath import mp

from geosolver._internal.solver.precision.type_guards.strict_to_mpf import strict_to_mpf
from geosolver._internal.solver.precision.type_guards.boundary_float_to_mpf import (
    boundary_float_to_mpf,
    BoundaryOrigin,
)

_CENTER_RATIO = (1, 2)
_LOW_RATIO = (1, 4)
_HIGH_RATIO = (3, 4)


def rank_candidates(
    candidates: Sequence[Sequence[Any]],
    *,
    score_fn: Callable[[Sequence[Any]], float],
    top_k: int | None = None,
) -> list[list[Any]]:
    scored: list[tuple[float, list[Any]]] = []
    for candidate in candidates:
        point = list(candidate)
        try:
            score = float(score_fn(point))
        except Exception:
            continue
        if not math.isfinite(score):
            continue
        scored.append((score, point))
    scored.sort(key=lambda item: item[0])
    ordered = [point for _, point in scored]
    if top_k is None:
        return ordered
    return ordered[: max(0, int(top_k))]


def _seed_identity(point: Sequence[Any]) -> tuple[str, ...]:
    return tuple(str(value) for value in point)


def _append_unique_seed(
    candidates: list[list[Any]],
    seen: set[tuple[str, ...]],
    point: Sequence[Any],
    *,
    limit: int,
) -> None:
    if len(candidates) >= int(limit):
        return
    key = _seed_identity(point)
    if key in seen:
        return
    candidates.append(list(point))
    seen.add(key)


def _interpolate_seed_value(
    lower_mpf: Any,
    upper_mpf: Any,
    *,
    ratio_spec: tuple[int, int],
) -> Any:
    numerator, denominator = ratio_spec
    span = upper_mpf - lower_mpf
    return lower_mpf + span * mp.mpf(numerator) / mp.mpf(denominator)


def build_high_precision_seed_candidates(
    *,
    n: int,
    bounds: Sequence[tuple[float, float]],
    sample_count: int,
) -> list[list[Any]]:
    """Build deterministic high-precision candidates without float search dependency."""
    safe_count = max(1, int(sample_count))
    if int(n) <= 0:
        return []

    hp_bounds: list[tuple[Any, Any]] = []
    for dim, (lower, upper) in enumerate(bounds[: int(n)]):
        if isinstance(lower, float):
            low_mpf = boundary_float_to_mpf(lower, origin=BoundaryOrigin.LEGACY_BOUND)
        else:
            low_mpf = strict_to_mpf(lower, context=f"extended_search.bounds[{dim}].lower")
        if isinstance(upper, float):
            high_mpf = boundary_float_to_mpf(upper, origin=BoundaryOrigin.LEGACY_BOUND)
        else:
            high_mpf = strict_to_mpf(upper, context=f"extended_search.bounds[{dim}].upper")
        hp_bounds.append((low_mpf, high_mpf))

    candidates: list[list[Any]] = []
    seen: set[tuple[str, ...]] = set()

    center_point: list[Any] = []
    for lower_mpf, upper_mpf in hp_bounds:
        center_point.append(
            _interpolate_seed_value(
                lower_mpf,
                upper_mpf,
                ratio_spec=_CENTER_RATIO,
            )
        )
    _append_unique_seed(candidates, seen, center_point, limit=safe_count)

    for focus_dim in range(int(n)):
        low_point: list[Any] = []
        high_point: list[Any] = []
        for dim, (lower_mpf, upper_mpf) in enumerate(hp_bounds):
            low_ratio = _LOW_RATIO if dim == focus_dim else _CENTER_RATIO
            high_ratio = _HIGH_RATIO if dim == focus_dim else _CENTER_RATIO
            low_point.append(
                _interpolate_seed_value(
                    lower_mpf,
                    upper_mpf,
                    ratio_spec=low_ratio,
                )
            )
            high_point.append(
                _interpolate_seed_value(
                    lower_mpf,
                    upper_mpf,
                    ratio_spec=high_ratio,
                )
            )
        _append_unique_seed(candidates, seen, low_point, limit=safe_count)
        _append_unique_seed(candidates, seen, high_point, limit=safe_count)
        if len(candidates) >= safe_count:
            return candidates

    denominator = mp.mpf(safe_count + 1)
    for index in range(max(0, safe_count - len(candidates)) + safe_count):
        if len(candidates) >= safe_count:
            break
        point: list[Any] = []
        numer_base = index + 1
        for dim, (lower_mpf, upper_mpf) in enumerate(hp_bounds):
            numer = ((numer_base * (2 * (dim + 1))) % (safe_count + 1)) + 1
            ratio = mp.mpf(numer) / denominator
            span = upper_mpf - lower_mpf
            point.append(lower_mpf + span * ratio)
        _append_unique_seed(candidates, seen, point, limit=safe_count)
    return candidates
