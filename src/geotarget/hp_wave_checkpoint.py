"""Durable state for an interrupted frozen HP/alternate/restoration wave."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

SCHEMA_VERSION = "geotarget.hp-wave-checkpoint/v1"
STAGES = ("primary", "alternate", "restoration", "complete")


class HpWaveCheckpointCorrupt(RuntimeError):
    """The product-owned wave checkpoint is malformed or was modified."""


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def create(
    *,
    stage: str,
    batch_record_ids: Sequence[str],
    pending_primary_record_ids: Sequence[str] = (),
    pending_alternate_record_ids: Sequence[str] = (),
    pending_restoration_record_ids: Sequence[str] = (),
    failed_primaries: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Create an integrity-bound checkpoint without changing frozen policy."""

    if stage not in STAGES:
        raise ValueError(f"unknown HP wave stage: {stage}")
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "stage": stage,
        "batch_record_ids": [str(value) for value in batch_record_ids],
        "pending_primary_record_ids": [str(value) for value in pending_primary_record_ids],
        "pending_alternate_record_ids": [str(value) for value in pending_alternate_record_ids],
        "pending_restoration_record_ids": [str(value) for value in pending_restoration_record_ids],
        "failed_primaries": [dict(value) for value in failed_primaries],
    }
    return {**payload, "content_sha256": _digest(payload)}


def validate(value: Any) -> dict[str, Any] | None:
    """Validate a checkpoint, returning ``None`` when no state is present."""

    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise HpWaveCheckpointCorrupt("HP wave checkpoint is not an object")
    if value.get("schema_version") != SCHEMA_VERSION:
        raise HpWaveCheckpointCorrupt("HP wave checkpoint schema is unsupported")
    supplied = value.get("content_sha256")
    payload = {key: item for key, item in value.items() if key != "content_sha256"}
    if not isinstance(supplied, str) or supplied != _digest(payload):
        raise HpWaveCheckpointCorrupt("HP wave checkpoint integrity check failed")
    stage = payload.get("stage")
    if stage not in STAGES:
        raise HpWaveCheckpointCorrupt("HP wave checkpoint stage is invalid")
    list_fields = (
        "batch_record_ids",
        "pending_primary_record_ids",
        "pending_alternate_record_ids",
        "pending_restoration_record_ids",
    )
    for field in list_fields:
        rows = payload.get(field)
        if not isinstance(rows, list) or not all(isinstance(row, str) for row in rows):
            raise HpWaveCheckpointCorrupt(f"HP wave checkpoint {field} is invalid")
        if len(rows) != len(set(rows)):
            raise HpWaveCheckpointCorrupt(f"HP wave checkpoint {field} is not unique")
    batch_ids = set(payload["batch_record_ids"])
    for field in list_fields[1:]:
        if not set(payload[field]).issubset(batch_ids):
            raise HpWaveCheckpointCorrupt(f"HP wave checkpoint {field} escapes the frozen batch")
    failed = payload.get("failed_primaries")
    if not isinstance(failed, list):
        raise HpWaveCheckpointCorrupt("HP wave failed-primary state is invalid")
    required = {"cluster_ordinal", "record_id", "ordinal", "artifact_directory"}
    for row in failed:
        if not isinstance(row, Mapping) or set(row) != required:
            raise HpWaveCheckpointCorrupt("HP wave failed-primary row is invalid")
        if (
            not isinstance(row["cluster_ordinal"], int)
            or not isinstance(row["ordinal"], int)
            or not isinstance(row["record_id"], str)
            or not isinstance(row["artifact_directory"], str)
        ):
            raise HpWaveCheckpointCorrupt("HP wave failed-primary fields are invalid")
        if row["record_id"] not in batch_ids:
            raise HpWaveCheckpointCorrupt("HP wave failed primary escapes the frozen batch")
    return dict(value)


def pending(value: Any) -> bool:
    checkpoint = validate(value)
    return checkpoint is not None and checkpoint["stage"] != "complete"
