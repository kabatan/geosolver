from __future__ import annotations

import math
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Variables(StrictModel):
    names: list[str]


class Construction(StrictModel):
    name: str
    expr: str


class Constraint(StrictModel):
    definition: str = Field(alias="def")
    value: float | str


class V15Problem(StrictModel):
    task: Literal["solve"]
    id: str
    variables: Variables
    construction: list[Construction]
    constraints: list[Constraint]
    guards: list[str]
    answer: str
    post_process: str

    def native_document(self) -> dict[str, Any]:
        """Return the champion-native document without semantic rewriting."""

        return self.model_dump(mode="json", by_alias=True)


class SolveOptions(StrictModel):
    time_limit_seconds: float = 180.0
    cores: int = 1
    seed: int = 0

    @field_validator("time_limit_seconds")
    @classmethod
    def finite_minimum_time(cls, value: float) -> float:
        if not math.isfinite(value) or value < 180.0:
            raise ValueError("time_limit_seconds must be finite and at least 180")
        return value

    @field_validator("cores")
    @classmethod
    def positive_cores(cls, value: int) -> int:
        if value < 1:
            raise ValueError("cores must be at least 1")
        return value


class ValidationIssue(StrictModel):
    path: str
    code: str
    message: str


class ValidationReport(StrictModel):
    valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
    normalized_problem: dict[str, Any] | None = None


class ResultStatus(StrEnum):
    EXACT_COMPLETE = "exact_complete"
    ANSWERS_FOUND = "answers_found_completeness_unknown"
    NO_ANSWER = "no_answer_found"
    CANCELLED = "cancelled"
    INVALID = "invalid_problem"
    RESOURCE_ERROR = "resource_error"
    ENGINE_ERROR = "engine_error"


class ResourceUsage(StrictModel):
    time_limit_seconds: float
    cores: int
    seed: int


class WorkCheckpoint(StrictModel):
    window: int = 0
    completed_start_ordinals: list[int] = Field(default_factory=list)
    pending_start_ordinals: list[int] = Field(default_factory=list)
    pending_reservoir_records: list[str] = Field(default_factory=list)
    pending_hp_alternates: list[str] = Field(default_factory=list)
    pending_restoration: list[str] = Field(default_factory=list)
    plan_sha256: str | None = None


class ExactAnswer(StrictModel):
    minimal_polynomial_high_to_low: list[int | str]
    selected_real_root_index: int
    isolating_interval: list[str]
    decimal: str
    exact_authority_kind: str | None = None
    approximate_witness: dict[str, Any] | None = None


class SolveResult(StrictModel):
    status: ResultStatus
    engine_id: str
    engine_hash: str
    problem_sha256: str
    requested_resources: ResourceUsage
    used_resources: ResourceUsage
    elapsed_seconds: float
    work_checkpoint: WorkCheckpoint
    warnings: list[str] = Field(default_factory=list)
    answers: list[ExactAnswer] = Field(default_factory=list)
    detail: str | None = None
