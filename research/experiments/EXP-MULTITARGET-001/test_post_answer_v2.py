from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import sys
from typing import Callable


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import candidate_v2  # noqa: E402
import worker_v2  # noqa: E402


@dataclass(frozen=True)
class CandidateSpec:
    value: float
    residual: float
    target: float
    cluster: int
    rank: int = 0

    @property
    def digest(self) -> str:
        return hashlib.sha256(f"endpoint:{self.value!r}".encode()).hexdigest()


@dataclass
class TraceClock:
    now: float = 100.0

    def monotonic(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@dataclass(frozen=True)
class TraceRun:
    events: tuple[tuple[str, ...], ...]
    attempts: tuple[dict[str, object], ...]
    descriptors: dict[str, dict[str, object]]
    statistics: dict[str, object]


def _authority(root: int) -> dict[str, object]:
    return {
        "authority_pass": True,
        "descriptor": {
            "minimal_polynomial_high_to_low": [1, -root],
            "selected_real_root_index": 0,
        },
    }


def _trace_run(
    specs: tuple[CandidateSpec, ...],
    *,
    candidate_service: bool,
    outcomes: dict[str, dict[str, object]] | None = None,
    elapsed_per_call: float = 0.25,
    hard_deadline: float = 140.0,
) -> TraceRun:
    base = worker_v2._load_frozen(worker_v2.DEFAULT_FROZEN_ROOT)
    candidates = tuple(
        base.ReplayCandidate(
            endpoint=(spec.value,),
            endpoint_sha256=spec.digest,
            residual_inf=spec.residual,
            provisional_target=spec.target,
            cluster_ordinal=spec.cluster,
            cluster_rank=spec.rank,
        )
        for spec in specs
    )
    results = outcomes or {}
    events: list[tuple[str, ...]] = []
    clock = TraceClock()

    def fake_hp(**kwargs: object) -> dict[str, object]:
        item = kwargs["candidate"]
        timeout = kwargs["timeout_seconds"]
        events.append(
            (
                "hp",
                item.endpoint_sha256,
                float(timeout).hex(),
                str(kwargs["output"]),
                str(kwargs["source"]),
                str(kwargs["source_sha256"]),
                str(kwargs["cpu"]),
            )
        )
        clock.advance(elapsed_per_call)
        return dict(
            results.get(
                item.endpoint_sha256,
                {"authority_pass": False, "descriptor": None},
            )
        )

    def fake_restoration(**kwargs: object) -> dict[str, object]:
        item = kwargs["candidate"]
        timeout = kwargs["timeout_seconds"]
        events.append(
            (
                "restoration",
                item.endpoint_sha256,
                float(timeout).hex(),
                str(kwargs["output"]),
                str(kwargs["failed_authority_artifact"]),
                str(kwargs["source"]),
                str(kwargs["source_sha256"]),
                str(kwargs["cpu"]),
            )
        )
        clock.advance(elapsed_per_call)
        return {"authority_pass": False, "descriptor": None}

    original_monotonic = base.time.monotonic
    base.time.monotonic = clock.monotonic
    base._run_hp_candidate = fake_hp
    base._run_restoration_candidate = fake_restoration
    try:
        if candidate_service:
            service: Callable[..., object] = lambda **kwargs: candidate_v2.service_candidates(
                base, **kwargs
            )
        else:
            service = base._service_candidates
        attempts, descriptors, statistics = service(
            source=Path("source.json"),
            source_sha256="a" * 64,
            candidates=candidates,
            cpu=7,
            output=Path("trace-output"),
            hard_deadline=hard_deadline,
        )
    finally:
        base.time.monotonic = original_monotonic
    return TraceRun(
        tuple(events), tuple(attempts), descriptors, statistics
    )


def _baseline_statistics(statistics: dict[str, object]) -> dict[str, object]:
    keys = (
        "primary_total",
        "primary_tranche_capacity",
        "primary_selected_count",
        "primary_deferred_unknown_count",
        "primary_attempted",
        "primary_wave_complete",
        "all_discovered_primaries_served",
        "eligible_alternate_count",
        "alternate_attempted",
        "alternate_wave_complete",
        "same_cluster_alternates_skipped_after_authority",
        "eligible_restoration_count",
        "restoration_attempted",
        "restoration_wave_complete",
    )
    return {key: statistics[key] for key in keys}


def test_no_authority_is_full_bitwise_schedule_equivalent(monkeypatch) -> None:
    specs = (
        CandidateSpec(0.0, 1e-12, 0.0, 0),
        CandidateSpec(1.0, 2e-12, 1.0, 0, 1),
        CandidateSpec(10.0, 3e-12, 10.0, 1),
        CandidateSpec(20.0, 4e-12, 20.0, 2),
        CandidateSpec(21.0, 5e-12, 21.0, 2, 1),
    )
    # The diversity function must be unreachable without confirmed authority.
    monkeypatch.setattr(
        candidate_v2,
        "_rank_by_verified_diversity",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("pre-answer diversity routing")
        ),
    )
    frozen = _trace_run(specs, candidate_service=False)
    candidate = _trace_run(specs, candidate_service=True)
    assert candidate.events == frozen.events
    assert candidate.attempts == frozen.attempts
    assert candidate.descriptors == frozen.descriptors == {}
    assert _baseline_statistics(candidate.statistics) == _baseline_statistics(
        frozen.statistics
    )
    assert candidate.statistics["adaptive_activated"] is False
    assert candidate.statistics["slack_hp_attempted"] == 0


def test_authority_preserves_complete_frozen_trace_then_appends_slack() -> None:
    specs = tuple(
        CandidateSpec(float(index), 1e-12 * (index + 1), float(index * 10), index)
        for index in range(5)
    ) + (CandidateSpec(0.5, 9e-12, 0.5, 0, 1),)
    outcomes = {specs[0].digest: _authority(1)}
    frozen = _trace_run(
        specs,
        candidate_service=False,
        outcomes=outcomes,
        hard_deadline=125.0,
    )
    candidate = _trace_run(
        specs,
        candidate_service=True,
        outcomes=outcomes,
        hard_deadline=125.0,
    )
    # Identity, output path, source contract, CPU, and float.hex timeout all
    # match for the full frozen schedule, not merely through first authority.
    assert candidate.events[: len(frozen.events)] == frozen.events
    assert candidate.attempts[: len(frozen.attempts)] == frozen.attempts
    assert len(candidate.events) > len(frozen.events)
    assert candidate.statistics["first_authority_attempt_ordinal"] == 0
    assert candidate.statistics["slack_hp_attempted"] > 0
    assert candidate.statistics["pre_confirmation_reserve_seconds"] == 0.0


def test_first_authority_prefix_is_bitwise_equal_when_first_attempt_fails() -> None:
    specs = tuple(
        CandidateSpec(float(index), 1e-12 * (index + 1), float(index), index)
        for index in range(4)
    )
    # Determine the frozen second scheduled endpoint without relying on an ID.
    probe = _trace_run(specs, candidate_service=False, hard_deadline=130.0)
    second_digest = probe.events[1][1]
    outcomes = {second_digest: _authority(7)}
    frozen = _trace_run(
        specs,
        candidate_service=False,
        outcomes=outcomes,
        hard_deadline=130.0,
    )
    candidate = _trace_run(
        specs,
        candidate_service=True,
        outcomes=outcomes,
        hard_deadline=130.0,
    )
    assert candidate.events[:2] == frozen.events[:2]
    assert candidate.attempts[:2] == frozen.attempts[:2]
    assert candidate.statistics["first_authority_attempt_ordinal"] == 1


class DistanceBase:
    @staticmethod
    def _configuration_distance(left: object, right: object) -> float:
        return abs(left.endpoint[0] - right.endpoint[0])


@dataclass(frozen=True)
class RankItem:
    endpoint: tuple[float, ...]
    endpoint_sha256: str
    residual_inf: float
    provisional_target: float


def test_post_answer_rank_is_permutation_and_affine_target_invariant() -> None:
    accepted = RankItem((0.0,), "accepted", 1e-12, 2.0)
    pending = (
        (3, RankItem((3.0,), "three", 3e-12, 4.0)),
        (1, RankItem((1.0,), "one", 1e-12, 2.5)),
        (2, RankItem((2.0,), "two", 2e-12, -5.0)),
    )

    def ranked(
        items: tuple[tuple[int, RankItem], ...], scale: float, shift: float
    ) -> list[str]:
        transformed = tuple(
            (
                ordinal,
                RankItem(
                    item.endpoint,
                    item.endpoint_sha256,
                    item.residual_inf,
                    scale * item.provisional_target + shift,
                ),
            )
            for ordinal, item in items
        )
        transformed_accepted = RankItem(
            accepted.endpoint,
            accepted.endpoint_sha256,
            accepted.residual_inf,
            scale * accepted.provisional_target + shift,
        )
        return [
            item.endpoint_sha256
            for _ordinal, item in candidate_v2._rank_by_verified_diversity(
                DistanceBase(), transformed, (transformed_accepted,)
            )
        ]

    expected = ranked(pending, 1.0, 0.0)
    assert ranked(tuple(reversed(pending)), 1.0, 0.0) == expected
    assert ranked(pending, 7.0, -100.0) == expected
    assert ranked(pending, -3.0, 11.0) == expected


def test_wrapper_changes_no_frozen_schedule_or_runtime_field() -> None:
    base = worker_v2._load_frozen(worker_v2.DEFAULT_FROZEN_ROOT)
    kwargs = {
        "source": Path("source.json"),
        "source_sha256": "b" * 64,
        "total_seconds": 30.0,
        "search_seconds": 20.0,
        "starts": 256,
        "callbacks_per_start": 600,
        "aggregate_callback_cap": 153600,
        "seed": 2,
        "cpu": 7,
        "output": Path("output"),
    }
    frozen = base._plan(**kwargs)
    decorated = candidate_v2.patch_plan(
        base._plan,
        overlay_worker_sha256="c" * 64,
        mechanism_sha256="d" * 64,
    )(**kwargs)
    overlay_keys = {
        "tail_policy",
        "overlay_worker_sha256",
        "tail_mechanism_sha256",
        "pre_confirmation_schedule",
        "pre_confirmation_reserve_seconds",
        "search_schedule_changed",
        "reservoir_replay_changed",
        "adaptive_activation",
        "post_confirmation_extra_work",
        "canonical_source_replay_changed",
        "exact_authority_changed",
    }
    comparable = {
        key: value
        for key, value in decorated.items()
        if key not in overlay_keys and key != "schema_version"
    }
    assert comparable == {
        key: value for key, value in frozen.items() if key != "schema_version"
    }
    assert decorated["selection_reserve_seconds"] == 1.0
    wrapper_source = (HERE / "worker_v2.py").read_text(encoding="utf-8")
    assert "base.SELECTION_RESERVE_SECONDS =" not in wrapper_source
    assert "base.PYTHON =" not in wrapper_source
    assert "base._run_search =" not in wrapper_source
    assert "base._fresh_replay_candidates =" not in wrapper_source


def test_worker_and_mechanism_are_hash_bound_and_truth_blind() -> None:
    frozen = worker_v2.DEFAULT_FROZEN_ROOT / worker_v2.FROZEN_RELATIVE_WORKER
    assert worker_v2._sha256(frozen) == worker_v2.EXPECTED_FROZEN_WORKER_SHA256
    source = (HERE / "candidate_v2.py").read_text(encoding="utf-8")
    assert "gold_targets" not in source
    assert "case_id" not in source
    assert '.get("known_target_count"' not in source
    assert '["known_target_count"]' not in source
    assert "problem_id" not in source
