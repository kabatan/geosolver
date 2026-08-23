"""Diagnostics collection interface."""

from .types import ConvergenceRecord, PhaseDiagnostics, SolverDiagnostics


class DiagnosticsCollector:
    """Mutable collector for assembling solver diagnostics."""

    def __init__(self, version: str = "1.0") -> None:
        self._diagnostics = SolverDiagnostics(version=version)

    def add_phase(self, name: str, duration_sec: float, status: str = "completed") -> None:
        self._diagnostics.phases.append(PhaseDiagnostics(name=name, duration_sec=duration_sec, status=status))

    def add_intermediate_solution(self, values: list[float]) -> None:
        self._diagnostics.intermediate_solutions.append(list(values))

    def add_convergence_record(self, iteration: int, residual: float) -> None:
        self._diagnostics.convergence_history.append(ConvergenceRecord(iteration=iteration, residual=residual))

    def build(self) -> SolverDiagnostics:
        return self._diagnostics
