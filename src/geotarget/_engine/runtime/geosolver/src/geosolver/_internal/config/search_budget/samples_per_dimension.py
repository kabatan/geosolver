"""Per-dimension search sample increment policy."""


def get_samples_per_dimension(config_value: int | None = None, default: int = 1500) -> int:
    """Return per-dimension increment with validation."""
    value = default if config_value is None else config_value
    return value if value >= 0 else default
