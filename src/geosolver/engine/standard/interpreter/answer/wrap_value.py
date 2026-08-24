"""Exact-value wrapping helpers."""

from __future__ import annotations

from typing import Any

from geosolver.engine.standard.result import ExactValue
from geosolver.exact import identify
from geosolver.exact.approximate_marker import is_approximate_marker

from .eval_to_mpf import _eval_exact_to_mpf
from .normalize_exact_string import _normalize_exact_string

def _is_approximate_text(value: Any) -> bool:
    return is_approximate_marker(value)


def _identify_exact_text(value: Any, precision: int) -> str | None:
    try:
        identified = identify(value, precision=int(precision))
    except Exception:
        return None
    if not isinstance(identified, str):
        return None
    text = identified.strip()
    if not text or _is_approximate_text(text):
        return None
    return _normalize_exact_string(text)


def _wrap_exact_value(
    value: Any,
    numeric_override: Any | None = None,
    *,
    precision: int | None = None,
) -> ExactValue:
    """Wrap textual exact answer while preserving numeric fallback.

    Legacy-compat contract:
    - `_wrap_exact_value(value, precision)` positional 2nd arg is accepted.
    - `_wrap_exact_value(value, numeric_override=...)` also supported.
    """
    normalized = _normalize_exact_string(value)

    effective_precision = precision
    effective_override = numeric_override
    is_numeric_value = isinstance(value, (int, float))
    if effective_precision is None and isinstance(effective_override, int) and not is_numeric_value:
        if effective_override >= 10:
            effective_precision = int(effective_override)
            effective_override = None
    if effective_precision is None:
        effective_precision = 80

    should_identify = not _is_approximate_text(value)
    if should_identify:
        identified = _identify_exact_text(value, int(effective_precision))
        if identified:
            normalized = identified

    if effective_override is None and not _is_approximate_text(value):
        try:
            parsed = _eval_exact_to_mpf(normalized, precision=effective_precision or 80)
            if parsed is not None:
                effective_override = parsed
        except Exception:
            effective_override = None

    return ExactValue(normalized, numeric_override=effective_override)
