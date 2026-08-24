"""Helper utilities for high_precision_compat wrapper logic."""

from contextlib import contextmanager
from functools import partial
from typing import Any, Callable, List

from mpmath import mp

from geosolver.geometry.mp.mp_api import use_mpmath_api
from geosolver.engine.standard.precision.utilities import PrecisionKwargCache, call_with_precision
from geosolver.engine.standard.precision.type_guards.boundary_float_to_mpf import (
    BoundaryOrigin,
    boundary_float_to_mpf,
)
from geosolver.engine.standard.precision.type_guards.high_precision_contamination_error import (
    HighPrecisionContaminationError,
)
from geosolver.engine.standard.precision.type_guards.high_precision_mode import (
    suspend_high_precision_mode,
)
from geosolver.engine.standard.precision.type_guards.strict_to_mpf import strict_to_mpf

from .high_precision_projection import _to_mpf_value


def _coerce_zone_a_numeric_to_mpf(value: Any, *, context: str) -> Any:
    """Normalize Zone A callback numeric outputs back into HP-safe values."""
    if isinstance(value, float):
        return boundary_float_to_mpf(value, origin=BoundaryOrigin.LEGACY_BOUND)
    if isinstance(value, list):
        return [
            _coerce_zone_a_numeric_to_mpf(item, context=f"{context}[{index}]")
            for index, item in enumerate(value)
        ]
    if isinstance(value, tuple):
        return tuple(
            _coerce_zone_a_numeric_to_mpf(item, context=f"{context}[{index}]")
            for index, item in enumerate(value)
        )
    try:
        return strict_to_mpf(value, context=context)
    except (TypeError, HighPrecisionContaminationError):
        return value


def _auto_wrapper_call(
    vec: List,
    *,
    f: Callable,
    precision: int,
    prec_cache: PrecisionKwargCache,
) -> Any:
    mp.dps = max(mp.dps, precision + 20)
    mp_vec = [_to_mpf_value(val, precision) for val in vec]
    globals_dict = f.__globals__
    with use_mpmath_api(globals_dict, precision):
        with _temporary_override_global(f, "precision", int(precision)):
            # User callbacks are treated as Zone A and converted at the boundary.
            with suspend_high_precision_mode():
                raw_result = call_with_precision(f, mp_vec, precision, cache=prec_cache)
                return _coerce_zone_a_numeric_to_mpf(
                    raw_result,
                    context="high_precision_compat.auto_wrapper_result",
                )


def _square_residual_function(xx: List, *, f_hp: Callable, v_mp: List, m: int) -> List:
    f_val = f_hp(xx)
    return [strict_to_mpf(f_val[k], context="high_precision_compat.square_residual") - v_mp[k] for k in range(m)]


def _auto_high_precision_wrapper(f: Callable, precision: int) -> Callable[[List], Any]:
    """元のfからmpmath版を自動生成（geometry APIをmp実装に差し替え）"""
    _prec_cache = PrecisionKwargCache()

    f_mp = partial(_auto_wrapper_call, f=f, precision=precision, prec_cache=_prec_cache)

    try:
        setattr(f_mp, "__geosolver_hp_wrapper__", True)
        setattr(f_mp, "__geosolver_hp_precision__", int(precision))
        setattr(f_mp, "__geosolver_hp_original__", f)
    except Exception:
        pass

    return f_mp


@contextmanager
def _temporary_override_global(fn: Callable, name: str, value: object) -> Any:
    g = getattr(fn, "__globals__", None)
    if not isinstance(g, dict) or name not in g:
        yield
        return
    old = g.get(name)
    if not isinstance(old, (int, float)):
        yield
        return
    try:
        g[name] = value
        yield
    finally:
        try:
            g[name] = old
        except Exception:
            pass


@contextmanager
def _override_evalf_precision(tmp_precision: int) -> Any:
    """User定義f()がevalfの精度を動的参照できるようにする（ダミー実装）。"""
    _ = tmp_precision
    yield


def mp_list_to_float(vec: List) -> List[float]:
    converted = []
    for entry in vec:
        try:
            converted.append(float(entry))
        except (ValueError, OverflowError):
            converted.append(float("inf") if entry > 0 else float("-inf"))
    return converted
