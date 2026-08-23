"""Runtime high-precision mode boundary based on contextvars.

WP6_5: Implements dynamic guards via mpmath monkeypatch.
Patches are applied once at module import; ContextVar flags control
whether guards are active (HP mode) or inactive (Zone A passthrough).
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from collections.abc import Iterator
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

# FIX-7: ContextVar-based precision audit and policy
_precision_policy_active: ContextVar[Any] = ContextVar("_precision_policy_active", default=None)
_precision_audit_log: ContextVar[Any] = ContextVar("_precision_audit_log", default=None)

# Audit counters (legacy)
_boundary_conversion_count: int = 0
_boundary_conversion_origins: set[str] = set()


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
def suspend_high_precision_mode() -> Iterator[None]:
    """Temporarily suspend HP mode to call Zone A user-provided functions.

    User-provided functions may contain float literals; suspending HP mode
    prevents the dynamic guard from rejecting mpf-float mixed operations.
    """
    token = _hp_mode_active.set(0)
    try:
        yield
    finally:
        _hp_mode_active.reset(token)


@contextmanager
def precision_policy_context(
    policy: Any,
    audit: Any,
) -> Iterator[None]:
    """Activate precision policy and audit in current context.

    FIX-7: Uses ContextVar so all boundary conversions within the scope
    automatically check policy and record audit data without parameter passing.

    Args:
        policy: PrecisionPolicy instance.
        audit: PrecisionAudit instance (mutated in-place).
    """
    policy_token = _precision_policy_active.set(policy)
    audit_token = _precision_audit_log.set(audit)
    try:
        yield
    finally:
        _precision_policy_active.reset(policy_token)
        _precision_audit_log.reset(audit_token)


def get_current_precision_audit() -> Any:
    """Return the current PrecisionAudit from ContextVar, or None."""
    return _precision_audit_log.get(None)


def get_current_precision_policy() -> Any:
    """Return the current PrecisionPolicy from ContextVar, or None."""
    return _precision_policy_active.get(None)


@contextmanager
def _boundary_conversion_context(*, origin: str) -> Iterator[None]:
    """Temporarily bypass constructor guard for boundary_float_to_mpf.

    Internal use only — must not be called outside boundary_float_to_mpf.
    FIX-7: Also records conversion in audit and checks policy.
    """
    global _boundary_conversion_count
    _boundary_conversion_count += 1
    _boundary_conversion_origins.add(origin)

    # FIX-7: Record in ContextVar audit if active
    audit = _precision_audit_log.get(None)
    if audit is not None:
        audit.record_conversion(origin=origin, stage="boundary")

    # FIX-7: Check policy if active
    policy = _precision_policy_active.get(None)
    if policy is not None and hasattr(policy, "blocked_origins"):
        if origin in policy.blocked_origins:
            violation_msg = f"Blocked boundary conversion from origin={origin!r}"
            if audit is not None:
                audit.record_violation(violation_msg)

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
    if (_is_hp_active()
            and _in_boundary_conversion.get(0) == 0
            and isinstance(val, _FLOAT_TYPES)):
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
    "sqrt", "sin", "cos", "exp", "log", "atan2", "asin", "acos", "power",
    "tan", "sinh", "cosh", "tanh",
)

_original_mpmath_funcs: dict[str, Any] = {}


def _guarded_mpmath_func_impl(x: Any, *args: Any, _name: str = "", _original: Any = None, **kwargs: Any) -> Any:
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
