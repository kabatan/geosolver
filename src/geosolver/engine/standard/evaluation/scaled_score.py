"""One residual score for all search backends and seed selection."""

import math


def scaled_score(residuals, scales=None):
    values = (
        (float(value) for value in residuals)
        if scales is None
        else (float(value) / float(scale) for value, scale in zip(residuals, scales, strict=True))
    )
    # Retain the ordinary squared-score rounding used for search ordering.
    # Squaring a rounded norm perturbs ties and can change the sampled basin.
    # Only an unrepresentable squared score needs the infinite-score fallback.
    try:
        return math.fsum(value**2 for value in values)
    except OverflowError:
        return math.inf
