"""Convergence threshold values for solver checks."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ConvergenceThresholds:
    """Convergence threshold bundle with validation."""

    residual_threshold: float = 1e-8
    gradient_threshold: float = 1e-10

    def __post_init__(self) -> None:
        if self.residual_threshold <= 0 or self.gradient_threshold <= 0:
            raise ValueError("convergence thresholds must be positive")
