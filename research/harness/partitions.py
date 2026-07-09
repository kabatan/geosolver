"""Fail-closed benchmark partition access and atomic burn/replacement records."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Iterable


class PartitionAccessError(PermissionError):
    """Raised when code attempts to read truth from the wrong research phase."""


class Partition(str, Enum):
    D1 = "D1"
    D2 = "D2"
    V1 = "V1"
    F1 = "F1"
    X1 = "X1"
    P1 = "P1"
    FUZZ = "FUZZ"


class PartitionStatus(str, Enum):
    DEVELOPMENT = "development"
    LOCKED = "locked"
    BLIND = "blind"
    BURNED = "burned"


class AccessMode(str, Enum):
    DEVELOPMENT = "development"
    VALIDATION_EVALUATION = "validation_evaluation"
    BLIND_EVALUATION = "blind_evaluation"


_EXPECTED_ACTIVE_STATUS = {
    Partition.D1: PartitionStatus.DEVELOPMENT,
    Partition.D2: PartitionStatus.DEVELOPMENT,
    Partition.V1: PartitionStatus.LOCKED,
    Partition.F1: PartitionStatus.BLIND,
    Partition.X1: PartitionStatus.LOCKED,
    Partition.P1: PartitionStatus.BLIND,
    Partition.FUZZ: PartitionStatus.DEVELOPMENT,
}


@dataclass(frozen=True, slots=True)
class PartitionRecord:
    """Immutable snapshot of one concrete family set in a logical partition."""

    record_id: str
    partition: Partition
    status: PartitionStatus
    family_ids: frozenset[str]
    replacement_for: str | None = None
    burn_reason: str | None = None


@dataclass(frozen=True, slots=True)
class BurnRecord:
    ordinal: int
    burned_record_id: str
    replacement_record_id: str
    partition: Partition
    burned_family_ids: tuple[str, ...]
    replacement_family_ids: tuple[str, ...]
    reason: str


def _validate_record(record: PartitionRecord, *, permit_replacement: bool) -> None:
    if not isinstance(record.record_id, str) or not record.record_id:
        raise ValueError("partition record_id must be nonempty")
    if not isinstance(record.partition, Partition):
        raise ValueError("partition must be a Partition enum value")
    if not isinstance(record.status, PartitionStatus):
        raise ValueError("status must be a PartitionStatus enum value")
    if not record.family_ids or any(
        not isinstance(value, str) or not value for value in record.family_ids
    ):
        raise ValueError("family_ids must contain nonempty atomic family IDs")
    if record.replacement_for is not None and (
        not permit_replacement
        or not isinstance(record.replacement_for, str)
        or not record.replacement_for
    ):
        raise ValueError("replacement records may only be installed by burn_and_replace")

    expected = _EXPECTED_ACTIVE_STATUS[record.partition]
    if record.status is PartitionStatus.BURNED:
        if expected is PartitionStatus.DEVELOPMENT:
            raise ValueError("development partitions cannot be burned")
        if not record.burn_reason:
            raise ValueError("burned records require a reason")
    else:
        if record.status is not expected:
            raise ValueError(
                f"partition {record.partition.value} requires active status {expected.value}"
            )
        if record.burn_reason is not None:
            raise ValueError("active records must not contain a burn reason")


class PartitionRegistry:
    """In-memory access gate suitable for wrapping manifest/truth readers.

    Family IDs denote the full generator/template clusters defined by the
    research envelope. Their disjointness is enforced across both active and
    burned records so an opened family cannot silently re-enter evaluation.
    """

    def __init__(self, records: Iterable[PartitionRecord] = ()) -> None:
        self._records: dict[str, PartitionRecord] = {}
        self._burn_records: list[BurnRecord] = []
        for record in records:
            self.register(record)

    @property
    def records(self) -> tuple[PartitionRecord, ...]:
        return tuple(self._records[key] for key in sorted(self._records))

    @property
    def burn_records(self) -> tuple[BurnRecord, ...]:
        return tuple(self._burn_records)

    def register(self, record: PartitionRecord) -> None:
        _validate_record(record, permit_replacement=False)
        self._validate_unique(record)
        self._records[record.record_id] = record

    def _validate_unique(self, record: PartitionRecord) -> None:
        if record.record_id in self._records:
            raise ValueError(f"duplicate partition record_id {record.record_id!r}")
        for existing in self._records.values():
            overlap = record.family_ids & existing.family_ids
            if overlap:
                raise ValueError(
                    "family clusters must be partition-disjoint; overlap "
                    f"{sorted(overlap)!r} between {record.record_id!r} and "
                    f"{existing.record_id!r}"
                )

    def access(self, record_id: str, mode: AccessMode) -> PartitionRecord:
        try:
            record = self._records[record_id]
        except KeyError as exc:
            raise KeyError(f"unknown partition record {record_id!r}") from exc

        allowed = False
        if mode is AccessMode.DEVELOPMENT:
            allowed = record.status in {
                PartitionStatus.DEVELOPMENT,
                PartitionStatus.BURNED,
            }
        elif mode is AccessMode.VALIDATION_EVALUATION:
            allowed = (
                record.status is PartitionStatus.LOCKED
                and record.partition in {Partition.V1, Partition.X1}
            )
        elif mode is AccessMode.BLIND_EVALUATION:
            allowed = (
                record.status is PartitionStatus.BLIND
                and record.partition in {Partition.F1, Partition.P1}
            )
        else:
            raise ValueError("mode must be an AccessMode enum value")

        if not allowed:
            raise PartitionAccessError(
                f"{mode.value} access denied for {record.partition.value}/"
                f"{record.record_id} in {record.status.value} state"
            )
        return record

    def burn_and_replace(
        self,
        record_id: str,
        replacement_record: PartitionRecord,
        *,
        reason: str,
    ) -> BurnRecord:
        """Atomically open a failed set for development and install a fresh set."""

        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("a nonempty burn reason is required")
        try:
            current = self._records[record_id]
        except KeyError as exc:
            raise KeyError(f"unknown partition record {record_id!r}") from exc
        if current.status not in {PartitionStatus.LOCKED, PartitionStatus.BLIND}:
            raise ValueError("only active locked or blind records can be burned")

        _validate_record(replacement_record, permit_replacement=True)
        if replacement_record.replacement_for != current.record_id:
            raise ValueError("replacement_for must name the record being burned")
        if replacement_record.partition is not current.partition:
            raise ValueError("replacement must preserve the logical partition")
        if replacement_record.status is not current.status:
            raise ValueError("replacement must preserve locked/blind access status")
        self._validate_unique(replacement_record)

        # All checks precede mutation, so a rejected replacement cannot expose truth.
        burned = replace(
            current,
            status=PartitionStatus.BURNED,
            burn_reason=reason.strip(),
        )
        burn_record = BurnRecord(
            ordinal=len(self._burn_records) + 1,
            burned_record_id=current.record_id,
            replacement_record_id=replacement_record.record_id,
            partition=current.partition,
            burned_family_ids=tuple(sorted(current.family_ids)),
            replacement_family_ids=tuple(sorted(replacement_record.family_ids)),
            reason=reason.strip(),
        )
        self._records[current.record_id] = burned
        self._records[replacement_record.record_id] = replacement_record
        self._burn_records.append(burn_record)
        return burn_record
