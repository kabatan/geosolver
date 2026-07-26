"""Failure-typed adaptive high-precision endpoint portfolio.

This module is deliberately independent of the common finalist worker.  It
composes already-reviewed endpoint authorities through a small callable
interface:

* two-prefix/four-stage 512/768 refinement with 512/768/1024 replay;
* event-refreshed direct-Broyden on prefix/refinement failure;
* condition-aware target-stability refinement on relation failure;
* a fresh 1280-bit refinement, restarted from the immutable Float64 endpoint,
  only when lower-precision evidence remains insufficient.

The adapter never changes source bytes, equations, variables, bounds, gauge,
or target expressions.  Every successful result must still carry the original
target-only exact authority (minimal polynomial plus isolated real root).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct
import sys
import time
from types import ModuleType
from typing import Callable, Iterable, Mapping, Protocol, Sequence


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]

THIN_RUNNER_PATH = (
    ROOT
    / "research/experiments/EXP-REAL61-008"
    / "hp_precision_schedule_v11/run_candidate_one.py"
)
BROYDEN_RUNNER_PATH = (
    ROOT
    / "research/experiments/EXP-REAL61-008"
    / "hp_combined_broyden_publicgate_v17/run_candidate_one.py"
)
TARGET_STABLE_PATH = (
    ROOT
    / "research/experiments/EXP-REAL61-006"
    / "adaptive_hp_escalation/target_stable_candidate.py"
)
ADAPTIVE_PATH = (
    ROOT
    / "research/experiments/EXP-REAL61-006"
    / "adaptive_hp_escalation/candidate.py"
)
AUTHORITY_ADAPTER_PATH = (
    ROOT
    / "research/experiments/EXP-REAL61-008"
    / "dev41_target_hp_adapter/adapter.py"
)

SCHEMA_VERSION = "geotarget.exp-v15-243-001.adaptive-hp-portfolio/v1"
FRESH_1280_LANE = (1280, 386, (70, 110, 180, 252, 340, 420))


class AttemptKind(str, Enum):
    THIN_PRIMARY = "THIN_512_768_REPLAY_1024"
    EVENT_BROYDEN = "EVENT_BROYDEN_512_768_REPLAY_1024"
    TARGET_STABILITY = "TARGET_STABILITY_512_768_REPLAY_1024"
    FRESH_1280 = "FRESH_1280_FROM_IMMUTABLE_ENDPOINT"


class FailureClass(str, Enum):
    READY = "READY"
    PREFIX_STAGNATION = "PREFIX_STAGNATION"
    PRECISION_LANE_FAILURE = "PRECISION_LANE_FAILURE"
    LANE_DISAGREEMENT = "LANE_DISAGREEMENT"
    TARGET_STABILITY = "TARGET_STABILITY"
    TARGET_RELATION = "TARGET_RELATION"
    SEMANTIC_REJECTION = "SEMANTIC_REJECTION"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    MALFORMED_AUTHORITY = "MALFORMED_AUTHORITY"
    UNKNOWN = "UNKNOWN"


ATTEMPT_PRECISION_CONTRACT = {
    AttemptKind.THIN_PRIMARY: {
        "independent_refinement_bits": [512, 768],
        "original_dsl_replay_bits": [512, 768, 1024],
        "immutable_float64_seed": True,
    },
    AttemptKind.EVENT_BROYDEN: {
        "independent_refinement_bits": [512, 768],
        "original_dsl_replay_bits": [512, 768, 1024],
        "immutable_float64_seed": True,
    },
    AttemptKind.TARGET_STABILITY: {
        "independent_refinement_bits": [512, 768],
        "original_dsl_replay_bits": [512, 768, 1024],
        "immutable_float64_seed": True,
    },
    AttemptKind.FRESH_1280: {
        "independent_refinement_bits": [512, 768, 1280],
        "original_dsl_replay_bits": [512, 768, 1024],
        "third_replay_anchor_refined_at_bits": 1280,
        "immutable_float64_seed": True,
    },
}


@dataclass(frozen=True)
class EndpointCandidate:
    endpoint: tuple[float, ...]
    residual_inf: float
    provisional_target: float | None = None
    uncertainty_bucket: str | None = None
    discovery_ordinal: int = 0

    def __post_init__(self) -> None:
        if not self.endpoint or not all(math.isfinite(value) for value in self.endpoint):
            raise ValueError("endpoint must be finite and nonempty")
        if not math.isfinite(self.residual_inf) or self.residual_inf < 0:
            raise ValueError("residual_inf must be finite and nonnegative")
        if self.provisional_target is not None and not math.isfinite(
            self.provisional_target
        ):
            raise ValueError("provisional_target must be finite")
        if self.discovery_ordinal < 0:
            raise ValueError("discovery_ordinal must be nonnegative")

    @property
    def endpoint_sha256(self) -> str:
        payload = struct.pack(">I", len(self.endpoint)) + b"".join(
            struct.pack(">d", float(value)) for value in self.endpoint
        )
        return hashlib.sha256(payload).hexdigest()

    @property
    def bucket_key(self) -> str:
        return self.uncertainty_bucket or f"endpoint:{self.endpoint_sha256}"


class AttemptRunner(Protocol):
    def __call__(
        self,
        source_payload: bytes,
        source_sha256: str,
        endpoint: Sequence[float],
        *,
        deadline_seconds: float,
    ) -> Mapping[str, object]: ...


@dataclass(frozen=True)
class BackendBundle:
    thin_primary: AttemptRunner | None = None
    event_broyden: AttemptRunner | None = None
    target_stability: AttemptRunner | None = None
    fresh_1280: AttemptRunner | None = None

    def get(self, kind: AttemptKind) -> AttemptRunner | None:
        return {
            AttemptKind.THIN_PRIMARY: self.thin_primary,
            AttemptKind.EVENT_BROYDEN: self.event_broyden,
            AttemptKind.TARGET_STABILITY: self.target_stability,
            AttemptKind.FRESH_1280: self.fresh_1280,
        }[kind]


@dataclass(frozen=True)
class BudgetPolicy:
    minimum_attempt_seconds: float = 0.25
    reserve_after_primary_seconds: float = 3.0
    maximum_attempt_seconds: Mapping[AttemptKind, float] = field(
        default_factory=lambda: {
            AttemptKind.THIN_PRIMARY: 18.0,
            AttemptKind.EVENT_BROYDEN: 18.0,
            AttemptKind.TARGET_STABILITY: 22.0,
            AttemptKind.FRESH_1280: 15.0,
        }
    )

    def __post_init__(self) -> None:
        if self.minimum_attempt_seconds <= 0:
            raise ValueError("minimum_attempt_seconds must be positive")
        if self.reserve_after_primary_seconds < 0:
            raise ValueError("reserve_after_primary_seconds must be nonnegative")
        if set(self.maximum_attempt_seconds) != set(AttemptKind):
            raise ValueError("maximum_attempt_seconds must cover every attempt kind")
        if any(value <= 0 for value in self.maximum_attempt_seconds.values()):
            raise ValueError("all maximum attempt budgets must be positive")


def _load_module(name: str, path: Path) -> ModuleType:
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _run_target_stability_authority(
    source_payload: bytes,
    source_sha256: str,
    endpoint: Sequence[float],
    *,
    deadline_seconds: float,
) -> Mapping[str, object]:
    adapter = _load_module(
        "geotarget_exp_v15_243_adaptive_hp_authority_adapter",
        AUTHORITY_ADAPTER_PATH,
    )
    candidate = _load_module(
        "geotarget_exp_v15_243_adaptive_hp_target_stable",
        TARGET_STABLE_PATH,
    )

    class CandidateWrapper:
        @staticmethod
        def refine_endpoint(evaluator, values, *, variant, deadline_seconds):
            del variant
            return candidate.refine_endpoint(
                evaluator,
                values,
                variant=candidate.TARGET_STABLE,
                deadline_seconds=deadline_seconds,
            )

    runtime = replace(adapter._load_runtime(), candidate=CandidateWrapper)
    result = adapter._build_with_runtime(
        source_payload,
        source_sha256,
        endpoint,
        deadline_seconds=deadline_seconds,
        runtime=runtime,
    )
    result["adaptive_hp_target_stability_backend"] = {
        "implementation": str(TARGET_STABLE_PATH.relative_to(ROOT)),
        "failure_typed_activation": True,
        "source_or_problem_modified": False,
    }
    return result


def _fresh_1280_refinement(
    adaptive: ModuleType | object,
    evaluator: object,
    endpoint: Sequence[float],
    *,
    deadline_seconds: float,
) -> Mapping[str, object]:
    """Run three independent lanes, replacing the third with fresh 1280 bits."""

    original_lanes = adaptive.BASE.LANES
    adaptive.BASE.LANES = (original_lanes[0], original_lanes[1], FRESH_1280_LANE)
    try:
        result = adaptive.refine_endpoint(
            evaluator,
            endpoint,
            variant=adaptive.ADAPTIVE_ESCALATION,
            deadline_seconds=deadline_seconds,
        )
    finally:
        adaptive.BASE.LANES = original_lanes
    output = dict(result)
    output["fresh_1280_refinement"] = {
        "activated": True,
        "restart": "IMMUTABLE_FLOAT64_ENDPOINT",
        "independent_lane_bits": [512, 768, 1280],
        "third_lane_schedule_dps": list(FRESH_1280_LANE[2]),
        "third_lane_used_as_fresh_1024_replay_anchor": True,
        "source_or_problem_modified": False,
    }
    return output


def _run_fresh_1280_authority(
    source_payload: bytes,
    source_sha256: str,
    endpoint: Sequence[float],
    *,
    deadline_seconds: float,
) -> Mapping[str, object]:
    adapter = _load_module(
        "geotarget_exp_v15_243_adaptive_hp_authority_adapter",
        AUTHORITY_ADAPTER_PATH,
    )
    adaptive = _load_module(
        "geotarget_exp_v15_243_adaptive_hp_ratio_escalation",
        ADAPTIVE_PATH,
    )

    class CandidateWrapper:
        @staticmethod
        def refine_endpoint(evaluator, values, *, variant, deadline_seconds):
            del variant
            return _fresh_1280_refinement(
                adaptive,
                evaluator,
                values,
                deadline_seconds=deadline_seconds,
            )

    runtime = replace(adapter._load_runtime(), candidate=CandidateWrapper)
    result = adapter._build_with_runtime(
        source_payload,
        source_sha256,
        endpoint,
        deadline_seconds=deadline_seconds,
        runtime=runtime,
    )
    result["adaptive_hp_fresh_1280_backend"] = {
        "implementation": str(ADAPTIVE_PATH.relative_to(ROOT)),
        "independent_refinement_bits": [512, 768, 1280],
        "original_dsl_replay_bits": [512, 768, 1024],
        "restart": "IMMUTABLE_FLOAT64_ENDPOINT",
        "source_or_problem_modified": False,
    }
    return result


def load_reused_backends() -> BackendBundle:
    """Return lazy wrappers around reviewed experimental implementations."""

    def thin(
        source_payload: bytes,
        source_sha256: str,
        endpoint: Sequence[float],
        *,
        deadline_seconds: float,
    ) -> Mapping[str, object]:
        runner = _load_module(
            "geotarget_exp_v15_243_adaptive_hp_thin_runner", THIN_RUNNER_PATH
        )
        return runner.build_candidate_authority(
            source_payload,
            source_sha256,
            list(endpoint),
            strict_stage_count=4,
            deadline_seconds=deadline_seconds,
        )

    def broyden(
        source_payload: bytes,
        source_sha256: str,
        endpoint: Sequence[float],
        *,
        deadline_seconds: float,
    ) -> Mapping[str, object]:
        runner = _load_module(
            "geotarget_exp_v15_243_adaptive_hp_broyden_runner",
            BROYDEN_RUNNER_PATH,
        )
        return runner.build_combined_authority(
            source_payload,
            source_sha256,
            list(endpoint),
            deadline_seconds=deadline_seconds,
        )

    return BackendBundle(
        thin_primary=thin,
        event_broyden=broyden,
        target_stability=_run_target_stability_authority,
        fresh_1280=_run_fresh_1280_authority,
    )


def backend_manifest() -> dict[str, object]:
    return {
        "schema_version": "geotarget.exp-v15-243-001.adaptive-hp-backends/v1",
        "thin_primary": str(THIN_RUNNER_PATH.relative_to(ROOT)),
        "event_broyden": str(BROYDEN_RUNNER_PATH.relative_to(ROOT)),
        "target_stability": str(TARGET_STABLE_PATH.relative_to(ROOT)),
        "fresh_1280_base": str(ADAPTIVE_PATH.relative_to(ROOT)),
        "common_worker_modified": False,
        "forbidden_components": [
            "deflation",
            "row_space_lm",
            "p19_threshold_retuning",
        ],
    }


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _final_authority(result: Mapping[str, object]) -> Mapping[str, object]:
    direct = _mapping(result.get("target_authority"))
    if direct:
        return direct
    final = _mapping(result.get("final_result"))
    return _mapping(final.get("target_authority"))


def exact_descriptor_key(result: Mapping[str, object]) -> str | None:
    authority = _final_authority(result)
    polynomial = authority.get("minimal_polynomial_high_to_low")
    isolator = _mapping(authority.get("isolating_interval"))
    root_index = authority.get("selected_real_root_index")
    if root_index is None:
        root_index = isolator.get("real_root_index")
    if (
        not isinstance(polynomial, list)
        or not polynomial
        or not isinstance(root_index, int)
        or isinstance(root_index, bool)
    ):
        return None
    payload = json.dumps(
        {
            "minimal_polynomial_high_to_low": polynomial,
            "real_root_index": root_index,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _collect_status_tokens(value: object, output: list[str], depth: int = 0) -> None:
    if depth > 5:
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in {
                "status",
                "failure",
                "failure_class",
                "failure_reasons",
                "detail",
            }:
                _collect_status_tokens(child, output, depth + 1)
            elif key in {
                "candidate",
                "refinement",
                "adaptive_prefix",
                "original_numerical_replay",
                "target_authority",
                "final_result",
            }:
                _collect_status_tokens(child, output, depth + 1)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _collect_status_tokens(child, output, depth + 1)
    elif isinstance(value, str):
        output.append(value.upper())


def classify_failure(result: Mapping[str, object]) -> FailureClass:
    if result.get("authority_pass") is True:
        return (
            FailureClass.READY
            if exact_descriptor_key(result) is not None
            else FailureClass.MALFORMED_AUTHORITY
        )

    tokens: list[str] = []
    _collect_status_tokens(result, tokens)
    joined = " ".join(tokens)
    failures = {
        str(value).lower()
        for value in result.get("failure_reasons", [])
        if isinstance(value, str)
    }
    replay = _mapping(result.get("original_numerical_replay"))
    if not replay:
        replay = _mapping(
            _mapping(result.get("final_result")).get("original_numerical_replay")
        )
    numerical_replay_ready = replay.get("numeric_v3_ready") is True
    replay_lanes = replay.get("lanes")
    complete_replay_lane_set = bool(
        isinstance(replay_lanes, list) and len(replay_lanes) == 3
    )

    if "DEADLINE" in joined or "TIMEOUT" in joined:
        return FailureClass.BUDGET_EXHAUSTED
    if any(
        marker in joined
        for marker in (
            "GUARD",
            "BRANCH",
            "SEMANTIC_REJECT",
            "INTRINSIC_DOMAIN",
            "NONFINITE",
        )
    ):
        return FailureClass.SEMANTIC_REJECTION
    if "INDEPENDENT_LANE_DISAGREEMENT" in joined or (
        complete_replay_lane_set
        and any("disagreement" in value for value in failures)
    ):
        return FailureClass.LANE_DISAGREEMENT
    if any(
        marker in joined
        for marker in (
            "LANE_COUNT_FAILED",
            "HIGH_PRECISION_REFINEMENT_FAILED",
            "PRECISION_DOWNGRADE",
            "INSUFFICIENT_PRECISION",
        )
    ) or "precision_lane_set" in failures:
        return FailureClass.PRECISION_LANE_FAILURE
    if any(
        marker in joined
        for marker in (
            "PREFIX_FAILED",
            "NO_SEMISMOOTH_DESCENT",
            "NO_ACCEPTED_DESCENT",
            "ITERATION_LIMIT",
            "PUBLIC_PREFIX_FAILED",
        )
    ):
        return FailureClass.PREFIX_STAGNATION
    if any(
        marker in joined
        for marker in (
            "TARGET_RELATION",
            "TARGET_PSLQ",
            "NO_RELATION",
            "EXACT_FACTOR_UNVERIFIED",
            "COEFFICIENT_LIMIT",
        )
    ) and numerical_replay_ready:
        return FailureClass.TARGET_RELATION
    if "target_relation_authority" in failures and numerical_replay_ready:
        return FailureClass.TARGET_RELATION
    if "TARGET_STABILITY" in joined:
        return FailureClass.TARGET_STABILITY
    if any(
        marker in joined
        for marker in (
            "TARGET_RELATION",
            "TARGET_PSLQ",
            "NO_RELATION",
            "EXACT_FACTOR_UNVERIFIED",
            "COEFFICIENT_LIMIT",
        )
    ):
        return FailureClass.TARGET_RELATION
    return FailureClass.UNKNOWN


def _route_candidates(failure: FailureClass) -> tuple[AttemptKind, ...]:
    if failure in {
        FailureClass.PREFIX_STAGNATION,
        FailureClass.PRECISION_LANE_FAILURE,
    }:
        return (AttemptKind.EVENT_BROYDEN, AttemptKind.FRESH_1280)
    if failure in {
        FailureClass.TARGET_RELATION,
        FailureClass.TARGET_STABILITY,
    }:
        return (AttemptKind.TARGET_STABILITY, AttemptKind.FRESH_1280)
    if failure is FailureClass.LANE_DISAGREEMENT:
        return (AttemptKind.FRESH_1280,)
    return ()


def _next_attempt(
    failure: FailureClass,
    used: set[AttemptKind],
    backends: BackendBundle,
) -> AttemptKind | None:
    for kind in _route_candidates(failure):
        if kind not in used and backends.get(kind) is not None:
            return kind
    return None


def _attempt_cap(
    kind: AttemptKind,
    remaining: float,
    policy: BudgetPolicy,
    *,
    fallback_available: bool,
) -> float:
    cap = min(float(policy.maximum_attempt_seconds[kind]), remaining)
    if (
        kind is AttemptKind.THIN_PRIMARY
        and fallback_available
        and remaining > policy.reserve_after_primary_seconds
    ):
        cap = min(cap, remaining - policy.reserve_after_primary_seconds)
    return max(0.0, cap)


def _charged_seconds(result: Mapping[str, object], observed: float) -> float:
    reported = result.get("elapsed_seconds")
    if isinstance(reported, (int, float)) and not isinstance(reported, bool):
        if math.isfinite(float(reported)) and float(reported) >= 0:
            return max(observed, float(reported))
    return observed


def _candidate_waves(
    candidates: Sequence[EndpointCandidate],
) -> tuple[list[EndpointCandidate], list[dict[str, object]]]:
    """Keep every reservoir discovery reachable until exact authority exists.

    Bitwise-identical endpoints and shared soft buckets are deliberately not
    collapsed here.  They can represent distinct reservoir discoveries with
    different ancestry or retry state.  Duplicate accounting is permitted
    only after an exact minimal-polynomial/root descriptor has been produced.
    """

    ordered = sorted(
        candidates,
        key=lambda row: (
            row.discovery_ordinal,
            row.endpoint_sha256,
            row.residual_inf,
        ),
    )
    return ordered, []


def run_adaptive_hp_portfolio(
    source_payload: bytes,
    source_sha256: str,
    candidates: Sequence[EndpointCandidate],
    *,
    total_budget_seconds: float = 31.0,
    backends: BackendBundle | None = None,
    budget_policy: BudgetPolicy | None = None,
    known_descriptor_keys: Iterable[str] = (),
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, object]:
    """Race failure-appropriate HP backends inside one explicit soft budget."""

    if hashlib.sha256(source_payload).hexdigest() != source_sha256:
        raise ValueError("source payload digest mismatch")
    if not math.isfinite(total_budget_seconds) or total_budget_seconds <= 0:
        raise ValueError("total_budget_seconds must be finite and positive")
    if not candidates:
        raise ValueError("at least one endpoint candidate is required")

    backends = backends or load_reused_backends()
    policy = budget_policy or BudgetPolicy()
    descriptor_keys = set(known_descriptor_keys)
    schedule, _preauthority_suppressed = _candidate_waves(candidates)
    remaining = float(total_budget_seconds)
    attempts: list[dict[str, object]] = []
    accepted: list[dict[str, object]] = []
    duplicate_authorities: list[dict[str, object]] = []
    deferred: list[dict[str, object]] = []

    for candidate in schedule:
        if remaining < policy.minimum_attempt_seconds:
            deferred.append(
                {
                    "endpoint_sha256": candidate.endpoint_sha256,
                    "uncertainty_bucket": candidate.bucket_key,
                    "discovery_ordinal": candidate.discovery_ordinal,
                    "reason": "PORTFOLIO_BUDGET_EXHAUSTED",
                    "retained_for_aging": True,
                }
            )
            continue

        kind = AttemptKind.THIN_PRIMARY
        used: set[AttemptKind] = set()
        while kind is not None:
            runner = backends.get(kind)
            if runner is None:
                break
            fallback_available = any(
                backends.get(row) is not None and row not in used
                for row in (
                    AttemptKind.EVENT_BROYDEN,
                    AttemptKind.TARGET_STABILITY,
                    AttemptKind.FRESH_1280,
                )
            )
            cap = _attempt_cap(
                kind,
                remaining,
                policy,
                fallback_available=fallback_available,
            )
            if cap < policy.minimum_attempt_seconds:
                deferred.append(
                    {
                        "endpoint_sha256": candidate.endpoint_sha256,
                        "uncertainty_bucket": candidate.bucket_key,
                        "discovery_ordinal": candidate.discovery_ordinal,
                        "reason": "INSUFFICIENT_REMAINING_ATTEMPT_BUDGET",
                        "next_attempt": kind.value,
                        "retained_for_aging": True,
                    }
                )
                break

            used.add(kind)
            started = clock()
            result = dict(
                runner(
                    source_payload,
                    source_sha256,
                    candidate.endpoint,
                    deadline_seconds=cap,
                )
            )
            observed = max(0.0, clock() - started)
            charged = min(remaining, _charged_seconds(result, observed))
            remaining -= charged
            failure = classify_failure(result)
            descriptor = exact_descriptor_key(result)
            attempts.append(
                {
                    "endpoint_sha256": candidate.endpoint_sha256,
                    "uncertainty_bucket": candidate.bucket_key,
                    "discovery_ordinal": candidate.discovery_ordinal,
                    "attempt_kind": kind.value,
                    "precision_contract": ATTEMPT_PRECISION_CONTRACT[kind],
                    "soft_cap_seconds": cap,
                    "charged_seconds": charged,
                    "remaining_seconds": remaining,
                    "status": result.get("status"),
                    "failure_class": failure.value,
                    "authority_pass": result.get("authority_pass") is True,
                    "exact_descriptor_key": descriptor,
                }
            )

            if failure is FailureClass.READY and descriptor is not None:
                if descriptor in descriptor_keys:
                    duplicate_authorities.append(
                        {
                            "endpoint_sha256": candidate.endpoint_sha256,
                            "uncertainty_bucket": candidate.bucket_key,
                            "discovery_ordinal": candidate.discovery_ordinal,
                            "exact_descriptor_key": descriptor,
                            "reason": "EXACT_DESCRIPTOR_DUPLICATE",
                        }
                    )
                else:
                    descriptor_keys.add(descriptor)
                    accepted.append(
                        {
                            "endpoint_sha256": candidate.endpoint_sha256,
                            "uncertainty_bucket": candidate.bucket_key,
                            "discovery_ordinal": candidate.discovery_ordinal,
                            "exact_descriptor_key": descriptor,
                            "attempt_kind": kind.value,
                            "result": result,
                        }
                    )
                break

            next_kind = _next_attempt(failure, used, backends)
            if next_kind is None:
                break
            kind = next_kind

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "COMPLETE",
        "source_sha256": source_sha256,
        "authority_count": len(accepted),
        "distinct_exact_descriptor_count": len(descriptor_keys),
        "accepted_authorities": accepted,
        "duplicate_authorities": duplicate_authorities,
        "attempts": attempts,
        "preauthority_suppressed_candidate_count": 0,
        "deferred_candidates": deferred,
        "budget": {
            "total_seconds": float(total_budget_seconds),
            "charged_seconds": float(total_budget_seconds) - remaining,
            "remaining_seconds": remaining,
            "policy": {
                "minimum_attempt_seconds": policy.minimum_attempt_seconds,
                "reserve_after_primary_seconds": (
                    policy.reserve_after_primary_seconds
                ),
                "maximum_attempt_seconds": {
                    key.value: value
                    for key, value in policy.maximum_attempt_seconds.items()
                },
            },
        },
        "backend_manifest": backend_manifest(),
        "safety_contract": {
            "source_or_problem_modified": False,
            "bounds_added_or_inferred": False,
            "gauge_or_symmetry_reduction": False,
            "coordinate_reparameterization": False,
            "truth_case_family_or_known_target_count_read": False,
            "all_successes_require_exact_descriptor": True,
            "preauthority_endpoint_suppression": False,
            "preauthority_bucket_suppression": False,
            "duplicate_accounting_basis": (
                "EXACT_MINIMAL_POLYNOMIAL_PLUS_REAL_ROOT_INDEX"
            ),
            "deferred_candidates_retained_for_aging": True,
        },
    }


__all__ = [
    "ATTEMPT_PRECISION_CONTRACT",
    "AttemptKind",
    "BackendBundle",
    "BudgetPolicy",
    "EndpointCandidate",
    "FailureClass",
    "backend_manifest",
    "classify_failure",
    "exact_descriptor_key",
    "load_reused_backends",
    "run_adaptive_hp_portfolio",
]
