"""Drop-in adaptive-HP composition for the champion_v0 endpoint bridge.

The frozen endpoint bridge accepts a composition artifact whose ``final_result``
is an existing 512/768/1024 target authority.  This module keeps that authority
field-for-field equivalent as JSON data on success and changes only which
already-reviewed backend is attempted next after a typed failure.

No case, family, truth, known target count, or target value is available to the
router.  The optional fresh 1280-bit refinement is an extra *refinement* lane;
the final authority remains the existing original-DSL 512/768/1024 replay and
owned target PSLQ contract.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import math
import signal
import struct
import threading
import time
from types import ModuleType
from typing import Callable, Iterator, Mapping, Sequence


COMPOSITION_SCHEMA = "geotarget.exp008-target-first-fallback-composition/v1"
BRIDGE_SCHEMA = "geotarget.exp-v15-243-001.adaptive-hp-champion-bridge/v1"
EXTRA_1280_ENV = "GEOTARGET_ADAPTIVE_HP_ENABLE_FRESH_1280"
FINALIZATION_RESERVE_SECONDS = 0.35

_REQUIRED_SCOPE_TRUE = (
    "numerical_configuration_512_768",
    "target_512_768_1024",
    "original_dsl_hp_replay",
    "target_only_owned_pslq",
    "minimal_polynomial_and_isolator",
)
_REQUIRED_SCOPE_FALSE = (
    "all_coordinate_exactification_required",
    "exact_configuration_witness_required",
    "target_image_completeness_required",
)
_FORBIDDEN_INPUT_KEYS = ("truth", "known_target_count", "case_id", "family")


class SoftDeadlineExceeded(TimeoutError):
    """Raised inside the HP worker before its public soft deadline."""


@dataclass(frozen=True)
class BridgeConfig:
    """Only scientifically relevant switch exposed by this adapter."""

    enable_fresh_1280: bool = True

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str]
    ) -> "BridgeConfig":
        raw = environment.get(EXTRA_1280_ENV, "1")
        if raw not in {"0", "1"}:
            raise ValueError(f"{EXTRA_1280_ENV} must be 0 or 1")
        return cls(enable_fresh_1280=raw == "1")


def endpoint_float64_sha256(endpoint: Sequence[float]) -> str:
    payload = struct.pack(">I", len(endpoint)) + b"".join(
        struct.pack(">d", float(value)) for value in endpoint
    )
    return hashlib.sha256(payload).hexdigest()


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _all_false(mapping: Mapping[str, object], names: Sequence[str]) -> bool:
    return all(mapping.get(name) is False for name in names)


def _successful_authority_contract(
    adapter: ModuleType | object,
    result: Mapping[str, object],
    *,
    source_sha256: str,
    endpoint_sha256: str,
) -> bool:
    """Apply the unchanged champion/frozen-bridge exact authority contract."""

    input_contract = _mapping(result.get("input_contract"))
    transformations = _mapping(result.get("problem_transformations"))
    scope = _mapping(result.get("authority_scope"))
    target = _mapping(result.get("target_authority"))
    return bool(
        result.get("authority_pass") is True
        and result.get("source_raw_sha256") == source_sha256
        and result.get("endpoint_float64_sha256") == endpoint_sha256
        and input_contract.get("source_bytes_and_digest") is True
        and input_contract.get("bare_float64_endpoint") is True
        and _all_false(input_contract, _FORBIDDEN_INPUT_KEYS)
        and transformations
        and all(value is False for value in transformations.values())
        and all(scope.get(name) is True for name in _REQUIRED_SCOPE_TRUE)
        and all(scope.get(name) is False for name in _REQUIRED_SCOPE_FALSE)
        and target.get("target_relation_confirmed") is True
        and adapter.exact_descriptor_key(result) is not None
    )


def _failure_authority(
    *,
    source_sha256: str,
    endpoint_sha256: str,
    reason: str,
) -> dict[str, object]:
    """Return a bridge-acceptable artifact that cannot yield a descriptor."""

    return {
        "schema_version": (
            "geotarget.exp-v15-243-001.adaptive-hp-fail-closed-authority/v1"
        ),
        "status": "ADAPTIVE_HP_FAIL_CLOSED",
        "authority_pass": False,
        "failure_reasons": [reason],
        "source_raw_sha256": source_sha256,
        "endpoint_float64_sha256": endpoint_sha256,
        "input_contract": {
            "source_bytes_and_digest": True,
            "bare_float64_endpoint": True,
            "truth": False,
            "known_target_count": False,
            "case_id": False,
            "family": False,
        },
        "problem_transformations": {
            "source_mutated": False,
            "bounds_added": False,
            "coordinate_fixing_or_gauge": False,
            "symmetry_reduction": False,
            "constraint_or_answer_changed": False,
        },
        # These are the required success authorities, not a claim that this
        # failed attempt established an exact target.
        "authority_scope": {
            "numerical_configuration_512_768": True,
            "target_512_768_1024": True,
            "original_dsl_hp_replay": True,
            "target_only_owned_pslq": True,
            "minimal_polynomial_and_isolator": True,
            "all_coordinate_exactification_required": False,
            "exact_configuration_witness_required": False,
            "target_image_completeness_required": False,
        },
    }


@contextmanager
def _posix_soft_alarm(seconds: float) -> Iterator[None]:
    """Interrupt Python HP work and leave wall time for atomic finalization."""

    if seconds <= 0.0 or not math.isfinite(seconds):
        raise SoftDeadlineExceeded("nonpositive soft work budget")
    if threading.current_thread() is not threading.main_thread():
        raise SoftDeadlineExceeded("soft alarm requires the main thread")
    if not hasattr(signal, "setitimer"):
        raise SoftDeadlineExceeded("POSIX interval timer is unavailable")

    def expire(_signum, _frame):
        raise SoftDeadlineExceeded("adaptive HP soft deadline exceeded")

    previous_handler = signal.getsignal(signal.SIGALRM)
    started = time.monotonic()
    signal.signal(signal.SIGALRM, expire)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, previous_handler)
        previous_delay, previous_interval = previous_timer
        if previous_delay > 0.0:
            elapsed = time.monotonic() - started
            signal.setitimer(
                signal.ITIMER_REAL,
                max(1.0e-6, previous_delay - elapsed),
                previous_interval,
            )


def configure_backends(
    adapter: ModuleType | object,
    base: object,
    *,
    enable_fresh_1280: bool,
):
    """Expose the extra lane as a one-bit, case-blind ablation seam."""

    return adapter.BackendBundle(
        thin_primary=base.thin_primary,
        event_broyden=base.event_broyden,
        target_stability=base.target_stability,
        fresh_1280=base.fresh_1280 if enable_fresh_1280 else None,
    )


def _budget_policy(
    adapter: ModuleType | object, *, primary_cap_seconds: float
):
    default = adapter.BudgetPolicy()
    maximum = dict(default.maximum_attempt_seconds)
    maximum[adapter.AttemptKind.THIN_PRIMARY] = min(
        maximum[adapter.AttemptKind.THIN_PRIMARY],
        primary_cap_seconds,
    )
    return adapter.BudgetPolicy(
        minimum_attempt_seconds=default.minimum_attempt_seconds,
        reserve_after_primary_seconds=default.reserve_after_primary_seconds,
        maximum_attempt_seconds=maximum,
    )


def _attempt_rows(
    portfolio: Mapping[str, object],
    *,
    source_sha256: str,
    endpoint_sha256: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    attempts = portfolio.get("attempts")
    if not isinstance(attempts, list):
        return rows
    for attempt in attempts:
        if not isinstance(attempt, Mapping):
            continue
        rows.append(
            {
                "name": attempt.get("attempt_kind"),
                "attempted": True,
                "authority_pass": attempt.get("authority_pass") is True,
                "status": attempt.get("status"),
                "failure_class": attempt.get("failure_class"),
                "source_raw_sha256": source_sha256,
                "endpoint_float64_sha256": endpoint_sha256,
                "elapsed_seconds": attempt.get("charged_seconds"),
                "soft_cap_seconds": attempt.get("soft_cap_seconds"),
            }
        )
    return rows


def _portfolio_summary(
    portfolio: Mapping[str, object] | None
) -> dict[str, object]:
    if portfolio is None:
        return {
            "status": "NOT_COMPLETED",
            "authority_count": 0,
            "attempts": [],
            "budget": None,
        }
    return {
        "schema_version": portfolio.get("schema_version"),
        "status": portfolio.get("status"),
        "authority_count": portfolio.get("authority_count"),
        "attempts": portfolio.get("attempts"),
        "deferred_candidates": portfolio.get("deferred_candidates"),
        "budget": portfolio.get("budget"),
        "safety_contract": portfolio.get("safety_contract"),
    }


def _compose(
    adapter: ModuleType | object,
    *,
    portfolio: Mapping[str, object] | None,
    source_sha256: str,
    endpoint_sha256: str,
    elapsed_seconds: float,
    deadline_seconds: float,
    primary_cap_seconds: float,
    enable_fresh_1280: bool,
    failure_reason: str | None,
) -> dict[str, object]:
    accepted_result: Mapping[str, object] | None = None
    winner: str | None = None
    if portfolio is not None:
        accepted = portfolio.get("accepted_authorities")
        if isinstance(accepted, list) and len(accepted) == 1:
            row = accepted[0]
            if isinstance(row, Mapping):
                candidate_result = row.get("result")
                if isinstance(candidate_result, Mapping):
                    accepted_result = candidate_result
                    winner_value = row.get("attempt_kind")
                    winner = (
                        winner_value if isinstance(winner_value, str) else None
                    )

    authority_pass = bool(
        accepted_result is not None
        and _successful_authority_contract(
            adapter,
            accepted_result,
            source_sha256=source_sha256,
            endpoint_sha256=endpoint_sha256,
        )
    )
    if authority_pass:
        # Copy the mapping only; do not add, remove, or modify authority fields.
        final_result = dict(accepted_result)
        status = final_result.get("status")
        reason = None
    else:
        reason = failure_reason or (
            "AUTHORITY_CONTRACT_REJECTED"
            if accepted_result is not None
            else "NO_EXACT_AUTHORITY"
        )
        final_result = _failure_authority(
            source_sha256=source_sha256,
            endpoint_sha256=endpoint_sha256,
            reason=reason,
        )
        status = "ADAPTIVE_HP_FAIL_CLOSED"
        winner = None

    attempts = _attempt_rows(
        portfolio or {},
        source_sha256=source_sha256,
        endpoint_sha256=endpoint_sha256,
    )
    fallback_attempted = any(
        row.get("name") != "THIN_512_768_REPLAY_1024" for row in attempts
    )
    return {
        "schema_version": COMPOSITION_SCHEMA,
        "status": status,
        "authority_pass": authority_pass,
        "winner": winner,
        "final_result": final_result,
        "attempts": attempts,
        "fallback_decision": {
            "primary_authority_failed": bool(
                attempts and attempts[0].get("authority_pass") is not True
            ),
            "remaining_budget_sufficient": fallback_attempted,
            "fallback_eligible": fallback_attempted,
            "fallback_enabled": True,
            "case_identity_read": False,
            "family_read": False,
            "truth_read": False,
            "known_target_count_read": False,
            "failure_status_subtype_read": True,
        },
        "input_contract": {
            "same_source_bytes_both_attempts": True,
            "same_float64_endpoint_both_attempts": True,
            "source_or_problem_modified": False,
            "bounds_added": False,
            "gauge_or_symmetry_reduction": False,
        },
        "deadline_seconds": float(deadline_seconds),
        "primary_cap_seconds": float(primary_cap_seconds),
        "elapsed_seconds": elapsed_seconds,
        "adaptive_hp_bridge": {
            "schema_version": BRIDGE_SCHEMA,
            "failure_reason": reason,
            "failure_typed_routing": True,
            "fresh_1280_refinement_enabled": enable_fresh_1280,
            "fresh_1280_is_not_final_authority": True,
            "final_authority_replay_bits": [512, 768, 1024],
            "successful_final_result_modified": False,
            "soft_deadline_fail_closed": True,
            "ablation_seam": {
                "environment": EXTRA_1280_ENV,
                "enabled_value": "1",
                "disabled_value": "0",
                "separate_no_1280_bridge": "champion_bridge_no_1280.py",
            },
            "case_family_truth_or_known_target_count_routing": False,
            "portfolio": _portfolio_summary(portfolio),
        },
    }


def fail_closed_composition(
    adapter: ModuleType | object,
    *,
    source_sha256: str,
    endpoint: Sequence[float],
    elapsed_seconds: float,
    deadline_seconds: float,
    primary_cap_seconds: float,
    config: BridgeConfig,
    reason: str,
) -> dict[str, object]:
    """Public construction used when the CLI prelude itself times out."""

    return _compose(
        adapter,
        portfolio=None,
        source_sha256=source_sha256,
        endpoint_sha256=endpoint_float64_sha256(endpoint),
        elapsed_seconds=elapsed_seconds,
        deadline_seconds=deadline_seconds,
        primary_cap_seconds=primary_cap_seconds,
        enable_fresh_1280=config.enable_fresh_1280,
        failure_reason=reason,
    )


def run_champion_adapter(
    adapter: ModuleType | object,
    source_payload: bytes,
    source_sha256: str,
    endpoint: Sequence[float],
    *,
    deadline_seconds: float,
    primary_cap_seconds: float,
    config: BridgeConfig,
    base_backends: object | None = None,
    portfolio_runner: Callable[..., Mapping[str, object]] | None = None,
    clock: Callable[[], float] = time.monotonic,
    enforce_posix_alarm: bool = True,
) -> dict[str, object]:
    """Run one immutable endpoint and always return a fail-closed composition."""

    started = clock()
    endpoint = tuple(float(value) for value in endpoint)
    endpoint_sha256 = endpoint_float64_sha256(endpoint)
    portfolio: Mapping[str, object] | None = None
    failure_reason: str | None = None

    try:
        if hashlib.sha256(source_payload).hexdigest() != source_sha256:
            raise ValueError("source payload digest mismatch")
        if not endpoint or not all(math.isfinite(value) for value in endpoint):
            raise ValueError("endpoint must be finite and nonempty")
        if (
            not math.isfinite(deadline_seconds)
            or not math.isfinite(primary_cap_seconds)
            or deadline_seconds <= 0.0
            or primary_cap_seconds <= 0.0
            or primary_cap_seconds > deadline_seconds
        ):
            raise ValueError("invalid HP deadline")

        reserve = min(
            FINALIZATION_RESERVE_SECONDS,
            max(0.02, 0.1 * deadline_seconds),
        )
        work_budget = deadline_seconds - reserve
        if work_budget <= 0.0:
            raise SoftDeadlineExceeded("no work budget before finalization")

        base = base_backends or adapter.load_reused_backends()
        configured = configure_backends(
            adapter,
            base,
            enable_fresh_1280=config.enable_fresh_1280,
        )
        runner = portfolio_runner or adapter.run_adaptive_hp_portfolio
        candidate = adapter.EndpointCandidate(
            endpoint,
            residual_inf=0.0,
            uncertainty_bucket=f"endpoint:{endpoint_sha256}",
        )

        def invoke() -> Mapping[str, object]:
            return runner(
                source_payload,
                source_sha256,
                [candidate],
                total_budget_seconds=work_budget,
                backends=configured,
                budget_policy=_budget_policy(
                    adapter,
                    primary_cap_seconds=min(primary_cap_seconds, work_budget),
                ),
            )

        if enforce_posix_alarm:
            with _posix_soft_alarm(work_budget):
                portfolio = dict(invoke())
        else:
            portfolio = dict(invoke())
        if clock() - started >= deadline_seconds:
            portfolio = None
            failure_reason = "SOFT_DEADLINE_EXCEEDED"
    except SoftDeadlineExceeded:
        portfolio = None
        failure_reason = "SOFT_DEADLINE_EXCEEDED"
    except Exception as error:
        portfolio = None
        failure_reason = f"ADAPTER_EXCEPTION_{type(error).__name__.upper()}"

    elapsed = max(0.0, clock() - started)
    return _compose(
        adapter,
        portfolio=portfolio,
        source_sha256=source_sha256,
        endpoint_sha256=endpoint_sha256,
        elapsed_seconds=elapsed,
        deadline_seconds=deadline_seconds,
        primary_cap_seconds=primary_cap_seconds,
        enable_fresh_1280=config.enable_fresh_1280,
        failure_reason=failure_reason,
    )


soft_deadline = _posix_soft_alarm


__all__ = [
    "BRIDGE_SCHEMA",
    "BridgeConfig",
    "COMPOSITION_SCHEMA",
    "EXTRA_1280_ENV",
    "SoftDeadlineExceeded",
    "configure_backends",
    "endpoint_float64_sha256",
    "fail_closed_composition",
    "run_champion_adapter",
    "soft_deadline",
]
