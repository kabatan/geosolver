from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import candidate_v3  # noqa: E402
import worker_v3  # noqa: E402


@dataclass(frozen=True)
class ReplayCandidate:
    endpoint: tuple[float, ...]
    endpoint_sha256: str
    residual_inf: float
    provisional_target: float
    cluster_ordinal: int = 0
    cluster_rank: int = 0


@dataclass
class FakeClock:
    now: float = 100.0

    def monotonic(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _descriptor(root: int) -> dict[str, object]:
    return {
        "minimal_polynomial_high_to_low": [1, -root],
        "selected_real_root_index": 0,
        "isolating_interval": {"left": str(root - 1), "right": str(root + 1)},
    }


class FakeBase:
    SCHEMA = "geotarget.exp008-finalist-numeric-worker-v15/v1"
    PROCESS_STARTED = 100.0
    MIN_HP_ATTEMPT_SECONDS = 3.0
    MAX_RESTORATION_ATTEMPT_SECONDS = 12.0

    def __init__(
        self,
        clock: FakeClock,
        candidates: tuple[ReplayCandidate, ...],
        hp_result: dict[str, object],
        *,
        hp_elapsed: float = 0.25,
        restoration_result: dict[str, object] | None = None,
    ) -> None:
        self.clock = clock
        self.candidates = candidates
        self.hp_result = hp_result
        self.hp_elapsed = hp_elapsed
        self.restoration_result = restoration_result or {
            "authority_pass": False,
            "descriptor": None,
        }
        self.events: list[tuple[str, str, float]] = []

    @staticmethod
    def _descriptor_key(descriptor: dict[str, object]) -> str:
        return json.dumps(
            {
                "minimal_polynomial_high_to_low": descriptor.get(
                    "minimal_polynomial_high_to_low"
                ),
                "selected_real_root_index": descriptor.get(
                    "selected_real_root_index"
                ),
            },
            sort_keys=True,
        )

    @staticmethod
    def _configuration_distance(left: ReplayCandidate, right: ReplayCandidate) -> float:
        return abs(left.endpoint[0] - right.endpoint[0])

    def _fresh_replay_candidates(
        self,
        _document: dict[str, object],
        _endpoints: list[object],
        *,
        hard_deadline: float,
    ) -> tuple[ReplayCandidate, ...]:
        assert hard_deadline <= self.clock.now + candidate_v3.REPLAY_MAX_SECONDS
        self.clock.advance(0.1)
        return self.candidates

    def _run_hp_candidate(self, **kwargs: Any) -> dict[str, object]:
        candidate = kwargs["candidate"]
        timeout = float(kwargs["timeout_seconds"])
        self.events.append(("hp", candidate.endpoint_sha256, timeout))
        self.clock.advance(self.hp_elapsed)
        return dict(self.hp_result)

    def _run_restoration_candidate(self, **kwargs: Any) -> dict[str, object]:
        candidate = kwargs["candidate"]
        timeout = float(kwargs["timeout_seconds"])
        self.events.append(("restoration", candidate.endpoint_sha256, timeout))
        self.clock.advance(0.25)
        return dict(self.restoration_result)

    @staticmethod
    def atomic_write_json(path: Path, document: dict[str, object]) -> None:
        path.write_text(
            json.dumps(document, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )


def _fixture(
    tmp_path: Path,
    *,
    candidates: tuple[ReplayCandidate, ...],
    clock: FakeClock,
    hp_result: dict[str, object] | None = None,
    hp_elapsed: float = 0.25,
    baseline_authority: bool = True,
) -> tuple[FakeBase, Path, str, Path, bytes]:
    source = tmp_path / "source.json"
    source.write_text(
        json.dumps({"task": "solve", "variables": {"names": ["x"]}}),
        encoding="utf-8",
    )
    source_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    output = tmp_path / "output"
    output.mkdir()
    (output / "search.json").write_text(
        json.dumps({"endpoints": [{"point": [0.0]}, {"point": [1.0]}]}),
        encoding="utf-8",
    )
    baseline_descriptor = _descriptor(1)
    baseline_digest = _digest("baseline")
    baseline_attempt = {
        "endpoint_float64_sha256": baseline_digest,
        "authority_pass": baseline_authority,
        "descriptor": baseline_descriptor if baseline_authority else None,
        "status": "TARGET_AUTHORITY_READY" if baseline_authority else "FAILED",
    }
    descriptors = [baseline_descriptor] if baseline_authority else []
    result = {
        "schema_version": FakeBase.SCHEMA,
        "completed": True,
        "status": "SEARCH_DEADLINE_REACHED",
        "source_sha256": source_sha256,
        "source_bytes_unchanged": True,
        "elapsed_wall_seconds": clock.now - FakeBase.PROCESS_STARTED,
        "within_total_wall_budget": True,
        "hp_attempt_count": 1,
        "hp_attempts": [baseline_attempt],
        "hp_schedule": {"policy": "frozen-v15"},
        "distinct_exact_targets": descriptors,
        "distinct_exact_target_descriptors": descriptors,
        "distinct_exact_target_count": len(descriptors),
    }
    result_path = output / "RESULT.json"
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    baseline_bytes = result_path.read_bytes()
    base = FakeBase(
        clock,
        candidates,
        hp_result or {"authority_pass": False, "descriptor": None},
        hp_elapsed=hp_elapsed,
    )
    return base, source, source_sha256, output, baseline_bytes


def _extend(
    base: FakeBase,
    source: Path,
    source_sha256: str,
    output: Path,
    *,
    total_seconds: float,
) -> candidate_v3.UnionOutcome:
    return candidate_v3.extend_frozen_result(
        base,
        source=source,
        source_sha256=source_sha256,
        total_seconds=total_seconds,
        cpu=7,
        output=output,
    )


def test_no_slack_keeps_result_byte_exact_and_starts_no_side_work(
    tmp_path: Path, monkeypatch
) -> None:
    clock = FakeClock(109.0)
    side = ReplayCandidate((1.0,), _digest("side"), 1e-12, 2.0)
    base, source, digest, output, baseline = _fixture(
        tmp_path, candidates=(side,), clock=clock
    )
    monkeypatch.setattr(candidate_v3.time, "monotonic", clock.monotonic)
    outcome = _extend(base, source, digest, output, total_seconds=10.0)
    assert outcome.status == "NO_ADMISSIBLE_SLACK"
    assert (output / "RESULT.json").read_bytes() == baseline
    assert not (output / candidate_v3.BASELINE_SNAPSHOT).exists()
    assert base.events == []


def test_replay_with_no_unattempted_candidate_keeps_result_byte_exact(
    tmp_path: Path, monkeypatch
) -> None:
    clock = FakeClock(102.0)
    already_attempted = ReplayCandidate(
        (0.0,), _digest("baseline"), 1e-12, 1.0
    )
    base, source, digest, output, baseline = _fixture(
        tmp_path, candidates=(already_attempted,), clock=clock
    )
    monkeypatch.setattr(candidate_v3.time, "monotonic", clock.monotonic)
    outcome = _extend(base, source, digest, output, total_seconds=15.0)
    assert outcome.status == "NO_UNATTEMPTED_REPLAY_CANDIDATE"
    assert outcome.replay_attempted is True
    assert (output / "RESULT.json").read_bytes() == baseline
    assert base.events == []


def test_novel_side_descriptor_unions_over_byte_exact_baseline_snapshot(
    tmp_path: Path, monkeypatch
) -> None:
    clock = FakeClock(102.0)
    baseline_candidate = ReplayCandidate(
        (0.0,), _digest("baseline"), 1e-12, 1.0
    )
    side = ReplayCandidate((10.0,), _digest("side"), 2e-12, 10.0)
    base, source, digest, output, baseline = _fixture(
        tmp_path,
        candidates=(baseline_candidate, side),
        clock=clock,
        hp_result={"authority_pass": True, "descriptor": _descriptor(2)},
    )
    monkeypatch.setattr(candidate_v3.time, "monotonic", clock.monotonic)
    outcome = _extend(base, source, digest, output, total_seconds=15.0)
    assert outcome.status == "NOVEL_DESCRIPTOR_UNIONED"
    assert outcome.finished_before_deadline is True
    assert outcome.baseline_bytes_preserved is True
    assert (output / candidate_v3.BASELINE_SNAPSHOT).read_bytes() == baseline
    union = json.loads((output / "RESULT.json").read_text(encoding="utf-8"))
    baseline_document = json.loads(baseline)
    mutable_union_fields = {
        "elapsed_wall_seconds",
        "within_total_wall_budget",
        "hp_attempt_count",
        "hp_attempts",
        "hp_schedule",
        "distinct_exact_targets",
        "distinct_exact_target_descriptors",
        "distinct_exact_target_count",
    }
    assert {
        key: value
        for key, value in union.items()
        if key not in mutable_union_fields
    } == {
        key: value
        for key, value in baseline_document.items()
        if key not in mutable_union_fields
    }
    assert union["hp_attempts"][:1] == baseline_document["hp_attempts"]
    assert union["distinct_exact_target_count"] == 2
    assert len(union["distinct_exact_target_descriptors"]) == 2
    assert union["hp_schedule"]["policy"] == "frozen-v15"
    assert union["hp_schedule"]["post_baseline_union"][
        "baseline_trace_retained_as_prefix"
    ] is True


def test_side_failure_and_restoration_without_novelty_leave_result_unchanged(
    tmp_path: Path, monkeypatch
) -> None:
    clock = FakeClock(101.0)
    side = ReplayCandidate((10.0,), _digest("side"), 2e-12, 10.0)
    base, source, digest, output, baseline = _fixture(
        tmp_path,
        candidates=(side,),
        clock=clock,
        baseline_authority=False,
    )
    monkeypatch.setattr(candidate_v3.time, "monotonic", clock.monotonic)
    outcome = _extend(base, source, digest, output, total_seconds=15.0)
    assert outcome.status == "SIDE_AUTHORITY_NO_NOVEL_DESCRIPTOR"
    assert outcome.side_hp_attempted == 1
    assert outcome.side_restoration_attempted == 1
    assert (output / "RESULT.json").read_bytes() == baseline
    assert (output / candidate_v3.BASELINE_SNAPSHOT).read_bytes() == baseline


def test_duplicate_side_authority_keeps_result_byte_exact(
    tmp_path: Path, monkeypatch
) -> None:
    clock = FakeClock(101.0)
    side = ReplayCandidate((10.0,), _digest("side"), 2e-12, 10.0)
    base, source, digest, output, baseline = _fixture(
        tmp_path,
        candidates=(side,),
        clock=clock,
        hp_result={"authority_pass": True, "descriptor": _descriptor(1)},
    )
    monkeypatch.setattr(candidate_v3.time, "monotonic", clock.monotonic)
    outcome = _extend(base, source, digest, output, total_seconds=15.0)
    assert outcome.status == "SIDE_AUTHORITY_NO_NOVEL_DESCRIPTOR"
    assert outcome.side_restoration_attempted == 0
    assert (output / "RESULT.json").read_bytes() == baseline


def test_side_timeout_admission_leaves_union_reserve(
    tmp_path: Path, monkeypatch
) -> None:
    clock = FakeClock(100.0)
    side = ReplayCandidate((10.0,), _digest("side"), 2e-12, 10.0)
    base, source, digest, output, _baseline = _fixture(
        tmp_path,
        candidates=(side,),
        clock=clock,
        hp_result={"authority_pass": True, "descriptor": _descriptor(2)},
        hp_elapsed=6.0,
        baseline_authority=False,
    )
    monkeypatch.setattr(candidate_v3.time, "monotonic", clock.monotonic)
    outcome = _extend(base, source, digest, output, total_seconds=9.0)
    assert outcome.status == "NOVEL_DESCRIPTOR_UNIONED"
    assert base.events[0][0] == "hp"
    admitted_timeout = base.events[0][2]
    assert admitted_timeout <= candidate_v3.MAX_SIDE_HP_SECONDS
    assert clock.now <= 109.0 - candidate_v3.SNAPSHOT_AND_UNION_RESERVE_SECONDS
    assert outcome.finished_before_deadline is True


def test_late_union_write_restores_baseline_bytes(tmp_path: Path, monkeypatch) -> None:
    clock = FakeClock(100.0)
    side = ReplayCandidate((10.0,), _digest("side"), 2e-12, 10.0)
    base, source, digest, output, baseline = _fixture(
        tmp_path,
        candidates=(side,),
        clock=clock,
        hp_result={"authority_pass": True, "descriptor": _descriptor(2)},
    )

    def late_atomic_write(path: Path, document: dict[str, object]) -> None:
        path.write_text(json.dumps(document), encoding="utf-8")
        clock.advance(6.0)

    base.atomic_write_json = late_atomic_write
    monkeypatch.setattr(candidate_v3.time, "monotonic", clock.monotonic)
    outcome = _extend(base, source, digest, output, total_seconds=6.0)
    assert outcome.status == "UNION_WRITE_DEADLINE_MISSED"
    assert outcome.novel_descriptor_count == 0
    assert (output / "RESULT.json").read_bytes() == baseline


def test_side_rank_is_permutation_and_affine_target_invariant() -> None:
    base = FakeBase(
        FakeClock(),
        (),
        {"authority_pass": False, "descriptor": None},
    )
    accepted = ReplayCandidate((0.0,), "accepted", 1e-12, 2.0)
    pending = (
        ReplayCandidate((3.0,), "three", 3e-12, 4.0),
        ReplayCandidate((1.0,), "one", 1e-12, 2.5),
        ReplayCandidate((2.0,), "two", 2e-12, -5.0),
    )

    def ranked(
        rows: tuple[ReplayCandidate, ...], scale: float, shift: float
    ) -> list[str]:
        transformed = tuple(
            ReplayCandidate(
                row.endpoint,
                row.endpoint_sha256,
                row.residual_inf,
                scale * row.provisional_target + shift,
            )
            for row in rows
        )
        transformed_accepted = ReplayCandidate(
            accepted.endpoint,
            accepted.endpoint_sha256,
            accepted.residual_inf,
            scale * accepted.provisional_target + shift,
        )
        return [
            row.endpoint_sha256
            for row in candidate_v3._rank_side_candidates(
                base, transformed, (transformed_accepted,)
            )
        ]

    expected = ranked(pending, 1.0, 0.0)
    assert ranked(tuple(reversed(pending)), 1.0, 0.0) == expected
    assert ranked(pending, 7.0, -100.0) == expected
    assert ranked(pending, -3.0, 11.0) == expected


def test_wrapper_dry_plan_is_byte_equal_to_unmodified_frozen(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "source.json"
    source.write_text(
        json.dumps({"task": "solve", "variables": {"names": ["x"]}}),
        encoding="utf-8",
    )
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    output = tmp_path / "dry"
    arguments = [
        "worker",
        "--source",
        str(source),
        "--source-sha256",
        digest,
        "--total-seconds",
        "10",
        "--search-seconds",
        "4",
        "--starts",
        "8",
        "--callbacks-per-start",
        "64",
        "--aggregate-callback-cap",
        "512",
        "--seed",
        "0",
        "--cpu",
        "7",
        "--output",
        str(output),
    ]
    frozen = worker_v3._load_frozen(worker_v3.DEFAULT_FROZEN_ROOT)
    monkeypatch.setattr(sys, "argv", list(arguments))
    frozen.main()
    frozen_plan = (output / "PLAN.json").read_bytes()

    monkeypatch.setattr(sys, "argv", list(arguments))
    worker_v3.main()
    assert (output / "PLAN.json").read_bytes() == frozen_plan


def test_wrapper_does_not_patch_frozen_surface_and_is_truth_blind() -> None:
    wrapper = (HERE / "worker_v3.py").read_text(encoding="utf-8")
    mechanism = (HERE / "candidate_v3.py").read_text(encoding="utf-8")
    assert "base._service_candidates =" not in wrapper
    assert "base._plan =" not in wrapper
    assert "base.PYTHON =" not in wrapper
    assert "base.SELECTION_RESERVE_SECONDS =" not in wrapper
    assert "gold_targets" not in mechanism
    assert "case_id" not in mechanism
    assert '.get("known_target_count"' not in mechanism
    assert '["known_target_count"]' not in mechanism
