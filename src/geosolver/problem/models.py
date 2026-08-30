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
    time_limit_seconds: StrictInt | StrictFloat = 180
    cores: StrictInt = 1
    seed: StrictInt = 0

    @field_validator("time_limit_seconds")
    @classmethod
    def valid_time_limit(cls, value: int | float) -> int | float:
        if isinstance(value, bool) or not math.isfinite(float(value)):
            raise ValueError("time_limit_seconds must be finite")
        if not 180 <= float(value) <= 900:
            raise ValueError("time_limit_seconds must be between 180 and 900")
        return value

    @field_validator("cores")
    @classmethod
    def valid_cores(cls, value: int) -> int:
        if isinstance(value, bool) or int(value) < 1:
            raise ValueError("cores must be a positive integer")
        return value

    @property
    def resolved_time_limit(self) -> float:
        return float(self.time_limit_seconds)

    @property
    def resolved_cores(self) -> int:
        return int(self.cores)


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
    name: Literal["standard"] = "standard"
    source_hash: str
    resolved_config_hash: str
    dependency_lock_hash: str

    @property
    def hash(self) -> str:
        """Compatibility accessor for the former single hash field."""
        return self.source_hash


class ResourceUsage(StrictModel):
    time_limit_seconds: float
    cores: int
    seed: int


class AlgebraicNumberDescriptor(StrictModel):
    """Canonical identity and isolation data for one real algebraic number."""

    minimal_polynomial: list[str]
    real_root_index: int
    isolating_interval: tuple[str, str]
    decimal: str

    def canonical_key(self) -> tuple[object, ...]:
        return (tuple(self.minimal_polynomial), self.real_root_index)


class AlgebraicAnswer(StrictModel):
    kind: Literal["algebraic"] = "algebraic"
    value: AlgebraicNumberDescriptor

    @property
    def minimal_polynomial(self) -> list[str]:
        return self.value.minimal_polynomial

    @property
    def real_root_index(self) -> int:
        return self.value.real_root_index

    @property
    def isolating_interval(self) -> tuple[str, str]:
        return self.value.isolating_interval

    @property
    def decimal(self) -> str:
        return self.value.decimal

    def canonical_key(self) -> tuple[object, ...]:
        return (self.kind, *self.value.canonical_key())


class AffinePiAnswer(StrictModel):
    kind: Literal["affine_pi"] = "affine_pi"
    pi_coefficient: AlgebraicNumberDescriptor
    constant: AlgebraicNumberDescriptor
    decimal: str

    def canonical_key(self) -> tuple[object, ...]:
        return (
            self.kind,
            self.pi_coefficient.canonical_key(),
            self.constant.canonical_key(),
        )


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
