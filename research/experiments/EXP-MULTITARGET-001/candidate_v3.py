"""Truth-free post-baseline RESULT union for frozen numerical-v15.

Unlike scheduler overlays, this mechanism does not patch the frozen worker.
The frozen worker first writes its complete RESULT.json.  Only then, when the
same monotonic hard deadline has enough genuine slack, a byte-exact snapshot
is retained and one unattempted replay endpoint may enter canonical HP.  A
novel canonical descriptor is set-unioned into a clone of the baseline result.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import time
from typing import Any


POLICY_ID = "post_baseline_result_union_v3"
BASELINE_SNAPSHOT = "BASELINE_RESULT.json"
SIDE_DIRECTORY = "post-baseline-union"
REPLAY_MAX_SECONDS = 1.0
REPLAY_MIN_SECONDS = 0.10
SNAPSHOT_AND_UNION_RESERVE_SECONDS = 2.0
MAX_SIDE_HP_SECONDS = 6.0


@dataclass(frozen=True)
class UnionOutcome:
    status: str
    baseline_result_sha256: str
    final_result_sha256: str
    baseline_bytes_preserved: bool
    slack_observed_seconds: float
    replay_attempted: bool
    side_hp_attempted: int
    side_restoration_attempted: int
    novel_descriptor_count: int
    finished_before_deadline: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "policy": POLICY_ID,
            "status": self.status,
            "baseline_result_sha256": self.baseline_result_sha256,
            "final_result_sha256": self.final_result_sha256,
            "baseline_bytes_preserved": self.baseline_bytes_preserved,
            "slack_observed_seconds": self.slack_observed_seconds,
            "replay_attempted": self.replay_attempted,
            "side_hp_attempted": self.side_hp_attempted,
            "side_restoration_attempted": self.side_restoration_attempted,
            "novel_descriptor_count": self.novel_descriptor_count,
            "finished_before_deadline": self.finished_before_deadline,
        }


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".partial", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _read_json(path: Path) -> dict[str, object] | None:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return document if isinstance(document, dict) else None


def _baseline_descriptor_map(
    base: Any, result: Mapping[str, object]
) -> dict[str, dict[str, object]] | None:
    rows = result.get("distinct_exact_target_descriptors")
    if not isinstance(rows, list):
        return None
    descriptors: dict[str, dict[str, object]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            return None
        descriptor = dict(row)
        descriptors.setdefault(base._descriptor_key(descriptor), descriptor)
    if result.get("distinct_exact_target_count") != len(descriptors):
        return None
    return descriptors


def _attempted_endpoint_hashes(result: Mapping[str, object]) -> set[str] | None:
    rows = result.get("hp_attempts")
    if not isinstance(rows, list):
        return None
    hashes: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            return None
        digest = row.get("endpoint_float64_sha256")
        if isinstance(digest, str) and len(digest) == 64:
            hashes.add(digest)
    return hashes


def _rank_side_candidates(
    base: Any,
    candidates: Sequence[Any],
    authoritative: Sequence[Any],
) -> tuple[Any, ...]:
    """Truth-free novelty order; never used as answer authority."""

    ordered = tuple(candidates)
    if len(ordered) < 2:
        return ordered

    residual_order = sorted(
        ordered, key=lambda item: (item.residual_inf, item.endpoint_sha256)
    )
    residual_rank = {
        candidate.endpoint_sha256: rank
        for rank, candidate in enumerate(residual_order)
    }

    def priority(candidate: Any) -> tuple[object, ...]:
        if authoritative:
            target_novelty = min(
                abs(candidate.provisional_target - accepted.provisional_target)
                for accepted in authoritative
            )
            configuration_novelty = min(
                base._configuration_distance(candidate, accepted)
                for accepted in authoritative
            )
        else:
            target_novelty = 0.0
            configuration_novelty = 0.0
        return (
            -target_novelty if math.isfinite(target_novelty) else math.inf,
            -configuration_novelty
            if math.isfinite(configuration_novelty)
            else math.inf,
            residual_rank[candidate.endpoint_sha256],
            candidate.residual_inf,
            candidate.endpoint_sha256,
        )

    return tuple(sorted(ordered, key=priority))


def _authority_candidates(
    candidates: Sequence[Any], result: Mapping[str, object]
) -> tuple[Any, ...]:
    rows = result.get("hp_attempts")
    if not isinstance(rows, list):
        return ()
    successful = {
        row.get("endpoint_float64_sha256")
        for row in rows
        if isinstance(row, Mapping) and row.get("authority_pass") is True
    }
    return tuple(
        candidate
        for candidate in candidates
        if candidate.endpoint_sha256 in successful
    )


def _record_novel_descriptor(
    base: Any,
    descriptors: dict[str, dict[str, object]],
    attempt: Mapping[str, object],
) -> bool:
    descriptor = attempt.get("descriptor")
    if attempt.get("authority_pass") is not True or not isinstance(
        descriptor, Mapping
    ):
        return False
    key = base._descriptor_key(descriptor)
    if key in descriptors:
        return False
    descriptors[key] = dict(descriptor)
    return True


def _unchanged_outcome(
    *,
    status: str,
    baseline_sha256: str,
    baseline_path: Path,
    initial_slack: float,
    replay_attempted: bool = False,
    side_hp_attempted: int = 0,
    side_restoration_attempted: int = 0,
    hard_deadline: float,
) -> UnionOutcome:
    final_payload = baseline_path.read_bytes()
    final_sha256 = _sha256(final_payload)
    return UnionOutcome(
        status=status,
        baseline_result_sha256=baseline_sha256,
        final_result_sha256=final_sha256,
        baseline_bytes_preserved=final_sha256 == baseline_sha256,
        slack_observed_seconds=initial_slack,
        replay_attempted=replay_attempted,
        side_hp_attempted=side_hp_attempted,
        side_restoration_attempted=side_restoration_attempted,
        novel_descriptor_count=0,
        finished_before_deadline=time.monotonic() <= hard_deadline,
    )


def extend_frozen_result(
    base: Any,
    *,
    source: Path,
    source_sha256: str,
    total_seconds: float,
    cpu: int,
    output: Path,
) -> UnionOutcome:
    """Append a side descriptor only after the frozen RESULT is complete."""

    output = output.resolve()
    result_path = output / "RESULT.json"
    baseline_payload = result_path.read_bytes()
    baseline_sha256 = _sha256(baseline_payload)
    baseline_result = json.loads(baseline_payload)
    if not isinstance(baseline_result, dict):
        raise RuntimeError("frozen RESULT must be an object")
    if (
        baseline_result.get("schema_version") != base.SCHEMA
        or baseline_result.get("completed") is not True
        or baseline_result.get("source_sha256") != source_sha256
        or baseline_result.get("source_bytes_unchanged") is not True
    ):
        raise RuntimeError("frozen RESULT contract failed before side union")

    hard_deadline = base.PROCESS_STARTED + total_seconds
    initial_slack = max(0.0, hard_deadline - time.monotonic())
    minimum_window = (
        REPLAY_MIN_SECONDS
        + base.MIN_HP_ATTEMPT_SECONDS
        + SNAPSHOT_AND_UNION_RESERVE_SECONDS
    )
    if initial_slack < minimum_window:
        return _unchanged_outcome(
            status="NO_ADMISSIBLE_SLACK",
            baseline_sha256=baseline_sha256,
            baseline_path=result_path,
            initial_slack=initial_slack,
            hard_deadline=hard_deadline,
        )

    source_payload = source.read_bytes()
    if _sha256(source_payload) != source_sha256:
        raise RuntimeError("source changed after frozen RESULT")
    source_document = json.loads(source_payload)
    search = _read_json(output / "search.json")
    endpoints = search.get("endpoints") if isinstance(search, Mapping) else None
    if not isinstance(source_document, dict) or not isinstance(endpoints, list):
        return _unchanged_outcome(
            status="REPLAY_INPUT_UNAVAILABLE",
            baseline_sha256=baseline_sha256,
            baseline_path=result_path,
            initial_slack=initial_slack,
            hard_deadline=hard_deadline,
        )

    replay_budget = min(
        REPLAY_MAX_SECONDS,
        hard_deadline
        - time.monotonic()
        - base.MIN_HP_ATTEMPT_SECONDS
        - SNAPSHOT_AND_UNION_RESERVE_SECONDS,
    )
    if replay_budget < REPLAY_MIN_SECONDS:
        return _unchanged_outcome(
            status="REPLAY_SLACK_EVAPORATED",
            baseline_sha256=baseline_sha256,
            baseline_path=result_path,
            initial_slack=initial_slack,
            hard_deadline=hard_deadline,
        )
    candidates = base._fresh_replay_candidates(
        source_document,
        endpoints,
        hard_deadline=time.monotonic() + replay_budget,
    )
    attempted_hashes = _attempted_endpoint_hashes(baseline_result)
    descriptors = _baseline_descriptor_map(base, baseline_result)
    if attempted_hashes is None or descriptors is None:
        raise RuntimeError("frozen RESULT HP/descriptor accounting is malformed")
    pending = tuple(
        candidate
        for candidate in candidates
        if candidate.endpoint_sha256 not in attempted_hashes
    )
    if not pending:
        return _unchanged_outcome(
            status="NO_UNATTEMPTED_REPLAY_CANDIDATE",
            baseline_sha256=baseline_sha256,
            baseline_path=result_path,
            initial_slack=initial_slack,
            replay_attempted=True,
            hard_deadline=hard_deadline,
        )

    authoritative = _authority_candidates(candidates, baseline_result)
    candidate = _rank_side_candidates(base, pending, authoritative)[0]

    # Retain the already materialized baseline bytes before starting any side
    # HP. If the snapshot cannot fit, fail closed with RESULT untouched.
    remaining = hard_deadline - time.monotonic()
    if remaining < base.MIN_HP_ATTEMPT_SECONDS + SNAPSHOT_AND_UNION_RESERVE_SECONDS:
        return _unchanged_outcome(
            status="HP_SLACK_EVAPORATED",
            baseline_sha256=baseline_sha256,
            baseline_path=result_path,
            initial_slack=initial_slack,
            replay_attempted=True,
            hard_deadline=hard_deadline,
        )
    snapshot_path = output / BASELINE_SNAPSHOT
    _atomic_write_bytes(snapshot_path, baseline_payload)
    if snapshot_path.read_bytes() != baseline_payload:
        raise RuntimeError("byte-exact baseline snapshot failed")

    timeout_seconds = min(
        MAX_SIDE_HP_SECONDS,
        hard_deadline - time.monotonic() - SNAPSHOT_AND_UNION_RESERVE_SECONDS,
    )
    if timeout_seconds < base.MIN_HP_ATTEMPT_SECONDS:
        return _unchanged_outcome(
            status="HP_SLACK_EVAPORATED_AFTER_SNAPSHOT",
            baseline_sha256=baseline_sha256,
            baseline_path=result_path,
            initial_slack=initial_slack,
            replay_attempted=True,
            hard_deadline=hard_deadline,
        )

    side_output = (
        output
        / SIDE_DIRECTORY
        / "hp"
        / f"{candidate.endpoint_sha256[:16]}"
    )
    hp_attempt = base._run_hp_candidate(
        source=source,
        source_sha256=source_sha256,
        candidate=candidate,
        cpu=cpu,
        output=side_output,
        timeout_seconds=timeout_seconds,
    )
    side_attempts: list[dict[str, object]] = [hp_attempt]
    novel_count = int(_record_novel_descriptor(base, descriptors, hp_attempt))
    restoration_attempted = 0

    # Restoration is failure-triggered and uses only this new side artifact;
    # no baseline HP or restoration artifact is rerun.
    if novel_count == 0 and hp_attempt.get("authority_pass") is not True:
        restoration_timeout = min(
            base.MAX_RESTORATION_ATTEMPT_SECONDS,
            hard_deadline - time.monotonic() - SNAPSHOT_AND_UNION_RESERVE_SECONDS,
        )
        if restoration_timeout >= base.MIN_HP_ATTEMPT_SECONDS:
            restoration = base._run_restoration_candidate(
                source=source,
                source_sha256=source_sha256,
                candidate=candidate,
                cpu=cpu,
                failed_authority_artifact=side_output / "authority.json",
                output=output / SIDE_DIRECTORY / "restoration",
                timeout_seconds=restoration_timeout,
            )
            side_attempts.append(restoration)
            restoration_attempted = 1
            novel_count += int(
                _record_novel_descriptor(base, descriptors, restoration)
            )

    if novel_count == 0:
        return _unchanged_outcome(
            status="SIDE_AUTHORITY_NO_NOVEL_DESCRIPTOR",
            baseline_sha256=baseline_sha256,
            baseline_path=result_path,
            initial_slack=initial_slack,
            replay_attempted=True,
            side_hp_attempted=1,
            side_restoration_attempted=restoration_attempted,
            hard_deadline=hard_deadline,
        )

    # A descriptor may be published only while the reserved finalization
    # interval is still intact. Otherwise the byte-exact baseline remains.
    if time.monotonic() > hard_deadline - SNAPSHOT_AND_UNION_RESERVE_SECONDS:
        return _unchanged_outcome(
            status="UNION_RESERVE_EXHAUSTED",
            baseline_sha256=baseline_sha256,
            baseline_path=result_path,
            initial_slack=initial_slack,
            replay_attempted=True,
            side_hp_attempted=1,
            side_restoration_attempted=restoration_attempted,
            hard_deadline=hard_deadline,
        )

    union_result = dict(baseline_result)
    exact_targets = [descriptors[key] for key in sorted(descriptors)]
    baseline_attempts = baseline_result.get("hp_attempts")
    if not isinstance(baseline_attempts, list):
        raise RuntimeError("frozen hp_attempts changed during union")
    union_result["hp_attempts"] = [*baseline_attempts, *side_attempts]
    union_result["hp_attempt_count"] = len(union_result["hp_attempts"])
    baseline_schedule = baseline_result.get("hp_schedule")
    union_schedule = (
        dict(baseline_schedule) if isinstance(baseline_schedule, Mapping) else {}
    )
    union_schedule["post_baseline_union"] = {
        "policy": POLICY_ID,
        "baseline_result_sha256": baseline_sha256,
        "baseline_trace_retained_as_prefix": True,
        "side_hp_attempted": 1,
        "side_restoration_attempted": restoration_attempted,
        "novel_descriptor_count": novel_count,
        "truth_case_family_known_target_count_read": False,
    }
    union_result["hp_schedule"] = union_schedule
    union_result["distinct_exact_targets"] = exact_targets
    union_result["distinct_exact_target_descriptors"] = exact_targets
    union_result["distinct_exact_target_count"] = len(descriptors)
    elapsed = time.monotonic() - base.PROCESS_STARTED
    union_result["elapsed_wall_seconds"] = elapsed
    union_result["within_total_wall_budget"] = elapsed <= total_seconds
    base.atomic_write_json(result_path, union_result)
    final_payload = result_path.read_bytes()
    final_sha256 = _sha256(final_payload)
    finished = time.monotonic()
    if finished > hard_deadline:
        # Fail closed on an unexpected filesystem stall. This cannot recover
        # wall time, but it prevents a late side descriptor from replacing the
        # already valid frozen answer.
        _atomic_write_bytes(result_path, baseline_payload)
        return _unchanged_outcome(
            status="UNION_WRITE_DEADLINE_MISSED",
            baseline_sha256=baseline_sha256,
            baseline_path=result_path,
            initial_slack=initial_slack,
            replay_attempted=True,
            side_hp_attempted=1,
            side_restoration_attempted=restoration_attempted,
            hard_deadline=hard_deadline,
        )
    return UnionOutcome(
        status="NOVEL_DESCRIPTOR_UNIONED",
        baseline_result_sha256=baseline_sha256,
        final_result_sha256=final_sha256,
        baseline_bytes_preserved=snapshot_path.read_bytes() == baseline_payload,
        slack_observed_seconds=initial_slack,
        replay_attempted=True,
        side_hp_attempted=1,
        side_restoration_attempted=restoration_attempted,
        novel_descriptor_count=novel_count,
        finished_before_deadline=finished <= hard_deadline,
    )
