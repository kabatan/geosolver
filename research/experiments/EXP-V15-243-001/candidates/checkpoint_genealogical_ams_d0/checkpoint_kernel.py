"""Callback-exact checkpointable fork of the mature v15 local kernel.

This candidate keeps the numerical policy of the frozen event-refreshed
direct-good-Broyden TR/LM kernel, but expresses evaluator work as an explicit
state machine.  ``advance_one`` charges at most one call to the untouched
source evaluator.  Consequently a checkpoint taken after any returned
callback event is a genuine continuation point, including in the middle of a
finite-difference Jacobian.

The checkpoint never contains a case identifier, source hash, truth, target,
or past outcome.  The caller reattaches the source evaluator and the compiled
source-semantic AD program when restoring a trusted checkpoint payload.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import hashlib
import hmac
import importlib.util
import math
import os
from pathlib import Path
import pickle
import struct
import sys
import time
from types import ModuleType
from typing import Mapping, Sequence

import numpy as np


HERE = Path(__file__).resolve().parent
# Candidate-private path adaptation only.  The remainder of this file is the
# direct Wave-10 checkpoint-kernel copy (upstream SHA-256 recorded in the
# experiment card).  D0 points this at the frozen extracted research runtime;
# no common checkpoint framework is introduced.
EXPERIMENTS = Path(
    os.environ.get("GEOTARGET_AMS_EXPERIMENTS_ROOT", str(HERE.parents[2]))
).resolve()
MATURE_PATH = (
    EXPERIMENTS / "EXP-REAL61-008/hybrid_direct_broyden_tr_lm_v9/candidate.py"
)
MATURE_SHA256 = "e9c9bd7fc950baafdb90b8899c86ef6286da539b868f6fd0e00664b709dd0caa"
CHECKPOINT_SCHEMA = "geotarget.v15.checkpoint-kernel/v1"
SOURCE_BINDING_DOMAIN = b"geotarget.v15.checkpoint-source-binding/v1\0"


def _load_mature() -> ModuleType:
    if hashlib.sha256(MATURE_PATH.read_bytes()).hexdigest() != MATURE_SHA256:
        raise RuntimeError("hash-bound mature v15 local kernel changed")
    name = "geotarget_wave10_checkpoint_frozen_mature"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    specification = importlib.util.spec_from_file_location(name, MATURE_PATH)
    if specification is None or specification.loader is None:
        raise ImportError(MATURE_PATH)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


_MATURE = _load_mature()
_ROW = _MATURE._ROW
_AD = _ROW._AD
_RUIZ = _MATURE._RUIZ

ADProgram = _MATURE.ADProgram
compile_program = _MATURE.compile_program
REFERENCE_NAME = "checkpointable_event_refreshed_direct_broyden_ruiz_tr_lm"


@dataclass(frozen=True)
class Configuration:
    """Numerical policy copied from the hash-bound mature v15 kernel."""

    name: str = REFERENCE_NAME
    base_configuration: object = _ROW.REFERENCE
    ruiz_configuration: object = _RUIZ.REFERENCE
    maximum_iterations: int = 96
    denominator_rtol: float = 1.0e-14
    secant_defect_refresh: float = 0.85
    poor_model_ratio: float = 0.05
    poor_model_refresh_after: int = 2
    maximum_consecutive_rejections: int = 8
    maximum_consecutive_linear_failures: int = 2
    maximum_fd_attempts: int = 3
    fd_retry_shrink: float = 0.5
    rng_seed: int = 0


REFERENCE = Configuration()
CONFIGURATIONS = {REFERENCE_NAME: REFERENCE}


@dataclass(frozen=True)
class CallbackRecord:
    ordinal: int
    kind: str
    point: tuple[float, ...]
    succeeded: bool
    raw_relation: tuple[float, ...] = ()
    raw_violation: tuple[float, ...] = ()
    augmented: tuple[float, ...] = ()
    semantics_valid: bool = False
    exception_type: str | None = None
    decision: str = "observed"


@dataclass(frozen=True)
class AdvanceEvent:
    """One externally visible state-machine event."""

    callback_ordinal: int | None
    kind: str
    phase: str
    terminal: bool
    status: str | None
    decision: str


@dataclass(frozen=True)
class CandidateOutcome:
    endpoint: np.ndarray
    status: str
    counters: Mapping[str, int]
    callback_ledger: tuple[CallbackRecord, ...]


@dataclass
class _JacobianBuild:
    matrix: np.ndarray
    supported: np.ndarray
    unsupported: np.ndarray
    z: np.ndarray
    column: int = 0
    attempt: int = 0
    attempt_points: tuple[tuple[float, float], ...] = ()
    fd_calls: int = 0
    initial: bool = False


def _counter_template() -> dict[str, int]:
    counters = dict(_MATURE._counter_template())
    counters.update(
        {
            "charged_callbacks": 0,
            "checkpoint_serializations": 0,
            "checkpoint_restorations": 0,
            "fd_retry_requests": 0,
            "fd_retry_successes": 0,
            "fd_retry_exhaustions": 0,
            "model_restart_generations": 0,
            "rng_draws": 0,
        }
    )
    return counters


def _validate_configuration(configuration: Configuration) -> None:
    if not isinstance(configuration, Configuration):
        raise TypeError("checkpoint-kernel Configuration is required")
    if configuration.maximum_iterations < 1:
        raise ValueError("maximum_iterations must be positive")
    if not (0.0 < configuration.denominator_rtol < 1.0):
        raise ValueError("denominator_rtol must lie in (0,1)")
    if not (0.0 < configuration.secant_defect_refresh < 2.0):
        raise ValueError("secant_defect_refresh must lie in (0,2)")
    if not (0.0 <= configuration.poor_model_ratio < 1.0):
        raise ValueError("poor_model_ratio must lie in [0,1)")
    if configuration.poor_model_refresh_after < 1:
        raise ValueError("poor_model_refresh_after must be positive")
    if configuration.maximum_fd_attempts < 1:
        raise ValueError("maximum_fd_attempts must be positive")
    if not (0.0 < configuration.fd_retry_shrink < 1.0):
        raise ValueError("fd_retry_shrink must lie in (0,1)")


def _configuration_payload(configuration: Configuration) -> tuple[object, ...]:
    base = configuration.base_configuration
    ruiz = configuration.ruiz_configuration
    return (
        configuration.name,
        configuration.maximum_iterations,
        configuration.denominator_rtol,
        configuration.secant_defect_refresh,
        configuration.poor_model_ratio,
        configuration.poor_model_refresh_after,
        configuration.maximum_consecutive_rejections,
        configuration.maximum_consecutive_linear_failures,
        configuration.maximum_fd_attempts,
        configuration.fd_retry_shrink,
        configuration.rng_seed,
        tuple(
            (name, getattr(base, name))
            for name in (
                "fd_relative_step",
                "initial_trust_radius",
                "maximum_trust_radius",
                "minimum_trust_radius",
                "initial_damping",
                "minimum_damping",
                "maximum_damping",
                "rank_rtol",
                "success_residual_inf",
                "guard_weight",
                "parity_rtol",
                "parity_atol",
                "nonmonotone_window",
                "sufficient_decrease",
                "nonmonotone_inf_growth",
            )
        ),
        tuple(
            (name, getattr(ruiz, name))
            for name in (
                "maximum_ruiz_iterations",
                "minimum_update_factor",
                "maximum_update_factor",
                "minimum_cumulative_factor",
                "maximum_cumulative_factor",
                "convergence_norm_ratio",
                "cpqr_condition_limit",
            )
        ),
    )


def _source_binding_digest(token: bytes) -> bytes:
    """Bind a worker-owned random token without exposing it to solver policy."""

    if not isinstance(token, bytes):
        raise TypeError("source_binding_token must be bytes")
    if len(token) < 16:
        raise ValueError("source_binding_token must contain at least 128 bits")
    return hashlib.sha256(SOURCE_BINDING_DOMAIN + token).digest()


def _state_to_payload(state: object | None) -> object | None:
    if state is None:
        return None
    return {
        "x": np.asarray(state.x, dtype=float).copy(),
        "augmented": np.asarray(state.augmented, dtype=float).copy(),
        "relation": np.asarray(state.relation, dtype=float).copy(),
        "semantics_valid": bool(state.semantics_valid),
        "violation_inf": float(state.violation_inf),
    }


def _state_from_payload(payload: Mapping[str, object] | None) -> object | None:
    if payload is None:
        return None
    return _AD._State(
        np.asarray(payload["x"], dtype=float).copy(),
        np.asarray(payload["augmented"], dtype=float).copy(),
        np.asarray(payload["relation"], dtype=float).copy(),
        bool(payload["semantics_valid"]),
        float(payload["violation_inf"]),
    )


def _record_to_payload(record: CallbackRecord) -> dict[str, object]:
    return {
        "ordinal": record.ordinal,
        "kind": record.kind,
        "point": record.point,
        "succeeded": record.succeeded,
        "raw_relation": record.raw_relation,
        "raw_violation": record.raw_violation,
        "augmented": record.augmented,
        "semantics_valid": record.semantics_valid,
        "exception_type": record.exception_type,
        "decision": record.decision,
    }


def _record_from_payload(payload: Mapping[str, object]) -> CallbackRecord:
    return CallbackRecord(
        ordinal=int(payload["ordinal"]),
        kind=str(payload["kind"]),
        point=tuple(float(value) for value in payload["point"]),
        succeeded=bool(payload["succeeded"]),
        raw_relation=tuple(float(value) for value in payload["raw_relation"]),
        raw_violation=tuple(float(value) for value in payload["raw_violation"]),
        augmented=tuple(float(value) for value in payload["augmented"]),
        semantics_valid=bool(payload["semantics_valid"]),
        exception_type=(
            None
            if payload["exception_type"] is None
            else str(payload["exception_type"])
        ),
        decision=str(payload["decision"]),
    )


@dataclass
class CheckpointState:
    """Complete resumable local-solver state.

    Construct through :func:`create_checkpoint`; direct construction is kept
    public only so schedulers can type-check an opaque checkpoint.
    """

    case: object
    program: object
    source_binding_digest: bytes
    configuration: Configuration
    anchor: np.ndarray
    variable_scale: np.ndarray
    explicit_lower: np.ndarray
    explicit_upper: np.ndarray
    lower_z: np.ndarray
    upper_z: np.ndarray
    max_callbacks: int
    deadline_monotonic: float
    phase: str = "initial_evaluation"
    terminal_status: str | None = None
    counters: dict[str, int] = field(default_factory=_counter_template)
    callback_ledger: list[CallbackRecord] = field(default_factory=list)
    current: object | None = None
    best: object | None = None
    current_generation: int = 0
    trust_radius: float = 0.0
    damping: float = 0.0
    objectives: deque[float] = field(default_factory=deque)
    relation_norms: deque[float] = field(default_factory=deque)
    consecutive_rejections: int = 0
    consecutive_linear_failures: int = 0
    consecutive_poor_ratios: int = 0
    refresh_requested: bool = False
    refresh_reasons: list[str] = field(default_factory=list)
    direct_model: np.ndarray | None = None
    raw_cache_generation: int | None = None
    raw_cache_x: np.ndarray | None = None
    raw_cache_augmented: np.ndarray | None = None
    raw_cache_model: np.ndarray | None = None
    raw_cache_fd_calls: int = 0
    jacobian_build: _JacobianBuild | None = None
    pending_step: np.ndarray | None = None
    pending_delta_z: np.ndarray | None = None
    pending_trial_x: np.ndarray | None = None
    pending_step_norm: float | None = None
    iteration_started: bool = False
    rng: np.random.Generator | None = None

    @property
    def terminal(self) -> bool:
        return self.terminal_status is not None

    @property
    def charged_callbacks(self) -> int:
        return int(self.counters["charged_callbacks"])

    def checkpoint(self) -> bytes:
        """Serialize all algorithmic state; payloads are trusted/local only."""

        payload = _snapshot_payload(self)
        # Diagnostics are intentionally not advanced in the serialized state:
        # resuming must be trajectory-identical to never having serialized.
        self.counters["checkpoint_serializations"] += 1
        return pickle.dumps(payload, protocol=5)

    @classmethod
    def resume(
        cls,
        case: object,
        program: object,
        configuration: Configuration,
        payload: bytes,
        *,
        source_binding_token: bytes,
        deadline_monotonic: float | None = None,
    ) -> "CheckpointState":
        raw = pickle.loads(payload)  # noqa: S301 - documented trusted payload.
        restored = _restore_payload(
            case,
            program,
            configuration,
            raw,
            source_binding_token=source_binding_token,
            deadline_monotonic=deadline_monotonic,
        )
        restored.counters["checkpoint_restorations"] += 1
        return restored

    def result(self) -> CandidateOutcome:
        if not self.terminal:
            raise RuntimeError("checkpoint state is not terminal")
        endpoint_state = self.best if self.best is not None else self.current
        endpoint = (
            self.anchor.copy()
            if endpoint_state is None
            else np.asarray(endpoint_state.x, dtype=float).copy()
        )
        return CandidateOutcome(
            endpoint,
            str(self.terminal_status),
            dict(self.counters),
            tuple(self.callback_ledger),
        )


def create_checkpoint(
    case: object,
    program: object,
    configuration: Configuration,
    start: Sequence[float],
    *,
    source_binding_token: bytes,
    per_start_scale: Sequence[float],
    source_lower: Sequence[float],
    source_upper: Sequence[float],
    max_callbacks: int,
    deadline_monotonic: float,
) -> CheckpointState:
    """Create an unevaluated start-local checkpoint."""

    _validate_configuration(configuration)
    source_binding_digest = _source_binding_digest(source_binding_token)
    anchor, scale, lower, upper = _ROW._coordinate_inputs(
        start, per_start_scale, source_lower, source_upper
    )
    if int(program.dimension) != int(case.dimension) or int(
        program.residual_dimension
    ) != int(case.residual_dimension):
        raise ValueError("AD program shape differs from the untouched evaluator")
    if anchor.shape != (int(program.dimension),):
        raise ValueError("start dimension differs from the untouched evaluator")
    if max_callbacks < 2:
        raise ValueError("max_callbacks must be at least two")
    base = configuration.base_configuration
    return CheckpointState(
        case=case,
        program=program,
        source_binding_digest=source_binding_digest,
        configuration=configuration,
        anchor=anchor,
        variable_scale=scale,
        explicit_lower=lower,
        explicit_upper=upper,
        lower_z=(lower - anchor) / scale,
        upper_z=(upper - anchor) / scale,
        max_callbacks=int(max_callbacks),
        deadline_monotonic=float(deadline_monotonic),
        trust_radius=float(base.initial_trust_radius),
        damping=float(base.initial_damping),
        objectives=deque(maxlen=int(base.nonmonotone_window)),
        relation_norms=deque(maxlen=int(base.nonmonotone_window)),
        rng=np.random.default_rng(int(configuration.rng_seed)),
    )


def _jacobian_to_payload(build: _JacobianBuild | None) -> object | None:
    if build is None:
        return None
    return {
        "matrix": build.matrix.copy(),
        "supported": build.supported.copy(),
        "unsupported": build.unsupported.copy(),
        "z": build.z.copy(),
        "column": build.column,
        "attempt": build.attempt,
        "attempt_points": build.attempt_points,
        "fd_calls": build.fd_calls,
        "initial": build.initial,
    }


def _jacobian_from_payload(payload: Mapping[str, object] | None) -> _JacobianBuild | None:
    if payload is None:
        return None
    return _JacobianBuild(
        matrix=np.asarray(payload["matrix"], dtype=float).copy(),
        supported=np.asarray(payload["supported"], dtype=bool).copy(),
        unsupported=np.asarray(payload["unsupported"], dtype=int).copy(),
        z=np.asarray(payload["z"], dtype=float).copy(),
        column=int(payload["column"]),
        attempt=int(payload["attempt"]),
        attempt_points=tuple(
            (float(point), float(delta)) for point, delta in payload["attempt_points"]
        ),
        fd_calls=int(payload["fd_calls"]),
        initial=bool(payload["initial"]),
    )


def _snapshot_payload(state: CheckpointState) -> dict[str, object]:
    return {
        "schema": CHECKPOINT_SCHEMA,
        "source_binding_digest": state.source_binding_digest,
        "configuration": _configuration_payload(state.configuration),
        "dimension": int(state.program.dimension),
        "residual_dimension": int(state.program.residual_dimension),
        "anchor": state.anchor.copy(),
        "variable_scale": state.variable_scale.copy(),
        "explicit_lower": state.explicit_lower.copy(),
        "explicit_upper": state.explicit_upper.copy(),
        "lower_z": state.lower_z.copy(),
        "upper_z": state.upper_z.copy(),
        "max_callbacks": state.max_callbacks,
        "deadline_monotonic": state.deadline_monotonic,
        "phase": state.phase,
        "terminal_status": state.terminal_status,
        "counters": dict(state.counters),
        "callback_ledger": [_record_to_payload(row) for row in state.callback_ledger],
        "current": _state_to_payload(state.current),
        "best": _state_to_payload(state.best),
        "current_generation": state.current_generation,
        "trust_radius": state.trust_radius,
        "damping": state.damping,
        "objectives": tuple(state.objectives),
        "relation_norms": tuple(state.relation_norms),
        "consecutive_rejections": state.consecutive_rejections,
        "consecutive_linear_failures": state.consecutive_linear_failures,
        "consecutive_poor_ratios": state.consecutive_poor_ratios,
        "refresh_requested": state.refresh_requested,
        "refresh_reasons": tuple(state.refresh_reasons),
        "direct_model": None if state.direct_model is None else state.direct_model.copy(),
        "raw_cache_generation": state.raw_cache_generation,
        "raw_cache_x": None if state.raw_cache_x is None else state.raw_cache_x.copy(),
        "raw_cache_augmented": (
            None
            if state.raw_cache_augmented is None
            else state.raw_cache_augmented.copy()
        ),
        "raw_cache_model": (
            None if state.raw_cache_model is None else state.raw_cache_model.copy()
        ),
        "raw_cache_fd_calls": state.raw_cache_fd_calls,
        "jacobian_build": _jacobian_to_payload(state.jacobian_build),
        "pending_step": None if state.pending_step is None else state.pending_step.copy(),
        "pending_delta_z": (
            None if state.pending_delta_z is None else state.pending_delta_z.copy()
        ),
        "pending_trial_x": (
            None if state.pending_trial_x is None else state.pending_trial_x.copy()
        ),
        "pending_step_norm": state.pending_step_norm,
        "iteration_started": state.iteration_started,
        "rng_state": state.rng.bit_generator.state,
    }


def _restore_payload(
    case: object,
    program: object,
    configuration: Configuration,
    payload: Mapping[str, object],
    *,
    source_binding_token: bytes,
    deadline_monotonic: float | None,
) -> CheckpointState:
    if payload.get("schema") != CHECKPOINT_SCHEMA:
        raise ValueError("unsupported checkpoint schema")
    expected_binding = _source_binding_digest(source_binding_token)
    stored_binding = payload.get("source_binding_digest")
    if not isinstance(stored_binding, bytes) or not hmac.compare_digest(
        stored_binding, expected_binding
    ):
        raise ValueError("checkpoint source binding differs from resumed evaluator")
    _validate_configuration(configuration)
    if payload.get("configuration") != _configuration_payload(configuration):
        raise ValueError("checkpoint configuration differs from the resumed kernel")
    if int(payload["dimension"]) != int(case.dimension) or int(
        payload["residual_dimension"]
    ) != int(case.residual_dimension):
        raise ValueError("checkpoint evaluator shape mismatch")
    if int(program.dimension) != int(case.dimension) or int(
        program.residual_dimension
    ) != int(case.residual_dimension):
        raise ValueError("checkpoint AD program shape mismatch")
    base = configuration.base_configuration
    rng = np.random.default_rng()
    rng.bit_generator.state = payload["rng_state"]
    return CheckpointState(
        case=case,
        program=program,
        source_binding_digest=expected_binding,
        configuration=configuration,
        anchor=np.asarray(payload["anchor"], dtype=float).copy(),
        variable_scale=np.asarray(payload["variable_scale"], dtype=float).copy(),
        explicit_lower=np.asarray(payload["explicit_lower"], dtype=float).copy(),
        explicit_upper=np.asarray(payload["explicit_upper"], dtype=float).copy(),
        lower_z=np.asarray(payload["lower_z"], dtype=float).copy(),
        upper_z=np.asarray(payload["upper_z"], dtype=float).copy(),
        max_callbacks=int(payload["max_callbacks"]),
        deadline_monotonic=(
            float(payload["deadline_monotonic"])
            if deadline_monotonic is None
            else float(deadline_monotonic)
        ),
        phase=str(payload["phase"]),
        terminal_status=(
            None if payload["terminal_status"] is None else str(payload["terminal_status"])
        ),
        counters={str(key): int(value) for key, value in payload["counters"].items()},
        callback_ledger=[
            _record_from_payload(row) for row in payload["callback_ledger"]
        ],
        current=_state_from_payload(payload["current"]),
        best=_state_from_payload(payload["best"]),
        current_generation=int(payload["current_generation"]),
        trust_radius=float(payload["trust_radius"]),
        damping=float(payload["damping"]),
        objectives=deque(
            (float(value) for value in payload["objectives"]),
            maxlen=int(base.nonmonotone_window),
        ),
        relation_norms=deque(
            (float(value) for value in payload["relation_norms"]),
            maxlen=int(base.nonmonotone_window),
        ),
        consecutive_rejections=int(payload["consecutive_rejections"]),
        consecutive_linear_failures=int(payload["consecutive_linear_failures"]),
        consecutive_poor_ratios=int(payload["consecutive_poor_ratios"]),
        refresh_requested=bool(payload["refresh_requested"]),
        refresh_reasons=[str(value) for value in payload["refresh_reasons"]],
        direct_model=(
            None
            if payload["direct_model"] is None
            else np.asarray(payload["direct_model"], dtype=float).copy()
        ),
        raw_cache_generation=(
            None
            if payload["raw_cache_generation"] is None
            else int(payload["raw_cache_generation"])
        ),
        raw_cache_x=(
            None
            if payload["raw_cache_x"] is None
            else np.asarray(payload["raw_cache_x"], dtype=float).copy()
        ),
        raw_cache_augmented=(
            None
            if payload["raw_cache_augmented"] is None
            else np.asarray(payload["raw_cache_augmented"], dtype=float).copy()
        ),
        raw_cache_model=(
            None
            if payload["raw_cache_model"] is None
            else np.asarray(payload["raw_cache_model"], dtype=float).copy()
        ),
        raw_cache_fd_calls=int(payload["raw_cache_fd_calls"]),
        jacobian_build=_jacobian_from_payload(payload["jacobian_build"]),
        pending_step=(
            None
            if payload["pending_step"] is None
            else np.asarray(payload["pending_step"], dtype=float).copy()
        ),
        pending_delta_z=(
            None
            if payload["pending_delta_z"] is None
            else np.asarray(payload["pending_delta_z"], dtype=float).copy()
        ),
        pending_trial_x=(
            None
            if payload["pending_trial_x"] is None
            else np.asarray(payload["pending_trial_x"], dtype=float).copy()
        ),
        pending_step_norm=(
            None
            if payload["pending_step_norm"] is None
            else float(payload["pending_step_norm"])
        ),
        iteration_started=bool(payload["iteration_started"]),
        rng=rng,
    )


def _finish(state: CheckpointState, status: str) -> None:
    state.terminal_status = status
    state.phase = "terminal"


def _request_refresh(state: CheckpointState, reason: str) -> None:
    _MATURE._request_refresh(state.counters, reason)
    state.refresh_requested = True
    state.refresh_reasons.append(reason)


def _observe(
    state: CheckpointState, point: np.ndarray, kind: str
) -> tuple[object | None, CallbackRecord]:
    if state.charged_callbacks >= state.max_callbacks:
        state.counters["budget_stops"] += 1
        _finish(state, "budget")
        raise RuntimeError("internal callback cap reached before evaluation")
    ordinal = state.charged_callbacks + 1
    state.counters["charged_callbacks"] = ordinal
    point = np.asarray(point, dtype=float).copy()
    try:
        observation = state.case.evaluate(point)
        relation = np.asarray(observation.residual, dtype=float)
        raw_relation = relation.copy()
        if (
            relation.shape != (int(state.case.residual_dimension),)
            or not observation.finite
            or not np.all(np.isfinite(relation))
        ):
            relation = np.full(int(state.case.residual_dimension), 1.0e6)
        raw_violation = np.asarray(observation.violation_vector, dtype=float)
        if raw_violation.ndim != 1:
            raise ValueError("source violation vector is not one-dimensional")
        transformed_violation = np.maximum(
            0.0, np.where(np.isfinite(raw_violation), raw_violation, 1.0e6)
        )
        augmented = np.concatenate(
            (
                relation,
                float(state.configuration.base_configuration.guard_weight)
                * np.log1p(transformed_violation),
            )
        )
        evaluated = _AD._State(
            point,
            augmented,
            relation,
            bool(observation.finite and observation.semantics_valid),
            float(np.max(transformed_violation, initial=0.0)),
        )
    except Exception as error:
        record = CallbackRecord(
            ordinal=ordinal,
            kind=kind,
            point=tuple(float(value) for value in point),
            succeeded=False,
            exception_type=type(error).__name__,
        )
        return None, record
    record = CallbackRecord(
        ordinal=ordinal,
        kind=kind,
        point=tuple(float(value) for value in point),
        succeeded=True,
        raw_relation=tuple(float(value) for value in raw_relation),
        raw_violation=tuple(float(value) for value in raw_violation),
        augmented=tuple(float(value) for value in augmented),
        semantics_valid=bool(evaluated.semantics_valid),
    )
    return evaluated, record


def _replace_decision(record: CallbackRecord, decision: str) -> CallbackRecord:
    return CallbackRecord(
        ordinal=record.ordinal,
        kind=record.kind,
        point=record.point,
        succeeded=record.succeeded,
        raw_relation=record.raw_relation,
        raw_violation=record.raw_violation,
        augmented=record.augmented,
        semantics_valid=record.semantics_valid,
        exception_type=record.exception_type,
        decision=decision,
    )


def _event(state: CheckpointState, record: CallbackRecord) -> AdvanceEvent:
    state.callback_ledger.append(record)
    return AdvanceEvent(
        callback_ordinal=record.ordinal,
        kind=record.kind,
        phase=state.phase,
        terminal=state.terminal,
        status=state.terminal_status,
        decision=record.decision,
    )


def _terminal_event(state: CheckpointState) -> AdvanceEvent:
    return AdvanceEvent(
        callback_ordinal=None,
        kind="terminal",
        phase=state.phase,
        terminal=True,
        status=state.terminal_status,
        decision=str(state.terminal_status),
    )


def _prepare_jacobian(state: CheckpointState, *, initial: bool) -> None:
    current = state.current
    if current is None:
        raise RuntimeError("Jacobian requested before initial state")

    if state.raw_cache_generation == state.current_generation:
        if not (
            state.raw_cache_x is not None
            and state.raw_cache_augmented is not None
            and state.raw_cache_model is not None
            and _MATURE._CACHE._bitwise_equal(current.x, state.raw_cache_x)
            and _MATURE._CACHE._bitwise_equal(
                current.augmented, state.raw_cache_augmented
            )
        ):
            state.counters["same_current_cache_state_mutations"] += 1
            _finish(state, "cache_state_mutation")
            return
        state.counters["same_current_raw_jacobian_cache_hits"] += 1
        state.counters["full_jacobian_cache_restores"] += 1
        state.counters["same_current_fd_direction_evaluations_avoided"] += int(
            state.raw_cache_fd_calls
        )
        state.direct_model = state.raw_cache_model.copy()
        state.refresh_requested = False
        state.refresh_reasons.clear()
        state.phase = "linear_step"
        return

    if state.raw_cache_generation is not None:
        state.counters["same_current_raw_jacobian_invalidations"] += 1

    program = state.program
    base = state.configuration.base_configuration
    row_count = int(current.augmented.size)
    matrix = np.zeros((row_count, int(program.dimension)), dtype=float)
    supported = np.zeros(row_count, dtype=bool)

    relation_rows = program.relation_rows(current.x)
    for index, row in enumerate(relation_rows):
        if row is None:
            continue
        if _AD._parity_matches(row.value, current.relation[index], base) and np.all(
            np.isfinite(row.derivative)
        ):
            matrix[index, :] = row.derivative * state.variable_scale
            supported[index] = True
            state.counters["analytic_relation_rows"] += 1
        else:
            state.counters["relation_parity_fallback_rows"] += 1

    guard_start = int(program.residual_dimension)
    guard_rows = program.guard_rows(current.x)
    for ordinal, row in enumerate(guard_rows):
        index = guard_start + ordinal
        if index >= row_count - 1 or row is None:
            continue
        transformed = float(base.guard_weight) * math.log1p(max(0.0, row.value))
        if _AD._parity_matches(transformed, current.augmented[index], base) and np.all(
            np.isfinite(row.derivative)
        ):
            matrix[index, :] = (
                float(base.guard_weight)
                * row.derivative
                / (1.0 + max(0.0, row.value))
            ) * state.variable_scale
            supported[index] = True
            state.counters["analytic_guard_rows"] += 1
        else:
            state.counters["guard_parity_fallback_rows"] += 1

    if row_count > guard_start + len(guard_rows) and current.augmented[-1] == 0.0:
        supported[-1] = True
        state.counters["analytic_inactive_hard_rows"] += 1

    unsupported = np.flatnonzero(~supported)
    state.counters["analytic_rows_total"] += int(np.count_nonzero(supported))
    state.counters["fd_fallback_rows_total"] += int(unsupported.size)
    build = _JacobianBuild(
        matrix=matrix,
        supported=supported,
        unsupported=unsupported,
        z=(current.x - state.anchor) / state.variable_scale,
        initial=initial,
    )
    state.jacobian_build = build
    if unsupported.size == 0:
        _complete_jacobian(state)
    else:
        state.phase = "jacobian_fd"
        _prepare_fd_attempts(state)


def _fd_candidates(state: CheckpointState, column: int) -> tuple[tuple[float, float], ...]:
    build = state.jacobian_build
    if build is None:
        raise RuntimeError("FD candidates requested without a Jacobian build")
    base = state.configuration.base_configuration
    z_value = float(build.z[column])
    nominal = float(base.fd_relative_step) * max(1.0, abs(z_value))
    preferred = min(float(state.upper_z[column]), z_value + nominal)
    if preferred == z_value:
        preferred = max(float(state.lower_z[column]), z_value - nominal)
    candidates: list[tuple[float, float]] = []

    def add(value: float) -> None:
        delta = value - z_value
        if delta == 0.0 or not math.isfinite(delta):
            return
        if any(existing == value for existing, _delta in candidates):
            return
        candidates.append((value, delta))

    add(preferred)
    opposite = (
        max(float(state.lower_z[column]), z_value - nominal)
        if preferred > z_value
        else min(float(state.upper_z[column]), z_value + nominal)
    )
    add(opposite)
    shrink = float(state.configuration.fd_retry_shrink)
    direction = 1.0 if preferred > z_value else -1.0
    for retry in range(1, int(state.configuration.maximum_fd_attempts)):
        distance = nominal * (shrink**retry)
        value = min(
            float(state.upper_z[column]),
            max(float(state.lower_z[column]), z_value + direction * distance),
        )
        add(value)
        direction *= -1.0
    return tuple(candidates[: int(state.configuration.maximum_fd_attempts)])


def _prepare_fd_attempts(state: CheckpointState) -> None:
    build = state.jacobian_build
    if build is None:
        raise RuntimeError("missing partial Jacobian")
    dimension = int(state.program.dimension)
    while build.column < dimension:
        candidates = _fd_candidates(state, build.column)
        if candidates:
            build.attempt_points = candidates
            build.attempt = 0
            return
        build.column += 1
    _complete_jacobian(state)


def _complete_jacobian(state: CheckpointState) -> None:
    build = state.jacobian_build
    current = state.current
    if build is None or current is None:
        raise RuntimeError("cannot complete missing Jacobian state")
    raw = np.asarray(build.matrix, dtype=float)
    if raw.ndim != 2 or raw.shape[0] != current.augmented.size:
        _finish(state, "jacobian_shape_failure")
        return
    if not np.all(np.isfinite(raw)):
        _finish(state, "jacobian_nonfinite_failure")
        return
    state.raw_cache_generation = state.current_generation
    state.raw_cache_x = np.asarray(current.x).copy()
    state.raw_cache_augmented = np.asarray(current.augmented).copy()
    state.raw_cache_model = raw.copy()
    state.raw_cache_fd_calls = int(build.fd_calls)
    state.counters["same_current_raw_jacobian_cache_misses"] += 1
    state.counters["full_jacobian_builds"] += 1
    if build.initial:
        state.counters["initial_fresh_jacobian_builds"] += 1
    else:
        state.counters["full_jacobian_refresh_builds"] += 1
    state.direct_model = raw.copy()
    state.jacobian_build = None
    state.refresh_requested = False
    state.refresh_reasons.clear()
    state.counters["model_restart_generations"] += 1
    # The mature kernel acquires its initial model before entering the first
    # termination/iteration check.  Refreshes, in contrast, continue the
    # iteration that requested them without incrementing the iteration count
    # a second time.
    state.phase = "iteration" if build.initial else "linear_step"


def _linear_failure(state: CheckpointState, reason: str) -> None:
    base = state.configuration.base_configuration
    state.counters["linear_failures"] += 1
    state.consecutive_linear_failures += 1
    _request_refresh(state, reason)
    state.damping = min(float(base.maximum_damping), state.damping * 8.0)
    state.trust_radius = max(
        float(base.minimum_trust_radius), state.trust_radius * 0.35
    )
    if (
        state.consecutive_linear_failures
        >= state.configuration.maximum_consecutive_linear_failures
    ):
        _finish(state, "stalled_or_budget")
    else:
        state.phase = "iteration"


def _prepare_trial(state: CheckpointState) -> None:
    if state.current is None or state.direct_model is None:
        _finish(state, "missing_linear_model")
        return
    base = state.configuration.base_configuration
    try:
        step, rank = _RUIZ._linear_step(
            state.direct_model,
            state.current.augmented,
            state.damping,
            base.rank_rtol,
            "cpqr",
            state.configuration.ruiz_configuration,
            state.counters,
        )
    except Exception:
        _linear_failure(state, "linear_failure")
        return
    state.counters["rank_deficient_iterations"] += int(
        rank < min(state.direct_model.shape)
    )
    state.consecutive_linear_failures = 0
    step_norm = float(np.linalg.norm(step))
    if not math.isfinite(step_norm) or step_norm == 0.0:
        state.counters["zero_step_failures"] += 1
        state.consecutive_rejections += 1
        _request_refresh(state, "zero_step")
        state.damping = min(float(base.maximum_damping), state.damping * 8.0)
        state.trust_radius = max(
            float(base.minimum_trust_radius), state.trust_radius * 0.35
        )
        if (
            state.consecutive_rejections
            >= state.configuration.maximum_consecutive_rejections
        ):
            _finish(state, "stalled_or_budget")
        else:
            state.phase = "iteration"
        return
    if step_norm > state.trust_radius:
        step = np.asarray(step, dtype=float).copy()
        step *= state.trust_radius / step_norm
        step_norm = state.trust_radius
        state.counters["trust_region_step_clips"] += 1
    current_z = (state.current.x - state.anchor) / state.variable_scale
    unprojected = current_z + step
    trial_z = np.minimum(np.maximum(unprojected, state.lower_z), state.upper_z)
    state.counters["explicit_source_bound_projections"] += int(
        not np.array_equal(unprojected, trial_z)
    )
    delta_z = trial_z - current_z
    if not np.any(delta_z):
        state.counters["zero_step_failures"] += 1
        state.consecutive_rejections += 1
        _request_refresh(state, "zero_step")
        state.damping = min(float(base.maximum_damping), state.damping * 8.0)
        state.trust_radius = max(
            float(base.minimum_trust_radius), state.trust_radius * 0.35
        )
        if (
            state.consecutive_rejections
            >= state.configuration.maximum_consecutive_rejections
        ):
            _finish(state, "stalled_or_budget")
        else:
            state.phase = "iteration"
        return
    state.pending_step = np.asarray(step, dtype=float).copy()
    state.pending_delta_z = np.asarray(delta_z, dtype=float).copy()
    state.pending_trial_x = state.anchor + state.variable_scale * trial_z
    state.pending_step_norm = float(step_norm)
    state.phase = "trial_evaluation"


def _post_trial(state: CheckpointState, trial: object) -> str:
    current = state.current
    direct_model = state.direct_model
    delta_z = state.pending_delta_z
    step_norm = state.pending_step_norm
    if current is None or direct_model is None or delta_z is None or step_norm is None:
        raise RuntimeError("trial result has no pending model state")
    base = state.configuration.base_configuration
    if state.best is None or _AD._better(trial, state.best):
        state.best = trial

    _predicted, predicted_reduction = _MATURE._raw_prediction(
        current, direct_model, delta_z
    )
    actual_reduction = current.objective - trial.objective
    raw_ratio = (
        actual_reduction / predicted_reduction
        if predicted_reduction > 0.0 and math.isfinite(predicted_reduction)
        else -math.inf
    )
    if not trial.semantics_valid:
        state.counters["semantic_invalid_trials"] += 1
        _request_refresh(state, "semantic_invalid")
    poor_ratio = bool(
        not math.isfinite(raw_ratio)
        or raw_ratio < state.configuration.poor_model_ratio
    )
    state.counters["poor_model_ratio_trials"] += int(poor_ratio)
    state.counters["nonpositive_model_predictions"] += int(
        not math.isfinite(predicted_reduction) or predicted_reduction <= 0.0
    )
    state.consecutive_poor_ratios = (
        state.consecutive_poor_ratios + 1 if poor_ratio else 0
    )
    if (
        state.consecutive_poor_ratios
        >= state.configuration.poor_model_refresh_after
    ):
        _request_refresh(state, "poor_ratio")
        state.consecutive_poor_ratios = 0

    accepted, reason = _ROW._ROW._raw_nonmonotone_accept(
        trial,
        current,
        tuple(state.objectives),
        tuple(state.relation_norms),
        predicted_reduction,
        base,
    )
    if accepted:
        residual_change = trial.augmented - current.augmented
        updated, defect, usable = _MATURE._good_broyden_update(
            direct_model,
            delta_z,
            residual_change,
            state.configuration.denominator_rtol,
        )
        state.counters["direct_broyden_secant_checks"] += 1
        if usable:
            state.direct_model = updated
            state.counters["direct_broyden_updates"] += 1
            secant_error = float(
                np.linalg.norm(state.direct_model @ delta_z - residual_change)
            )
            secant_scale = max(1.0, float(np.linalg.norm(residual_change)))
            state.counters["direct_broyden_secant_check_failures"] += int(
                not math.isfinite(secant_error)
                or secant_error > 1.0e-10 * secant_scale
            )
        else:
            state.counters["direct_broyden_denominator_skips"] += 1
            _request_refresh(state, "denominator")
        if defect is not None and defect > state.configuration.secant_defect_refresh:
            _request_refresh(state, "secant_defect")
        state.current = trial
        state.current_generation += 1
        state.counters["accepted_steps"] += 1
        state.counters["raw_lexicographic_accepts"] += int(
            reason == "raw_lexicographic"
        )
        state.counters["raw_nonmonotone_accepts"] += int(
            reason == "raw_nonmonotone"
        )
        state.objectives.append(float(trial.objective))
        state.relation_norms.append(float(trial.relation_inf))
        state.consecutive_rejections = 0
        if raw_ratio > 0.75:
            state.trust_radius = min(
                float(base.maximum_trust_radius),
                max(state.trust_radius, 2.0 * step_norm),
            )
            state.damping = max(float(base.minimum_damping), state.damping * 0.3)
        elif raw_ratio < 0.25:
            state.trust_radius = max(
                float(base.minimum_trust_radius), state.trust_radius * 0.5
            )
            state.damping = min(float(base.maximum_damping), state.damping * 3.0)
        decision = f"accepted:{reason}"
    else:
        state.counters["rejected_steps"] += 1
        state.consecutive_rejections += 1
        state.trust_radius = max(
            float(base.minimum_trust_radius), state.trust_radius * 0.35
        )
        state.damping = min(float(base.maximum_damping), state.damping * 8.0)
        decision = f"rejected:{reason}"
        if (
            state.consecutive_rejections
            >= state.configuration.maximum_consecutive_rejections
        ):
            _finish(state, "stalled_or_budget")
    if not state.terminal:
        state.phase = "iteration"
    state.pending_step = None
    state.pending_delta_z = None
    state.pending_trial_x = None
    state.pending_step_norm = None
    return decision


def _final_status(state: CheckpointState) -> str:
    base = state.configuration.base_configuration
    best = state.best
    if (
        best is not None
        and best.semantics_valid
        and best.relation_inf <= base.success_residual_inf
    ):
        state.counters["reported_safe_endpoint"] = 1
        return "safe_root"
    if state.counters["budget_stops"]:
        return "budget"
    return "stalled_or_budget"


def advance_one(state: CheckpointState) -> AdvanceEvent:
    """Run deterministic transitions through at most one charged callback."""

    if not isinstance(state, CheckpointState):
        raise TypeError("CheckpointState is required")
    if state.terminal:
        return _terminal_event(state)

    while not state.terminal:
        if time.monotonic() >= state.deadline_monotonic:
            state.counters["deadline_stops"] += 1
            _finish(state, "deadline")
            break
        if state.phase == "initial_evaluation":
            if state.charged_callbacks >= state.max_callbacks:
                state.counters["budget_stops"] += 1
                _finish(state, "budget_before_start")
                continue
            current, record = _observe(state, state.anchor, "initial")
            if current is None:
                if record.exception_type == "BudgetExceeded":
                    state.counters["budget_stops"] += 1
                    _finish(state, "budget_before_start")
                else:
                    _finish(state, "initial_evaluation_failure")
                return _event(state, _replace_decision(record, state.terminal_status))
            state.current = current
            state.best = current
            state.counters["initial_state_evaluations"] += 1
            state.objectives.append(float(current.objective))
            state.relation_norms.append(float(current.relation_inf))
            state.phase = "jacobian_prepare"
            return _event(state, _replace_decision(record, "initial_state"))

        if state.phase == "iteration":
            current = state.current
            if current is None:
                _finish(state, "missing_current_state")
                continue
            base = state.configuration.base_configuration
            if current.semantics_valid and current.relation_inf <= base.success_residual_inf:
                state.counters["reported_safe_endpoint"] = 1
                _finish(state, "safe_root")
                continue
            if state.counters["iterations"] >= state.configuration.maximum_iterations:
                _finish(state, _final_status(state))
                continue
            state.counters["iterations"] += 1
            if state.refresh_requested or state.direct_model is None:
                state.phase = "jacobian_prepare"
            else:
                state.phase = "linear_step"
            continue

        if state.phase == "jacobian_prepare":
            _prepare_jacobian(
                state,
                initial=state.counters["full_jacobian_builds"] == 0,
            )
            continue

        if state.phase == "jacobian_fd":
            build = state.jacobian_build
            current = state.current
            if build is None or current is None:
                _finish(state, "missing_partial_jacobian")
                continue
            if build.column >= int(state.program.dimension):
                _complete_jacobian(state)
                continue
            if build.attempt >= len(build.attempt_points):
                state.counters["fd_retry_exhaustions"] += 1
                _finish(state, "jacobian_fd_retry_exhausted")
                continue
            if state.charged_callbacks >= state.max_callbacks:
                state.counters["budget_stops"] += 1
                _finish(
                    state,
                    "budget_during_initial_jacobian"
                    if build.initial
                    else "budget_during_jacobian",
                )
                continue
            trial_value, delta = build.attempt_points[build.attempt]
            trial_z = build.z.copy()
            trial_z[build.column] = trial_value
            point = state.anchor + state.variable_scale * trial_z
            trial, record = _observe(state, point, "jacobian_fd")
            build.fd_calls += 1
            state.counters["fd_direction_evaluations"] += 1
            if trial is None:
                if record.exception_type == "BudgetExceeded":
                    state.counters["budget_stops"] += 1
                    _finish(state, "budget_during_jacobian")
                    decision = "budget_during_jacobian"
                else:
                    build.attempt += 1
                    state.counters["fd_retry_requests"] += 1
                    if build.attempt >= len(build.attempt_points):
                        state.counters["fd_retry_exhaustions"] += 1
                        _finish(state, "jacobian_fd_retry_exhausted")
                        decision = "fd_retry_exhausted"
                    else:
                        decision = "fd_retry"
                return _event(state, _replace_decision(record, decision))
            if build.attempt > 0:
                state.counters["fd_retry_successes"] += 1
            build.matrix[build.unsupported, build.column] = (
                trial.augmented[build.unsupported]
                - current.augmented[build.unsupported]
            ) / delta
            decision = f"fd_column:{build.column}:attempt:{build.attempt}"
            build.column += 1
            build.attempt = 0
            build.attempt_points = ()
            _prepare_fd_attempts(state)
            return _event(state, _replace_decision(record, decision))

        if state.phase == "linear_step":
            _prepare_trial(state)
            continue

        if state.phase == "trial_evaluation":
            if state.pending_trial_x is None:
                _finish(state, "missing_trial_point")
                continue
            if state.charged_callbacks >= state.max_callbacks:
                state.counters["budget_stops"] += 1
                _finish(state, "budget")
                continue
            trial, record = _observe(state, state.pending_trial_x, "trial")
            if trial is None:
                base = state.configuration.base_configuration
                if record.exception_type == "BudgetExceeded":
                    state.counters["budget_stops"] += 1
                    _finish(state, "budget")
                    decision = "budget"
                else:
                    state.counters["rejected_steps"] += 1
                    state.consecutive_rejections += 1
                    _request_refresh(state, "semantic_invalid")
                    state.damping = min(
                        float(base.maximum_damping), state.damping * 8.0
                    )
                    state.trust_radius = max(
                        float(base.minimum_trust_radius), state.trust_radius * 0.35
                    )
                    state.pending_step = None
                    state.pending_delta_z = None
                    state.pending_trial_x = None
                    state.pending_step_norm = None
                    state.phase = "iteration"
                    decision = "trial_exception_rejected"
                return _event(state, _replace_decision(record, decision))
            state.counters["trial_state_evaluations"] += 1
            decision = _post_trial(state, trial)
            return _event(state, _replace_decision(record, decision))

        _finish(state, f"invalid_phase:{state.phase}")

    return _terminal_event(state)


def run_to_completion(state: CheckpointState) -> CandidateOutcome:
    while not state.terminal:
        advance_one(state)
    return state.result()


def solve_local(
    case: object,
    program: object,
    configuration: Configuration,
    start: Sequence[float],
    *,
    source_binding_token: bytes,
    per_start_scale: Sequence[float],
    source_lower: Sequence[float],
    source_upper: Sequence[float],
    max_callbacks: int,
    deadline_monotonic: float,
) -> CandidateOutcome:
    return run_to_completion(
        create_checkpoint(
            case,
            program,
            configuration,
            start,
            source_binding_token=source_binding_token,
            per_start_scale=per_start_scale,
            source_lower=source_lower,
            source_upper=source_upper,
            max_callbacks=max_callbacks,
            deadline_monotonic=deadline_monotonic,
        )
    )


def trajectory_digest(outcome: CandidateOutcome) -> str:
    """Bit-sensitive digest used only by parity fixtures."""

    digest = hashlib.sha256()
    digest.update(outcome.status.encode("utf-8"))
    digest.update(np.asarray(outcome.endpoint, dtype=float).tobytes(order="C"))
    for record in outcome.callback_ledger:
        digest.update(struct.pack("!q", int(record.ordinal)))
        for value in (record.kind, record.exception_type or "", record.decision):
            encoded = value.encode("utf-8")
            digest.update(struct.pack("!I", len(encoded)))
            digest.update(encoded)
        digest.update(bytes((int(record.succeeded), int(record.semantics_valid))))
        for values in (
            record.point,
            record.raw_relation,
            record.raw_violation,
            record.augmented,
        ):
            digest.update(struct.pack("!I", len(values)))
            digest.update(np.asarray(values, dtype=">f8").tobytes(order="C"))
    for name, value in sorted(outcome.counters.items()):
        if name in {"checkpoint_serializations", "checkpoint_restorations"}:
            continue
        digest.update(f"{name}={int(value)}\n".encode("ascii"))
    return digest.hexdigest()


def configuration_manifest(
    configuration: Configuration = REFERENCE,
) -> Mapping[str, object]:
    return {
        "candidate": configuration.name,
        "mature_kernel_sha256": MATURE_SHA256,
        "mechanism": "callback-exact resumable fork of event-refreshed direct-good-Broyden Ruiz TR/LM",
        "advance_contract": "at most one untouched source-evaluator callback per advance_one call",
        "checkpointed_state": [
            "partial hybrid Jacobian and FD retry cursor",
            "direct good-Broyden model and same-current raw-J cache",
            "trust radius and LM damping",
            "accept/reject and refresh counters/windows",
            "current/best endpoint and pending trial",
            "PCG64 RNG state",
            "charged callback work ledger",
            "opaque worker-owned source binding digest used only at resume",
        ],
        "fd_policy": "mature preferred one-sided sample; deterministic opposite/shrunk retries only after evaluator exception",
        "checkpoint_excludes": [
            "case identity",
            "source hash or filename",
            "worker-owned source binding token",
            "truth or target",
            "past offline outcome",
        ],
        "source_evaluator_reattached_on_resume": True,
        "source_problem_modified": False,
        "variables_or_equations_changed": False,
        "source_rewrite_or_reparameterization": False,
        "added_or_inferred_bounds": False,
        "case_family_truth_target_count_or_outcome_routing": False,
        "production_core_modified": False,
    }


__all__ = [
    "ADProgram",
    "AdvanceEvent",
    "CONFIGURATIONS",
    "CandidateOutcome",
    "CheckpointState",
    "Configuration",
    "REFERENCE",
    "REFERENCE_NAME",
    "advance_one",
    "compile_program",
    "configuration_manifest",
    "create_checkpoint",
    "run_to_completion",
    "solve_local",
    "trajectory_digest",
]
