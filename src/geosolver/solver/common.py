"""
共通ユーティリティ（solver / optimizer 共有）

- 境界処理や目的関数生成を一箇所にまとめて重複を削減
- API は既存クラスから呼び出すだけで変更しない
"""

from __future__ import annotations

from functools import partial
from typing import Callable, List, Optional, Sequence, Tuple

import numpy as np

# デフォルトの探索範囲
DEFAULT_BOUNDS: Tuple[float, float] = (-100.0, 100.0)
FAILURE_OBJECTIVE_VALUE: float = float("inf")
FAILURE_RESIDUAL_VALUE: float = 1e20
FAILURE_INEQUALITY_VALUE: float = -1e20


def _objective_value(
    x: List[float],
    *,
    f: Callable[[List[float]], Sequence[float]],
    v_arr: np.ndarray,
) -> float:
    try:
        residuals = np.asarray(f(x), dtype=float) - v_arr
        if not residuals.shape == v_arr.shape:
            residuals = residuals.reshape(v_arr.shape)
        if not np.all(np.isfinite(residuals)):
            return FAILURE_OBJECTIVE_VALUE
        return float(np.dot(residuals, residuals))
    except Exception:
        return FAILURE_OBJECTIVE_VALUE


def _inequality_value(x: List[float], *, func: Callable[[List[float]], float]) -> float:
    try:
        val = func(x)
        if isinstance(val, (list, tuple, np.ndarray)):
            return float(val[0])
        return float(val)
    except Exception:
        return FAILURE_INEQUALITY_VALUE


def normalize_bounds(bounds: Optional[Sequence[Optional[Tuple[float, float]]]], n: int) -> List[Tuple[float, float]]:
    """与えられた bounds を長さ n の (lo, hi) リストに正規化する。"""
    if bounds is None:
        return [DEFAULT_BOUNDS] * n

    normalized: List[Tuple[float, float]] = []
    for b in bounds:
        if b is None:
            normalized.append(DEFAULT_BOUNDS)
            continue
        lo, hi = b
        normalized.append((float(lo), float(hi)))
    # 足りない場合はデフォルトで埋める
    while len(normalized) < n:
        normalized.append(DEFAULT_BOUNDS)
    return normalized[:n]


def expand_bounds_around_point(
    bounds: Sequence[Tuple[float, float]],
    x0: Sequence[float],
    *,
    margin_scale: float = 0.5,
    margin_min: float = 10.0,
) -> List[Tuple[float, float]]:
    """Return a copy of bounds expanded enough to contain the start point x0.

    The old public helper name was ``tighten_bounds_around_point`` even though
    the implementation intentionally widens the search region.  The clearer
    name is used internally; a compatibility alias is kept below.
    """
    tightened: List[Tuple[float, float]] = []
    for val, (lo, hi) in zip(x0, bounds):
        margin = abs(val) * margin_scale + margin_min
        lo2 = min(lo, val - margin)
        hi2 = max(hi, val + margin)
        tightened.append((lo2, hi2))
    return tightened


def tighten_bounds_around_point(
    bounds: Sequence[Tuple[float, float]],
    x0: Sequence[float],
    *,
    margin_scale: float = 0.5,
    margin_min: float = 10.0,
) -> List[Tuple[float, float]]:
    """Compatibility alias for :func:`expand_bounds_around_point`."""

    return expand_bounds_around_point(
        bounds,
        x0,
        margin_scale=margin_scale,
        margin_min=margin_min,
    )


def objective_from_residuals(f: Callable[[List[float]], Sequence[float]], v_arr: np.ndarray) -> Callable[[List[float]], float]:
    """f(x) の残差二乗和を返す objective を生成。数値異常時は inf を返す。"""
    return partial(_objective_value, f=f, v_arr=v_arr)


def residual_vector(f: Callable[[List[float]], Sequence[float]], v_arr: np.ndarray, x: Sequence[float]) -> np.ndarray:
    """等式制約用に f(x) - v を安全に計算する。失敗時は巨大値を返す。"""
    try:
        res = np.asarray(f(x), dtype=float) - v_arr
        if not np.all(np.isfinite(res)):
            return np.full_like(v_arr, FAILURE_RESIDUAL_VALUE, dtype=float)
        if res.shape != v_arr.shape:
            res = res.reshape(v_arr.shape)
        return res
    except Exception:
        return np.full_like(v_arr, FAILURE_RESIDUAL_VALUE, dtype=float)


def inequality_wrapper(func: Callable[[List[float]], float]) -> Callable[[List[float]], float]:
    """scipy 用の inequality constraint ラッパー（>0 を期待）。"""
    return partial(_inequality_value, func=func)

