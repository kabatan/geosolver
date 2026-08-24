"""Policy contract for ordered production-baseline search attempts."""

from __future__ import annotations

from dataclasses import dataclass

from geosolver.engine.standard.search.nomad_config import (
    DEFAULT_SEED_VALUES,
    derive_seed_values,
)

SEARCH_ATTEMPT_PRIMARY = "primary"
SEARCH_ATTEMPT_HYBRID_FALLBACK = "hybrid_fallback"


@dataclass(frozen=True)
class SearchAttemptConfig:
    """Concrete configuration for one ordered search attempt."""

    attempt_id: str
    search_mode: str
    seed_values: tuple[int, ...]

    def __post_init__(self) -> None:
        normalized_seed_values = tuple(int(seed) for seed in self.seed_values)
        object.__setattr__(self, "attempt_id", str(self.attempt_id))
        object.__setattr__(self, "search_mode", str(self.search_mode))
        object.__setattr__(self, "seed_values", normalized_seed_values)
        if not self.attempt_id:
            raise ValueError("attempt_id must not be empty")
        if not self.search_mode:
            raise ValueError("search_mode must not be empty")
        if not normalized_seed_values:
            raise ValueError("seed_values must not be empty")


@dataclass(frozen=True)
class BaselineSearchPolicy:
    """Ordered search attempts for the production baseline."""

    ordered_attempts: tuple[SearchAttemptConfig, ...]

    def __post_init__(self) -> None:
        if not self.ordered_attempts:
            raise ValueError("ordered_attempts must not be empty")
        attempt_ids = tuple(attempt.attempt_id for attempt in self.ordered_attempts)
        if len(set(attempt_ids)) != len(attempt_ids):
            raise ValueError("ordered_attempts must use unique attempt_id values")

    @classmethod
    def production_baseline(
        cls,
        *,
        authoritative_seed: int,
        primary_search_mode: str,
        hybrid_fallback_search_mode: str,
        fallback_seed_count: int = len(DEFAULT_SEED_VALUES),
    ) -> "BaselineSearchPolicy":
        """Build the current ordered attempt policy for production-baseline runs."""
        primary_seed = int(authoritative_seed)
        normalized_fallback_seed_count = max(1, int(fallback_seed_count))
        return cls(
            ordered_attempts=(
                SearchAttemptConfig(
                    attempt_id=SEARCH_ATTEMPT_PRIMARY,
                    search_mode=primary_search_mode,
                    seed_values=(primary_seed,),
                ),
                SearchAttemptConfig(
                    attempt_id=SEARCH_ATTEMPT_HYBRID_FALLBACK,
                    search_mode=hybrid_fallback_search_mode,
                    seed_values=derive_seed_values(
                        primary_seed,
                        count=normalized_fallback_seed_count,
                    ),
                ),
            )
        )
