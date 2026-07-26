"""Base sample-count policy."""


def get_base_samples(config_value: int | None = None, default: int = 5000) -> int:
    """Return configured base samples with validation."""
    value = default if config_value is None else config_value
    return value if value > 0 else default
