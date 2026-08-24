"""Numerical helper implementations for high-precision projection."""

from __future__ import annotations

import time
from typing import Callable, List, Optional, Tuple

from mpmath import mp, mpf


def compute_constraint_residual_hp(
    f: Callable,
    v: List,
    x: List,
    precision: Optional[int],
    *,
    to_mpf_value: Callable,
) -> Optional[mpf]:
    """高精度での制約残差 ||f(x) - v|| を計算"""
    try:
        f_val = f(x)
        if f_val is None:
            return None
        if not hasattr(f_val, "__len__") or len(f_val) != len(v):
            return None

        res_sq = mpf(0)
        for i in range(len(v)):
            try:
                f_i = to_mpf_value(f_val[i], precision)
                v_i = to_mpf_value(v[i], precision)
                if not mp.isfinite(f_i) or not mp.isfinite(v_i):
                    return None
                diff = f_i - v_i
                res_sq += diff * diff
            except Exception:
                return None

        result = mp.sqrt(res_sq)
        return result if mp.isfinite(result) else None
    except Exception:
        return None


def solve_square_system_hp(
    F: Callable,
    x0: List,
    n: int,
    precision: int,
    *,
    to_mpf_value: Callable,
    clamp_to_bounds_hp: Callable,
    deadline: Optional[float] = None,
    bounds: Optional[List[Tuple[float, float]]] = None,
    max_iter: int = 50,
    tol_digits: int = 60,
    stagnation_limit: int = 20,
    ls_steps: int = 12,
    delta_cap: int = 200,
) -> Tuple[List, Optional[mpf]]:
    """簡易的な高精度ニュートン法 (Square system求解)"""
    from functools import partial
    from mpmath import matrix, lu_solve

    x = x0[:]
    to_mpf = partial(to_mpf_value, precision=precision)

    best_x = x[:]
    best_norm = mpf("inf")
    delta = mpf(10) ** (-max(20, precision // 3))

    for _ in range(max_iter):
        if deadline is not None and time.time() > deadline:
            break

        try:
            residuals = F(x)
            norm = mp.sqrt(sum(r * r for r in residuals))

            if norm < best_norm:
                best_norm = norm
                best_x = x[:]

            if norm < mpf(10) ** (-tol_digits):
                break

            J_cols = []
            for j in range(n):
                x_plus = x[:]
                x_plus[j] = to_mpf(x_plus[j]) + delta
                res_plus = F(x_plus)
                col = [(res_plus[k] - residuals[k]) / delta for k in range(n)]
                J_cols.append(col)

            J_mat = matrix(n, n)
            for r in range(n):
                for c in range(n):
                    J_mat[r, c] = J_cols[c][r]

            res_vec = matrix([-r for r in residuals])
            step = lu_solve(J_mat, res_vec)

            accepted = False
            for k in range(ls_steps):
                alpha = mpf(0.5) ** k
                x_next = []
                for j in range(n):
                    x_next.append(x[j] + alpha * step[j])

                if bounds:
                    x_next = clamp_to_bounds_hp(x_next, bounds, to_mpf)

                try:
                    res_next = F(x_next)
                    norm_next = mp.sqrt(sum(r * r for r in res_next))
                    if norm_next < norm:
                        x = x_next
                        accepted = True
                        break
                except Exception:
                    pass

            if not accepted:
                break

        except Exception:
            break

    return best_x, best_norm