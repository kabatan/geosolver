"""Solver configuration dataclass."""

from dataclasses import dataclass


@dataclass
class SolverConfig:
    """Configuration for equation solving."""

    n: int
    precision: int = 15
    time_limit: float = 300
    seed: int | None = None
    verbose: bool = False
    find_all: bool = False
    max_solutions: int = 1
    strategy: str = "scale_adaptive"
    v: list[float] | None = None
