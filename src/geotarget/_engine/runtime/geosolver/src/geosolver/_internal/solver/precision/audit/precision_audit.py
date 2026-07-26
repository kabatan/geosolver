"""Precision audit records for tracking boundary conversions."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PrecisionAuditRecord:
    """Single record of a boundary float-to-mpf conversion."""

    origin: str
    stage: str
    count: int = 1


@dataclass
class PrecisionAudit:
    """Collects boundary conversion records and policy violations.

    Attached to ContextVar so all code paths within a pipeline
    automatically contribute audit data without parameter passing.
    """

    records: list[PrecisionAuditRecord] = field(default_factory=list)
    policy_violations: list[str] = field(default_factory=list)

    def record_conversion(self, *, origin: str, stage: str) -> None:
        """Record a boundary float-to-mpf conversion."""
        for record in self.records:
            if record.origin == origin and record.stage == stage:
                record.count += 1
                return
        self.records.append(PrecisionAuditRecord(origin=origin, stage=stage))

    def record_violation(self, message: str) -> None:
        """Record a policy violation."""
        self.policy_violations.append(message)

    def has_violations(self) -> bool:
        """Whether any policy violations were recorded."""
        return len(self.policy_violations) > 0

    def total_conversions(self) -> int:
        """Total number of boundary conversions."""
        return sum(r.count for r in self.records)
