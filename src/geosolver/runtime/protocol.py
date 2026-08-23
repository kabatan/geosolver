from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt

ARTIFACT_PROTOCOL_VERSION = 1


class WorkerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol_version: Literal[1] = ARTIFACT_PROTOCOL_VERSION
    engine_document: dict[str, Any]
    seed: StrictInt = 0
    prefer_fast: StrictBool = True


class WorkerError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str


class WorkerArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol_version: Literal[1] = ARTIFACT_PROTOCOL_VERSION
    status: Literal["completed", "failed", "cancelled"]
    solver_status: str | None = None
    exact_candidates: list[str] = Field(default_factory=list)
    numeric_candidates: list[str] = Field(default_factory=list)
    elapsed_seconds: float = 0.0
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    error: WorkerError | None = None
