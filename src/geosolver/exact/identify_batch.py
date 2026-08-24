"""Batch exact-value identification."""

from collections.abc import Sequence
import math
from typing import Any

from mpmath import mpf
from geosolver.exact.approximate_marker import (
    is_approximate_marker,
    strip_approximate_marker_prefix,
)

from .identify_value import identify_value


def _is_approximate_marker(value: Any) -> bool:
    return is_approximate_marker(value)


def _normalize_identify_input(value: Any) -> Any:
    if _is_approximate_marker(value):
        return value
    if isinstance(value, str):
        text = strip_approximate_marker_prefix(value)
        if not text:
            return value
        try:
            return mpf(text)
        except Exception:
            return value
    return value


def _skipped_result(value: Any, *, reason: str) -> dict[str, object]:
    return {
        "value": str(value),
        "pslq": None,
        "minimal_polynomial": None,
        "exact": None,
        "verified": False,
        "error": reason,
    }


def _identify_single(
    value: Any,
    *,
    max_degree: int,
    precision: int,
) -> dict[str, object]:
    if _is_approximate_marker(value):
        return _skipped_result(value, reason="approximate_value")

    identify_input = _normalize_identify_input(value)
    if isinstance(identify_input, (int, float)) and not math.isfinite(float(identify_input)):
        return _skipped_result(value, reason="non_finite_value")
    try:
        identified = identify_value(identify_input, max_degree=max_degree, precision=precision)
    except Exception as exc:
        return {
            "value": str(value),
            "pslq": None,
            "minimal_polynomial": None,
            "exact": None,
            "verified": False,
            "error": str(exc),
        }
    identified.setdefault("error", None)
    return identified


def identify_exact_answers(
    values: Sequence[object],
    max_degree: int = 4,
    precision: int = 50,
) -> list[dict[str, object]]:
    """Identify exact structure for all values in a batch."""
    return [
        _identify_single(value, max_degree=max_degree, precision=precision)
        for value in values
    ]
