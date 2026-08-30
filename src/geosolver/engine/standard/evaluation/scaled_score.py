"""One residual score for all search backends and seed selection."""

import math


def scaled_score(residuals, scales=None):
    if scales is None:
        return math.fsum(float(value) ** 2 for value in residuals)
    return math.fsum(
        (float(value) / float(scale)) ** 2 for value, scale in zip(residuals, scales, strict=True)
    )
