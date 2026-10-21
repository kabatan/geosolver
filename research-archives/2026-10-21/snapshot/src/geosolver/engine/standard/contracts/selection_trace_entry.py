"""Selection trace entry contract for Intersect near/far/exclude decisions."""

from __future__ import annotations

from dataclasses import dataclass

SELECTOR_EXCLUDE = "exclude"
SELECTOR_NEAR = "near"
SELECTOR_FAR = "far"
_ALLOWED_SELECTORS = (SELECTOR_EXCLUDE, SELECTOR_NEAR, SELECTOR_FAR, "n", "unique")


@dataclass(frozen=True)
class SelectionTraceEntry:
    """Single selector decision recorded during construction evaluation."""

    symbol_name: str
    selector_kind: str
    candidate_count: int
    selected_index: int
    call_site_id: str = ""
    candidates: tuple[tuple[object, object], ...] = ()
    margin: object = None

    @property
    def branch_index(self):
        return self.selected_index

    @property
    def kind(self):
        return self.selector_kind

    def __post_init__(self) -> None:
        if self.selector_kind not in _ALLOWED_SELECTORS:
            raise ValueError(
                f"selector_kind must be one of {_ALLOWED_SELECTORS}, got {self.selector_kind!r}"
            )
