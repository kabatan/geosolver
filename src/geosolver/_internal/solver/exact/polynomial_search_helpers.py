"""Shared helpers for polynomial search utilities."""

from __future__ import annotations

import re
from typing import Any, List

from mpmath import almosteq, fabs, mp, mpf


def strip_whitespace(value: str) -> str:
    return re.sub(r"\s+", "", value)


def scale_candidates_for_value(val: Any) -> List[Any]:
    vabs = fabs(val)
    if vabs == 0:
        return [mpf("1")]
    try:
        k = int(mp.floor(mp.log10(vabs)))
    except Exception:
        return [mpf("1")]

    scales: List[Any] = []
    for kk in (k, k - 1, k + 1):
        try:
            scales.append(mpf(10) ** kk)
        except Exception:
            pass
    scales.append(mpf("1"))

    uniq: List[Any] = []
    for s in scales:
        if s == 0:
            continue
        if any(almosteq(s, t, rel_eps=mpf("1e-20"), abs_eps=mpf("0")) for t in uniq):
            continue
        uniq.append(s)
    return uniq


def gram_schmidt_lll(B: Any) -> tuple[Any, Any]:
    import numpy as np

    n = len(B)
    Q = np.zeros_like(B, dtype=np.float64)
    mu = np.zeros((n, n), dtype=np.float64)

    for i in range(n):
        Q[i] = B[i].copy()
        for j in range(i):
            if np.dot(Q[j], Q[j]) > 1e-10:
                mu[i, j] = np.dot(B[i], Q[j]) / np.dot(Q[j], Q[j])
                Q[i] = Q[i] - mu[i, j] * Q[j]

    return Q, mu


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


def simple_lll(basis: Any, delta: float = 3 / 4) -> Any:
    """Simple LLL implementation based on Gram-Schmidt orthogonalization."""
    import numpy as np

    n = len(basis)
    B = basis.astype(np.float64).copy()

    k = 1
    while k < n:
        Q, mu = gram_schmidt_lll(B)

        for j in range(k - 1, -1, -1):
            if abs(mu[k, j]) > 0.5:
                B[k] = B[k] - round(mu[k, j]) * B[j]
                Q, mu = gram_schmidt_lll(B)

        if np.dot(Q[k], Q[k]) >= (delta - mu[k, k - 1] ** 2) * np.dot(Q[k - 1], Q[k - 1]):
            k += 1
        else:
            B[[k, k - 1]] = B[[k - 1, k]]
            k = max(k - 1, 1)

    norms = [np.linalg.norm(row) for row in B]
    indices = np.argsort(norms)
    return B[indices]


def verify_polynomial(coeffs: List[int], r: Any, precision: float) -> bool:
    """Verify whether the polynomial has ``r`` as a root."""
    mp.dps = max(int(precision) + 20, 50)

    val = mpf(0)
    degree = len(coeffs) - 1
    for i, c in enumerate(coeffs):
        val += mpf(c) * (r ** (degree - i))

    if precision > 100:
        tol = mpf(10) ** (-(precision * 3 / 5))
    else:
        tol = mpf(10) ** (-(precision * 2 / 5))
    return fabs(val) < tol