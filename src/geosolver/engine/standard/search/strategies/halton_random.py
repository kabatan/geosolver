"""Halton + random search-point generation."""

from collections.abc import Sequence

import numpy as np
from scipy.stats import qmc

from geosolver.engine.standard.search.quasirandom.generate_points import _generate_halton_points


def generate_halton_random_points(
    n: int, bounds: Sequence[tuple[float, float]], n_points: int, seed: int = 0
) -> list[list[float]]:
    """Generate mixed Halton and random points inside bounds."""
    n_halton = max(1, n_points // 2)
    if n > 0 and n_halton > 0:
        lower = np.array([low for low, _ in bounds], dtype=float)
        upper = np.array([high for _, high in bounds], dtype=float)
        sampler = qmc.Halton(d=n, scramble=True, seed=seed)
        halton = qmc.scale(sampler.random(n=n_halton), lower, upper).tolist()
    else:
        halton = _generate_halton_points(n, list(bounds), n_halton, start_index=1)
    rng = np.random.default_rng(seed)
    random_points = [[float(rng.uniform(low, high)) for low, high in bounds] for _ in range(max(0, n_points - n_halton))]
    return halton + random_points
