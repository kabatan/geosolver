"""Branch-local bounds used by finite NOMAD rescue searches."""

from __future__ import annotations

from dataclasses import dataclass

STAGE_SEARCH_RESCUE = "search_rescue"

_ALLOWED_STAGES = (STAGE_SEARCH_RESCUE,)


@dataclass(frozen=True)
class BranchBox:
    """A bounded local region built around one branch candidate."""

    box_id: int
    center: tuple[float, ...]
    lower_bounds: tuple[float, ...]
    upper_bounds: tuple[float, ...]
    source_candidate_ids: tuple[int, ...]
    priority: float
    stage: str

    def __post_init__(self) -> None:
        if self.stage not in _ALLOWED_STAGES:
            raise ValueError(f"stage must be one of {_ALLOWED_STAGES}, got {self.stage!r}")
        if len(self.lower_bounds) != len(self.upper_bounds):
            raise ValueError("lower_bounds and upper_bounds must have matching dimensions")
        for low, high in zip(self.lower_bounds, self.upper_bounds, strict=False):
            if float(low) > float(high):
                raise ValueError("lower_bounds must be <= upper_bounds for every axis")
