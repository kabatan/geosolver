"""Wall-clock runtime budget tracker for staged orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
import time


@dataclass
class RuntimeBudget:
    """Track consumed runtime using monotonic wall-clock time."""

    total_budget_sec: float
    started_at_monotonic: float = field(default_factory=time.monotonic)
    consumed_sec: float = 0.0

    def remaining_sec(self) -> float:
        """Return remaining runtime budget in seconds."""
        elapsed = max(0.0, float(time.monotonic() - self.started_at_monotonic))
        remaining = float(self.total_budget_sec) - elapsed - float(self.consumed_sec)
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
        self.consumed_sec += needed
