"""Tolerance parameter values for solver stages."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Tolerances:
    """Tolerance bundle with validation."""

    constraint_tol: float = 1e-10
    objective_tol: float = 1e-12

    def __post_init__(self) -> None:
        if self.constraint_tol <= 0 or self.objective_tol <= 0:
            raise ValueError("tolerances must be positive")
