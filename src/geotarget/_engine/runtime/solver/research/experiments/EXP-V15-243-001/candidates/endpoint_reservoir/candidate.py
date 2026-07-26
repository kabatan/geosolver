#!/usr/bin/env python3
"""Soft endpoint reservoir candidate for the current v15 endpoint schema.

The current v15 worker irreversibly reduces every fixed-tolerance provisional
target cluster to at most two endpoints before high-precision descriptors
exist.  This independent candidate instead:

* keeps every admitted source-semantic near-root endpoint as a distinct record;
* reuses the EXP-REAL61-008 uncertainty-aware soft-bucket implementation;
* services the residual-best record first in each bucket;
* orders the remaining records by configuration maximin diversity; and
* exposes all deferred records through deterministic breadth-first aging.

The module is intentionally a thin scheduling layer.  It does not read case
identity, family, truth, known target count, or benchmark outcomes, and it does
not alter the common worker.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct
import sys
import time
from typing import Hashable, Mapping, Sequence


HERE = Path(__file__).resolve().parent
EXPERIMENTS = HERE.parents[2]
REUSED_RESERVOIR_PATH = (
    EXPERIMENTS / "EXP-REAL61-008/hp_uncertainty_reservoir/reservoir.py"
)
REUSED_MODULE_NAME = "geotarget_exp_v15_243_reused_hp_uncertainty_reservoir"
RAW_SAFE_RESIDUAL_MAX = 1.0e-8
NEAR_ROOT_RESIDUAL_MAX = 1.0e-3
TARGETED_ROLE = "SOURCE_SAFE_TARGETED"
TARGET_UNAVAILABLE_RAW_SAFE_ROLE = "TARGET_UNAVAILABLE_RAW_SAFE"
TARGET_UNAVAILABLE_NEAR_ROOT_ROLE = "TARGET_UNAVAILABLE_NEAR_ROOT"
DEADLINE_BACKLOG_ROLE = "DEADLINE_UNEXAMINED_CONFIGURATION_BACKLOG"
TARGETED_BUCKET_KIND = "TARGET_UNCERTAINTY_SOFT_BUCKET"
ANONYMOUS_BUCKET_KIND = "TARGET_UNAVAILABLE_CONFIGURATION_POOL"


def _load_reused_reservoir():
    cached = sys.modules.get(REUSED_MODULE_NAME)
    if cached is not None:
        return cached
    specification = importlib.util.spec_from_file_location(
        REUSED_MODULE_NAME, REUSED_RESERVOIR_PATH
    )
    if specification is None or specification.loader is None:
        raise ImportError(REUSED_RESERVOIR_PATH)
    module = importlib.util.module_from_spec(specification)
    sys.modules[REUSED_MODULE_NAME] = module
    specification.loader.exec_module(module)
    return module


_REUSED = _load_reused_reservoir()
ReservoirCandidate = _REUSED.Candidate
SoftBucket = _REUSED.SoftBucket
DescriptorSplit = _REUSED.DescriptorSplit


def endpoint_float64_sha256(endpoint: Sequence[float]) -> str:
    """Return the bit-exact endpoint digest used by v15."""

    values = tuple(float(value) for value in endpoint)
    payload = struct.pack(">I", len(values)) + b"".join(
        struct.pack(">d", value) for value in values
    )
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class EndpointObservation:
    """One admitted original-evaluator semantic near-root replay."""

    endpoint: tuple[float, ...]
    endpoint_sha256: str
    residual_inf: float
    provisional_target: float | None
    discovery_ordinal: int
    admission_role: str = TARGETED_ROLE

    def __post_init__(self) -> None:
        if any(not math.isfinite(value) for value in self.endpoint):
            raise ValueError("endpoint must contain only finite Float64 values")
        if self.endpoint_sha256 != endpoint_float64_sha256(self.endpoint):
            raise ValueError("endpoint_sha256 does not match endpoint Float64 bytes")
        if not math.isfinite(self.residual_inf) or self.residual_inf < 0.0:
            raise ValueError("residual_inf must be finite and nonnegative")
        if self.provisional_target is not None and not math.isfinite(
            self.provisional_target
        ):
            raise ValueError("provisional_target must be finite when available")
        if self.discovery_ordinal < 0:
            raise ValueError("discovery_ordinal must be nonnegative")
        allowed_roles = {
            TARGETED_ROLE,
            TARGET_UNAVAILABLE_RAW_SAFE_ROLE,
            TARGET_UNAVAILABLE_NEAR_ROOT_ROLE,
            DEADLINE_BACKLOG_ROLE,
        }
        if self.admission_role not in allowed_roles:
            raise ValueError("unknown admission_role")
        if (self.provisional_target is None) == (self.admission_role == TARGETED_ROLE):
            raise ValueError("admission_role is inconsistent with target availability")

    @classmethod
    def from_endpoint(
        cls,
        endpoint: Sequence[float],
        *,
        residual_inf: float,
        provisional_target: float | None,
        discovery_ordinal: int,
        admission_role: str | None = None,
    ) -> "EndpointObservation":
        values = tuple(float(value) for value in endpoint)
        if admission_role is None:
            admission_role = (
                TARGETED_ROLE
                if provisional_target is not None
                else TARGET_UNAVAILABLE_NEAR_ROOT_ROLE
            )
        return cls(
            endpoint=values,
            endpoint_sha256=endpoint_float64_sha256(values),
            residual_inf=float(residual_inf),
            provisional_target=(
                None
                if provisional_target is None
                else float(provisional_target)
            ),
            discovery_ordinal=int(discovery_ordinal),
            admission_role=admission_role,
        )

    @classmethod
    def from_source_replay(
        cls,
        endpoint: Sequence[float],
        replay: Mapping[str, object],
        *,
        discovery_ordinal: int,
        near_root_residual_max: float = NEAR_ROOT_RESIDUAL_MAX,
    ) -> "EndpointObservation | None":
        """Admit targeted and target-unavailable semantic near roots.

        High-precision answer evaluation is deliberately not an admission
        requirement.  Finite residual, original hard feasibility, original
        guard/branch validity, and the global near-root band are sufficient to
        retain an anonymous configuration record.
        """

        try:
            residual = float(replay.get("residual_inf"))
        except (TypeError, ValueError, OverflowError):
            return None
        if (
            not math.isfinite(residual)
            or residual < 0.0
            or residual > near_root_residual_max
            or replay.get("guard_ok") is not True
            or replay.get("hard_feasible") is not True
        ):
            return None
        raw_target = replay.get("diagnostic_target")
        target = None
        if raw_target is not None:
            try:
                parsed = float(str(raw_target))
            except (TypeError, ValueError, OverflowError):
                parsed = math.nan
            if math.isfinite(parsed):
                target = parsed
        if target is not None:
            role = TARGETED_ROLE
        elif residual <= RAW_SAFE_RESIDUAL_MAX:
            role = TARGET_UNAVAILABLE_RAW_SAFE_ROLE
        else:
            role = TARGET_UNAVAILABLE_NEAR_ROOT_ROLE
        return cls.from_endpoint(
            endpoint,
            residual_inf=residual,
            provisional_target=target,
            discovery_ordinal=discovery_ordinal,
            admission_role=role,
        )

    @property
    def record_id(self) -> str:
        # Discovery ordinal deliberately prevents equal Float64 endpoint bytes
        # from being collapsed before an exact authority descriptor exists.
        return f"{self.discovery_ordinal:012d}:{self.endpoint_sha256}"


@dataclass(frozen=True)
class CheapScanResult:
    """Diagnostics for the target-free Float64 selection pass."""

    observations: tuple[EndpointObservation, ...]
    input_count: int
    examined_count: int
    malformed_count: int
    evaluator_failure_count: int
    semantic_ineligible_count: int
    deadline_unexamined_count: int
    provisional_target_evaluation_count: int = 0

    def __post_init__(self) -> None:
        if self.examined_count != self.input_count:
            raise ValueError("cheap scan must structurally account for every row")
        classified = (
            len(self.observations)
            + self.malformed_count
            + self.evaluator_failure_count
            + self.semantic_ineligible_count
        )
        if classified != self.input_count:
            raise ValueError("cheap scan input-count accounting mismatch")
        if self.provisional_target_evaluation_count != 0:
            raise ValueError("cheap scan must not evaluate provisional targets")
        if self.deadline_backlog_count > self.deadline_unexamined_count:
            raise ValueError("deadline backlog exceeds unexamined row count")

    @property
    def deadline_backlog_count(self) -> int:
        return sum(
            observation.admission_role == DEADLINE_BACKLOG_ROLE
            for observation in self.observations
        )

    @property
    def verified_semantic_near_root_count(self) -> int:
        return len(self.observations) - self.deadline_backlog_count


@dataclass(frozen=True)
class ReservoirPlan:
    """Complete, lossless endpoint schedule."""

    observations: tuple[EndpointObservation, ...]
    buckets: tuple[SoftBucket, ...]
    bucket_kind_by_id: tuple[tuple[str, str], ...]
    aging_waves: tuple[tuple[str, ...], ...]

    def __post_init__(self) -> None:
        expected = {observation.record_id for observation in self.observations}
        scheduled = [
            record_id for wave in self.aging_waves for record_id in wave
        ]
        if len(expected) != len(self.observations):
            raise ValueError("record ids must be unique")
        if len(scheduled) != len(expected) or set(scheduled) != expected:
            raise ValueError("aging schedule must retain every record exactly once")
        members = [
            record_id for bucket in self.buckets for record_id in bucket.member_ids
        ]
        if len(members) != len(expected) or set(members) != expected:
            raise ValueError("soft buckets must cover every record exactly once")
        kinds = dict(self.bucket_kind_by_id)
        if len(kinds) != len(self.bucket_kind_by_id):
            raise ValueError("bucket kind ids must be unique")
        if set(kinds) != {bucket.bucket_id for bucket in self.buckets}:
            raise ValueError("every bucket must have exactly one bucket kind")
        allowed_kinds = {TARGETED_BUCKET_KIND, ANONYMOUS_BUCKET_KIND}
        if not set(kinds.values()).issubset(allowed_kinds):
            raise ValueError("unknown bucket kind")

    @property
    def first_wave_record_ids(self) -> tuple[str, ...]:
        return self.aging_waves[0] if self.aging_waves else ()

    @property
    def full_service_order(self) -> tuple[str, ...]:
        return tuple(
            record_id for wave in self.aging_waves for record_id in wave
        )

    @property
    def deferred_record_ids(self) -> tuple[str, ...]:
        first = set(self.first_wave_record_ids)
        return tuple(
            record_id
            for record_id in self.full_service_order
            if record_id not in first
        )

    @property
    def irreversible_dedup_count(self) -> int:
        return 0

    @property
    def anonymous_record_ids(self) -> tuple[str, ...]:
        return tuple(
            observation.record_id
            for observation in self.observations
            if observation.provisional_target is None
        )

    @property
    def deadline_backlog_record_ids(self) -> tuple[str, ...]:
        return tuple(
            observation.record_id
            for observation in self.observations
            if observation.admission_role == DEADLINE_BACKLOG_ROLE
        )


@dataclass(frozen=True)
class ScheduledEndpoint:
    """Worker-facing endpoint plus reservoir scheduling metadata."""

    record_id: str
    endpoint: tuple[float, ...]
    endpoint_sha256: str
    residual_inf: float
    provisional_target: float | None
    admission_role: str
    bucket_id: str
    bucket_kind: str
    bucket_ordinal: int
    bucket_rank: int
    aging_wave: int


def policy_document() -> dict[str, object]:
    """Return the truth-blind candidate policy."""

    return {
        "schema_version": "geotarget.exp-v15-243-endpoint-reservoir-policy/v1",
        "input_schema": {
            "endpoint": "tuple[finite Float64]",
            "endpoint_sha256": "v15 bit-exact endpoint digest",
            "residual_inf": "finite nonnegative original-evaluator residual",
            "provisional_target": (
                "finite original-evaluator diagnostic scalar or unavailable"
            ),
            "discovery_ordinal": "nonnegative search discovery order",
        },
        "runtime_inputs": [
            "endpoint",
            "endpoint_sha256",
            "original_evaluator_residual_inf",
            "provisional_scalar_target",
            "discovery_ordinal",
        ],
        "forbidden_runtime_inputs": [
            "case_id",
            "problem_name",
            "family",
            "source_hash_for_routing",
            "truth",
            "known_target_count",
            "benchmark_outcome",
            "exact_target_value",
        ],
        "reused_component": (
            "EXP-REAL61-008/hp_uncertainty_reservoir: uncertainty-aware "
            "soft buckets, descriptor mismatch splitting, and aging waves"
        ),
        "soft_bucket": (
            "connected components of residual/ulp/configuration-calibrated "
            "overlapping target uncertainty intervals"
        ),
        "target_unavailable_pool": (
            "finite, source-hard-feasible, guard/branch-valid residual<=1e-3 "
            "endpoints remain in an anonymous configuration-maximin pool"
        ),
        "selection_time_target_evaluation": (
            "prohibited in the primary cheap scan; evaluate_float_residual, "
            "evaluate_guard, and evaluate_float_hard_feasibility only"
        ),
        "selection_deadline_fallback": (
            "structurally valid but not yet replayed endpoint configurations "
            "remain in a worst-priority anonymous backlog and must receive "
            "cheap semantic replay before HP service"
        ),
        "global_admission_thresholds": {
            "raw_safe_residual_max": RAW_SAFE_RESIDUAL_MAX,
            "near_root_residual_max": NEAR_ROOT_RESIDUAL_MAX,
            "origin": "existing source replay and hp_baseline_cpqr contracts",
        },
        "bucket_champion": "minimum residual, then oldest discovery ordinal",
        "deferred_order": (
            "configuration-distance maximin; uncertainty-normalized target "
            "separation, age, residual, and record id are deterministic tie-breaks"
        ),
        "aging": (
            "breadth-first bucket waves; concatenated waves contain every "
            "discovered source-replayed record exactly once"
        ),
        "pre_descriptor_irreversible_deduplication": False,
        "equal_endpoint_bytes_policy": (
            "retain separate discovery records; exact descriptor authority "
            "is required before any semantic equivalence decision"
        ),
        "descriptor_feedback": (
            "confirmed descriptor mismatch splits the soft bucket and promotes "
            "one unserved record from each resulting partition"
        ),
        "tuned_numeric_thresholds": [],
        "post_hp_authority": (
            "fresh high-precision exact replay and exact descriptor only; "
            "neither provisional target nor bucket identity is authority"
        ),
        "source_or_problem_modified": False,
        "case_or_truth_routing": False,
    }


def policy_sha256() -> str:
    payload = json.dumps(
        policy_document(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def cheap_scan_endpoints(
    evaluator: object,
    endpoint_rows: Sequence[object],
    *,
    hard_deadline: float | None = None,
) -> CheapScanResult:
    """Collect semantic near roots without evaluating the answer/target.

    This is the intended v15 selection path. It uses only the untouched
    Float64 residual, guard/branch, and hard-feasibility evaluator methods.
    All admitted records enter with an unknown target and are differentiated
    by residual quality plus configuration maximin scheduling.
    """

    observations = []
    malformed_count = 0
    evaluator_failure_count = 0
    semantic_ineligible_count = 0
    examined_count = 0
    deadline_mode = False
    deadline_unexamined_count = 0
    for discovery_ordinal, row in enumerate(endpoint_rows):
        examined_count += 1
        deadline_mode = bool(
            deadline_mode
            or (
                hard_deadline is not None
                and time.monotonic() >= hard_deadline
            )
        )
        if deadline_mode:
            deadline_unexamined_count += 1
        if not isinstance(row, Mapping) or not isinstance(row.get("point"), list):
            malformed_count += 1
            continue
        try:
            endpoint = tuple(float(value) for value in row["point"])
        except (TypeError, ValueError, OverflowError):
            malformed_count += 1
            continue
        if any(not math.isfinite(value) for value in endpoint):
            malformed_count += 1
            continue
        if deadline_mode:
            observations.append(
                EndpointObservation.from_endpoint(
                    endpoint,
                    residual_inf=NEAR_ROOT_RESIDUAL_MAX,
                    provisional_target=None,
                    discovery_ordinal=discovery_ordinal,
                    admission_role=DEADLINE_BACKLOG_ROLE,
                )
            )
            continue
        try:
            residual_observation = evaluator.evaluate_float_residual(endpoint)
            residual = float(residual_observation.residual_norm_float)
            residual_finite = bool(
                getattr(
                    residual_observation,
                    "is_finite",
                    math.isfinite(residual),
                )
            )
            guard_ok, _violations = evaluator.evaluate_guard(endpoint)
            hard = evaluator.evaluate_float_hard_feasibility(endpoint)
        except Exception:
            evaluator_failure_count += 1
            continue
        replay = {
            "residual_inf": residual if residual_finite else None,
            "guard_ok": bool(guard_ok),
            "hard_feasible": bool(hard.hard_feasible),
            # Deliberately unavailable: selection must not call
            # evaluator.evaluate_answer_hp.
            "diagnostic_target": None,
        }
        admitted = EndpointObservation.from_source_replay(
            endpoint,
            replay,
            discovery_ordinal=discovery_ordinal,
        )
        if admitted is None:
            semantic_ineligible_count += 1
            continue
        observations.append(admitted)
    return CheapScanResult(
        observations=tuple(observations),
        input_count=len(endpoint_rows),
        examined_count=examined_count,
        malformed_count=malformed_count,
        evaluator_failure_count=evaluator_failure_count,
        semantic_ineligible_count=semantic_ineligible_count,
        deadline_unexamined_count=deadline_unexamined_count,
    )


def _as_reservoir_candidates(
    observations: Sequence[EndpointObservation],
) -> tuple[ReservoirCandidate, ...]:
    return tuple(
        ReservoirCandidate(
            record_id=observation.record_id,
            target=observation.provisional_target,
            residual=observation.residual_inf,
            configuration=observation.endpoint,
            discovery_ordinal=observation.discovery_ordinal,
        )
        for observation in observations
        if observation.provisional_target is not None
    )


def _as_anonymous_reservoir_candidates(
    observations: Sequence[EndpointObservation],
) -> tuple[ReservoirCandidate, ...]:
    # The reused Candidate requires a finite scalar.  Zero is an internal
    # placeholder only within the separately tagged anonymous pool; it never
    # participates in target bucketing or target authority.
    return tuple(
        ReservoirCandidate(
            record_id=observation.record_id,
            target=0.0,
            residual=observation.residual_inf,
            configuration=observation.endpoint,
            discovery_ordinal=observation.discovery_ordinal,
        )
        for observation in observations
        if observation.provisional_target is None
    )


def _target_separation(
    left: ReservoirCandidate,
    right: ReservoirCandidate,
    uncertainties: Mapping[str, float],
) -> float:
    denominator = max(
        uncertainties[left.record_id] + uncertainties[right.record_id],
        math.ulp(left.target),
        math.ulp(right.target),
    )
    return abs(left.target - right.target) / denominator


def _configuration_maximin_order(
    members: Sequence[ReservoirCandidate],
    uncertainties: Mapping[str, float],
) -> tuple[str, ...]:
    champion = min(
        members,
        key=lambda item: (item.residual, item.discovery_ordinal, item.record_id),
    )
    serviced = [champion]
    unserved = {
        member.record_id: member for member in members if member.record_id != champion.record_id
    }
    minimum_configuration_distance = {
        record_id: _REUSED._configuration_distance(candidate, champion)
        for record_id, candidate in unserved.items()
    }
    minimum_target_separation = {
        record_id: _target_separation(candidate, champion, uncertainties)
        for record_id, candidate in unserved.items()
    }
    while unserved:
        selected = min(
            unserved.values(),
            key=lambda candidate: (
                -minimum_configuration_distance[candidate.record_id],
                -minimum_target_separation[candidate.record_id],
                candidate.discovery_ordinal,
                candidate.residual,
                candidate.record_id,
            ),
        )
        serviced.append(selected)
        del unserved[selected.record_id]
        minimum_configuration_distance.pop(selected.record_id)
        minimum_target_separation.pop(selected.record_id)
        for record_id, candidate in unserved.items():
            minimum_configuration_distance[record_id] = min(
                minimum_configuration_distance[record_id],
                _REUSED._configuration_distance(candidate, selected),
            )
            minimum_target_separation[record_id] = min(
                minimum_target_separation[record_id],
                _target_separation(candidate, selected, uncertainties),
            )
    return tuple(candidate.record_id for candidate in serviced)


def build_plan(
    observations: Sequence[EndpointObservation],
) -> ReservoirPlan:
    """Build a lossless soft-bucket and aging schedule."""

    ordered = tuple(
        sorted(
            observations,
            key=lambda item: (
                item.discovery_ordinal,
                item.endpoint_sha256,
                item.residual_inf,
                item.provisional_target,
            ),
        )
    )
    ordinals = [observation.discovery_ordinal for observation in ordered]
    if len(set(ordinals)) != len(ordinals):
        raise ValueError("discovery_ordinal values must be unique")
    if not ordered:
        return ReservoirPlan(
            observations=(),
            buckets=(),
            bucket_kind_by_id=(),
            aging_waves=(),
        )
    dimensions = {len(observation.endpoint) for observation in ordered}
    if len(dimensions) != 1:
        raise ValueError("endpoint dimensions differ")

    targeted_candidates = _as_reservoir_candidates(ordered)
    base_buckets = _REUSED.build_soft_buckets(targeted_candidates)
    by_id = {
        candidate.record_id: candidate for candidate in targeted_candidates
    }
    bucket_rows: list[tuple[SoftBucket, str]] = []
    for base in base_buckets:
        members = tuple(by_id[record_id] for record_id in base.member_ids)
        uncertainties = dict(base.uncertainty_by_id)
        service_order = _configuration_maximin_order(members, uncertainties)
        bucket_rows.append(
            (
                SoftBucket(
                bucket_id=base.bucket_id,
                member_ids=base.member_ids,
                champion_id=service_order[0],
                service_order=service_order,
                uncertainty_by_id=base.uncertainty_by_id,
                ),
                TARGETED_BUCKET_KIND,
            )
        )
    anonymous_candidates = _as_anonymous_reservoir_candidates(ordered)
    if anonymous_candidates:
        anonymous_uncertainties = {
            candidate.record_id: math.ulp(0.0)
            for candidate in anonymous_candidates
        }
        anonymous_order = _configuration_maximin_order(
            anonymous_candidates, anonymous_uncertainties
        )
        member_ids = tuple(
            sorted(candidate.record_id for candidate in anonymous_candidates)
        )
        digest = hashlib.sha256(
            b"target-unavailable-configuration-pool\0"
            + b"\0".join(record_id.encode("utf-8") for record_id in member_ids)
        ).hexdigest()
        bucket_rows.append(
            (
                SoftBucket(
                    bucket_id=digest,
                    member_ids=member_ids,
                    champion_id=anonymous_order[0],
                    service_order=anonymous_order,
                    uncertainty_by_id=tuple(
                        sorted(anonymous_uncertainties.items())
                    ),
                ),
                ANONYMOUS_BUCKET_KIND,
            )
        )
    all_candidates = {
        candidate.record_id: candidate
        for candidate in targeted_candidates + anonymous_candidates
    }
    bucket_rows.sort(
        key=lambda row: (
            all_candidates[row[0].champion_id].residual,
            all_candidates[row[0].champion_id].discovery_ordinal,
            row[1],
            row[0].bucket_id,
        )
    )
    frozen_buckets = tuple(row[0] for row in bucket_rows)
    return ReservoirPlan(
        observations=ordered,
        buckets=frozen_buckets,
        bucket_kind_by_id=tuple(
            (bucket.bucket_id, kind) for bucket, kind in bucket_rows
        ),
        aging_waves=_REUSED.aging_waves(frozen_buckets),
    )


def scheduled_endpoints(plan: ReservoirPlan) -> tuple[ScheduledEndpoint, ...]:
    """Adapt the plan to worker-facing endpoint records in service order."""

    observations = {
        observation.record_id: observation for observation in plan.observations
    }
    bucket_metadata = {}
    bucket_kinds = dict(plan.bucket_kind_by_id)
    for bucket_ordinal, bucket in enumerate(plan.buckets):
        for bucket_rank, record_id in enumerate(bucket.service_order):
            bucket_metadata[record_id] = (
                bucket.bucket_id,
                bucket_ordinal,
                bucket_rank,
            )
    wave_by_id = {
        record_id: wave
        for wave, record_ids in enumerate(plan.aging_waves)
        for record_id in record_ids
    }
    result = []
    for record_id in plan.full_service_order:
        observation = observations[record_id]
        bucket_id, bucket_ordinal, bucket_rank = bucket_metadata[record_id]
        result.append(
            ScheduledEndpoint(
                record_id=record_id,
                endpoint=observation.endpoint,
                endpoint_sha256=observation.endpoint_sha256,
                residual_inf=observation.residual_inf,
                provisional_target=observation.provisional_target,
                admission_role=observation.admission_role,
                bucket_id=bucket_id,
                bucket_kind=bucket_kinds[bucket_id],
                bucket_ordinal=bucket_ordinal,
                bucket_rank=bucket_rank,
                aging_wave=wave_by_id[record_id],
            )
        )
    return tuple(result)


def next_service_batch(
    plan: ReservoirPlan,
    *,
    capacity: int,
    already_served: Sequence[str] = (),
    promoted_record_ids: Sequence[str] = (),
) -> tuple[ScheduledEndpoint, ...]:
    """Return the next bounded batch without deleting deferred records.

    Exact-descriptor mismatch promotions are served first.  Remaining capacity
    follows the deterministic breadth-first aging schedule.
    """

    if capacity < 0:
        raise ValueError("capacity must be nonnegative")
    schedule = {row.record_id: row for row in scheduled_endpoints(plan)}
    served = set(already_served)
    backlog = set(plan.deadline_backlog_record_ids)
    unknown = served.difference(schedule)
    if unknown:
        raise ValueError("already_served contains an unknown record")
    promoted = []
    for record_id in promoted_record_ids:
        if record_id not in schedule:
            raise ValueError("promoted_record_ids contains an unknown record")
        if record_id in backlog:
            raise ValueError(
                "deadline backlog must be cheaply replayed before promotion"
            )
        if record_id not in served and record_id not in promoted:
            promoted.append(record_id)
    order = promoted + [
        record_id
        for record_id in plan.full_service_order
        if record_id not in served
        and record_id not in promoted
        and record_id not in backlog
    ]
    return tuple(schedule[record_id] for record_id in order[:capacity])


def descriptor_feedback(
    plan: ReservoirPlan,
    *,
    bucket_id: str,
    observations: Mapping[str, Hashable | None],
) -> DescriptorSplit:
    """Apply exact-authority feedback without discarding unresolved records."""

    matches = [bucket for bucket in plan.buckets if bucket.bucket_id == bucket_id]
    if len(matches) != 1:
        raise ValueError("bucket_id must identify exactly one soft bucket")
    candidates = {
        candidate.record_id: candidate
        for candidate in (
            _as_reservoir_candidates(plan.observations)
            + _as_anonymous_reservoir_candidates(plan.observations)
        )
    }
    return _REUSED.split_on_descriptor_mismatch(
        matches[0], candidates, observations
    )
