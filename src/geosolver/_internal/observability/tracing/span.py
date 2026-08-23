"""Trace span for timing and metadata collection."""

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TraceSpan:
    name: str
    metadata: dict[str, Any] = field(default_factory=dict)
    parent: str | None = None
    start_time: float = field(default_factory=time.perf_counter)
    end_time: float | None = None

    def finish(self) -> None:
        if self.end_time is None:
            self.end_time = time.perf_counter()

    @property
    def duration_sec(self) -> float:
        end = time.perf_counter() if self.end_time is None else self.end_time
        return max(0.0, end - self.start_time)

    def to_record(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "parent": self.parent,
            "duration_sec": self.duration_sec,
            "metadata": dict(self.metadata),
        }
