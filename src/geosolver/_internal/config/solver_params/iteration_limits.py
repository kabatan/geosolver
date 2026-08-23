"""Iteration limit parameter values for solver loops."""

from dataclasses import dataclass


@dataclass(frozen=True)
class IterationLimits:
    """Iteration limit bundle with validation."""

    max_iterations: int = 1000
    max_refinement_steps: int = 200

    def __post_init__(self) -> None:
        if self.max_iterations <= 0 or self.max_refinement_steps <= 0:
            raise ValueError("iteration limits must be positive")
