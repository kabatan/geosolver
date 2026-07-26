"""Reader for GEOSOLVER_NUM_WORKERS."""

import os


def get_num_workers(config_value: int | None = None, default: int = 0) -> int:
    """Resolve worker count with priority env > config > default."""
    raw = os.getenv("GEOSOLVER_NUM_WORKERS")
    if raw is not None:
        try:
            value = int(raw)
            return value if value >= 0 else default
        except ValueError:
            return default
    if config_value is not None:
        return config_value if config_value >= 0 else default
    return default
