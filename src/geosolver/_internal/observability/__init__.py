"""Unified observability interface.

Example:
	>>> obs = initialize_observability(log_mode="json")
	>>> obs.start_phase("broad_search", target_precision=50)
	>>> obs.record_solution([1.0, 2.0])
	>>> obs.record_convergence(iteration=1, residual=1e-3)
	>>> obs.end_phase(status="completed")
	>>> exported = obs.export()
	>>> assert "diagnostics" in exported
"""

from dataclasses import dataclass

from .diagnostics import DiagnosticsCollector, SolverDiagnostics
from .diagnostics.exporter import diagnostics_to_dict
from .logging import StructuredLogger
from .tracing import Tracer


@dataclass
class ObservabilityRuntime:
	logger: StructuredLogger
	diagnostics: DiagnosticsCollector
	tracer: Tracer

	def start_phase(self, phase: str, **fields: object) -> None:
		self.logger.info("phase_started", phase=phase, **fields)
		self.tracer.start_span(phase, **fields)

	def end_phase(self, status: str = "completed", **fields: object) -> None:
		span = self.tracer.end_span()
		self.diagnostics.add_phase(span.name, span.duration_sec, status=status)
		self.logger.info("phase_finished", phase=span.name, status=status, **fields)

	def record_solution(self, values: list[float]) -> None:
		self.diagnostics.add_intermediate_solution(values)

	def record_convergence(self, iteration: int, residual: float) -> None:
		self.diagnostics.add_convergence_record(iteration, residual)

	def export(self) -> dict[str, object]:
		return {
			"diagnostics": diagnostics_to_dict(self.diagnostics.build()),
			"trace_spans": self.tracer.export(),
			"log_lines": self.logger.lines(),
		}


def initialize_observability(log_mode: str = "human", diagnostics_version: str = "1.0") -> ObservabilityRuntime:
	return ObservabilityRuntime(
		logger=StructuredLogger(mode=log_mode),
		diagnostics=DiagnosticsCollector(version=diagnostics_version),
		tracer=Tracer(),
	)


__all__ = ["ObservabilityRuntime", "SolverDiagnostics", "StructuredLogger", "Tracer", "initialize_observability"]
