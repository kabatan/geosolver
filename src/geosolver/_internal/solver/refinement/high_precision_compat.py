"""Compatibility wrapper for high-precision refinement APIs."""

from typing import Callable, List, Tuple, Optional
from functools import partial
import traceback

from mpmath import mp, mpf

from geosolver._internal.observability.logging import emit_legacy_log as _emit_log
from geosolver._internal.solver.precision.type_guards.strict_to_mpf import strict_to_mpf
from .high_precision_projection import (
    _compute_constraint_residual_hp,
    _project_to_constraint_hp,
    _solve_square_system_hp,
    _to_mpf_value,
)
from .high_precision_compat_helpers import (
    _auto_high_precision_wrapper,
    _square_residual_function,
)


RESIDUAL_CHECK_PRECISION_SCALE = 1.05
ROBUST_PROJECTION_EXTRA_DIGITS = 120
ROBUST_PROJECTION_PRECISION_SCALE = 1.6


def refine_high_precision(
    f: Callable,
    v: List[float],
    solutions: List[List[float]],
    precision: int,
    verbose: bool = False,
    bounds: Optional[List[Tuple[float, float]]] = None,
    deadline: Optional[float] = None,
) -> Tuple[List[List[float]], List[float], Optional[List]]:
    """高精度射影による解精密化"""
    if getattr(f, "__geosolver_hp_wrapper__", False):
        f_hp = f
    else:
        f_hp = _auto_high_precision_wrapper(f, precision) or f

    try:
        mp.dps = max(int(mp.dps), int(precision) + 90)
    except Exception:
        mp.dps = max(mp.dps, precision + 90)

    refined_solutions: List[List] = []
    refined_residuals: List = []  # Changed from List[float] to preserve mpf precision
    hp_solutions: List[List] = []

    if not solutions:
        return [], [], []

    n = len(solutions[0])
    m = len(v)
    v_mp = [_to_mpf_value(vi, precision) for vi in v]

    for idx, sol in enumerate(solutions):
        if verbose:
            _emit_log(f"  解#{idx + 1}を高精度射影中...")

        try:
            x_mp = [_to_mpf_value(xi, precision) for xi in sol]

            f_init = f_hp(x_mp)
            res_init_vec = [
                strict_to_mpf(f_init[k], context="high_precision_compat.initial_residual") - v_mp[k]
                for k in range(m)
            ]
            res_init_norm = mp.sqrt(sum(r**2 for r in res_init_vec))
            if verbose:
                _emit_log(f"    初期残差norm={float(res_init_norm):.4e}")
                _emit_log(f"    初期残差vec={[float(r) for r in res_init_vec]}")
                _emit_log(f"    v_mp={[float(val) for val in v_mp]}")
                _emit_log(f"    f_val={[float(val) for val in f_init]}")

            projected = x_mp
            projected = _project_to_constraint_hp(
                f_hp, v_mp, projected, n, m, precision, deadline=deadline, bounds=bounds
            )
            residual = _compute_constraint_residual_hp(
                f_hp,
                v_mp,
                projected,
                precision=max(precision, int(precision * RESIDUAL_CHECK_PRECISION_SCALE)),
            )

            if residual is None:
                if verbose:
                    _emit_log("    残差がNoneのため初期点へフォールバック")
                projected = x_mp
                residual = mpf("inf")
            else:
                try:
                    is_finite = mp.isfinite(residual)
                except:
                    try:
                        residual_str = str(residual)
                        is_finite = not (
                            "inf" in residual_str.lower() or "nan" in residual_str.lower()
                        )
                    except:
                        is_finite = False

                if not is_finite:
                    if verbose:
                        _emit_log("    残差が非有限のため初期点へフォールバック")
                    projected = x_mp
                    residual = mpf("inf")

            if verbose:
                _emit_log(f"    制約残差={float(residual):.2e}")

            try:
                target_res = mpf(10) ** (-(precision + 10))
            except Exception:
                target_res = None
            if target_res is not None and residual is not None and residual > target_res and m == n:
                if verbose:
                    _emit_log("    追加のNewton高精度化を試行...")

                F_sq = partial(_square_residual_function, f_hp=f_hp, v_mp=v_mp, m=m)

                try:
                    best_x, best_norm = _solve_square_system_hp(
                        F_sq,
                        projected,
                        n,
                        precision,
                        deadline=deadline,
                        bounds=bounds,
                        max_iter=min(120, max(60, int(precision * 1.0))),
                        tol_digits=int(precision),
                        stagnation_limit=30,
                    )
                    if best_norm is not None and best_norm < residual:
                        projected = best_x
                        residual = best_norm
                        if verbose:
                            _emit_log(f"    Newton後残差={float(residual):.2e}")
                except Exception:
                    pass

            try:
                if residual is not None:
                    target2 = mpf(10) ** (-(precision + 10))
                else:
                    target2 = None
                if target2 is not None and residual is not None and residual > target2:
                    if verbose:
                        _emit_log("    追加のHP射影(robust)を試行...")
                    proj2 = _project_to_constraint_hp(
                        f_hp,
                        v_mp,
                        projected,
                        n,
                        m,
                        max(
                            int(precision) + ROBUST_PROJECTION_EXTRA_DIGITS,
                            int(precision * ROBUST_PROJECTION_PRECISION_SCALE),
                        ),
                        deadline=deadline,
                        bounds=bounds,
                    )
                    residual2 = _compute_constraint_residual_hp(
                        f_hp,
                        v_mp,
                        proj2,
                        precision=max(precision, int(precision * RESIDUAL_CHECK_PRECISION_SCALE)),
                    )
                    if residual2 is not None and residual2 < residual:
                        projected = proj2
                        residual = residual2
                        if verbose:
                            _emit_log(f"    robust後残差={float(residual):.2e}")
            except Exception:
                pass

            refined_solutions.append([_to_mpf_value(x, precision) for x in projected])
            refined_residuals.append(residual)
            hp_solutions.append(projected)

        except Exception as exc:
            if verbose:
                _emit_log(f"    高精度射影失敗: {exc}")
                traceback.print_exc()
            refined_solutions.append(sol)
            refined_residuals.append(1.0)
            hp_solutions.append([_to_mpf_value(xi, precision) for xi in sol])

    return refined_solutions, refined_residuals, hp_solutions

