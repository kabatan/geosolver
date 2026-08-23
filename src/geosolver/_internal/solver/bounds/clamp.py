"""Clamp helpers for float and high-precision vectors."""

from typing import Callable, Optional, Sequence


def _clamp_to_bounds_float(
    values: Sequence[float], bounds: Optional[Sequence[tuple[float, float]]]
) -> list[float]:
    """Clamp float vector into closed intervals."""
    if bounds is None:
        return list(values)
    output = list(values)
    for idx, (lower, upper) in enumerate(bounds[: len(output)]):
        output[idx] = max(float(lower), min(float(upper), float(output[idx])))
    return output


def _clamp_to_bounds_hp(
    values: Sequence[object], bounds: Optional[Sequence[tuple[float, float]]], to_mpf: Callable[[float], object]
) -> list[object]:
    """Clamp high-precision vector with converter-based bound casting."""
    if bounds is None:
        return list(values)
    output = list(values)
    for idx, (lower, upper) in enumerate(bounds[: len(output)]):
        lo_mpf = to_mpf(lower)
        hi_mpf = to_mpf(upper)
        if output[idx] < lo_mpf:
            output[idx] = lo_mpf
        elif output[idx] > hi_mpf:
            output[idx] = hi_mpf
    return output
