"""Reader for GEOSOLVER_ALLOW_DEGENERATE."""

import os


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_allow_degenerate(config_value: bool | None = None, default: bool = False) -> bool:
    """Resolve degenerate-geometry flag with env > config > default."""
    raw = os.getenv("GEOSOLVER_ALLOW_DEGENERATE")
    if raw is not None:
        return _as_bool(raw)
    if config_value is not None:
        return config_value
    return default
