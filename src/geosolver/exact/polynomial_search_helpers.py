"""Shared helpers for polynomial search utilities."""

from __future__ import annotations

import re
from contextlib import suppress
from typing import Any

from mpmath import almosteq, fabs, mp, mpf


def strip_whitespace(value: str) -> str:
    return re.sub(r"\s+", "", value)


def scale_candidates_for_value(val: Any) -> list[Any]:
    vabs = fabs(val)
    if vabs == 0:
        return [mpf("1")]
    try:
        k = int(mp.floor(mp.log10(vabs)))
    except Exception:
        return [mpf("1")]

    scales: list[Any] = []
    for kk in (k, k - 1, k + 1):
        with suppress(Exception):
            scales.append(mpf(10) ** kk)
    scales.append(mpf("1"))

    uniq: list[Any] = []
    for s in scales:
        if s == 0:
            continue
        if any(almosteq(s, t, rel_eps=mpf("1e-20"), abs_eps=mpf("0")) for t in uniq):
            continue
        uniq.append(s)
    return uniq


def to_mpf_sanitized(val: Any) -> Any:
    """Convert numeric-ish inputs to mpf with robust string handling."""
    if isinstance(val, mpf):
        return val

    try:
        return mpf(val)
    except Exception:
        pass

    if hasattr(val, "evalf"):
        try:
            s = str(val.evalf(int(getattr(mp, "dps", 50))))
            return mpf(strip_whitespace(s))
        except Exception:
            pass

    try:
        s0 = strip_whitespace(str(val))
        m = re.fullmatch(r"mpf\((['\"])(.*)\1\)", s0)
        if m:
            s0 = m.group(2)
        return mpf(s0)
    except Exception:
        return mpf("nan")


def verify_polynomial(coeffs: list[int], r: Any, precision: float) -> bool:
    """Verify whether the polynomial has ``r`` as a root."""
    with mp.workdps(max(mp.dps, int(precision) + 20, 50)):
        val = mpf(0)
        magnitude = mpf(0)
        degree = len(coeffs) - 1
        for i, c in enumerate(coeffs):
            term = mpf(c) * (r ** (degree - i))
            val += term
            magnitude += abs(term)

        if precision > 100:
            tol = mpf(10) ** (-(precision * 3 / 5))
        else:
            tol = mpf(10) ** (-(precision * 2 / 5))
        return val == 0 or (magnitude > 0 and fabs(val) / magnitude < tol)
