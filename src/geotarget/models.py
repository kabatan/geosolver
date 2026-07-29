from __future__ import annotations

import math
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from geotarget.qualification import (
    DEFAULT_CORES,
    DEFAULT_ENGINE,
    DEFAULT_MAX_TIME_SECONDS,
    DEFAULT_RUN_MODE,
)


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
    engine: Literal["optimized", "reference"] = DEFAULT_ENGINE
    run_mode: Literal["adaptive", "fixed_time"] = DEFAULT_RUN_MODE
    max_time_seconds: float = DEFAULT_MAX_TIME_SECONDS
    cores: Literal["auto"] | int = DEFAULT_CORES
    seed: int = 0
    time_limit_seconds: float | None = Field(
        default=None,
        exclude=True,
        json_schema_extra={"deprecated": True},
    )

    @model_validator(mode="after")
    def accept_legacy_time_limit(self) -> SolveOptions:
        if "time_limit_seconds" not in self.model_fields_set:
            return self
        legacy_value = self.__dict__["time_limit_seconds"]
        if legacy_value is None:
            raise ValueError("time_limit_seconds cannot be null when provided")
        if "max_time_seconds" in self.model_fields_set and self.max_time_seconds != legacy_value:
            raise ValueError(
                "time_limit_seconds and max_time_seconds must match when both are provided"
            )
        if "run_mode" in self.model_fields_set and self.run_mode != "fixed_time":
            raise ValueError("time_limit_seconds is only compatible with run_mode='fixed_time'")
        self.max_time_seconds = legacy_value
        self.run_mode = "fixed_time"
        return self

    @model_validator(mode="after")
    def enforce_reference_contract(self) -> SolveOptions:
        if self.engine == "reference" and (
            self.run_mode != "fixed_time" or self.max_time_seconds != 180.0 or self.cores != 1
        ):
            raise ValueError(
                "reference requires run_mode='fixed_time', max_time_seconds=180, and cores=1"
            )
        return self

    @field_validator("max_time_seconds", "time_limit_seconds")
    @classmethod
    def finite_minimum_time(cls, value: float | None) -> float | None:
        if value is None:
            return value
        if not math.isfinite(value) or not 180.0 <= value <= 900.0:
            raise ValueError("max_time_seconds must be finite and between 180 and 900")
        return value

    @field_validator("cores")
    @classmethod
    def positive_cores(cls, value: Literal["auto"] | int) -> Literal["auto"] | int:
        if value == "auto":
            return value
        if isinstance(value, bool):
            raise ValueError("cores must be 'auto' or an integer of at least 1")
        if value < 1:
            raise ValueError("cores must be 'auto' or an integer of at least 1")
        return value

    @property
    def compatibility_time_limit_used(self) -> bool:
        """Whether the caller used the deprecated time-limit spelling."""

        return "time_limit_seconds" in self.model_fields_set


class ValidationIssue(StrictModel):
    path: str
    code: str
    message: str


class ValidationReport(StrictModel):
    valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[ValidationIssue] = Field(default_factory=list)
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
    cores: Literal["auto"] | int
    seed: int
    max_time_seconds: float | None = None


class TerminationReason(StrEnum):
    INITIAL_WORK_ANSWERED = "initial_work_answered"
    EXTENSION_STABLE = "extension_stable"
    SAFETY_CAP = "safety_cap"
    EXACT_COMPLETE = "exact_complete"
    CANCELLED = "cancelled"
    ENGINE_ERROR = "engine_error"


class PhaseMetadata(StrictModel):
    current: str | None = None
    completed: list[str] = Field(default_factory=list)
    elapsed_seconds: dict[str, float] = Field(default_factory=dict)


class WorkMetadata(StrictModel):
    completed_items: int = 0
    pending_items: int = 0
    total_items: int | None = None


class CacheMetadata(StrictModel):
    hits: int = 0
    misses: int = 0
    writes: int = 0
    runtime_generation: int = 0
    runtime_warm: bool = False
    hp_preloader_warm: bool = False


class WorkCheckpoint(StrictModel):
    window: int = 0
    phase: str = "initial"
    completed_start_ordinals: list[int] = Field(default_factory=list)
    pending_start_ordinals: list[int] = Field(default_factory=list)
    pending_reservoir_records: list[str] = Field(default_factory=list)
    pending_hp_alternates: list[str] = Field(default_factory=list)
    pending_restoration: list[str] = Field(default_factory=list)
    plan_sha256: str | None = None
    extension_batches_completed: int = 0
    consecutive_empty_extension_batches: int = 0
    descriptors_before_extension: int = 0
    descriptors_after_extension: int = 0
    termination_reason: TerminationReason | None = None
    phase_elapsed_seconds: dict[str, float] = Field(default_factory=dict)


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
    engine_variant: Literal["optimized", "reference"] = "reference"
    termination_reason: TerminationReason | None = None
    phase_metadata: PhaseMetadata = Field(default_factory=PhaseMetadata)
    work_metadata: WorkMetadata = Field(default_factory=WorkMetadata)
    cache_metadata: CacheMetadata = Field(default_factory=CacheMetadata)
