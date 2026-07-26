"""Halton-based initial-point search strategy."""

from abc import ABC, abstractmethod
from collections.abc import Callable

import numpy as np
from scipy.stats import qmc

from geosolver._internal.config.search_budget import SearchBudget
from geosolver._internal.solver.base import SolverConfig

_HALTON_SAMPLE_BUDGET = SearchBudget(
    base_samples=500,
    samples_per_dimension=200,
    max_samples_with_exact=3000,
    max_samples_without_exact=3000,
)
_RANDOM_SAMPLE_BUDGET = SearchBudget(
    base_samples=300,
    samples_per_dimension=150,
    max_samples_with_exact=2000,
    max_samples_without_exact=2000,
)


class SearchStrategy(ABC):
    """Abstract base class for initial-point search strategies."""

    @abstractmethod
    def generate_initial_points(
        self,
        n: int,
        bounds: list[tuple[float, float]],
        objective: Callable[[list[float]], float],
        config: SolverConfig,
    ) -> list[list[float]]:
        """Generate and return promising initial points."""


class HaltonSearchStrategy(SearchStrategy):
    """Search strategy based on mixed Halton and random samples."""

    def generate_initial_points(
        self,
        n: int,
        bounds: list[tuple[float, float]],
        objective: Callable[[list[float]], float],
        config: SolverConfig,
    ) -> list[list[float]]:
        seed = config.seed
        rng = np.random.default_rng(seed)

        n_halton_samples = _HALTON_SAMPLE_BUDGET.compute_sample_size(
            dimension=n,
            has_exact=False,
        )
        n_random_samples = _RANDOM_SAMPLE_BUDGET.compute_sample_size(
            dimension=n,
            has_exact=False,
        )

        if n > 0 and n_halton_samples > 0:
            lower = np.array([low for low, _ in bounds], dtype=float)
            upper = np.array([high for _, high in bounds], dtype=float)
            sampler = qmc.Halton(d=n, scramble=True, seed=seed)
            halton_samples = qmc.scale(sampler.random(n=n_halton_samples), lower, upper)
            halton_points = halton_samples.tolist()
        else:
            halton_points = []

        random_points: list[list[float]] = []
        for _ in range(n_random_samples):
            random_points.append([rng.uniform(low, high) for low, high in bounds])

        all_samples = halton_points + random_points
        scored: list[tuple[float, list[float]]] = []
        for point in all_samples:
            try:
                cost = objective(point)
                if np.isfinite(cost):
                    scored.append((cost, point))
            except Exception:
                continue

        scored.sort(key=lambda item: item[0])
        keep_count = min(50, max(20, 3 * n))
        initial_points = [point for _, point in scored[:keep_count]]

        if not initial_points:
            return random_points[:10] if random_points else [[0.0] * n]
        return initial_points


def _first_primes(k: int) -> list[int]:
    """Return first k primes."""
    if k <= 0:
        return []
    primes: list[int] = []
    candidate = 2
    while len(primes) < k:
        is_prime = True
        for prime in primes:
            if prime * prime > candidate:
                break
            if candidate % prime == 0:
                is_prime = False
                break
        if is_prime:
            primes.append(candidate)
        candidate += 1 if candidate == 2 else 2
    return primes


def _radical_inverse(index: int, base: int) -> float:
    """Van der Corput radical inverse."""
    if base <= 1:
        return 0.0
    result = 0.0
    fraction = 1.0 / base
    value = index
    while value > 0:
        result += (value % base) * fraction
        value //= base
        fraction /= base
    return result


def _halton_value(sample_index: int, base: int) -> float:
    """Halton sequence value."""
    return _radical_inverse(sample_index, base)
