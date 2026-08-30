from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from geosolver.problem.models import ExactAnswer

ARTIFACT_PROTOCOL_VERSION = 3


class WorkerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol_version: Literal[3] = ARTIFACT_PROTOCOL_VERSION
    engine_document: dict[str, Any]
    seed: StrictInt = 0
    deadline_monotonic: float
    effective_cores: StrictInt = 1
    config_snapshot: dict[str, Any] = Field(default_factory=dict)


class WorkerError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str


class WorkerArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol_version: Literal[3] = ARTIFACT_PROTOCOL_VERSION
    status: Literal["completed", "failed", "cancelled"]
    solver_status: str | None = None
    termination_reason: str | None = None
    execution_identity: dict[str, Any] = Field(default_factory=dict)
    numeric_feasible: bool = False
    exact_identified: bool = False
    public_solved: bool = False
    exact_candidates: list[str] = Field(default_factory=list)
    answers: list[ExactAnswer] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    numeric_candidates: list[str] = Field(default_factory=list)
    elapsed_seconds: float = 0.0
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    phase_timings: dict[str, float] = Field(default_factory=dict)
    counters: dict[str, int] = Field(default_factory=dict)
    candidate_records: list[dict[str, Any]] = Field(default_factory=list)
    rejection_tags: list[str] = Field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    process_info: dict[str, Any] = Field(default_factory=dict)
    config_snapshot: dict[str, Any] = Field(default_factory=dict)
    error: WorkerError | None = None
