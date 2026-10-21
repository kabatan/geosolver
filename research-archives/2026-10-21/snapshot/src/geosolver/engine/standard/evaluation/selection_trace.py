"""Selection-trace capture utilities for hard-feasibility evaluation."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from geosolver.engine.standard.contracts.selection_trace_entry import SelectionTraceEntry
from geosolver.problem.evaluation_trace import evaluation_scope

_ACTIVE_TRACE: ContextVar[list[SelectionTraceEntry] | None] = ContextVar(
    "pipeline_active_selection_trace",
    default=None,
)
_ACTIVE_SYMBOL: ContextVar[str | None] = ContextVar(
    "pipeline_active_selection_symbol",
    default=None,
)


def replay_selection_trace(entries):
    destination = _ACTIVE_TRACE.get()
    if destination is not None:
        destination.extend(entries)


def selection_evaluation_identity():
    from geosolver.problem.evaluation_trace import current_evaluation_scope

    return _ACTIVE_SYMBOL.get(), current_evaluation_scope()


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
        with evaluation_scope(symbol_name):
            yield
    finally:
        _ACTIVE_SYMBOL.reset(token)


def record_selection_trace(
    *,
    selector_kind: str,
    candidate_count: int,
    selected_index: int,
    candidates: tuple[tuple[object, object], ...] = (),
    margin: object = None,
) -> SelectionTraceEntry:
    """Record one selection decision if capture is active."""
    trace = _ACTIVE_TRACE.get()
    symbol_name = _ACTIVE_SYMBOL.get()
    from geosolver.problem.evaluation_trace import current_call_site

    entry = SelectionTraceEntry(
        symbol_name=symbol_name or "",
        selector_kind=selector_kind,
        candidate_count=int(candidate_count),
        selected_index=int(selected_index),
        candidates=candidates,
        call_site_id=current_call_site(),
        margin=margin,
    )
    if trace is not None:
        trace.append(entry)
    return entry


def index_selection_trace(
    trace: tuple[SelectionTraceEntry, ...] | list[SelectionTraceEntry],
) -> dict[str, SelectionTraceEntry]:
    """Index selection trace by symbol name (latest entry wins)."""
    indexed: dict[str, SelectionTraceEntry] = {}
    for entry in trace:
        indexed[entry.symbol_name] = entry
    return indexed
