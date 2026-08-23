"""Environment helper for debug exception logging flag."""

from __future__ import annotations

import os


def debug_exceptions_enabled() -> bool:
    """Return whether GEOSOLVER_DEBUG_EXCEPTIONS is enabled."""
    value = os.getenv("GEOSOLVER_DEBUG_EXCEPTIONS", "").strip().lower()
    return value in {"1", "true", "yes", "on"}
