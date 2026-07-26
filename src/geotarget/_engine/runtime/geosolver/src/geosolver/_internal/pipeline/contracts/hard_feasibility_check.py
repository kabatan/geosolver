"""Contract for one hard-feasibility check specification."""

from __future__ import annotations

from dataclasses import dataclass

KIND_GUARD = "guard"
KIND_LINE_DISTINCT = "line_distinct"
KIND_TRIANGLE_NONDEGENERATE = "triangle_nondegenerate"
KIND_INTERSECTION_EXCLUDE_DISTINCT = "intersection_exclude_distinct"
KIND_INTERSECTION_SELECTION_TRACE = "intersection_selection_trace"

_ALLOWED_KINDS = (
    KIND_GUARD,
    KIND_LINE_DISTINCT,
    KIND_TRIANGLE_NONDEGENERATE,
    KIND_INTERSECTION_EXCLUDE_DISTINCT,
    KIND_INTERSECTION_SELECTION_TRACE,
)


@dataclass(frozen=True)
class HardFeasibilityCheck:
    """Static check metadata compiled from IR structure."""

    check_id: str
    kind: str
    symbol_names: tuple[str, ...]
    reference_symbol: str | None

    def __post_init__(self) -> None:
        if self.kind not in _ALLOWED_KINDS:
            raise ValueError(f"kind must be one of {_ALLOWED_KINDS}, got {self.kind!r}")
