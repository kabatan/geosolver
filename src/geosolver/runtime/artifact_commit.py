"""An atomic artifact and a small, request-bound receipt of its completed save.

The completion time cannot be embedded in the artifact it timestamps. The
receipt is published only after the artifact has been flushed, synced and
renamed. Readers verify both identity and bytes before trusting that time.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from geosolver.runtime.artifact_records import normalize_artifact
from geosolver.runtime.protocol import WorkerArtifact


class CommitReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    request_id: str
    sha256: str
    size_bytes: int = Field(ge=0)
    solver_completed_monotonic: float
    commit_started_monotonic: float
    committed_monotonic: float
    serialization_seconds: float = Field(ge=0)
    write_seconds: float = Field(ge=0)
    fsync_seconds: float = Field(ge=0)

    def matches(self, request_id: str, deadline: float) -> bool:
        return (
            self.request_id == request_id
            and self.solver_completed_monotonic
            <= self.commit_started_monotonic
            <= self.committed_monotonic
            <= deadline
        )

    def verify_bytes(self, payload: bytes) -> bool:
        return (
            len(payload) == self.size_bytes and hashlib.sha256(payload).hexdigest() == self.sha256
        )


def receipt_path(path: Path) -> Path:
    return path.with_name(path.name + ".commit.json")


def _write_bytes(path: Path, payload: bytes) -> tuple[float, float]:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    started = time.monotonic()
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            synced_at = time.monotonic()
            os.fsync(stream.fileno())
            sync_seconds = time.monotonic() - synced_at
        os.replace(temporary_name, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary_name)
        raise
    return time.monotonic() - started - sync_seconds, sync_seconds


def atomic_write(path: Path, artifact: WorkerArtifact) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    normalized = normalize_artifact(artifact.model_dump(mode="json"))
    payload = (json.dumps(normalized, ensure_ascii=False, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )
    digest = hashlib.sha256(payload).hexdigest()
    serialized_at = time.monotonic()
    write_seconds, fsync_seconds = _write_bytes(path, payload)
    committed = time.monotonic()
    receipt = CommitReceipt(
        request_id=artifact.request_id,
        sha256=digest,
        size_bytes=len(payload),
        solver_completed_monotonic=artifact.process_info.get("solver_completed_monotonic", started),
        commit_started_monotonic=started,
        committed_monotonic=committed,
        serialization_seconds=serialized_at - started,
        write_seconds=write_seconds,
        fsync_seconds=fsync_seconds,
    )
    _write_bytes(receipt_path(path), receipt.model_dump_json().encode("utf-8"))


def read_receipt(path: Path) -> CommitReceipt | None:
    try:
        return CommitReceipt.model_validate_json(receipt_path(path).read_bytes())
    except (OSError, ValueError, json.JSONDecodeError):
        return None
