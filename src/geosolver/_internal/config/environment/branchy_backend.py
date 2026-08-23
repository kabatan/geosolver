"""Reader for GEOSOLVER_BRANCHY_BACKEND."""

import os


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_branchy_backend(config_value: bool | None = None, default: bool = False) -> bool:
    """Resolve branchy-backend flag with env > config > default."""
    raw = os.getenv("GEOSOLVER_BRANCHY_BACKEND")
    if raw is not None:
        return _as_bool(raw)
    if config_value is not None:
        return config_value
    return default
