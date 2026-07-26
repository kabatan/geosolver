from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from geotarget.continuation import _pending_candidates
from geotarget.parallel import service_candidates_parallel


@dataclass(frozen=True)
class Candidate:
    record_id: str
    endpoint_sha256: str
    cluster_ordinal: int
    cluster_rank: int = 0


class Reservoir(tuple):
    def __new__(cls, verified, backlog=()):
        value = super().__new__(cls, verified)
        value.deadline_backlog = tuple(backlog)
        return value


class PendingBase:
    SELECTION_RESERVE_SECONDS = 3.0

    def _fresh_replay_candidates(self, document, endpoints, *, hard_deadline):
        del document, endpoints, hard_deadline
        return Reservoir(
            (Candidate("r0", "0" * 64, 0), Candidate("r1", "1" * 64, 1)),
            (Candidate("r2", "2" * 64, 2),),
        )


def test_continuation_selects_only_frozen_deferred_record_ids() -> None:
    selected = _pending_candidates(
        PendingBase(),
        {},
        {"endpoints": [1]},
        {"hp_schedule": {"deferred_record_ids": ["r1", "r2"]}},
        time.monotonic() + 30,
    )
    assert [candidate.record_id for candidate in selected] == ["r1"]
    assert [candidate.record_id for candidate in selected.deadline_backlog] == ["r2"]


class ParallelBase:
    FINALIZE_RESERVE_SECONDS = 0.0
    MIN_HP_ATTEMPT_SECONDS = 0.01
    MAX_HP_ATTEMPT_SECONDS = 1.0
    MAX_RESTORATION_ATTEMPT_SECONDS = 1.0

    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    @staticmethod
    def _primary_tranche_capacity(remaining, count):
        del remaining
        return count

    @staticmethod
    def _select_primary_tranche(primaries, capacity):
        return primaries[:capacity], primaries[capacity:]

    @staticmethod
    def _wave_attempt_seconds(remaining, count, cap):
        return min(cap, remaining / count) if remaining > 0 and count else 0.0

    @staticmethod
    def _descriptor_key(descriptor):
        return str(descriptor["selected_real_root_index"])

    @staticmethod
    def _same_cluster_authority_exists(candidate, successful):
        return candidate.cluster_ordinal in successful

    def _run_hp_candidate(self, *, candidate, cpu, **kwargs):
        del kwargs
        time.sleep(0.003 * (3 - candidate.cluster_ordinal))
        self.calls.append((candidate.record_id, cpu))
        return {
            "record_id": candidate.record_id,
            "authority_pass": True,
            "descriptor": {
                "minimal_polynomial_high_to_low": [1, -candidate.cluster_ordinal],
                "selected_real_root_index": candidate.cluster_ordinal,
            },
        }

    def _run_restoration_candidate(self, **kwargs):
        raise AssertionError(f"unexpected restoration: {kwargs}")


def test_parallel_wave_merges_attempts_in_stable_ordinal_order(tmp_path: Path) -> None:
    base = ParallelBase()
    candidates = tuple(Candidate(f"r{ordinal}", str(ordinal) * 64, ordinal) for ordinal in range(4))
    attempts, descriptors, statistics = service_candidates_parallel(
        base=base,
        source=tmp_path / "problem.json",
        source_sha256="a" * 64,
        candidates=candidates,
        output=tmp_path,
        hard_deadline=time.monotonic() + 10,
        cpus=(2, 4),
    )
    assert [attempt["record_id"] for attempt in attempts] == ["r0", "r1", "r2", "r3"]
    assert list(descriptors) == ["0", "1", "2", "3"]
    assert statistics["parallel_physical_cpus"] == [2, 4]
    assert statistics["stable_attempt_merge"] is True
