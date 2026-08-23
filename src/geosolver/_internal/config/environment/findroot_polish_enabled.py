"""Reader for GEOSOLVER_ENABLE_FINDROOT_POLISH."""

import os


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_findroot_polish_enabled(config_value: bool | None = None, default: bool = False) -> bool:
    """Resolve findroot-polish flag with env > config > default."""
    raw = os.getenv("GEOSOLVER_ENABLE_FINDROOT_POLISH")
    if raw is not None:
        return _as_bool(raw)
    if config_value is not None:
        return config_value
    return default
