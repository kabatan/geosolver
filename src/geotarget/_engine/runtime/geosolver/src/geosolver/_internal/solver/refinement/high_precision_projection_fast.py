"""Fast high-precision projection algorithm extracted from projection algorithms."""

from __future__ import annotations

import re
import time
from functools import partial
from typing import Callable, List, Optional, Tuple

from mpmath import mp, mpf


def _projection_to_mpf_fast(val: object, *, precision: int, to_mpf_value: Callable) -> mpf:
    try:
        return to_mpf_value(val, precision)
    except Exception:
        s = re.sub(r"\s+", "", str(val))
        return mpf(s)


def _resolve_base_helpers_fast() -> tuple[Callable, Callable, Callable]:
    from . import high_precision_projection as _base

    return _base._set_mp_dps_for_precision, _base._to_mpf_value, _base._clamp_to_bounds_hp


def project_to_constraint_hp_fast_impl(
    f: Callable,
    v: List,
    x: List,
    n: int,
    m: int,
    precision: int,
    deadline: Optional[float] = None,
    bounds: Optional[List[Tuple[float, float]]] = None,
) -> List:
    _set_mp_dps_for_precision, _to_mpf_value, _clamp_to_bounds_hp = _resolve_base_helpers_fast()
    _set_mp_dps_for_precision(precision, extra=60)

    to_mpf = partial(_projection_to_mpf_fast, precision=precision, to_mpf_value=_to_mpf_value)

    x = _clamp_to_bounds_hp(x, bounds, to_mpf)

    v_norm = mp.sqrt(sum(to_mpf(vi) ** 2 for vi in v))
    if v_norm < 1:
        v_norm = mpf("1")

    max_iter = min(30, precision // 10 + 10)

    for _ in range(max_iter):
        if deadline is not None and time.time() >= deadline:
            break
        try:
            f_val = f(x)
            residual = [to_mpf(f_val[k]) - v[k] for k in range(m)]

            res_norm = mp.sqrt(sum(r**2 for r in residual))

            if res_norm / v_norm < mpf(10) ** (-(precision * 0.5)):
                break

            if res_norm > 1e10:
                break

            delta = mpf(10) ** (-max(20, precision // 3))
            J = []
            for j in range(n):
                x_plus = x[:]
                x_plus[j] = to_mpf(x_plus[j]) + delta
                f_plus = f(x_plus)
                col = [(to_mpf(f_plus[k]) - to_mpf(f_val[k])) / delta for k in range(m)]
                J.append(col)

            from mpmath import matrix, lu_solve

            J_mat = matrix(m, n)
            for r in range(m):
                for c in range(n):
                    J_mat[r, c] = J[c][r]

            res_vec = matrix(m, 1)
            for r in range(m):
                res_vec[r] = -residual[r]

            if m == n:
                step = lu_solve(J_mat, res_vec)
            else:
                jtj = J_mat.T * J_mat
                jtr = J_mat.T * res_vec
                for k in range(n):
                    jtj[k, k] += mpf(10) ** (-20)
                step = lu_solve(jtj, jtr)

            x_next = []
            alpha = mpf(1.0)
            for j in range(n):
                x_next.append(x[j] + alpha * step[j])

            x_next_clamped = _clamp_to_bounds_hp(x_next, bounds, to_mpf)

            try:
                res_next_val = f(x_next_clamped)
                res_next_norm = mp.sqrt(sum((to_mpf(res_next_val[k]) - v[k]) ** 2 for k in range(m)))
                if res_next_norm > res_norm * 10:
                    break
                x = x_next_clamped
            except Exception:
                break

        except Exception:
            break

    return x