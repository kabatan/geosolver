"""
高精度最適化ソルバーモジュール

Archiveのgeosolver.py/optimizer.pyから高精度計算機能（mpmath使用）を抽出し、
現在のgeosolverアーキテクチャに統合したもの。
"""

from typing import Callable, List, Tuple, Optional, Any, Dict, Union
import math
import os
import time
import re
from contextlib import contextmanager
from functools import partial
import traceback

import numpy as np
from mpmath import mp, mpf

from geosolver.engine.standard.precision.utilities import (
    call_with_precision,
    PrecisionKwargCache,
    ensure_mp_dps,
    compute_target_dps,
)
from geosolver.runtime.logging import emit_legacy_log as _emit_log
from geosolver.geometry.mp.mp_api import use_mpmath_api, _to_mpf
from geosolver.engine.standard.precision.type_guards.ensure_no_float import (
    ensure_high_precision_mode,
    ensure_no_float,
)
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.engine.standard.precision.type_guards.strict_to_mpf import strict_to_mpf

# -----------------------------------------------------------------------------
# Internal Helpers
# -----------------------------------------------------------------------------


def _strip_ws(s: str) -> str:
    return re.sub(r"\s+", "", s)


def _to_mpf_value(val, precision: int, *, nsimplify_float: bool = False):
    """sympy定数や文字列を含む値を mpf に安全変換（optimizer.py互換）。"""
    if isinstance(val, mpf):
        return val
    if isinstance(val, float):
        raise TypeError("float is forbidden in high precision projection")
    if isinstance(val, (int, mpf)):
        return strict_to_mpf(val, context="high_precision_projection._to_mpf_value")
    return strict_to_mpf(val, context="high_precision_projection._to_mpf_value")


def _set_mp_dps_for_precision(precision: int, extra: int = 0) -> None:
    """高精度フェーズ用の mp.dps 設定。"""
    try:
        prec = max(1, int(precision))
    except Exception:
        prec = 50

    buffer = max(40, min(prec // 4 + 40, 160))
    extra_guard = max(0, min(int(extra), max(40, prec // 4)))

    target = prec + buffer + extra_guard
    if prec <= 240:
        target = min(target, prec + 180)
    target = min(target, 2000)

    # 既に十分な精度が設定されている場合はスキップ（高速化）
    if mp.dps >= target:
        return
    mp.dps = target


def _clamp_to_bounds_hp(
    x: List,
    bounds: Optional[List[Tuple[float, float]]],
    to_mpf: Callable,
) -> List:
    if bounds is None:
        return x
    out = x[:]
    for j in range(min(len(out), len(bounds))):
        lo, hi = bounds[j]
        lo_m = to_mpf(lo)
        hi_m = to_mpf(hi)
        if out[j] < lo_m:
            out[j] = lo_m
        elif out[j] > hi_m:
            out[j] = hi_m
    return out


def _compute_constraint_residual_hp(
    f: Callable, v: List, x: List, precision: int = None
) -> Optional[mpf]:
    return _compute_constraint_residual_hp_impl(
        f,
        v,
        x,
        precision,
        to_mpf_value=_to_mpf_value,
    )


def _solve_square_system_hp(
    F: Callable,
    x0: List,
    n: int,
    precision: int,
    deadline: Optional[float] = None,
    bounds: Optional[List[Tuple[float, float]]] = None,
    max_iter: int = 50,
    tol_digits: int = 60,
    stagnation_limit: int = 20,
    ls_steps: int = 12,
    delta_cap: int = 200,
) -> Tuple[List, Optional[mpf]]:
    return _solve_square_system_hp_impl(
        F,
        x0,
        n,
        precision,
        to_mpf_value=_to_mpf_value,
        clamp_to_bounds_hp=_clamp_to_bounds_hp,
        deadline=deadline,
        bounds=bounds,
        max_iter=max_iter,
        tol_digits=tol_digits,
        stagnation_limit=stagnation_limit,
        ls_steps=ls_steps,
        delta_cap=delta_cap,
    )


# -----------------------------------------------------------------------------
# Core Algorithms (from optimizer.py)
# -----------------------------------------------------------------------------


from .high_precision_projection_algorithms import (
    _project_to_constraint_hp,
    _project_to_constraint_hp_fast,
    project_constraint_follow,
)
from .high_precision_projection_numerics import (
    compute_constraint_residual_hp as _compute_constraint_residual_hp_impl,
    solve_square_system_hp as _solve_square_system_hp_impl,
)



# -----------------------------------------------------------------------------
# Main Wrapper (from geosolver.py)
# -----------------------------------------------------------------------------


def project_high_precision(
    f: Callable,
    v: List,
    x: List,
    n: int,
    m: int,
    precision: int,
    deadline: Optional[float] = None,
    bounds: Optional[List[Tuple[float, float]]] = None,
) -> List:
    """Compatibility wrapper for HP projection + constraint-follow path."""
    with high_precision_mode():
        ensure_high_precision_mode(context="project_high_precision")
        ensure_no_float(v, context="project_high_precision.target")
        ensure_no_float(x, context="project_high_precision.seed")
        return project_constraint_follow(
            f,
            v,
            x,
            n,
            m,
            precision,
            deadline=deadline,
            bounds=bounds,
        )

