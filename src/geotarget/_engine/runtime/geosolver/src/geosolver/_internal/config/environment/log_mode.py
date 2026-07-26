"""Environment helpers for structured log mode."""

from __future__ import annotations

import os


def get_log_mode(default: str = "human") -> str:
    """Return normalized log mode from GEOSOLVER_LOG_MODE."""
    return os.getenv("GEOSOLVER_LOG_MODE", default).strip().lower()
