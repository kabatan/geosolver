"""Backward-compatible exports for solver base types."""

from geosolver._internal.solver.base import (
    AbstractSolver,
    SolverConfig,
)

__all__ = [
    "AbstractSolver",
    "SolverConfig",
]
