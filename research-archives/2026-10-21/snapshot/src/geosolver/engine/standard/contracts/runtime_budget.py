"""Wall-clock runtime budget tracker for staged orchestration."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class RuntimeBudget:
    """Track consumed runtime using monotonic wall-clock time."""

    total_budget_sec: float
    started_at_monotonic: float = field(default_factory=time.monotonic)
    deadline_monotonic: float | None = None

    def __post_init__(self) -> None:
        if self.deadline_monotonic is None:
            self.deadline_monotonic = self.started_at_monotonic + float(self.total_budget_sec)

    def remaining_sec(self) -> float:
        """Return remaining runtime budget in seconds."""
        assert self.deadline_monotonic is not None
        remaining = float(self.deadline_monotonic) - time.monotonic()
        if remaining <= 0.0:
            return 0.0
        return float(remaining)

    def reserve_or_fail(self, required_sec: float) -> None:
        """Reserve a time slice or fail when budget is insufficient."""
        needed = float(required_sec)
        if needed <= 0.0:
            return
        if self.remaining_sec() < needed:
            raise RuntimeError(
                f"runtime budget exhausted: required={needed}, remaining={self.remaining_sec()}"
            )

    def deadline_before_reserve(self, *, fraction: float, max_seconds: float) -> float:
        """A local cutoff; unused reserved time is never charged or discarded."""
        assert self.deadline_monotonic is not None
        reserve = min(float(max_seconds), self.remaining_sec() * float(fraction))
        return float(self.deadline_monotonic) - reserve
