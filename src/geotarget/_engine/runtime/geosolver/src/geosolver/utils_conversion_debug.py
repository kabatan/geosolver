"""Conversion and debug helpers extracted from utils."""

from __future__ import annotations

from typing import Any, Dict, Optional
import re
import traceback

from geosolver._internal.config.environment.exception_debug_flag import (
    debug_exceptions_enabled as _debug_exceptions_enabled_from_env,
)
from geosolver._internal.observability.logging.compat import emit_legacy_log


def to_mpf_sanitized(val: Any, *, dps: Optional[int] = None) -> Any:
    """Robustly convert numeric-ish values to mpmath.mpf."""
    try:
        from mpmath import mp, mpf
    except Exception:
        return val

    if type(val).__name__ == "mpf":
        return val

    val_type = type(val)
    if val_type is int or val_type is float:
        try:
            return mpf(val)
        except Exception:
            pass

    try:
        return mpf(val)
    except Exception:
        pass

    if hasattr(val, "evalf"):
        try:
            use_dps = int(dps) if dps is not None else int(getattr(mp, "dps", 50))
            s = str(val.evalf(use_dps))
            return mpf(s.replace(" ", "").replace("\n", "").replace("\r", "").replace("\t", ""))
        except Exception:
            pass

    try:
        s0 = str(val).replace(" ", "").replace("\n", "").replace("\r", "").replace("\t", "")
        if s0.startswith("mpf("):
            m = re.fullmatch(r"mpf\((['\"])(.*)\\1\)", s0)
            if m:
                s0 = m.group(2)
        return mpf(s0)
    except Exception:
        return mpf("nan")


_EXC_PRINT_COUNTS: Dict[str, int] = {}


def debug_exceptions_enabled() -> bool:
    """Enable verbose exception printing in places that normally swallow exceptions."""
    return _debug_exceptions_enabled_from_env()


def debug_print_exception(where: str, exc: BaseException, *, max_times: int = 3) -> None:
    """Print a short traceback a limited number of times per `where` key."""
    if not debug_exceptions_enabled():
        return

    count = _EXC_PRINT_COUNTS.get(where, 0)
    if count >= int(max_times):
        return
    _EXC_PRINT_COUNTS[where] = count + 1

    try:
        emit_legacy_log(f"[debug] swallowed exception in {where}: {type(exc).__name__}: {exc}")
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        lines = tb.splitlines()
        if len(lines) > 30:
            lines = lines[:30] + ["... (truncated)"]
        emit_legacy_log("\n".join(lines))
    except Exception:
        return