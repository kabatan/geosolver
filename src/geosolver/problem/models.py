from __future__ import annotations

import math
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


Scalar = StrictInt | StrictFloat | StrictStr


class Construction(StrictModel):
    name: str
    expression: str


class RelationCondition(StrictModel):
    left: str
    operator: Literal["=", "!=", "<", "<=", ">", ">="]
    right: Scalar


class PredicateCondition(StrictModel):
    predicate: str


Condition = Annotated[RelationCondition | PredicateCondition, Field(union_mode="left_to_right")]


class GeometryProblem(StrictModel):
    id: str
    variables: list[str]
    constructions: list[Construction]
    conditions: list[Condition]
    target: str

    def engine_document(self) -> dict[str, Any]:
        from geosolver.problem.adapter import to_engine_document

        return to_engine_document(self)


class SolveOptions(StrictModel):
    engine: Literal["standard", "reference"] = "standard"
    time_limit_seconds: StrictInt | StrictFloat | None = None
    cores: Literal["auto"] | StrictInt | None = None
    seed: StrictInt = 0

    @model_validator(mode="after")
    def resolve_defaults(self) -> SolveOptions:
        if self.time_limit_seconds is None:
            self.time_limit_seconds = 180 if self.engine == "reference" else 900
        if self.cores is None:
            self.cores = 1 if self.engine == "reference" else "auto"
        if self.engine == "reference" and (
            float(self.time_limit_seconds) != 180.0 or self.cores != 1
        ):
            raise ValueError("reference engine requires 180 seconds and one core")
        return self

    @field_validator("time_limit_seconds")
    @classmethod
    def valid_time_limit(cls, value: int | float | None) -> int | float | None:
        if value is None:
            return value
        if isinstance(value, bool) or not math.isfinite(float(value)):
            raise ValueError("time_limit_seconds must be finite")
        if not 180 <= float(value) <= 900:
            raise ValueError("time_limit_seconds must be between 180 and 900")
        return value

    @field_validator("cores")
    @classmethod
    def valid_cores(cls, value: str | int | None) -> str | int | None:
        if value in {None, "auto"}:
            return value
        if isinstance(value, bool) or int(value) < 1:
            raise ValueError("cores must be 'auto' or a positive integer")
        return value

    @property
    def resolved_time_limit(self) -> float:
        assert self.time_limit_seconds is not None
        return float(self.time_limit_seconds)

    @property
    def resolved_cores(self) -> Literal["auto"] | int:
        assert self.cores is not None
        return self.cores


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
    SOLVED = "solved"
    NO_ANSWER = "no_answer_found"
    CANCELLED = "cancelled"
    INVALID = "invalid_problem"
    RESOURCE_ERROR = "resource_error"
    UNSUPPORTED_PLATFORM = "unsupported_platform"
    ENGINE_ERROR = "engine_error"


class Completeness(StrEnum):
    PROVEN = "proven"
    UNKNOWN = "unknown"


class TerminationReason(StrEnum):
    ANSWER_FOUND = "answer_found"
    NO_ANSWER_FOUND = "no_answer_found"
    TIME_LIMIT = "time_limit_reached"
    EXACT_COMPLETE = "exact_search_complete"
    CANCELLED = "cancelled"
    ENGINE_FAILED = "engine_failed"
    NO_PROGRESS = "no_progress"


class EngineIdentity(StrictModel):
    name: Literal["standard", "reference"]
    hash: str


class ResourceUsage(StrictModel):
    time_limit_seconds: float
    cores: Literal["auto"] | int
    seed: int


class AlgebraicAnswer(StrictModel):
    kind: Literal["algebraic"] = "algebraic"
    minimal_polynomial: list[str]
    real_root_index: int
    isolating_interval: tuple[str, str]
    decimal: str

    def canonical_key(self) -> tuple[object, ...]:
        return (self.kind, tuple(self.minimal_polynomial), self.real_root_index)


class AffinePiAnswer(StrictModel):
    kind: Literal["affine_pi"] = "affine_pi"
    pi_coefficient: str
    constant: str
    decimal: str

    def canonical_key(self) -> tuple[object, ...]:
        return (self.kind, self.pi_coefficient, self.constant)


ExactAnswer = Annotated[AlgebraicAnswer | AffinePiAnswer, Field(discriminator="kind")]


class SolveError(StrictModel):
    code: str
    message: str


class SolveResult(StrictModel):
    status: ResultStatus
    completeness: Completeness = Completeness.UNKNOWN
    engine: EngineIdentity
    problem_hash: str
    requested_resources: ResourceUsage
    used_resources: ResourceUsage
    elapsed_seconds: float
    answers: list[ExactAnswer] = Field(default_factory=list)
    termination_reason: TerminationReason
    warnings: list[str] = Field(default_factory=list)
    error: SolveError | None = None
    diagnostics: dict[str, Any] | None = None
