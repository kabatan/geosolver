"""Reader for SKIP_EXACT_IDENTIFICATION."""

import os


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_skip_exact_identification(default: bool = False) -> bool:
    """Resolve exact-identification skip flag from environment."""
    raw = os.getenv("SKIP_EXACT_IDENTIFICATION")
    if raw is None:
        return default
    return _as_bool(raw)
