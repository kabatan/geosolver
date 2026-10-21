"""Shared coordinate distance for candidate coverage and rescue boxes."""


def normalized_distance(
    *,
    first: tuple[float, ...],
    second: tuple[float, ...],
    bounds: list[tuple[float, float]],
) -> float:
    """Preserve the established axis scaling and floating-point operation order."""
    total = 0.0
    for index, (low, high) in enumerate(bounds):
        width = max(high - low, 1e-12)
        diff = (first[index] - second[index]) / width
        total += diff * diff
    return total**0.5
