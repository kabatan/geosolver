from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import sys
import time

import pytest


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import candidate  # noqa: E402
import worker  # noqa: E402


@dataclass(frozen=True)
class ReplayCandidate:
    endpoint: tuple[float, ...]
    endpoint_sha256: str
    residual_inf: float
    provisional_target: float
    cluster_ordinal: int
    cluster_rank: int


def _item(
    point: float,
    residual: float,
    target: float,
    cluster: int,
    rank: int = 0,
) -> ReplayCandidate:
    digest = hashlib.sha256(f"{point!r}".encode()).hexdigest()
    return ReplayCandidate((point,), digest, residual, target, cluster, rank)


class FakeBase:
    FINALIZE_RESERVE_SECONDS = 2.0
    MIN_HP_ATTEMPT_SECONDS = 3.0
    MAX_HP_ATTEMPT_SECONDS = 18.0
    MAX_RESTORATION_ATTEMPT_SECONDS = 12.0

    def __init__(self, outcomes: dict[str, dict[str, object]]) -> None:
        self.outcomes = outcomes
        self.events: list[tuple[str, str]] = []

    @staticmethod
    def _normalized_target_distance(left: ReplayCandidate, right: ReplayCandidate) -> float:
        scale = max(abs(left.provisional_target), abs(right.provisional_target), 1.0)
        return abs(left.provisional_target - right.provisional_target) / scale

    @staticmethod
    def _configuration_distance(left: ReplayCandidate, right: ReplayCandidate) -> float:
        scale = abs(left.endpoint[0]) + abs(right.endpoint[0])
        return abs(left.endpoint[0] - right.endpoint[0]) / max(scale, 1.0)

    @staticmethod
    def _primary_tranche_capacity(remaining: float, count: int) -> int:
        return candidate._tranche_capacity(remaining, count, 18.0, 3.0)

    @staticmethod
    def _select_primary_tranche(items, capacity):
        ordered = tuple(sorted(items, key=lambda item: item[1].residual_inf))
        return ordered[:capacity], ordered[capacity:]

    @staticmethod
    def _wave_attempt_seconds(remaining: float, count: int, maximum: float) -> float:
        reserve = 3.0 * (count - 1)
        admitted = min(maximum, remaining - reserve)
        return admitted if admitted >= 3.0 else 0.0

    @staticmethod
    def _descriptor_key(descriptor):
        return str((descriptor["minimal_polynomial_high_to_low"], descriptor["selected_real_root_index"]))

    def _run_hp_candidate(self, **kwargs):
        item = kwargs["candidate"]
        self.events.append(("hp", item.endpoint_sha256))
        return self.outcomes.get(
            item.endpoint_sha256, {"authority_pass": False, "descriptor": None}
        )

    def _run_restoration_candidate(self, **kwargs):
        item = kwargs["candidate"]
        self.events.append(("restoration", item.endpoint_sha256))
        return {"authority_pass": False, "descriptor": None}


def _authority(root: int) -> dict[str, object]:
    return {
        "authority_pass": True,
        "descriptor": {
            "minimal_polynomial_high_to_low": [1, -root],
            "selected_real_root_index": 0,
        },
    }


def test_first_descriptor_does_not_stop_later_target() -> None:
    first = _item(0.0, 1.0e-12, 0.0, 0)
    second = _item(100.0, 2.0e-12, 100.0, 1)
    base = FakeBase(
        {first.endpoint_sha256: _authority(1), second.endpoint_sha256: _authority(2)}
    )
    attempts, descriptors, schedule = candidate.service_candidates(
        base,
        source=Path("source.json"),
        source_sha256="a" * 64,
        candidates=(first, second),
        cpu=0,
        output=Path("out"),
        hard_deadline=time.monotonic() + 40.0,
    )
    assert len(attempts) == 2
    assert len(descriptors) == 2
    assert schedule["attempts_after_first_authority"] == 1
    assert schedule["authority_attempt_ordinals"] == [0, 1]


def test_same_provisional_target_alternate_is_not_suppressed() -> None:
    primary = _item(1.0, 1.0e-12, 10.0, 0, 0)
    alternate = _item(20.0, 2.0e-12, 10.0 + 1.0e-10, 0, 1)
    base = FakeBase(
        {
            primary.endpoint_sha256: _authority(1),
            alternate.endpoint_sha256: _authority(2),
        }
    )
    _attempts, descriptors, schedule = candidate.service_candidates(
        base,
        source=Path("source.json"),
        source_sha256="b" * 64,
        candidates=(primary, alternate),
        cpu=0,
        output=Path("out"),
        hard_deadline=time.monotonic() + 40.0,
    )
    assert base.events == [
        ("hp", primary.endpoint_sha256),
        ("hp", alternate.endpoint_sha256),
    ]
    assert len(descriptors) == 2
    assert schedule["same_cluster_alternates_skipped_after_authority"] == 0
    assert schedule["same_target_candidate_suppression"] is False


def test_verified_target_diversity_reorders_pending_candidates() -> None:
    accepted = _item(0.0, 1.0e-12, 0.0, 0)
    residual_better_near = _item(0.1, 2.0e-12, 0.1, 1)
    residual_worse_far = _item(100.0, 1.0e-8, 100.0, 2)
    base = FakeBase({})
    ranked = candidate._rank_by_verified_diversity(
        base,
        ((1, residual_better_near), (2, residual_worse_far)),
        (accepted,),
    )
    assert [ordinal for ordinal, _item_value in ranked] == [2, 1]


def test_tail_reserve_keeps_fallback_capacity() -> None:
    assert candidate._tranche_capacity(6.0, 100, 6.0, 3.0) == 1
    assert candidate._tranche_capacity(12.0, 100, 6.0, 3.0) == 3
    assert candidate._tranche_capacity(2.9, 100, 6.0, 3.0) == 0
    assert candidate._tranche_capacity(3.0, 100, 6.0, 3.0) == 0
    assert candidate._tranche_capacity(3.25, 100, 6.0, 3.0) == 1


def test_frozen_worker_is_hash_bound_and_overlay_is_truth_blind() -> None:
    frozen = worker.DEFAULT_FROZEN_ROOT / worker.FROZEN_RELATIVE_WORKER
    assert frozen.is_file()
    assert worker._sha256(frozen) == worker.EXPECTED_FROZEN_WORKER_SHA256
    source = (HERE / "candidate.py").read_text(encoding="utf-8")
    assert "gold_targets" not in source
    assert "case_id" not in source
    assert '.get("known_target_count"' not in source
    assert '["known_target_count"]' not in source


def test_short_tail_requires_explicit_s0_override(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "worker.py",
            "--total-seconds",
            "30",
            "--search-seconds",
            "20",
            "--source",
            "unused.json",
            "--source-sha256",
            "a" * 64,
            "--output",
            "unused",
        ],
    )
    with pytest.raises(SystemExit, match="post-search tail"):
        worker.main()


def test_experiment_python_keeps_venv_entrypoint() -> None:
    assert worker.DEFAULT_PYTHON.is_symlink()
    assert worker.DEFAULT_PYTHON.absolute() != worker.DEFAULT_PYTHON.resolve()
