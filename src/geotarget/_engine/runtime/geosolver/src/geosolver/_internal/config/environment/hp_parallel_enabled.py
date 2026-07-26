"""Reader for GEOSOLVER_HP_SERIAL."""

import os


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_hp_parallel_enabled(config_value: bool | None = None, default: bool = True) -> bool:
    """Resolve high-precision parallel flag with env > config > default."""
    raw = os.getenv("GEOSOLVER_HP_SERIAL")
    if raw is not None:
        return not _as_bool(raw)
    if config_value is not None:
        return config_value
    return default
