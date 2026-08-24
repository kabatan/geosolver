"""Search budget dataclass and sample-size computation."""

from dataclasses import dataclass
from .base_samples import get_base_samples
from .max_samples import get_max_samples
from .samples_per_dimension import get_samples_per_dimension


@dataclass(frozen=True)
class SearchBudget:
    """Typed search-budget policy with validated sample-size computation."""

    base_samples: int = 5000
    samples_per_dimension: int = 1500
    max_samples_with_exact: int = 12000
    max_samples_without_exact: int = 8000

    def compute_sample_size(self, dimension: int, has_exact: bool) -> int:
        """Compute bounded sample size from dimension and exact-mode availability."""
        if dimension < 0:
            raise ValueError("dimension must be non-negative")
        base = get_base_samples(self.base_samples)
        increment = get_samples_per_dimension(self.samples_per_dimension)
        cap = get_max_samples(has_exact, self.max_samples_with_exact, self.max_samples_without_exact)
        return min(cap, base + increment * dimension)
