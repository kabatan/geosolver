"""Readers for MP degeneracy floor environment variables."""

import os


def _read_str_env(key: str, default: str) -> str:
    raw = os.getenv(key)
    if raw is None:
        return default
    value = raw.strip()
    return value if value else default


def get_mp_degenerate_rel_floor(default: str = "1e-30") -> str:
    """Resolve relative floor string for MP degeneracy checks."""
    return _read_str_env("GEOSOLVER_MP_DEGENERATE_REL_FLOOR", default)


def get_mp_degenerate_abs_floor(default: str = "0") -> str:
    """Resolve absolute floor string for MP degeneracy checks."""
    return _read_str_env("GEOSOLVER_MP_DEGENERATE_ABS_FLOOR", default)
