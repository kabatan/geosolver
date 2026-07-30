"""Append-aware candidate-reservoir checkpoints for champion continuation.

This experiment removes repeated semantic replay of an immutable endpoint
prefix.  It deliberately does *not* cache final answers or high-precision
authority.  A checkpoint is reusable only when source bytes, the truth-blind
search policy, and the complete covered endpoint prefix match exactly.

The integration surface is intentionally small: ``incremental_candidates``
accepts an adapter for the frozen champion seam.  ``FrozenChampionAdapter`` is
the concrete adapter for the pinned ``0967ff1c`` worker; tests use a tiny fake
adapter so this candidate remains runnable on the experiment branch without
copying the product package.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


SCHEMA_VERSION = "geotarget.incremental-candidate-reservoir/v2"
_CANDIDATE_FIELDS = (
    "endpoint",
    "endpoint_sha256",
    "residual_inf",
    "provisional_target",
    "cluster_ordinal",
    "cluster_rank",
    "discovery_ordinal",
    "admission_role",
    "record_id",
    "bucket_id",
    "bucket_kind",
    "aging_wave",
    "semantic_verified",
)
_OBSERVATION_FIELDS = (
    "endpoint",
    "endpoint_sha256",
    "residual_inf",
    "provisional_target",
    "discovery_ordinal",
    "admission_role",
    "semantic_verified",
)


class IncrementalCheckpointCorrupt(RuntimeError):
    """The checkpoint is partial, malformed, or fails its content digest."""


class ReservoirSnapshot(tuple):
    """Tuple-compatible candidate reservoir with an explicit backlog."""

    def __new__(cls, verified: Sequence[Any], deadline_backlog: Sequence[Any] = ()):
        instance = super().__new__(cls, tuple(verified))
        instance.deadline_backlog = tuple(deadline_backlog)
        return instance


@dataclass(frozen=True)
class Observation:
    endpoint: tuple[float, ...]
    endpoint_sha256: str
    residual_inf: float
    provisional_target: float | None
    discovery_ordinal: int
    admission_role: str
    semantic_verified: bool


@dataclass(frozen=True)
class LoadedCheckpoint:
    reservoir: Sequence[Any]
    observations: tuple[Observation, ...]
    covered_endpoint_count: int
    exact: bool


@dataclass(frozen=True)
class IncrementalResult:
    reservoir: Sequence[Any]
    mode: str
    covered_endpoint_count: int
    semantic_replay_count: int
    reused_verified_count: int
    retried_backlog_count: int
    retried_unobserved_count: int


class ReservoirAdapter(Protocol):
    def full_replay(
        self,
        source_document: Mapping[str, Any],
        endpoints: Sequence[Any],
        *,
        hard_deadline: float,
    ) -> Sequence[Any]: ...

    def observations_from_reservoir(
        self, reservoir: Sequence[Any]
    ) -> tuple[Observation, ...]: ...

    def scan_indexed(
        self,
        source_document: Mapping[str, Any],
        indexed_endpoints: Sequence[tuple[int, Any]],
        *,
        hard_deadline: float,
    ) -> tuple[Observation, ...]: ...

    def plan(self, observations: Sequence[Observation]) -> Sequence[Any]: ...


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _endpoints(search: Mapping[str, Any]) -> list[Any]:
    endpoints = search.get("endpoints")
    if not isinstance(endpoints, list):
        raise ValueError("search endpoints are required")
    return endpoints


def _stable_plan(search: Mapping[str, Any]) -> dict[str, Any]:
    """Return only immutable, truth-blind policy inputs.

    Dynamic work counters and completed-start ordinals intentionally do not
    participate: they grow between continuation windows.  The literal proposal
    prefix, arm, seed and declared budget must remain identical.
    """

    literal = search.get("literal_prefix")
    budget = search.get("budget")
    return {
        "arm": search.get("arm"),
        "seed": search.get("seed"),
        "literal_prefix": dict(literal) if isinstance(literal, Mapping) else {},
        "budget": dict(budget) if isinstance(budget, Mapping) else {},
    }


def _exact_binding(source_sha256: str, search: Mapping[str, Any]) -> dict[str, str]:
    endpoints = _endpoints(search)
    literal = search.get("literal_prefix")
    parallel = search.get("optimized_parallel_search")
    work = search.get("work")
    budget = search.get("budget")
    plan = {
        "literal_prefix": dict(literal) if isinstance(literal, Mapping) else {},
        "optimized_parallel_search": (
            dict(parallel) if isinstance(parallel, Mapping) else {}
        ),
        "work": dict(work) if isinstance(work, Mapping) else {},
        "budget": dict(budget) if isinstance(budget, Mapping) else {},
        "seed": search.get("seed"),
        "arm": search.get("arm"),
    }
    return {
        "source_sha256": source_sha256,
        "search_endpoints_sha256": _sha256(endpoints),
        "full_prefix_sha256": str(
            (dict(literal).get("full_prefix_sha256") if isinstance(literal, Mapping) else "")
            or ""
        ),
        "search_plan_sha256": _sha256(plan),
    }


def _candidate_payload(candidate: Any) -> dict[str, Any]:
    row = {field: getattr(candidate, field) for field in _CANDIDATE_FIELDS}
    row["endpoint"] = [float(value) for value in row["endpoint"]]
    row["residual_inf"] = float(row["residual_inf"])
    row["provisional_target"] = (
        None if row["provisional_target"] is None else float(row["provisional_target"])
    )
    if not math.isfinite(row["residual_inf"]) or (
        row["provisional_target"] is not None
        and not math.isfinite(row["provisional_target"])
    ):
        raise ValueError("candidate numeric fields must be finite")
    return row


def _observation_payload(observation: Observation) -> dict[str, Any]:
    row = {field: getattr(observation, field) for field in _OBSERVATION_FIELDS}
    row["endpoint"] = [float(value) for value in row["endpoint"]]
    return row


def _reservoir_payload(reservoir: Sequence[Any]) -> dict[str, Any]:
    return {
        "verified": [_candidate_payload(candidate) for candidate in reservoir],
        "deadline_backlog": [
            _candidate_payload(candidate)
            for candidate in getattr(reservoir, "deadline_backlog", ())
        ],
    }


def _payload(
    *,
    source_sha256: str,
    search: Mapping[str, Any],
    reservoir: Sequence[Any],
    observations: Sequence[Observation],
) -> dict[str, Any]:
    endpoints = _endpoints(search)
    return {
        "schema_version": SCHEMA_VERSION,
        "source_sha256": source_sha256,
        "stable_plan_sha256": _sha256(_stable_plan(search)),
        "exact_binding": _exact_binding(source_sha256, search),
        "covered_endpoint_count": len(endpoints),
        "covered_endpoints_sha256": _sha256(endpoints),
        "candidate_fields": list(_CANDIDATE_FIELDS),
        "observation_fields": list(_OBSERVATION_FIELDS),
        "stable_order": "verified_then_deadline_backlog",
        "reservoir": _reservoir_payload(reservoir),
        "observations": [_observation_payload(value) for value in observations],
    }


def write_checkpoint(
    path: Path,
    *,
    source_sha256: str,
    search: Mapping[str, Any],
    reservoir: Sequence[Any],
    observations: Sequence[Observation],
) -> None:
    """Atomically persist a complete append-aware checkpoint."""

    payload = _payload(
        source_sha256=source_sha256,
        search=search,
        reservoir=reservoir,
        observations=observations,
    )
    envelope = {**payload, "content_sha256": _sha256(payload)}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(envelope, stream, ensure_ascii=False, allow_nan=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def _rows(value: Any, fields: tuple[str, ...], label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise IncrementalCheckpointCorrupt(f"{label} is not a list")
    result: list[dict[str, Any]] = []
    for row in value:
        if not isinstance(row, Mapping) or set(row) != set(fields):
            raise IncrementalCheckpointCorrupt(f"{label} has an incomplete row")
        endpoint = row.get("endpoint")
        if not isinstance(endpoint, list) or not all(
            isinstance(value, int | float)
            and not isinstance(value, bool)
            and math.isfinite(float(value))
            for value in endpoint
        ):
            raise IncrementalCheckpointCorrupt(f"{label} has an invalid endpoint")
        result.append(dict(row))
    return result


def load_checkpoint(
    path: Path,
    *,
    source_sha256: str,
    search: Mapping[str, Any],
    candidate_type: type[Any],
    reservoir_type: type[Any],
) -> LoadedCheckpoint | None:
    """Load an exact or append-compatible checkpoint.

    Old/future schema, source/plan mismatch, endpoint deletion and endpoint
    prefix mutation are clean cache misses.  Malformed same-schema content is
    corrupt and fails closed.
    """

    if not path.is_file():
        return None
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise IncrementalCheckpointCorrupt("checkpoint is partial or invalid") from error
    if not isinstance(envelope, Mapping):
        raise IncrementalCheckpointCorrupt("checkpoint is not an object")
    if envelope.get("schema_version") != SCHEMA_VERSION:
        return None
    supplied_digest = envelope.get("content_sha256")
    payload = {key: value for key, value in envelope.items() if key != "content_sha256"}
    if not isinstance(supplied_digest, str) or supplied_digest != _sha256(payload):
        raise IncrementalCheckpointCorrupt("checkpoint integrity check failed")
    if envelope.get("source_sha256") != source_sha256:
        return None
    if envelope.get("stable_plan_sha256") != _sha256(_stable_plan(search)):
        return None
    if envelope.get("candidate_fields") != list(_CANDIDATE_FIELDS):
        return None
    if envelope.get("observation_fields") != list(_OBSERVATION_FIELDS):
        return None
    if envelope.get("stable_order") != "verified_then_deadline_backlog":
        return None
    covered = envelope.get("covered_endpoint_count")
    if not isinstance(covered, int) or isinstance(covered, bool) or covered < 0:
        raise IncrementalCheckpointCorrupt("invalid covered endpoint count")
    endpoints = _endpoints(search)
    if covered > len(endpoints):
        return None
    if envelope.get("covered_endpoints_sha256") != _sha256(endpoints[:covered]):
        return None
    reservoir_row = envelope.get("reservoir")
    if not isinstance(reservoir_row, Mapping):
        raise IncrementalCheckpointCorrupt("reservoir is not an object")
    verified_rows = _rows(reservoir_row.get("verified"), _CANDIDATE_FIELDS, "verified")
    backlog_rows = _rows(
        reservoir_row.get("deadline_backlog"), _CANDIDATE_FIELDS, "deadline_backlog"
    )
    observation_rows = _rows(
        envelope.get("observations"), _OBSERVATION_FIELDS, "observations"
    )
    try:
        verified = tuple(
            candidate_type(**{**row, "endpoint": tuple(row["endpoint"])})
            for row in verified_rows
        )
        backlog = tuple(
            candidate_type(**{**row, "endpoint": tuple(row["endpoint"])})
            for row in backlog_rows
        )
        observations = tuple(
            Observation(**{**row, "endpoint": tuple(row["endpoint"])})
            for row in observation_rows
        )
        reservoir = reservoir_type(verified, backlog)
    except (TypeError, ValueError) as error:
        raise IncrementalCheckpointCorrupt("checkpoint reconstruction failed") from error
    exact = envelope.get("exact_binding") == _exact_binding(source_sha256, search)
    return LoadedCheckpoint(reservoir, observations, covered, exact)


def incremental_candidates(
    *,
    adapter: ReservoirAdapter,
    source_document: Mapping[str, Any],
    search: Mapping[str, Any],
    source_sha256: str,
    checkpoint_input: Path | None,
    checkpoint_output: Path | None,
    hard_deadline: float,
    candidate_type: type[Any],
    reservoir_type: type[Any],
) -> IncrementalResult:
    """Return a reservoir while replaying only an unverified append suffix."""

    endpoints = _endpoints(search)
    loaded = (
        load_checkpoint(
            checkpoint_input,
            source_sha256=source_sha256,
            search=search,
            candidate_type=candidate_type,
            reservoir_type=reservoir_type,
        )
        if checkpoint_input is not None
        else None
    )
    if loaded is not None and loaded.exact:
        result = IncrementalResult(
            loaded.reservoir,
            "exact-hit",
            loaded.covered_endpoint_count,
            0,
            sum(value.semantic_verified for value in loaded.observations),
            0,
            0,
        )
        observations = loaded.observations
    elif loaded is not None:
        verified = tuple(value for value in loaded.observations if value.semantic_verified)
        backlog = tuple(value for value in loaded.observations if not value.semantic_verified)
        observed_ordinals = {value.discovery_ordinal for value in loaded.observations}
        unobserved_ordinals = tuple(
            ordinal
            for ordinal in range(loaded.covered_endpoint_count)
            if ordinal not in observed_ordinals
        )
        indexed = [
            (value.discovery_ordinal, {"point": list(value.endpoint)}) for value in backlog
        ]
        indexed.extend((ordinal, endpoints[ordinal]) for ordinal in unobserved_ordinals)
        indexed.extend(
            (ordinal, endpoints[ordinal])
            for ordinal in range(loaded.covered_endpoint_count, len(endpoints))
        )
        rescanned = adapter.scan_indexed(
            source_document, indexed, hard_deadline=hard_deadline
        )
        by_ordinal = {value.discovery_ordinal: value for value in (*verified, *rescanned)}
        observations = tuple(by_ordinal[key] for key in sorted(by_ordinal))
        reservoir = adapter.plan(observations)
        result = IncrementalResult(
            reservoir,
            "prefix-extend",
            len(endpoints),
            len(indexed),
            len(verified),
            len(backlog),
            len(unobserved_ordinals),
        )
    else:
        reservoir = adapter.full_replay(
            source_document, endpoints, hard_deadline=hard_deadline
        )
        observations = adapter.observations_from_reservoir(reservoir)
        result = IncrementalResult(
            reservoir,
            "full-replay",
            len(endpoints),
            len(endpoints),
            0,
            0,
            0,
        )
    if checkpoint_output is not None:
        write_checkpoint(
            checkpoint_output,
            source_sha256=source_sha256,
            search=search,
            reservoir=result.reservoir,
            observations=observations,
        )
    return result


class FrozenChampionAdapter:
    """Adapter for the champion-v0 reservoir seam pinned by ``0967ff1c``."""

    def __init__(self, base: Any):
        self.base = base
        self.original_fresh = getattr(
            base,
            "_geotarget_exp_eval_001_original_fresh_replay",
            base._fresh_replay_candidates,
        )
        globals_ = self.original_fresh.__globals__
        self.reservoir_module = globals_["RESERVOIR"]
        self.precision_base = globals_["BASE"]
        # The frozen wrapper publishes the seam function but does not promise
        # these implementation types as module attributes.  Resolve them from
        # the exact function globals that construct the original reservoir.
        self.candidate_type = globals_["ReplayCandidate"]
        self.reservoir_type = globals_["CandidateReservoir"]
        self.precision_runtime = self.precision_base._load_module(
            "geotarget_exp_eval_001_precision_runtime",
            self.precision_base.PRECISION_RUNTIME,
        )

    def full_replay(
        self,
        source_document: Mapping[str, Any],
        endpoints: Sequence[Any],
        *,
        hard_deadline: float,
    ) -> Sequence[Any]:
        return self.original_fresh(
            dict(source_document), endpoints, hard_deadline=hard_deadline
        )

    def observations_from_reservoir(
        self, reservoir: Sequence[Any]
    ) -> tuple[Observation, ...]:
        values = tuple(reservoir) + tuple(getattr(reservoir, "deadline_backlog", ()))
        return tuple(
            Observation(
                endpoint=tuple(float(item) for item in candidate.endpoint),
                endpoint_sha256=str(candidate.endpoint_sha256),
                residual_inf=float(candidate.residual_inf),
                provisional_target=(
                    None
                    if candidate.provisional_target is None
                    else float(candidate.provisional_target)
                ),
                discovery_ordinal=int(candidate.discovery_ordinal),
                admission_role=str(candidate.admission_role),
                semantic_verified=bool(candidate.semantic_verified),
            )
            for candidate in sorted(values, key=lambda value: value.discovery_ordinal)
        )

    def scan_indexed(
        self,
        source_document: Mapping[str, Any],
        indexed_endpoints: Sequence[tuple[int, Any]],
        *,
        hard_deadline: float,
    ) -> tuple[Observation, ...]:
        if not indexed_endpoints:
            return ()
        rows = [row for _ordinal, row in indexed_endpoints]
        _case, _budget, evaluator = self.precision_runtime.build_source_case(
            dict(source_document),
            callback_cap=max(1, len(rows)),
            deadline=max(__import__("time").monotonic() + 0.01, hard_deadline),
        )
        scan = self.reservoir_module.cheap_scan_endpoints(
            evaluator, rows, hard_deadline=hard_deadline
        )
        local_to_global = {
            local: global_ordinal
            for local, (global_ordinal, _row) in enumerate(indexed_endpoints)
        }
        return tuple(
            Observation(
                endpoint=tuple(float(item) for item in observation.endpoint),
                endpoint_sha256=str(observation.endpoint_sha256),
                residual_inf=float(observation.residual_inf),
                provisional_target=(
                    None
                    if observation.provisional_target is None
                    else float(observation.provisional_target)
                ),
                discovery_ordinal=local_to_global[observation.discovery_ordinal],
                admission_role=str(observation.admission_role),
                semantic_verified=(
                    observation.admission_role
                    != self.reservoir_module.DEADLINE_BACKLOG_ROLE
                ),
            )
            for observation in scan.observations
        )

    def plan(self, observations: Sequence[Observation]) -> Sequence[Any]:
        endpoint_observations = tuple(
            self.reservoir_module.EndpointObservation(
                endpoint=value.endpoint,
                endpoint_sha256=value.endpoint_sha256,
                residual_inf=value.residual_inf,
                provisional_target=value.provisional_target,
                discovery_ordinal=value.discovery_ordinal,
                admission_role=value.admission_role,
            )
            for value in observations
        )
        plan = self.reservoir_module.build_plan(endpoint_observations)
        scheduled = self.reservoir_module.scheduled_endpoints(plan)
        converted = tuple(
            self.candidate_type(
                endpoint=row.endpoint,
                endpoint_sha256=row.endpoint_sha256,
                residual_inf=row.residual_inf,
                provisional_target=None,
                cluster_ordinal=cluster_ordinal,
                cluster_rank=0,
                discovery_ordinal=int(row.record_id.split(":", 1)[0]),
                admission_role=row.admission_role,
                record_id=row.record_id,
                bucket_id=row.bucket_id,
                bucket_kind=row.bucket_kind,
                aging_wave=row.aging_wave,
                semantic_verified=(
                    row.admission_role
                    != self.reservoir_module.DEADLINE_BACKLOG_ROLE
                ),
            )
            for cluster_ordinal, row in enumerate(scheduled)
        )
        verified = tuple(value for value in converted if value.semantic_verified)
        backlog = tuple(value for value in converted if not value.semantic_verified)
        return self.reservoir_type(verified, backlog)


def install_initial_checkpoint(base: Any, checkpoint_path: Path, source_sha256: str) -> None:
    """Patch only the frozen initial reservoir seam to emit schema v2."""

    original = base._fresh_replay_candidates
    base._geotarget_exp_eval_001_original_fresh_replay = original
    adapter = FrozenChampionAdapter(base)
    resolved = checkpoint_path.resolve()

    def checkpointing_fresh(*args: Any, **kwargs: Any):
        reservoir = original(*args, **kwargs)
        search_path = resolved.parent / "search.json"
        if not search_path.is_file():
            raise RuntimeError("search artifact is absent at reservoir commit")
        search = json.loads(search_path.read_text(encoding="utf-8"))
        write_checkpoint(
            resolved,
            source_sha256=source_sha256,
            search=search,
            reservoir=reservoir,
            observations=adapter.observations_from_reservoir(reservoir),
        )
        return reservoir

    base._fresh_replay_candidates = checkpointing_fresh
