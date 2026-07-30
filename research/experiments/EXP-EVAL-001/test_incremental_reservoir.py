from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path

import pytest

from incremental_reservoir import (
    IncrementalCheckpointCorrupt,
    Observation,
    ReservoirSnapshot,
    incremental_candidates,
)


def _endpoint_sha(endpoint: tuple[float, ...]) -> str:
    payload = json.dumps(endpoint, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class Candidate:
    endpoint: tuple[float, ...]
    endpoint_sha256: str
    residual_inf: float
    provisional_target: float | None = None
    cluster_ordinal: int = 0
    cluster_rank: int = 0
    discovery_ordinal: int = 0
    admission_role: str = "RAW_SAFE"
    record_id: str = ""
    bucket_id: str = "anonymous"
    bucket_kind: str = "ANONYMOUS"
    aging_wave: int = 0
    semantic_verified: bool = True


class FakeAdapter:
    def __init__(self) -> None:
        self.evaluations = 0

    @staticmethod
    def _observation(ordinal: int, row: object) -> Observation | None:
        if not isinstance(row, dict) or not isinstance(row.get("point"), list):
            return None
        endpoint = tuple(float(value) for value in row["point"])
        if any(not math.isfinite(value) for value in endpoint):
            return None
        residual = abs(math.sin(endpoint[0]) + math.cos(endpoint[-1])) * 1e-4
        semantic = not bool(row.get("backlog"))
        return Observation(
            endpoint=endpoint,
            endpoint_sha256=_endpoint_sha(endpoint),
            residual_inf=residual if semantic else 1e-3,
            provisional_target=None,
            discovery_ordinal=ordinal,
            admission_role="RAW_SAFE" if semantic else "DEADLINE_BACKLOG",
            semantic_verified=semantic,
        )

    def full_replay(self, source_document, endpoints, *, hard_deadline):
        del source_document, hard_deadline
        observations = []
        for ordinal, row in enumerate(endpoints):
            self.evaluations += 1
            observation = self._observation(ordinal, row)
            if observation is not None:
                observations.append(observation)
        return self.plan(observations)

    @staticmethod
    def observations_from_reservoir(reservoir):
        candidates = tuple(reservoir) + tuple(reservoir.deadline_backlog)
        return tuple(
            Observation(
                value.endpoint,
                value.endpoint_sha256,
                value.residual_inf,
                value.provisional_target,
                value.discovery_ordinal,
                value.admission_role,
                value.semantic_verified,
            )
            for value in sorted(candidates, key=lambda item: item.discovery_ordinal)
        )

    def scan_indexed(self, source_document, indexed_endpoints, *, hard_deadline):
        del source_document, hard_deadline
        values = []
        for ordinal, row in indexed_endpoints:
            self.evaluations += 1
            # A previous deadline row is represented only by its point and is
            # therefore retried as a verified semantic replay.
            observation = self._observation(ordinal, row)
            if observation is not None:
                values.append(observation)
        return tuple(values)

    @staticmethod
    def plan(observations):
        order = sorted(
            observations,
            key=lambda value: (
                not value.semantic_verified,
                value.residual_inf,
                value.discovery_ordinal,
            ),
        )
        converted = tuple(
            Candidate(
                endpoint=value.endpoint,
                endpoint_sha256=value.endpoint_sha256,
                residual_inf=value.residual_inf,
                cluster_ordinal=cluster,
                discovery_ordinal=value.discovery_ordinal,
                admission_role=value.admission_role,
                record_id=f"{value.discovery_ordinal:012d}:{value.endpoint_sha256}",
                aging_wave=cluster,
                semantic_verified=value.semantic_verified,
            )
            for cluster, value in enumerate(order)
        )
        return ReservoirSnapshot(
            tuple(value for value in converted if value.semantic_verified),
            tuple(value for value in converted if not value.semantic_verified),
        )


def _search(endpoints, *, callbacks=0, arm="candidate"):
    return {
        "arm": arm,
        "seed": 0,
        "endpoints": list(endpoints),
        "literal_prefix": {"full_prefix_sha256": "a" * 64},
        "optimized_parallel_search": {"completed_start_ordinals": []},
        "work": {"callbacks": callbacks},
        "budget": {"starts": 256, "callbacks_per_start": 600},
    }


def _characterize(reservoir):
    candidates = tuple(reservoir) + tuple(reservoir.deadline_backlog)
    return tuple(
        (
            candidate.endpoint,
            candidate.endpoint_sha256,
            candidate.residual_inf.hex(),
            candidate.cluster_ordinal,
            candidate.discovery_ordinal,
            candidate.admission_role,
            candidate.record_id,
            candidate.aging_wave,
            candidate.semantic_verified,
        )
        for candidate in candidates
    )


def test_append_windows_are_bit_identical_to_full_replay(tmp_path: Path) -> None:
    randomizer = random.Random(81357)
    endpoints = [
        {"lane": index, "point": [randomizer.uniform(-8, 8), randomizer.uniform(-8, 8)]}
        for index in range(512)
    ]
    checkpoint = None
    candidate_adapter = FakeAdapter()
    bit_matches = 0
    for window, end in enumerate((32, 64, 96, 160, 256, 384, 512), start=1):
        search = _search(endpoints[:end], callbacks=end * 600)
        output = tmp_path / f"reservoir-{window}.json"
        observed = incremental_candidates(
            adapter=candidate_adapter,
            source_document={},
            search=search,
            source_sha256="f" * 64,
            checkpoint_input=checkpoint,
            checkpoint_output=output,
            hard_deadline=math.inf,
            candidate_type=Candidate,
            reservoir_type=ReservoirSnapshot,
        )
        control_adapter = FakeAdapter()
        expected = control_adapter.full_replay({}, endpoints[:end], hard_deadline=math.inf)
        assert _characterize(observed.reservoir) == _characterize(expected)
        bit_matches += len(expected)
        checkpoint = output

    assert bit_matches == 1504
    assert candidate_adapter.evaluations == 512
    assert sum((32, 64, 96, 160, 256, 384, 512)) == 1504


def test_exact_hit_replays_nothing(tmp_path: Path) -> None:
    adapter = FakeAdapter()
    search = _search([{"lane": 0, "point": [1.0, 2.0]}], callbacks=600)
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    initial = incremental_candidates(
        adapter=adapter,
        source_document={},
        search=search,
        source_sha256="f" * 64,
        checkpoint_input=None,
        checkpoint_output=first,
        hard_deadline=math.inf,
        candidate_type=Candidate,
        reservoir_type=ReservoirSnapshot,
    )
    cached = incremental_candidates(
        adapter=adapter,
        source_document={},
        search=search,
        source_sha256="f" * 64,
        checkpoint_input=first,
        checkpoint_output=second,
        hard_deadline=math.inf,
        candidate_type=Candidate,
        reservoir_type=ReservoirSnapshot,
    )
    assert initial.mode == "full-replay"
    assert cached.mode == "exact-hit"
    assert adapter.evaluations == 1
    assert _characterize(cached.reservoir) == _characterize(initial.reservoir)


def test_prefix_mutation_or_plan_change_falls_back_to_full_replay(tmp_path: Path) -> None:
    adapter = FakeAdapter()
    original = _search([{"lane": 0, "point": [1.0]}])
    checkpoint = tmp_path / "checkpoint.json"
    incremental_candidates(
        adapter=adapter,
        source_document={},
        search=original,
        source_sha256="f" * 64,
        checkpoint_input=None,
        checkpoint_output=checkpoint,
        hard_deadline=math.inf,
        candidate_type=Candidate,
        reservoir_type=ReservoirSnapshot,
    )
    mutated = _search(
        [{"lane": 0, "point": [2.0]}, {"lane": 1, "point": [3.0]}]
    )
    result = incremental_candidates(
        adapter=adapter,
        source_document={},
        search=mutated,
        source_sha256="f" * 64,
        checkpoint_input=checkpoint,
        checkpoint_output=None,
        hard_deadline=math.inf,
        candidate_type=Candidate,
        reservoir_type=ReservoirSnapshot,
    )
    changed_arm = incremental_candidates(
        adapter=adapter,
        source_document={},
        search=_search(mutated["endpoints"], arm="other"),
        source_sha256="f" * 64,
        checkpoint_input=checkpoint,
        checkpoint_output=None,
        hard_deadline=math.inf,
        candidate_type=Candidate,
        reservoir_type=ReservoirSnapshot,
    )
    assert result.mode == changed_arm.mode == "full-replay"


def test_backlog_is_retried_when_suffix_arrives(tmp_path: Path) -> None:
    adapter = FakeAdapter()
    first_search = _search([{"lane": 0, "point": [1.0], "backlog": True}])
    checkpoint = tmp_path / "first.json"
    first = incremental_candidates(
        adapter=adapter,
        source_document={},
        search=first_search,
        source_sha256="f" * 64,
        checkpoint_input=None,
        checkpoint_output=checkpoint,
        hard_deadline=math.inf,
        candidate_type=Candidate,
        reservoir_type=ReservoirSnapshot,
    )
    second = incremental_candidates(
        adapter=adapter,
        source_document={},
        search=_search(
            [
                {"lane": 0, "point": [1.0], "backlog": True},
                {"lane": 1, "point": [2.0]},
            ]
        ),
        source_sha256="f" * 64,
        checkpoint_input=checkpoint,
        checkpoint_output=None,
        hard_deadline=math.inf,
        candidate_type=Candidate,
        reservoir_type=ReservoirSnapshot,
    )
    assert len(first.reservoir.deadline_backlog) == 1
    assert second.mode == "prefix-extend"
    assert second.retried_backlog_count == 1
    assert len(second.reservoir) == 2
    assert not second.reservoir.deadline_backlog


def test_previously_unobserved_ordinal_is_not_permanently_discarded(
    tmp_path: Path,
) -> None:
    adapter = FakeAdapter()
    first_search = _search([{"lane": 0, "malformed": True}])
    checkpoint = tmp_path / "first.json"
    first = incremental_candidates(
        adapter=adapter,
        source_document={},
        search=first_search,
        source_sha256="f" * 64,
        checkpoint_input=None,
        checkpoint_output=checkpoint,
        hard_deadline=math.inf,
        candidate_type=Candidate,
        reservoir_type=ReservoirSnapshot,
    )
    second = incremental_candidates(
        adapter=adapter,
        source_document={},
        search=_search(
            [
                {"lane": 0, "malformed": True},
                {"lane": 1, "point": [2.0]},
            ]
        ),
        source_sha256="f" * 64,
        checkpoint_input=checkpoint,
        checkpoint_output=None,
        hard_deadline=math.inf,
        candidate_type=Candidate,
        reservoir_type=ReservoirSnapshot,
    )
    assert not first.reservoir
    assert second.mode == "prefix-extend"
    assert second.retried_unobserved_count == 1
    assert second.semantic_replay_count == 2
    assert len(second.reservoir) == 1


@pytest.mark.parametrize("mutation", ["truncate", "tamper"])
def test_same_schema_corruption_fails_closed(tmp_path: Path, mutation: str) -> None:
    adapter = FakeAdapter()
    search = _search([{"lane": 0, "point": [1.0]}])
    checkpoint = tmp_path / "checkpoint.json"
    incremental_candidates(
        adapter=adapter,
        source_document={},
        search=search,
        source_sha256="f" * 64,
        checkpoint_input=None,
        checkpoint_output=checkpoint,
        hard_deadline=math.inf,
        candidate_type=Candidate,
        reservoir_type=ReservoirSnapshot,
    )
    if mutation == "truncate":
        checkpoint.write_text(checkpoint.read_text()[:40])
    else:
        document = json.loads(checkpoint.read_text())
        document["reservoir"]["verified"][0]["record_id"] = "tampered"
        checkpoint.write_text(json.dumps(document))
    with pytest.raises(IncrementalCheckpointCorrupt):
        incremental_candidates(
            adapter=adapter,
            source_document={},
            search=search,
            source_sha256="f" * 64,
            checkpoint_input=checkpoint,
            checkpoint_output=None,
            hard_deadline=math.inf,
            candidate_type=Candidate,
            reservoir_type=ReservoirSnapshot,
        )
