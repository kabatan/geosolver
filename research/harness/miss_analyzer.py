"""Conservative first-checkpoint diagnosis for benchmark misses.

The analyzer is deliberately research-side.  It consumes the benchmark harness'
typed truth/run/evaluation values and may consume canonical Core evidence logs,
checkpoints, and separately audited diagnostic facts.  Missing telemetry never
becomes evidence that sampling, capture, or completeness succeeded.
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

from .matching import RunEvaluation, evaluate_run
from .models import (
    CaseInput,
    MatchMode,
    RunInput,
    TargetInterval,
    parse_case_input,
    parse_run_input,
)


ANALYZER_VERSION = "0.1.0"
DIAGNOSTICS_SCHEMA_VERSION = "geotarget.miss-diagnostics/v1"
REPORT_SCHEMA_VERSION = "geotarget.miss-report/v1"


class MissInputError(ValueError):
    """Raised when analyzer evidence is incomplete, ambiguous, or ill typed."""


class MissOutcome(str, Enum):
    NO_FAILURE = "no_failure"
    CLASSIFIED = "classified"
    UNKNOWN = "unknown"


class SubjectKind(str, Enum):
    RUN = "run"
    TARGET = "target"
    ANSWER = "answer"
    TASK = "task"


class FactSource(str, Enum):
    INDEPENDENT_TRUTH_AUDIT = "independent_truth_audit"
    REFERENCE_DIFFERENTIAL = "reference_differential"
    INSTRUMENTED_CAPTURE = "instrumented_capture"
    COUNTERFACTUAL_REPLAY = "counterfactual_replay"
    CANONICAL_VALIDATION = "canonical_validation"
    ARCHIVE_AUDIT = "archive_audit"
    SCHEDULER_AUDIT = "scheduler_audit"
    OUTPUT_AUDIT = "output_audit"
    DETERMINISM_AUDIT = "determinism_audit"
    PERFORMANCE_COMPARISON = "performance_comparison"


class FactKind(str, Enum):
    GOLD_TRUTH_INVALID = "gold_truth_invalid"
    REFERENCE_COMPILED_MISMATCH = "reference_compiled_mismatch"
    DOMAIN_INVALID = "domain_invalid"
    SCALING_INVALID = "scaling_invalid"
    CAPTURE_REGION_NOT_ENTERED = "capture_region_not_entered"
    CAPTURE_REGION_ENTERED = "capture_region_entered"
    LOCAL_SOLVER_FAILED = "local_solver_failed"
    NONZERO_STATIONARY_POINT = "nonzero_stationary_point"
    GUARD_INVALID = "guard_invalid"
    BRANCH_INVALID = "branch_invalid"
    SINGULAR_OR_MANIFOLD_INCONCLUSIVE = "singular_or_manifold_inconclusive"
    ARCHIVE_WITNESS_LOST = "archive_witness_lost"
    SCHEDULER_STARVATION_OR_DUPLICATE_WORK = "scheduler_starvation_or_duplicate_work"
    REFINEMENT_FAILED = "refinement_failed"
    CONFIGURATION_CERTIFICATE_FAILED = "configuration_certificate_failed"
    TARGET_IDENTITY_FAILED = "target_identity_failed"
    OUTPUT_MISMATCH_OR_FALSE_COMPLETE = "output_mismatch_or_false_complete"
    ADAPTIVE_SHELL_NOT_COVERED = "adaptive_shell_not_covered"
    NONDETERMINISTIC_REPLAY = "nondeterministic_replay"
    SAME_BUDGET_OVERHEAD_GATE_FAILED = "same_budget_overhead_gate_failed"


@dataclass(frozen=True, slots=True)
class DiagnosticFact:
    kind: FactKind
    subject_kind: SubjectKind
    subject_id: str | None
    source: FactSource
    evidence_ref: str
    causal: bool


@dataclass(frozen=True, slots=True)
class DiagnosticBundle:
    facts: tuple[DiagnosticFact, ...]


@dataclass(frozen=True, slots=True)
class TraceObservation:
    sequence: int
    evidence_ref: str
    target: TargetInterval | None
    canonical_near_feasible: bool
    canonical_valid: bool
    verified: bool
    needs_refinement: bool
    diagnostic: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class ParsedTrace:
    origin: str
    observations: tuple[TraceObservation, ...]


@dataclass(frozen=True, slots=True)
class FailureSignal:
    kind: FactKind
    subject_kind: SubjectKind
    subject_id: str | None
    source: str
    evidence_ref: str


@dataclass(frozen=True, slots=True)
class FailureSpec:
    failure_id: str
    checkpoint: str
    order: int


@dataclass(frozen=True, slots=True)
class ReportEvidence:
    signal_kind: str
    subject_kind: str
    subject_id: str | None
    source: str
    evidence_ref: str


@dataclass(frozen=True, slots=True)
class MissReport:
    case_id: str
    run_id: str
    outcome: MissOutcome
    failure_id: str | None
    checkpoint: str | None
    missing_validated_target_ids: tuple[str, ...]
    missing_exact_target_ids: tuple[str, ...]
    safety_violation_count: int
    evidence: tuple[ReportEvidence, ...]
    unclassified_reason_codes: tuple[str, ...]
    evidence_log_provided: bool
    checkpoint_provided: bool
    diagnostic_fact_count: int

    def to_document(self) -> dict[str, Any]:
        return {
            "schema_version": REPORT_SCHEMA_VERSION,
            "analyzer_version": ANALYZER_VERSION,
            "case_id": self.case_id,
            "run_id": self.run_id,
            "outcome": self.outcome.value,
            "failure_id": self.failure_id,
            "checkpoint": self.checkpoint,
            "missing_validated_target_ids": list(self.missing_validated_target_ids),
            "missing_exact_target_ids": list(self.missing_exact_target_ids),
            "safety_violation_count": self.safety_violation_count,
            "evidence": [
                {
                    "signal_kind": item.signal_kind,
                    "subject_kind": item.subject_kind,
                    "subject_id": item.subject_id,
                    "source": item.source,
                    "evidence_ref": item.evidence_ref,
                }
                for item in self.evidence
            ],
            "unclassified_reason_codes": list(self.unclassified_reason_codes),
            "inputs": {
                "evidence_log": self.evidence_log_provided,
                "checkpoint": self.checkpoint_provided,
                "diagnostic_fact_count": self.diagnostic_fact_count,
            },
        }


# Order follows docs/research/FAILURES.md's checkpoint chain, not F-number order.
_FAILURE_SPECS: dict[FactKind, FailureSpec] = {
    FactKind.GOLD_TRUTH_INVALID: FailureSpec("F0", "truth", 0),
    FactKind.NONDETERMINISTIC_REPLAY: FailureSpec("F17", "replay_environment", 1),
    FactKind.REFERENCE_COMPILED_MISMATCH: FailureSpec(
        "F1", "reference_plugin_semantics", 2
    ),
    FactKind.SCALING_INVALID: FailureSpec("F3", "scaling", 3),
    FactKind.SAME_BUDGET_OVERHEAD_GATE_FAILED: FailureSpec(
        "F18", "resource_overhead", 4
    ),
    FactKind.ADAPTIVE_SHELL_NOT_COVERED: FailureSpec("F16", "sample", 5),
    FactKind.CAPTURE_REGION_NOT_ENTERED: FailureSpec("F4", "capture", 6),
    FactKind.LOCAL_SOLVER_FAILED: FailureSpec("F5", "local_solve", 7),
    FactKind.NONZERO_STATIONARY_POINT: FailureSpec("F6", "canonical_residual", 8),
    FactKind.SINGULAR_OR_MANIFOLD_INCONCLUSIVE: FailureSpec(
        "F9", "singular_or_feasible_manifold", 9
    ),
    FactKind.DOMAIN_INVALID: FailureSpec("F2", "domain", 10),
    FactKind.GUARD_INVALID: FailureSpec("F8", "guard", 11),
    FactKind.BRANCH_INVALID: FailureSpec("F7", "branch", 12),
    FactKind.ARCHIVE_WITNESS_LOST: FailureSpec("F10", "archive", 13),
    FactKind.SCHEDULER_STARVATION_OR_DUPLICATE_WORK: FailureSpec(
        "F11", "scheduler", 14
    ),
    FactKind.REFINEMENT_FAILED: FailureSpec("F12", "high_precision_refinement", 15),
    FactKind.CONFIGURATION_CERTIFICATE_FAILED: FailureSpec(
        "F13", "configuration_certificate", 16
    ),
    FactKind.TARGET_IDENTITY_FAILED: FailureSpec("F14", "target_identity", 17),
    FactKind.OUTPUT_MISMATCH_OR_FALSE_COMPLETE: FailureSpec("F15", "output", 18),
}


_ALLOWED_SOURCES: dict[FactKind, frozenset[FactSource]] = {
    FactKind.GOLD_TRUTH_INVALID: frozenset({FactSource.INDEPENDENT_TRUTH_AUDIT}),
    FactKind.REFERENCE_COMPILED_MISMATCH: frozenset(
        {FactSource.REFERENCE_DIFFERENTIAL}
    ),
    FactKind.CAPTURE_REGION_NOT_ENTERED: frozenset(
        {FactSource.INSTRUMENTED_CAPTURE, FactSource.COUNTERFACTUAL_REPLAY}
    ),
    FactKind.CAPTURE_REGION_ENTERED: frozenset(
        {FactSource.INSTRUMENTED_CAPTURE, FactSource.COUNTERFACTUAL_REPLAY}
    ),
    FactKind.DOMAIN_INVALID: frozenset(
        {FactSource.CANONICAL_VALIDATION, FactSource.COUNTERFACTUAL_REPLAY}
    ),
    FactKind.SCALING_INVALID: frozenset(
        {FactSource.REFERENCE_DIFFERENTIAL, FactSource.COUNTERFACTUAL_REPLAY}
    ),
    FactKind.LOCAL_SOLVER_FAILED: frozenset(
        {
            FactSource.INSTRUMENTED_CAPTURE,
            FactSource.COUNTERFACTUAL_REPLAY,
            FactSource.CANONICAL_VALIDATION,
        }
    ),
    FactKind.NONZERO_STATIONARY_POINT: frozenset(
        {
            FactSource.INSTRUMENTED_CAPTURE,
            FactSource.COUNTERFACTUAL_REPLAY,
            FactSource.CANONICAL_VALIDATION,
        }
    ),
    FactKind.GUARD_INVALID: frozenset(
        {FactSource.CANONICAL_VALIDATION, FactSource.COUNTERFACTUAL_REPLAY}
    ),
    FactKind.BRANCH_INVALID: frozenset(
        {FactSource.CANONICAL_VALIDATION, FactSource.COUNTERFACTUAL_REPLAY}
    ),
    FactKind.SINGULAR_OR_MANIFOLD_INCONCLUSIVE: frozenset(
        {FactSource.CANONICAL_VALIDATION, FactSource.COUNTERFACTUAL_REPLAY}
    ),
    FactKind.ARCHIVE_WITNESS_LOST: frozenset({FactSource.ARCHIVE_AUDIT}),
    FactKind.SCHEDULER_STARVATION_OR_DUPLICATE_WORK: frozenset(
        {FactSource.SCHEDULER_AUDIT}
    ),
    FactKind.REFINEMENT_FAILED: frozenset(
        {FactSource.CANONICAL_VALIDATION, FactSource.COUNTERFACTUAL_REPLAY}
    ),
    FactKind.CONFIGURATION_CERTIFICATE_FAILED: frozenset(
        {FactSource.CANONICAL_VALIDATION, FactSource.COUNTERFACTUAL_REPLAY}
    ),
    FactKind.TARGET_IDENTITY_FAILED: frozenset(
        {FactSource.CANONICAL_VALIDATION, FactSource.COUNTERFACTUAL_REPLAY}
    ),
    FactKind.OUTPUT_MISMATCH_OR_FALSE_COMPLETE: frozenset({FactSource.OUTPUT_AUDIT}),
    FactKind.ADAPTIVE_SHELL_NOT_COVERED: frozenset(
        {FactSource.SCHEDULER_AUDIT, FactSource.INSTRUMENTED_CAPTURE}
    ),
    FactKind.NONDETERMINISTIC_REPLAY: frozenset({FactSource.DETERMINISM_AUDIT}),
    FactKind.SAME_BUDGET_OVERHEAD_GATE_FAILED: frozenset(
        {FactSource.PERFORMANCE_COMPARISON}
    ),
}


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise MissInputError(f"{path}: expected object with string keys")
    return value


def _strict_keys(value: Mapping[str, Any], required: set[str], path: str) -> None:
    missing = required - value.keys()
    extra = value.keys() - required
    if missing:
        raise MissInputError(f"{path}: missing keys {sorted(missing)}")
    if extra:
        raise MissInputError(f"{path}: unexpected keys {sorted(extra)}")


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise MissInputError(f"{path}: expected nonempty string")
    return value


def _boolean(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise MissInputError(f"{path}: expected boolean")
    return value


def _integer(value: Any, path: str, *, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise MissInputError(f"{path}: expected integer >= {minimum}")
    return value


def _enum(enum_type: type[Enum], value: Any, path: str) -> Any:
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        raise MissInputError(f"{path}: unsupported value {value!r}") from exc


def parse_diagnostic_bundle(value: Any) -> DiagnosticBundle:
    document = _mapping(value, "diagnostics")
    _strict_keys(document, {"schema_version", "facts"}, "diagnostics")
    if document["schema_version"] != DIAGNOSTICS_SCHEMA_VERSION:
        raise MissInputError(
            f"diagnostics.schema_version: expected {DIAGNOSTICS_SCHEMA_VERSION!r}"
        )
    raw_facts = document["facts"]
    if not isinstance(raw_facts, Sequence) or isinstance(raw_facts, (str, bytes)):
        raise MissInputError("diagnostics.facts: expected array")
    facts: list[DiagnosticFact] = []
    for index, raw in enumerate(raw_facts):
        path = f"diagnostics.facts[{index}]"
        fact_data = _mapping(raw, path)
        _strict_keys(
            fact_data,
            {"kind", "subject_kind", "subject_id", "source", "evidence_ref", "causal"},
            path,
        )
        subject_kind = _enum(
            SubjectKind, fact_data["subject_kind"], f"{path}.subject_kind"
        )
        subject_id = fact_data["subject_id"]
        if subject_kind is SubjectKind.RUN:
            if subject_id is not None:
                raise MissInputError(f"{path}.subject_id: run facts require null")
        else:
            subject_id = _string(subject_id, f"{path}.subject_id")
        kind = _enum(FactKind, fact_data["kind"], f"{path}.kind")
        source = _enum(FactSource, fact_data["source"], f"{path}.source")
        allowed = _ALLOWED_SOURCES.get(kind)
        if allowed is not None and source not in allowed:
            raise MissInputError(
                f"{path}.source: {source.value!r} cannot establish {kind.value!r}"
            )
        facts.append(
            DiagnosticFact(
                kind,
                subject_kind,
                subject_id,
                source,
                _string(fact_data["evidence_ref"], f"{path}.evidence_ref"),
                _boolean(fact_data["causal"], f"{path}.causal"),
            )
        )
    keys = [
        (
            fact.kind,
            fact.subject_kind,
            fact.subject_id,
            fact.source,
            fact.evidence_ref,
            fact.causal,
        )
        for fact in facts
    ]
    if len(keys) != len(set(keys)):
        raise MissInputError("diagnostics.facts: duplicate facts are not allowed")
    entered = {
        (fact.subject_kind, fact.subject_id)
        for fact in facts
        if fact.kind is FactKind.CAPTURE_REGION_ENTERED and fact.causal
    }
    for fact in facts:
        if (
            fact.kind
            in {FactKind.LOCAL_SOLVER_FAILED, FactKind.NONZERO_STATIONARY_POINT}
            and fact.source is FactSource.INSTRUMENTED_CAPTURE
            and (fact.subject_kind, fact.subject_id) not in entered
        ):
            raise MissInputError(
                "instrumented local failure requires a causal capture_region_entered "
                "fact for the same subject"
            )
    return DiagnosticBundle(tuple(facts))


def _decimal_text(value: str, path: str) -> Decimal:
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise MissInputError(f"{path}: invalid decimal") from exc
    if not result.is_finite():
        raise MissInputError(f"{path}: real must be finite")
    return result


def _trace_real(value: Any, path: str) -> Decimal:
    if isinstance(value, bool):
        raise MissInputError(f"{path}: boolean is not a real")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise MissInputError(f"{path}: real must be finite")
        return Decimal.from_float(value)
    raw = _mapping(value, path)
    if set(raw) == {"type", "value"}:
        _string(raw["type"], f"{path}.type")
        return _decimal_text(_string(raw["value"], f"{path}.value"), f"{path}.value")
    kind = _string(raw.get("kind"), f"{path}.kind")
    if kind == "integer":
        _strict_keys(raw, {"kind", "type", "decimal"}, path)
        _string(raw["type"], f"{path}.type")
        return _decimal_text(
            _string(raw["decimal"], f"{path}.decimal"), f"{path}.decimal"
        )
    if kind == "bigfloat":
        _strict_keys(raw, {"kind", "precision_bits", "decimal"}, path)
        _integer(raw["precision_bits"], f"{path}.precision_bits", minimum=2)
        return _decimal_text(
            _string(raw["decimal"], f"{path}.decimal"), f"{path}.decimal"
        )
    if kind == "binary_float":
        _strict_keys(raw, {"kind", "type", "bits"}, path)
        type_name = _string(raw["type"], f"{path}.type")
        formats = {"Float16": (4, ">e"), "Float32": (8, ">f"), "Float64": (16, ">d")}
        if type_name not in formats:
            raise MissInputError(f"{path}.type: unsupported binary float")
        width, format_code = formats[type_name]
        bits = _string(raw["bits"], f"{path}.bits")
        if len(bits) != width or any(
            character not in "0123456789abcdef" for character in bits
        ):
            raise MissInputError(
                f"{path}.bits: expected fixed-width lowercase hexadecimal"
            )
        decoded = struct.unpack(format_code, bytes.fromhex(bits))[0]
        if not math.isfinite(decoded):
            raise MissInputError(f"{path}: real must be finite")
        return Decimal.from_float(decoded)
    raise MissInputError(f"{path}.kind: unsupported typed real")


def _trace_target(value: Any, path: str) -> TargetInterval | None:
    if value is None:
        return None
    target = _mapping(value, path)
    expected = {"lower", "upper"}
    if "type" in target:
        expected.add("type")
        _string(target["type"], f"{path}.type")
    _strict_keys(target, expected, path)
    lower = _trace_real(target["lower"], f"{path}.lower")
    upper = _trace_real(target["upper"], f"{path}.upper")
    if lower > upper:
        raise MissInputError(f"{path}: target lower exceeds upper")
    return TargetInterval(lower, upper, False)


def _diagnostic_fields(value: Any, path: str) -> tuple[tuple[str, str], ...]:
    if value is None:
        return ()
    text = _string(value, path)
    fields: dict[str, str] = {}
    for index, part in enumerate(text.split(";")):
        if "=" not in part:
            if (
                part
                not in {
                    "cancelled_before_canonical_validation",
                    "deadline_before_canonical_validation",
                    "oracle_budget_before_canonical_validation",
                }
                or "resource" in fields
            ):
                raise MissInputError(
                    f"{path}: field {index} is not a known typed token"
                )
            key, entry = "resource", part
        else:
            key, entry = part.split("=", 1)
        if not key or not entry or key in fields:
            raise MissInputError(
                f"{path}: malformed or duplicate diagnostic field {key!r}"
            )
        fields[key] = entry
    return tuple(sorted(fields.items()))


def _parse_observation(payload: Any, path: str, sequence: int) -> TraceObservation:
    observation = _mapping(payload, path)
    fields = {
        "task_id",
        "configuration_id",
        "canonical_near_feasible",
        "canonical_valid",
        "target",
        "target_identity",
        "branch_signature",
        "verified",
        "verified_payload",
        "needs_refinement",
        "residual_score",
        "oracle_work",
        "endpoint",
        "diagnostic",
    }
    if "type" in observation:
        fields.add("type")
        _string(observation["type"], f"{path}.type")
    _strict_keys(observation, fields, path)
    _integer(observation["oracle_work"], f"{path}.oracle_work")
    return TraceObservation(
        sequence=sequence,
        evidence_ref=f"{path}.diagnostic",
        target=_trace_target(observation["target"], f"{path}.target"),
        canonical_near_feasible=_boolean(
            observation["canonical_near_feasible"], f"{path}.canonical_near_feasible"
        ),
        canonical_valid=_boolean(
            observation["canonical_valid"], f"{path}.canonical_valid"
        ),
        verified=_boolean(observation["verified"], f"{path}.verified"),
        needs_refinement=_boolean(
            observation["needs_refinement"], f"{path}.needs_refinement"
        ),
        diagnostic=_diagnostic_fields(observation["diagnostic"], f"{path}.diagnostic"),
    )


_EVIDENCE_KINDS = {
    "EVENT_SCHEDULED",
    "EVENT_PROPOSED",
    "EVENT_OBSERVED",
    "EVENT_BUDGET_CHARGED",
    "EVENT_STATUS",
    "EVENT_CALLBACK_FAILED",
    "EVENT_PROTOCOL_FAILED",
}
_CHECKPOINT_KINDS = {
    "scheduled",
    "proposed",
    "observed",
    "budget_charged",
    "status",
    "callback_failed",
    "protocol_failed",
}


def parse_solver_trace(value: Any, *, origin: str) -> ParsedTrace:
    """Parse either ``geotarget.evidence-log/v1`` or a checkpoint v1 document."""

    document = _mapping(value, origin)
    if document.get("schema") == "geotarget.evidence-log/v1":
        _strict_keys(document, {"schema", "resume_identity", "events"}, origin)
        raw_events = document["events"]
        event_prefix = f"{origin}.events"
        observed_kind = "EVENT_OBSERVED"
        allowed_kinds = _EVIDENCE_KINDS
    elif document.get("schema_version") == "geotarget.checkpoint/v1":
        _strict_keys(
            document,
            {"schema_version", "content_hash", "target_image_status", "state"},
            origin,
        )
        state = _mapping(document["state"], f"{origin}.state")
        _strict_keys(
            state,
            {
                "resume_identity",
                "policy_version",
                "budget",
                "workspace",
                "events",
                "rng_state",
                "precision_bits",
                "remaining_seconds",
                "cancelled",
            },
            f"{origin}.state",
        )
        raw_events = state["events"]
        event_prefix = f"{origin}.state.events"
        observed_kind = "observed"
        allowed_kinds = _CHECKPOINT_KINDS
    else:
        raise MissInputError(f"{origin}: unsupported solver evidence schema")
    if not isinstance(raw_events, Sequence) or isinstance(raw_events, (str, bytes)):
        raise MissInputError(f"{event_prefix}: expected array")
    observations: list[TraceObservation] = []
    for index, raw_event in enumerate(raw_events):
        path = f"{event_prefix}[{index}]"
        event = _mapping(raw_event, path)
        _strict_keys(event, {"sequence", "kind", "payload"}, path)
        sequence = _integer(event["sequence"], f"{path}.sequence", minimum=1)
        if sequence != index + 1:
            raise MissInputError(
                f"{path}.sequence: expected contiguous sequence {index + 1}"
            )
        kind = _string(event["kind"], f"{path}.kind")
        if kind not in allowed_kinds:
            raise MissInputError(f"{path}.kind: unsupported event kind {kind!r}")
        if kind == observed_kind:
            observations.append(
                _parse_observation(event["payload"], f"{path}.payload", sequence)
            )
        elif not isinstance(event["payload"], Mapping):
            raise MissInputError(f"{path}.payload: expected typed event object")
    return ParsedTrace(origin, tuple(observations))


def _trace_matches(case: CaseInput, interval: TargetInterval) -> tuple[str, ...]:
    matches: list[str] = []
    for target in case.gold_targets:
        if case.matching.mode is MatchMode.CERTIFIED_INTERVAL:
            # A non-certified trace enclosure may associate with a certified
            # Gold target only by containment. Mere overlap would let a broad
            # interval spanning unrelated values manufacture causality.
            matched = (
                target.interval.lower <= interval.lower
                and interval.upper <= target.interval.upper
            )
        else:
            tolerance = case.matching.tolerance
            assert tolerance is not None
            matched = (
                abs(interval.midpoint - target.interval.midpoint) <= tolerance
                and interval.width <= tolerance * 2
            )
        if matched:
            matches.append(target.target_id)
    return tuple(sorted(matches))


_VALIDATION_FACTS = {
    "CANDIDATE_DOMAIN_FAILED": FactKind.DOMAIN_INVALID,
    "CANDIDATE_STRICT_GUARD_UNSEPARATED": FactKind.GUARD_INVALID,
    "CANDIDATE_NONSTRICT_GUARD_FAILED": FactKind.GUARD_INVALID,
    "CANDIDATE_BRANCH_KEY_MISMATCH": FactKind.BRANCH_INVALID,
    "CANDIDATE_BRANCH_VALIDITY_FAILED": FactKind.BRANCH_INVALID,
    "CANDIDATE_BRANCH_SELECTOR_UNSEPARATED": FactKind.BRANCH_INVALID,
    "CANDIDATE_FAST_OBSERVATION_FAILED": FactKind.CONFIGURATION_CERTIFICATE_FAILED,
    "CANDIDATE_CANONICAL_EVALUATION_FAILED": FactKind.CONFIGURATION_CERTIFICATE_FAILED,
    "CANDIDATE_VARIABLE_BOUNDS_FAILED": FactKind.CONFIGURATION_CERTIFICATE_FAILED,
    "CANDIDATE_RELATION_RESIDUAL_FAILED": FactKind.CONFIGURATION_CERTIFICATE_FAILED,
    "CANDIDATE_RELATION_TRUTH_FAILED": FactKind.CONFIGURATION_CERTIFICATE_FAILED,
    "CANDIDATE_TARGET_INCONSISTENT": FactKind.CONFIGURATION_CERTIFICATE_FAILED,
}
_SINGULAR_IMAGE_FAILURES = {
    "TARGET_IMAGE_INSUFFICIENT_STENCIL",
    "TARGET_IMAGE_NONFINITE_LINEARIZATION",
    "TARGET_IMAGE_INSUFFICIENT_PROBES",
    "TARGET_IMAGE_SINGULAR_LINEARIZATION",
    "TARGET_IMAGE_UNRESOLVED_VARIATION",
}
_RESOURCE_IMAGE_FAILURES = {
    "TARGET_IMAGE_CANCELLED",
    "TARGET_IMAGE_DEADLINE_REACHED",
    "TARGET_IMAGE_ORACLE_BUDGET_EXHAUSTED",
}
_RESOURCE_DIAGNOSTICS = {
    "cancelled_before_canonical_validation",
    "deadline_before_canonical_validation",
    "oracle_budget_before_canonical_validation",
    "oracle_budget_exhausted",
}
_LOCAL_FAILURES = {
    "LOCAL_MAX_ITERATIONS",
    "LOCAL_MAX_EVALUATIONS",
    "LOCAL_NO_PROGRESS",
    "LOCAL_EVALUATION_FAILED",
}


def _trace_signals(
    case: CaseInput,
    trace: ParsedTrace,
    relevant_targets: frozenset[str],
) -> tuple[tuple[FailureSignal, ...], bool]:
    signals: list[FailureSignal] = []
    unassociated_diagnostic = False
    for observation in trace.observations:
        fields = dict(observation.diagnostic)
        if not fields:
            continue
        matched = (
            ()
            if observation.target is None
            else _trace_matches(case, observation.target)
        )
        associated = tuple(target for target in matched if target in relevant_targets)
        if len(associated) != 1:
            unassociated_diagnostic = True
            continue
        target_id = associated[0]
        kind: FactKind | None = None
        validation = fields.get("validation")
        image_failure = fields.get("target_image_failure")
        local_status = fields.get("local_status")
        if validation in _VALIDATION_FACTS:
            kind = _VALIDATION_FACTS[validation]
        elif image_failure in _SINGULAR_IMAGE_FAILURES:
            kind = FactKind.SINGULAR_OR_MANIFOLD_INCONCLUSIVE
        elif (
            image_failure in _RESOURCE_IMAGE_FAILURES
            or fields.get("resource") in _RESOURCE_DIAGNOSTICS
            or observation.needs_refinement
        ):
            kind = FactKind.REFINEMENT_FAILED
        elif local_status in _LOCAL_FAILURES and observation.canonical_near_feasible:
            kind = FactKind.LOCAL_SOLVER_FAILED
        if kind is not None:
            signals.append(
                FailureSignal(
                    kind,
                    SubjectKind.TARGET,
                    target_id,
                    FactSource.CANONICAL_VALIDATION.value,
                    observation.evidence_ref,
                )
            )
    return tuple(signals), unassociated_diagnostic


def _run_signals(
    case: CaseInput, run: RunInput, evaluation: RunEvaluation
) -> list[FailureSignal]:
    signals: list[FailureSignal] = []

    def add(kind: FactKind, reference: str, subject_id: str | None = None) -> None:
        signals.append(
            FailureSignal(
                kind,
                SubjectKind.RUN if subject_id is None else SubjectKind.ANSWER,
                subject_id,
                "run_evaluation",
                reference,
            )
        )

    if evaluation.false_guard_count or evaluation.false_boundary_count:
        add(FactKind.GUARD_INVALID, "evaluation.false_guard_or_boundary_count")
    if evaluation.false_branch_count:
        add(FactKind.BRANCH_INVALID, "evaluation.false_branch_count")
    for answer in run.answers:
        if not answer.configuration_validated:
            add(
                FactKind.CONFIGURATION_CERTIFICATE_FAILED,
                f"run.answers[{answer.answer_id}].configuration_validated",
                answer.answer_id,
            )
        if answer.level.value == "exact" and not answer.target_identity_certified:
            add(
                FactKind.TARGET_IDENTITY_FAILED,
                f"run.answers[{answer.answer_id}].target_identity_certified",
                answer.answer_id,
            )
    if evaluation.false_answer_count or evaluation.ambiguous_target_count:
        add(FactKind.OUTPUT_MISMATCH_OR_FALSE_COMPLETE, "evaluation.false_answer_count")
    if evaluation.false_complete_count:
        add(
            FactKind.OUTPUT_MISMATCH_OR_FALSE_COMPLETE,
            "evaluation.false_complete_count",
        )
    # A validated-complete exact-eligible case isolates the remaining failure to
    # exact target identity; do not make this inference while validated targets
    # are still missing.
    if evaluation.full_validated and case.exact_eligible and not evaluation.full_exact:
        add(FactKind.TARGET_IDENTITY_FAILED, "evaluation.full_exact")
    return signals


def _fact_applies(
    fact: DiagnosticFact,
    case: CaseInput,
    run: RunInput,
    relevant_targets: frozenset[str],
) -> bool:
    if fact.subject_kind is SubjectKind.RUN or fact.subject_kind is SubjectKind.TASK:
        return True
    if fact.subject_kind is SubjectKind.TARGET:
        all_targets = {target.target_id for target in case.gold_targets}
        if fact.subject_id not in all_targets:
            raise MissInputError(
                f"diagnostic fact references unknown target {fact.subject_id!r}"
            )
        return fact.subject_id in relevant_targets
    answer_ids = {answer.answer_id for answer in run.answers}
    if fact.subject_id not in answer_ids:
        raise MissInputError(
            f"diagnostic fact references unknown answer {fact.subject_id!r}"
        )
    return True


def analyze_miss(
    case: CaseInput,
    run: RunInput,
    evaluation: RunEvaluation,
    *,
    evidence_log: ParsedTrace | None = None,
    checkpoint: ParsedTrace | None = None,
    diagnostics: DiagnosticBundle | None = None,
) -> MissReport:
    """Return the earliest evidenced failed checkpoint for one benchmark run."""

    recomputed = evaluate_run(case, run)
    if recomputed != evaluation:
        raise MissInputError("evaluation does not equal evaluate_run(case, run)")
    missing_validated = tuple(
        sorted(evaluation.gold_target_ids - evaluation.covered_validated_targets)
    )
    missing_exact = tuple(
        sorted(evaluation.gold_target_ids - evaluation.covered_exact_targets)
        if case.exact_eligible
        else ()
    )
    has_failure = bool(
        missing_validated
        or evaluation.safety_violation_count
        or (case.exact_eligible and not evaluation.full_exact)
    )
    facts = diagnostics.facts if diagnostics is not None else ()
    if not has_failure:
        return MissReport(
            case.case_id,
            run.run_id,
            MissOutcome.NO_FAILURE,
            None,
            None,
            missing_validated,
            missing_exact,
            evaluation.safety_violation_count,
            (),
            (),
            evidence_log is not None,
            checkpoint is not None,
            len(facts),
        )

    relevant_targets = frozenset((*missing_validated, *missing_exact))
    signals = _run_signals(case, run, evaluation)
    ignored_noncausal = False
    for fact in facts:
        if not fact.causal:
            ignored_noncausal = True
            continue
        if fact.kind is FactKind.CAPTURE_REGION_ENTERED:
            continue
        if _fact_applies(fact, case, run, relevant_targets):
            signals.append(
                FailureSignal(
                    fact.kind,
                    fact.subject_kind,
                    fact.subject_id,
                    fact.source.value,
                    fact.evidence_ref,
                )
            )
    unassociated = False
    for trace in (evidence_log, checkpoint):
        if trace is None:
            continue
        derived, trace_unassociated = _trace_signals(case, trace, relevant_targets)
        signals.extend(derived)
        unassociated |= trace_unassociated

    if signals:
        selected_spec = min(
            (_FAILURE_SPECS[signal.kind] for signal in signals),
            key=lambda spec: (spec.order, spec.failure_id),
        )
        selected = sorted(
            {
                signal
                for signal in signals
                if _FAILURE_SPECS[signal.kind] == selected_spec
            },
            key=lambda signal: (
                signal.kind.value,
                signal.subject_kind.value,
                signal.subject_id or "",
                signal.source,
                signal.evidence_ref,
            ),
        )
        evidence = tuple(
            ReportEvidence(
                signal.kind.value,
                signal.subject_kind.value,
                signal.subject_id,
                signal.source,
                signal.evidence_ref,
            )
            for signal in selected
        )
        return MissReport(
            case.case_id,
            run.run_id,
            MissOutcome.CLASSIFIED,
            selected_spec.failure_id,
            selected_spec.checkpoint,
            missing_validated,
            missing_exact,
            evaluation.safety_violation_count,
            evidence,
            (),
            evidence_log is not None,
            checkpoint is not None,
            len(facts),
        )

    reasons = {"insufficient_causal_evidence"}
    if evidence_log is None and checkpoint is None:
        reasons.add("missing_solver_trace")
    if missing_validated:
        reasons.add("missing_targets_unclassified")
    elif missing_exact:
        reasons.add("exact_shortfall_unclassified")
    if ignored_noncausal:
        reasons.add("noncausal_diagnostics_ignored")
    if unassociated:
        reasons.add("unassociated_trace_diagnostics_ignored")
    return MissReport(
        case.case_id,
        run.run_id,
        MissOutcome.UNKNOWN,
        None,
        None,
        missing_validated,
        missing_exact,
        evaluation.safety_violation_count,
        (),
        tuple(sorted(reasons)),
        evidence_log is not None,
        checkpoint is not None,
        len(facts),
    )


def canonical_report_json(report: MissReport) -> str:
    return json.dumps(
        report.to_document(),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _read_json(path: str, label: str) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MissInputError(f"{label}: cannot read JSON: {exc}") from exc


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Diagnose a GeoTarget benchmark miss")
    parser.add_argument("--case", required=True, help="typed CaseInput JSON")
    parser.add_argument("--run", required=True, help="typed RunInput JSON")
    parser.add_argument(
        "--evidence-log", help="canonical geotarget.evidence-log/v1 JSON"
    )
    parser.add_argument("--checkpoint", help="canonical geotarget.checkpoint/v1 JSON")
    parser.add_argument("--diagnostics", help="typed miss-diagnostics/v1 JSON")
    parser.add_argument("--output", help="write canonical miss-report/v1 JSON")
    arguments = parser.parse_args(argv)
    try:
        case = parse_case_input(_read_json(arguments.case, "case"))
        run = parse_run_input(_read_json(arguments.run, "run"))
        evaluation = evaluate_run(case, run)
        evidence = (
            parse_solver_trace(
                _read_json(arguments.evidence_log, "evidence_log"), origin="evidence"
            )
            if arguments.evidence_log
            else None
        )
        checkpoint = (
            parse_solver_trace(
                _read_json(arguments.checkpoint, "checkpoint"), origin="checkpoint"
            )
            if arguments.checkpoint
            else None
        )
        diagnostics = (
            parse_diagnostic_bundle(_read_json(arguments.diagnostics, "diagnostics"))
            if arguments.diagnostics
            else None
        )
        rendered = canonical_report_json(
            analyze_miss(
                case,
                run,
                evaluation,
                evidence_log=evidence,
                checkpoint=checkpoint,
                diagnostics=diagnostics,
            )
        )
        if arguments.output:
            Path(arguments.output).write_text(
                rendered + "\n", encoding="utf-8", newline="\n"
            )
        else:
            print(rendered)
        return 0
    except (MissInputError, ValueError) as exc:
        print(f"miss-analyzer: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
