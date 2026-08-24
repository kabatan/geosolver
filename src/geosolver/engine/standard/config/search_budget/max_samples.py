"""Maximum sample cap policy."""


def get_max_samples(
    has_exact: bool,
    max_with_exact: int = 12000,
    max_without_exact: int = 8000,
) -> int:
    """Return max sample cap depending on exact-solver availability."""
    selected = max_with_exact if has_exact else max_without_exact
    return selected if selected > 0 else (12000 if has_exact else 8000)
