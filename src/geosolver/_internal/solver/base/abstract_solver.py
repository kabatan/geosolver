"""Abstract solver interfaces."""

from abc import ABC, abstractmethod
from collections.abc import Callable

from geosolver.core.result import SolveResult

from .solver_config import SolverConfig


class AbstractSolver(ABC):
    """Base class for solvers."""

    def __init__(self, config: SolverConfig):
        self.config = config

    @abstractmethod
    def solve(self, f: Callable[[list[float]], list[float]], v: list[float]) -> SolveResult:
        """Solve equations f(x) = v."""
