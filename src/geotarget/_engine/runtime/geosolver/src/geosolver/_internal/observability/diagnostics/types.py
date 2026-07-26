"""Typed diagnostics models with stable version field."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ConvergenceRecord:
    iteration: int
    residual: float


@dataclass(frozen=True)
class PhaseDiagnostics:
    name: str
    duration_sec: float
    status: str = "completed"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SolverDiagnostics:
    phases: list[PhaseDiagnostics] = field(default_factory=list)
    intermediate_solutions: list[list[float]] = field(default_factory=list)
    convergence_history: list[ConvergenceRecord] = field(default_factory=list)
    version: str = "1.0"
