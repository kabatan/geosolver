"""Integrity-bound checkpoints for the frozen champion candidate reservoir."""

from __future__ import annotations

import hashlib
import json
import math
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "geotarget.candidate-reservoir-checkpoint/v1"
_CANDIDATE_FIELDS = (
    "endpoint",
    "endpoint_sha256",
    "residual_inf",
    "provisional_target",
    "cluster_ordinal",
    "cluster_rank",
    "discovery_ordinal",
    "admission_role",
    "record_id",
    "bucket_id",
    "bucket_kind",
    "aging_wave",
    "semantic_verified",
)


class ReservoirCheckpointCorrupt(RuntimeError):
    """The checkpoint is partial, malformed, or fails its integrity digest."""


class CandidateReservoirSnapshot(tuple):
    """Tuple-compatible reconstruction of the frozen reservoir seam."""

    def __new__(cls, verified: Sequence[Any], deadline_backlog: Sequence[Any] = ()):
        instance = super().__new__(cls, tuple(verified))
        instance.deadline_backlog = tuple(deadline_backlog)
        return instance


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def search_binding(source_sha256: str, search: Mapping[str, Any]) -> dict[str, str]:
    """Bind a reservoir to source bytes, endpoints, and the exact search plan."""

    endpoints = search.get("endpoints")
    literal = search.get("literal_prefix")
    parallel = search.get("optimized_parallel_search")
    work = search.get("work")
    budget = search.get("budget")
    if not isinstance(endpoints, list):
        raise ValueError("search endpoints are required for a reservoir checkpoint")
    literal_map = dict(literal) if isinstance(literal, Mapping) else {}
    plan = {
        "literal_prefix": literal_map,
        "optimized_parallel_search": dict(parallel) if isinstance(parallel, Mapping) else {},
        "work": dict(work) if isinstance(work, Mapping) else {},
        "budget": dict(budget) if isinstance(budget, Mapping) else {},
        "seed": search.get("seed"),
        "arm": search.get("arm"),
    }
    return {
        "source_sha256": source_sha256,
        "search_endpoints_sha256": _sha256(endpoints),
        "full_prefix_sha256": str(literal_map.get("full_prefix_sha256") or ""),
        "search_plan_sha256": _sha256(plan),
    }


def _candidate_payload(candidate: Any) -> dict[str, Any]:
    payload = {field: getattr(candidate, field) for field in _CANDIDATE_FIELDS}
    endpoint = payload["endpoint"]
    if not isinstance(endpoint, tuple | list):
        raise ValueError("candidate endpoint must be a sequence")
    payload["endpoint"] = [float(value) for value in endpoint]
    residual = float(payload["residual_inf"])
    provisional = payload["provisional_target"]
    if not math.isfinite(residual) or (
        provisional is not None and not math.isfinite(float(provisional))
    ):
        raise ValueError("candidate numeric fields must be finite")
    payload["residual_inf"] = residual
    payload["provisional_target"] = (
        None if provisional is None else float(provisional)
    )
    return payload


def _payload(binding: Mapping[str, str], reservoir: Sequence[Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "binding": dict(binding),
        "candidate_fields": list(_CANDIDATE_FIELDS),
        "stable_order": "verified_then_deadline_backlog",
        "verified": [_candidate_payload(candidate) for candidate in reservoir],
        "deadline_backlog": [
            _candidate_payload(candidate)
            for candidate in getattr(reservoir, "deadline_backlog", ())
        ],
    }


def write_checkpoint(
    path: Path, *, binding: Mapping[str, str], reservoir: Sequence[Any]
) -> None:
    """Atomically persist a complete reservoir and its content digest."""

    payload = _payload(binding, reservoir)
    envelope = {**payload, "content_sha256": _sha256(payload)}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(envelope, stream, ensure_ascii=False, allow_nan=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def _validated_rows(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ReservoirCheckpointCorrupt(f"{label} is not a complete list")
    rows: list[dict[str, Any]] = []
    for row in value:
        if not isinstance(row, Mapping) or set(row) != set(_CANDIDATE_FIELDS):
            raise ReservoirCheckpointCorrupt(f"{label} has an incomplete candidate")
        endpoint = row.get("endpoint")
        if not isinstance(endpoint, list) or not all(
            isinstance(item, int | float) and not isinstance(item, bool)
            and math.isfinite(float(item))
            for item in endpoint
        ):
            raise ReservoirCheckpointCorrupt(f"{label} has an invalid endpoint")
        rows.append(dict(row))
    return rows


def load_checkpoint(
    path: Path,
    *,
    expected_binding: Mapping[str, str],
    candidate_type: type[Any],
    reservoir_type: type[Any],
) -> Sequence[Any] | None:
    """Load a matching checkpoint; return ``None`` for a clean binding miss.

    An absent checkpoint, a future/old schema, or a checkpoint for another
    source/search plan safely falls back to frozen full replay. Malformed,
    partial, or digest-invalid content is never executed.
    """

    if not path.is_file():
        return None
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ReservoirCheckpointCorrupt("reservoir checkpoint is partial or invalid") from error
    if not isinstance(envelope, Mapping):
        raise ReservoirCheckpointCorrupt("reservoir checkpoint is not an object")
    if envelope.get("schema_version") != SCHEMA_VERSION:
        return None
    supplied_digest = envelope.get("content_sha256")
    payload = {key: value for key, value in envelope.items() if key != "content_sha256"}
    if not isinstance(supplied_digest, str) or supplied_digest != _sha256(payload):
        raise ReservoirCheckpointCorrupt("reservoir checkpoint integrity check failed")
    binding = envelope.get("binding")
    if not isinstance(binding, Mapping) or dict(binding) != dict(expected_binding):
        return None
    if envelope.get("candidate_fields") != list(_CANDIDATE_FIELDS):
        return None
    if envelope.get("stable_order") != "verified_then_deadline_backlog":
        return None
    verified_rows = _validated_rows(envelope.get("verified"), "verified")
    backlog_rows = _validated_rows(envelope.get("deadline_backlog"), "deadline_backlog")
    try:
        verified = tuple(
            candidate_type(**{**row, "endpoint": tuple(row["endpoint"])})
            for row in verified_rows
        )
        backlog = tuple(
            candidate_type(**{**row, "endpoint": tuple(row["endpoint"])})
            for row in backlog_rows
        )
        return reservoir_type(verified, backlog)
    except (TypeError, ValueError) as error:
        raise ReservoirCheckpointCorrupt("reservoir candidate reconstruction failed") from error
