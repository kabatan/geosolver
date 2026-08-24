"""Small shared utilities for geosolver/optimizer.

This module is intentionally dependency-light and import-safe.
It exists to avoid copy-pasted helper logic across geosolver.py/optimizer.py.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Generator
import inspect
from geosolver.engine.standard.precision.conversion import (
    debug_exceptions_enabled,
    debug_print_exception,
    to_mpf_sanitized,
)

# =============================================================================
# mpmath precision management utilities
# =============================================================================

# Global cache for current precision state to avoid redundant mp.dps changes
_CURRENT_DPS_CACHE: Dict[str, int] = {}


@dataclass
class PrecisionKwargCache:
    """Cache for detecting whether a callable accepts `prec`/`precision`.

    Values:
    - 'prec'      -> call fn(..., prec=...)
    - 'precision' -> call fn(..., precision=...)
    - None        -> call fn(...) without precision kw

    We key by id(fn) to keep it cheap and avoid holding strong refs.
    """

    modes: Dict[int, Optional[str]] = field(default_factory=dict)

    def get_mode(self, fn: Callable[..., Any]) -> Optional[str]:
        key = id(fn)
        if key in self.modes:
            return self.modes[key]

        try:
            sig = inspect.signature(fn)
            params = sig.parameters
            if 'prec' in params:
                mode: Optional[str] = 'prec'
            elif 'precision' in params:
                mode = 'precision'
            elif any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
                # If **kwargs exists, prefer `prec` as a convention.
                mode = 'prec'
            else:
                mode = None
        except Exception:
            mode = None

        self.modes[key] = mode
        return mode


def call_with_precision(
    fn: Callable[..., Any],
    vec: Any,
    prec: int,
    *,
    cache: Optional[PrecisionKwargCache] = None,
) -> Any:
    """Call fn(vec, prec=...) if supported; otherwise call fn(vec).

    - Accepts numpy arrays for vec; converts to list for user functions.
    - Uses a small cache to avoid repeated inspect.signature calls.
    """

    if cache is None:
        cache = PrecisionKwargCache()

    try:
        # numpy.ndarray is common in scipy; avoid importing numpy here.
        if type(vec).__name__ == 'ndarray':
            vec2 = list(vec)
        else:
            vec2 = vec
    except Exception:
        vec2 = vec

    mode = cache.get_mode(fn)
    if mode == 'prec':
        return fn(vec2, prec=int(prec))
    if mode == 'precision':
        return fn(vec2, precision=int(prec))
    return fn(vec2)


@contextmanager
def mp_precision(target_dps: int) -> Generator[None, None, None]:
    """Context manager for temporarily setting mpmath precision.

    Only changes precision if current dps is lower than target.
    Restores original precision on exit.

    Usage:
        with mp_precision(100):
            # High precision operations here
            result = some_calculation()
    """
    try:
        from mpmath import mp
    except ImportError:
        yield
        return

    old_dps = mp.dps
    if old_dps < target_dps:
        mp.dps = target_dps
        try:
            yield
        finally:
            mp.dps = old_dps
    else:
        yield


def ensure_mp_dps(target_dps: int) -> bool:
    """Ensure mp.dps is at least target_dps. Returns True if changed.

    This is a no-op if current dps already meets the requirement.
    Use this for one-way precision increases during high-precision phases.
    """
    try:
        from mpmath import mp
    except ImportError:
        return False

    if mp.dps >= target_dps:
        return False

    mp.dps = target_dps
    return True


def compute_target_dps(precision: int, extra: int = 0) -> int:
    """Compute target mp.dps for a given precision level.

    Returns a reasonable dps that provides enough guard digits without
    over-inflating for very high precision targets.
    """
    try:
        prec = max(1, int(precision))
    except Exception:
        prec = 50

    # guard digits: Newton/projection safety margin without excessive inflation
    buffer = max(40, min(prec // 4 + 40, 160))
    extra_guard = max(0, min(int(extra), max(40, prec // 4)))

    target = prec + buffer + extra_guard
    # Avoid excessive boost for moderate precision
    if prec <= 240:
        target = min(target, prec + 180)
    return min(target, 2000)


