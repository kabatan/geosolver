"""Minimal proposal-only 75/25 seam; no Difference-Map implementation."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping, Sequence


BETA = 1.0
FIXED_ITERATIONS = 64
BASELINE_NUMERATOR = 3
SIDE_DENOMINATOR = 4


@dataclass(frozen=True)
class Partition:
    baseline_ordinals: tuple[int, ...]
    side_ordinals: tuple[int, ...]
    activated: bool
    reason: str


def _gate_pass(source_scan: Mapping[str, Any], recurrence: Mapping[str, Any]) -> bool:
    return bool(
        source_scan.get("eligible") is True
        and source_scan.get("decision") == "STATIC_GATE_PASS"
        and recurrence.get("recurrence_gate_pass") is True
        and recurrence.get("eligible_attempt_count", 0) >= 4
        and recurrence.get("anonymous_eligible_hash_count", 0) >= 2
    )


def partition_starts(
    start_count: int,
    source_scan: Mapping[str, Any],
    recurrence: Mapping[str, Any],
) -> Partition:
    if not isinstance(start_count, int) or isinstance(start_count, bool) or start_count < 0:
        raise ValueError("start_count must be a nonnegative integer")
    if not _gate_pass(source_scan, recurrence):
        return Partition(tuple(range(start_count)), (), False, "STATIC_OR_RECURRENCE_GATE_HOLD")
    # The fourth start in each source-fixed block is the proposal-only side.
    side = tuple(index for index in range(start_count) if index % SIDE_DENOMINATOR == 3)
    side_set = set(side)
    baseline = tuple(index for index in range(start_count) if index not in side_set)
    if len(side) * SIDE_DENOMINATOR > start_count:
        raise AssertionError("side allocation exceeded one quarter")
    if len(baseline) * SIDE_DENOMINATOR < BASELINE_NUMERATOR * start_count:
        raise AssertionError("baseline allocation fell below three quarters")
    return Partition(baseline, side, True, "SOURCE_FIXED_OPERATOR_GRAPH")


def replica_weights(replica_count: int) -> tuple[float, ...]:
    if not isinstance(replica_count, int) or isinstance(replica_count, bool) or not 1 <= replica_count <= 4:
        raise ValueError("replica_count must match factor arity 1..4")
    weight = 1.0 / replica_count
    result = tuple(weight for _ in range(replica_count))
    if not math.isclose(sum(result), 1.0, rel_tol=0.0, abs_tol=1.0e-15):
        raise AssertionError("factor duplication weight is not one")
    return result


def proposal_disposition(terminal: object) -> str:
    if not isinstance(terminal, Mapping):
        return "FULL_ATTEMPT_BASELINE_FALLBACK"
    status = terminal.get("status")
    if status == "UNKNOWN_FULL_ATTEMPT_FALLBACK":
        return "FULL_ATTEMPT_BASELINE_FALLBACK"
    if (
        status == "DIVIDE_CONCUR_PROPOSAL_ONLY"
        and terminal.get("authority_pass") is False
        and terminal.get("descriptor") is None
        and terminal.get("beta") == BETA
        and terminal.get("fixed_iterations") == FIXED_ITERATIONS
        and terminal.get("canonical_lm_required") is True
        and terminal.get("canonical_source_replay_required") is True
        and terminal.get("truth_used") is False
    ):
        return "SEND_TO_CANONICAL_LM_AND_REPLAY"
    return "FULL_ATTEMPT_BASELINE_FALLBACK"


def canonical_authority_ready(terminal: object) -> bool:
    return bool(
        isinstance(terminal, Mapping)
        and terminal.get("status") == "TARGET_AUTHORITY_READY"
        and terminal.get("authority_pass") is True
        and isinstance(terminal.get("descriptor"), Mapping)
        and terminal.get("canonical_lm_completed") is True
        and terminal.get("canonical_source_replay_exact") is True
        and terminal.get("guard_replay_exact") is True
        and terminal.get("branch_replay_exact") is True
        and terminal.get("raw_target_replay_exact") is True
        and terminal.get("proposal_was_authority") is False
    )


def connector_manifest() -> dict[str, Any]:
    return {
        "candidate": "OPERATOR_GRAPH_DIVIDE_CONCUR_V1",
        "beta": BETA,
        "fixed_iterations": FIXED_ITERATIONS,
        "baseline_start_fraction_minimum": 0.75,
        "side_start_fraction_maximum": 0.25,
        "proposal_only": True,
        "canonical_lm_and_replay_required": True,
        "unknown_full_attempt_fallback": True,
        "dimensionless_replica_normalization": True,
        "factor_duplication_total_weight": 1,
        "worker_binding_installed": False,
        "binding_condition": "real static recurrence gate pass",
        "truth_case_family_target_or_result_routing": False,
    }


__all__ = [
    "BETA", "FIXED_ITERATIONS", "Partition", "canonical_authority_ready",
    "connector_manifest", "partition_starts", "proposal_disposition",
    "replica_weights",
]
