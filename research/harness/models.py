"""Strict typed input parsing for benchmark truth and solver run records."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Sequence


class InputError(ValueError):
    """Raised when benchmark input is incomplete, ambiguous, or ill typed."""


class DomainKind(str, Enum):
    BOUNDED = "bounded"
    ADAPTIVE_UNBOUNDED = "adaptive_unbounded"


class MatchMode(str, Enum):
    CERTIFIED_INTERVAL = "certified_interval"
    DECLARED_TOLERANCE = "declared_tolerance"


class AnswerLevel(str, Enum):
    VALIDATED = "validated"
    EXACT = "exact"


@dataclass(frozen=True, slots=True)
class TargetInterval:
    lower: Decimal
    upper: Decimal
    certified: bool

    @property
    def midpoint(self) -> Decimal:
        return (self.lower + self.upper) / Decimal(2)

    @property
    def width(self) -> Decimal:
        return self.upper - self.lower

    def overlaps(self, other: "TargetInterval") -> bool:
        return max(self.lower, other.lower) <= min(self.upper, other.upper)


@dataclass(frozen=True, slots=True)
class MatchSpec:
    mode: MatchMode
    tolerance: Decimal | None


@dataclass(frozen=True, slots=True)
class GoldTarget:
    target_id: str
    interval: TargetInterval
    allowed_branches: frozenset[str] | None


@dataclass(frozen=True, slots=True)
class CaseInput:
    case_id: str
    family_id: str
    strata: tuple[str, ...]
    domain_kind: DomainKind
    exact_eligible: bool
    matching: MatchSpec
    gold_targets: tuple[GoldTarget, ...]


@dataclass(frozen=True, slots=True)
class ReportedAnswer:
    answer_id: str
    level: AnswerLevel
    interval: TargetInterval
    branch: str | None
    configuration_validated: bool
    target_identity_certified: bool
    guard_valid: bool
    boundary_valid: bool
    configuration_id: str | None


@dataclass(frozen=True, slots=True)
class RunInput:
    run_id: str
    case_id: str
    seed: int
    budget_seconds: int
    answers: tuple[ReportedAnswer, ...]
    claims_complete: bool
    coverage_certificate: bool


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise InputError(f"{path}: expected object")
    if not all(isinstance(key, str) for key in value):
        raise InputError(f"{path}: object keys must be strings")
    return MappingProxyType(dict(value))


def _strict_keys(
    value: Mapping[str, Any],
    *,
    required: set[str],
    optional: set[str] = frozenset(),
    path: str,
) -> None:
    missing = required - value.keys()
    extra = value.keys() - required - optional
    if missing:
        raise InputError(f"{path}: missing keys {sorted(missing)}")
    if extra:
        raise InputError(f"{path}: unexpected keys {sorted(extra)}")


def _string(value: Any, path: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        raise InputError(f"{path}: expected nonempty string")
    return value


def _boolean(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise InputError(f"{path}: expected boolean")
    return value


def _integer(value: Any, path: str, *, minimum: int | None = None) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise InputError(f"{path}: expected integer")
    if minimum is not None and value < minimum:
        raise InputError(f"{path}: must be at least {minimum}")
    return value


def _decimal(value: Any, path: str) -> Decimal:
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        raise InputError(f"{path}: decimal values must be strings or integers, never binary floats")
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise InputError(f"{path}: invalid decimal {value!r}") from exc
    if not result.is_finite():
        raise InputError(f"{path}: decimal must be finite")
    return result


def _string_sequence(value: Any, path: str, *, nonempty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise InputError(f"{path}: expected array of strings")
    result = tuple(_string(item, f"{path}[{index}]") for index, item in enumerate(value))
    if nonempty and not result:
        raise InputError(f"{path}: must not be empty")
    if len(result) != len(set(result)):
        raise InputError(f"{path}: duplicate values are not allowed")
    return result


def _enum(enum_type: type[Enum], value: Any, path: str) -> Any:
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        allowed = [entry.value for entry in enum_type]
        raise InputError(f"{path}: expected one of {allowed}, got {value!r}") from exc


def _parse_interval(value: Any, path: str) -> TargetInterval:
    data = _mapping(value, path)
    _strict_keys(data, required={"lower", "upper", "certified"}, path=path)
    lower = _decimal(data["lower"], f"{path}.lower")
    upper = _decimal(data["upper"], f"{path}.upper")
    if lower > upper:
        raise InputError(f"{path}: lower must not exceed upper")
    return TargetInterval(lower, upper, _boolean(data["certified"], f"{path}.certified"))


def _parse_match_spec(value: Any, path: str) -> MatchSpec:
    data = _mapping(value, path)
    _strict_keys(data, required={"mode"}, optional={"tolerance"}, path=path)
    mode = _enum(MatchMode, data["mode"], f"{path}.mode")
    tolerance = None
    if "tolerance" in data:
        tolerance = _decimal(data["tolerance"], f"{path}.tolerance")
        if tolerance <= 0:
            raise InputError(f"{path}.tolerance: must be positive")
    if mode is MatchMode.DECLARED_TOLERANCE and tolerance is None:
        raise InputError(f"{path}: declared_tolerance mode requires tolerance")
    if mode is MatchMode.CERTIFIED_INTERVAL and tolerance is not None:
        raise InputError(f"{path}: certified_interval mode must not include tolerance")
    return MatchSpec(mode, tolerance)


def _parse_gold_target(value: Any, path: str) -> GoldTarget:
    data = _mapping(value, path)
    _strict_keys(data, required={"target_id", "interval"}, optional={"allowed_branches"}, path=path)
    branches = None
    if "allowed_branches" in data:
        parsed = _string_sequence(data["allowed_branches"], f"{path}.allowed_branches", nonempty=True)
        branches = frozenset(parsed)
    return GoldTarget(
        target_id=_string(data["target_id"], f"{path}.target_id"),
        interval=_parse_interval(data["interval"], f"{path}.interval"),
        allowed_branches=branches,
    )


def parse_case_input(value: Any) -> CaseInput:
    data = _mapping(value, "case")
    _strict_keys(
        data,
        required={
            "case_id",
            "family_id",
            "strata",
            "domain_kind",
            "exact_eligible",
            "matching",
            "gold_targets",
        },
        path="case",
    )
    strata = _string_sequence(data["strata"], "case.strata", nonempty=True)
    for stratum in strata:
        if re_fullmatch_stratum(stratum) is False:
            raise InputError(f"case.strata: invalid stratum {stratum!r}")
    raw_targets = data["gold_targets"]
    if not isinstance(raw_targets, Sequence) or isinstance(raw_targets, (str, bytes)) or not raw_targets:
        raise InputError("case.gold_targets: expected nonempty array")
    gold_targets = tuple(
        _parse_gold_target(item, f"case.gold_targets[{index}]")
        for index, item in enumerate(raw_targets)
    )
    ids = [target.target_id for target in gold_targets]
    if len(ids) != len(set(ids)):
        raise InputError("case.gold_targets: target_id values must be unique distinct targets")

    matching = _parse_match_spec(data["matching"], "case.matching")
    if matching.mode is MatchMode.CERTIFIED_INTERVAL:
        if any(not target.interval.certified for target in gold_targets):
            raise InputError("case.gold_targets: certified_interval mode requires certified Gold intervals")
        for index, left in enumerate(gold_targets):
            for right in gold_targets[index + 1 :]:
                if left.interval.overlaps(right.interval):
                    raise InputError(
                        "case.gold_targets: certified intervals for distinct targets must be disjoint"
                    )

    return CaseInput(
        case_id=_string(data["case_id"], "case.case_id"),
        family_id=_string(data["family_id"], "case.family_id"),
        strata=strata,
        domain_kind=_enum(DomainKind, data["domain_kind"], "case.domain_kind"),
        exact_eligible=_boolean(data["exact_eligible"], "case.exact_eligible"),
        matching=matching,
        gold_targets=gold_targets,
    )


def re_fullmatch_stratum(value: str) -> bool:
    return len(value) == 2 and value[0] == "S" and value[1] in "12345678"


def _parse_reported_answer(value: Any, path: str) -> ReportedAnswer:
    data = _mapping(value, path)
    _strict_keys(
        data,
        required={
            "answer_id",
            "level",
            "interval",
            "branch",
            "configuration_validated",
            "target_identity_certified",
            "guard_valid",
            "boundary_valid",
            "configuration_id",
        },
        path=path,
    )
    branch = data["branch"]
    if branch is not None:
        branch = _string(branch, f"{path}.branch")
    configuration_id = data["configuration_id"]
    if configuration_id is not None:
        configuration_id = _string(configuration_id, f"{path}.configuration_id")
    return ReportedAnswer(
        answer_id=_string(data["answer_id"], f"{path}.answer_id"),
        level=_enum(AnswerLevel, data["level"], f"{path}.level"),
        interval=_parse_interval(data["interval"], f"{path}.interval"),
        branch=branch,
        configuration_validated=_boolean(
            data["configuration_validated"], f"{path}.configuration_validated"
        ),
        target_identity_certified=_boolean(
            data["target_identity_certified"], f"{path}.target_identity_certified"
        ),
        guard_valid=_boolean(data["guard_valid"], f"{path}.guard_valid"),
        boundary_valid=_boolean(data["boundary_valid"], f"{path}.boundary_valid"),
        configuration_id=configuration_id,
    )


def parse_run_input(value: Any) -> RunInput:
    data = _mapping(value, "run")
    _strict_keys(
        data,
        required={
            "run_id",
            "case_id",
            "seed",
            "budget_seconds",
            "answers",
            "claims_complete",
            "coverage_certificate",
        },
        path="run",
    )
    raw_answers = data["answers"]
    if not isinstance(raw_answers, Sequence) or isinstance(raw_answers, (str, bytes)):
        raise InputError("run.answers: expected array")
    answers = tuple(
        _parse_reported_answer(item, f"run.answers[{index}]")
        for index, item in enumerate(raw_answers)
    )
    answer_ids = [answer.answer_id for answer in answers]
    if len(answer_ids) != len(set(answer_ids)):
        raise InputError("run.answers: answer_id values must be unique")
    return RunInput(
        run_id=_string(data["run_id"], "run.run_id"),
        case_id=_string(data["case_id"], "run.case_id"),
        seed=_integer(data["seed"], "run.seed", minimum=0),
        budget_seconds=_integer(data["budget_seconds"], "run.budget_seconds", minimum=1),
        answers=answers,
        claims_complete=_boolean(data["claims_complete"], "run.claims_complete"),
        coverage_certificate=_boolean(
            data["coverage_certificate"], "run.coverage_certificate"
        ),
    )
