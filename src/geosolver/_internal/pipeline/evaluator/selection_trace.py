"""Selection-trace capture utilities for hard-feasibility evaluation."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token

from geosolver._internal.pipeline.contracts.selection_trace_entry import SelectionTraceEntry

_ACTIVE_TRACE: ContextVar[list[SelectionTraceEntry] | None] = ContextVar(
    "pipeline_active_selection_trace",
    default=None,
)
_ACTIVE_SYMBOL: ContextVar[str | None] = ContextVar(
    "pipeline_active_selection_symbol",
    default=None,
)


@contextmanager
def capture_selection_trace() -> Iterator[list[SelectionTraceEntry]]:
    """Capture selection traces emitted while evaluating constructions."""
    trace: list[SelectionTraceEntry] = []
    token = _ACTIVE_TRACE.set(trace)
    try:
        yield trace
    finally:
        _ACTIVE_TRACE.reset(token)


@contextmanager
def use_selection_symbol(symbol_name: str) -> Iterator[None]:
    """Set active construction symbol for subsequent selection records."""
    token = _ACTIVE_SYMBOL.set(symbol_name)
    try:
        yield
    finally:
        _ACTIVE_SYMBOL.reset(token)


def record_selection_trace(
    *,
    selector_kind: str,
    candidate_count: int,
    selected_index: int,
) -> None:
    """Record one selection decision if capture is active."""
    trace = _ACTIVE_TRACE.get()
    symbol_name = _ACTIVE_SYMBOL.get()
    if trace is None or symbol_name is None:
        return
    trace.append(
        SelectionTraceEntry(
            symbol_name=symbol_name,
            selector_kind=selector_kind,
            candidate_count=int(candidate_count),
            selected_index=int(selected_index),
        )
    )


def index_selection_trace(
    trace: tuple[SelectionTraceEntry, ...] | list[SelectionTraceEntry],
) -> dict[str, SelectionTraceEntry]:
    """Index selection trace by symbol name (latest entry wins)."""
    indexed: dict[str, SelectionTraceEntry] = {}
    for entry in trace:
        indexed[entry.symbol_name] = entry
    return indexed
