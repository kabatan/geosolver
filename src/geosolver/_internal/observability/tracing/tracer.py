"""Tracer for managing nested spans."""

from .span import TraceSpan


class Tracer:
    """Collect nested spans and expose diagnostics-compatible records."""

    def __init__(self) -> None:
        self._stack: list[TraceSpan] = []
        self._finished: list[TraceSpan] = []

    def start_span(self, name: str, **metadata: object) -> TraceSpan:
        parent = self._stack[-1].name if self._stack else None
        span = TraceSpan(name=name, metadata=dict(metadata), parent=parent)
        self._stack.append(span)
        return span

    def end_span(self) -> TraceSpan:
        if not self._stack:
            raise RuntimeError("no active span to end")
        span = self._stack.pop()
        span.finish()
        self._finished.append(span)
        return span

    def export(self) -> list[dict[str, object]]:
        return [span.to_record() for span in self._finished]
