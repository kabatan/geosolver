"""Runtime high-precision mode boundary based on contextvars.

Implements dynamic float-contamination guards via mpmath monkeypatch.
Patches are applied once at module import; ContextVar flags control
whether guards are active (HP mode) or inactive (Zone A passthrough).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from mpmath import mp, mpf

from .high_precision_contamination_error import HighPrecisionContaminationError

try:
    import numpy as np

    _NUMPY_FLOATING_TYPES: tuple[type, ...] = (np.floating,)
except Exception:  # pragma: no cover
    _NUMPY_FLOATING_TYPES = ()

try:
    from sympy import Float as _SympyFloat

    _FLOAT_TYPES: tuple[type, ...] = (float,) + _NUMPY_FLOATING_TYPES + (_SympyFloat,)
except Exception:  # pragma: no cover
    _FLOAT_TYPES = (float,) + _NUMPY_FLOATING_TYPES

# ---------------------------------------------------------------------------
# ContextVars (reference-counted for reentrancy)
# ---------------------------------------------------------------------------

_hp_mode_active: ContextVar[int] = ContextVar("_hp_mode_active", default=0)
_in_boundary_conversion: ContextVar[int] = ContextVar("_in_boundary_conversion", default=0)

def is_high_precision_mode() -> bool:
    """Return whether current execution context is in high-precision mode."""
    return _hp_mode_active.get(0) > 0


@contextmanager
def high_precision_mode() -> Iterator[None]:
    """Enable high-precision mode in current context (reentrant)."""
    token = _hp_mode_active.set(_hp_mode_active.get(0) + 1)
    try:
        yield
    finally:
        _hp_mode_active.reset(token)


@contextmanager
def _boundary_conversion_context() -> Iterator[None]:
    """Temporarily bypass constructor guard for boundary_float_to_mpf.

    Internal use only — must not be called outside boundary_float_to_mpf.
    """
    token = _in_boundary_conversion.set(_in_boundary_conversion.get(0) + 1)
    try:
        yield
    finally:
        _in_boundary_conversion.reset(token)


# ---------------------------------------------------------------------------
# Guard helpers
# ---------------------------------------------------------------------------


def _is_hp_active() -> bool:
    return _hp_mode_active.get(0) > 0


def _check_float_operand(other: Any, op: str) -> None:
    # Exact mpf and int operands cannot be float contamination. Avoid reading
    # context state for these common operands; subclasses keep the full check.
    if type(other) is mpf or type(other) is int:
        return
    if _is_hp_active() and isinstance(other, _FLOAT_TYPES):
        raise HighPrecisionContaminationError(f"mpf {op} float: {other!r}")


# ---------------------------------------------------------------------------
# Original methods (saved before patching)
# ---------------------------------------------------------------------------

_original_add = mpf.__add__
_original_radd = mpf.__radd__
_original_sub = mpf.__sub__
_original_rsub = mpf.__rsub__
_original_mul = mpf.__mul__
_original_rmul = mpf.__rmul__
_original_truediv = mpf.__truediv__
_original_rtruediv = mpf.__rtruediv__
_original_pow = mpf.__pow__
_original_rpow = mpf.__rpow__
_original_le = mpf.__le__
_original_lt = mpf.__lt__
_original_ge = mpf.__ge__
_original_gt = mpf.__gt__
_original_eq = mpf.__eq__
_original_ne = mpf.__ne__
_original_float = mpf.__float__
_original_new = mpf.__new__


# ---------------------------------------------------------------------------
# Phase 1: Constructor + __float__ guards
# ---------------------------------------------------------------------------


def _guarded_mpf_new(cls: type, val: Any = 0, **kwargs: Any) -> mpf:
    if _is_hp_active() and _in_boundary_conversion.get(0) == 0 and isinstance(val, _FLOAT_TYPES):
        raise HighPrecisionContaminationError(f"mp.mpf(float) in HP mode: {val!r}")
    return _original_new(cls, val, **kwargs)


def _guarded_float(self: mpf) -> float:
    if _is_hp_active():
        raise HighPrecisionContaminationError(
            f"float(mpf) in HP mode: {self!r} — use mpf for computation, "
            f"convert to float only at serialization boundary"
        )
    return _original_float(self)


# ---------------------------------------------------------------------------
# Phase 2: Comparison operator guards
# ---------------------------------------------------------------------------


def _guarded_le(self: mpf, other: Any) -> bool:
    _check_float_operand(other, "<=")
    return _original_le(self, other)


def _guarded_lt(self: mpf, other: Any) -> bool:
    _check_float_operand(other, "<")
    return _original_lt(self, other)


def _guarded_ge(self: mpf, other: Any) -> bool:
    _check_float_operand(other, ">=")
    return _original_ge(self, other)


def _guarded_gt(self: mpf, other: Any) -> bool:
    _check_float_operand(other, ">")
    return _original_gt(self, other)


def _guarded_eq(self: mpf, other: Any) -> bool:
    _check_float_operand(other, "==")
    return _original_eq(self, other)


def _guarded_ne(self: mpf, other: Any) -> bool:
    _check_float_operand(other, "!=")
    return _original_ne(self, other)


# ---------------------------------------------------------------------------
# Phase 3: Arithmetic operator guards
# ---------------------------------------------------------------------------


def _guarded_add(self: mpf, other: Any) -> mpf:
    _check_float_operand(other, "+")
    return _original_add(self, other)


def _guarded_radd(self: mpf, other: Any) -> mpf:
    _check_float_operand(other, "r+")
    return _original_radd(self, other)


def _guarded_sub(self: mpf, other: Any) -> mpf:
    _check_float_operand(other, "-")
    return _original_sub(self, other)


def _guarded_rsub(self: mpf, other: Any) -> mpf:
    _check_float_operand(other, "r-")
    return _original_rsub(self, other)


def _guarded_mul(self: mpf, other: Any) -> mpf:
    _check_float_operand(other, "*")
    return _original_mul(self, other)


def _guarded_rmul(self: mpf, other: Any) -> mpf:
    _check_float_operand(other, "r*")
    return _original_rmul(self, other)


def _guarded_truediv(self: mpf, other: Any) -> mpf:
    _check_float_operand(other, "/")
    return _original_truediv(self, other)


def _guarded_rtruediv(self: mpf, other: Any) -> mpf:
    _check_float_operand(other, "r/")
    return _original_rtruediv(self, other)


def _guarded_pow(self: mpf, other: Any) -> mpf:
    _check_float_operand(other, "**")
    return _original_pow(self, other)


def _guarded_rpow(self: mpf, other: Any) -> mpf:
    _check_float_operand(other, "r**")
    return _original_rpow(self, other)


# ---------------------------------------------------------------------------
# Phase 3: mpmath function guards
# ---------------------------------------------------------------------------

_MPMATH_FUNC_NAMES = (
    "sqrt",
    "sin",
    "cos",
    "exp",
    "log",
    "atan2",
    "asin",
    "acos",
    "power",
    "tan",
    "sinh",
    "cosh",
    "tanh",
)

_original_mpmath_funcs: dict[str, Any] = {}


def _guarded_mpmath_func_impl(
    x: Any, *args: Any, _name: str = "", _original: Any = None, **kwargs: Any
) -> Any:
    """Guard implementation for mpmath functions (no nested closure)."""
    if _is_hp_active():
        all_positional = (x, *args)
        for index, arg in enumerate(all_positional):
            if isinstance(arg, _FLOAT_TYPES):
                raise HighPrecisionContaminationError(
                    f"mp.{_name} float arg in HP mode at position {index}: {arg!r}"
                )
        for key, value in kwargs.items():
            if isinstance(value, _FLOAT_TYPES):
                raise HighPrecisionContaminationError(
                    f"mp.{_name} float kwarg in HP mode at {key}: {value!r}"
                )
    return _original(x, *args, **kwargs)


def _make_guarded_mpmath_func(name: str, original: Any) -> Any:
    """Create a guarded wrapper for an mpmath function via functools.partial."""
    from functools import partial

    wrapper = partial(_guarded_mpmath_func_impl, _name=name, _original=original)
    wrapper.__name__ = f"_guarded_{name}"  # type: ignore[attr-defined]
    wrapper.__qualname__ = f"_guarded_{name}"  # type: ignore[attr-defined]
    return wrapper


# ---------------------------------------------------------------------------
# Apply all patches (called once at module import)
# ---------------------------------------------------------------------------


def _apply_all_patches() -> None:
    """Apply all monkeypatches. Called once at module import time."""
    # Phase 1
    mpf.__new__ = _guarded_mpf_new
    mpf.__float__ = _guarded_float

    # Phase 2
    mpf.__le__ = _guarded_le
    mpf.__lt__ = _guarded_lt
    mpf.__ge__ = _guarded_ge
    mpf.__gt__ = _guarded_gt
    mpf.__eq__ = _guarded_eq
    mpf.__ne__ = _guarded_ne

    # Phase 3 - operators
    mpf.__add__ = _guarded_add
    mpf.__radd__ = _guarded_radd
    mpf.__sub__ = _guarded_sub
    mpf.__rsub__ = _guarded_rsub
    mpf.__mul__ = _guarded_mul
    mpf.__rmul__ = _guarded_rmul
    mpf.__truediv__ = _guarded_truediv
    mpf.__rtruediv__ = _guarded_rtruediv
    mpf.__pow__ = _guarded_pow
    mpf.__rpow__ = _guarded_rpow

    # Phase 3 - mpmath functions
    for func_name in _MPMATH_FUNC_NAMES:
        original = getattr(mp, func_name, None)
        if original is not None:
            _original_mpmath_funcs[func_name] = original
            setattr(mp, func_name, _make_guarded_mpmath_func(func_name, original))


# Apply patches at import time
_apply_all_patches()
