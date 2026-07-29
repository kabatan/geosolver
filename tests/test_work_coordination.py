from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

from geotarget import continuation as continuation_module
from geotarget import optimized_search as optimized_search_module
from geotarget.adaptive_continuation import (
    extension_batch_end,
    has_safe_extension_window,
    update_extension_stability,
    verify_policy_prefix_extension,
)
from geotarget.continuation import ContinuationContext, _pending_candidates, run_controller
from geotarget.hp_wave_checkpoint import create as create_wave_checkpoint
from geotarget.optimized_search import (
    _accepted,
    _checkpoint_chunks,
    _requeue_crashed_lease,
    _run_full_prefix,
)
from geotarget.parallel import (
    install_reservoir_checkpoint,
    resume_candidates_parallel,
    service_candidates_parallel,
)
from geotarget.reservoir_checkpoint import load_checkpoint, search_binding
from geotarget.search_pool_worker_entrypoint import (
    _claim,
    _lane_finished_before_deadline,
    _release,
    _replay_action,
)


def test_parallel_search_never_commits_a_deadline_terminal_lane() -> None:
    assert _lane_finished_before_deadline(finished_at=9.999, deadline=10.0)
    assert not _lane_finished_before_deadline(finished_at=10.0, deadline=10.0)
    assert not _lane_finished_before_deadline(finished_at=10.001, deadline=10.0)


def test_single_core_search_uses_frozen_full_prefix_protocol(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "problem.json"
    source.write_text("{}", encoding="utf-8")

    class Base:
        PYTHON = Path("/qualified/python")
        SEARCH_WORKER = Path("/frozen/search_worker.py")

    def fake_run(command: list[str], timeout: float):
        assert timeout == 154.0
        assert "--compiled-evaluator" in command
        assert command[command.index("--starts") + 1] == "256"
        output = Path(command[command.index("--output") + 1])
        output.write_text(
            json.dumps(
                {
                    "completed": True,
                    "arm": optimized_search_module.SEARCH_ARM,
                    "source_sha256": "a" * 64,
                    "source_bytes_unchanged": True,
                    "source_semantics_modified": False,
                    "all_source_variables_and_equations_retained": True,
                    "truth_used": False,
                    "completeness_claim": False,
                    "optimized_full_prefix": {
                        "frozen_work_graph_preserved": True,
                        "case_specific_routing": False,
                    },
                }
            ),
            encoding="utf-8",
        )
        return 1.0, ""

    monkeypatch.setattr(optimized_search_module, "_run_shard", fake_run)
    status, artifact = _run_full_prefix(
        base=Base(),
        cpu=3,
        source=source,
        source_sha256="a" * 64,
        search_seconds=146.0,
        starts=256,
        callbacks_per_start=600,
        aggregate_callback_cap=153600,
        seed=0,
        output=tmp_path,
    )
    assert status.accepted_output is True
    assert status.classification == "OPTIMIZED_FULL_PREFIX_ACCEPTED"
    assert artifact is not None


@dataclass(frozen=True)
class Candidate:
    record_id: str
    endpoint_sha256: str
    cluster_ordinal: int
    cluster_rank: int = 0


@dataclass(frozen=True)
class CompleteCandidate:
    endpoint: tuple[float, ...]
    endpoint_sha256: str
    residual_inf: float
    provisional_target: float | None = None
    cluster_ordinal: int = 0
    cluster_rank: int = 0
    discovery_ordinal: int = 0
    admission_role: str = "RAW_SAFE"
    record_id: str = ""
    bucket_id: str = ""
    bucket_kind: str = ""
    aging_wave: int = 0
    semantic_verified: bool = True


class Reservoir(tuple):
    def __new__(cls, verified, backlog=()):
        value = super().__new__(cls, verified)
        value.deadline_backlog = tuple(backlog)
        return value


def _write_controller_checkpoint(path: Path, deferred: list[str]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "RESULT.json").write_text(
        json.dumps(
            {
                "hp_schedule": {"deferred_record_ids": deferred},
                "distinct_exact_target_descriptors": [],
            }
        ),
        encoding="utf-8",
    )
    (path / "search.json").write_text(
        json.dumps({"work": {"lanes_started": 256, "callbacks": 10}}),
        encoding="utf-8",
    )


def test_continuation_controller_reuses_one_context_and_commits_ordered_windows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial = tmp_path / "initial"
    output = tmp_path / "controller"
    source = tmp_path / "problem.json"
    source.write_text("{}", encoding="utf-8")
    _write_controller_checkpoint(initial, ["r0", "r1", "r2"])
    context = ContinuationContext(base=object(), source_document={})
    observed_contexts: list[ContinuationContext] = []
    observed_deferred: list[list[str]] = []

    monkeypatch.setattr(continuation_module, "prepare_context", lambda **_kwargs: context)

    def fake_continue_result(*, initial_output: Path, output: Path, context, **_kwargs):
        observed_contexts.append(context)
        prior = json.loads((initial_output / "RESULT.json").read_text(encoding="utf-8"))
        deferred = list(prior["hp_schedule"]["deferred_record_ids"])
        observed_deferred.append(deferred)
        remaining = deferred[1:]
        _write_controller_checkpoint(output, remaining)
        return {
            "hp_schedule": {"deferred_record_ids": remaining},
            "distinct_exact_target_descriptors": [],
            "continuation": {"no_progress": False, "pending_start_ordinals": []},
        }

    monkeypatch.setattr(continuation_module, "continue_result", fake_continue_result)
    state = run_controller(
        runtime=tmp_path,
        source=source,
        source_sha256="a" * 64,
        initial_output=initial,
        output=output,
        seconds=60.0,
        cpu=0,
        cpus=(0, 1),
        seed=0,
    )

    assert state["windows_completed"] == 3
    assert observed_contexts == [context, context, context]
    assert observed_deferred == [["r0", "r1", "r2"], ["r1", "r2"], ["r2"]]
    assert [item["post_search_cap_seconds"] for item in state["windows"]] == [34.0] * 3
    assert Path(state["active_output"]) == output / "window-003"
    assert (
        json.loads((output / "controller-state.json").read_text(encoding="utf-8"))["status"]
        == "completed"
    )


def test_continuation_controller_crash_keeps_last_committed_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial = tmp_path / "initial"
    output = tmp_path / "controller"
    source = tmp_path / "problem.json"
    source.write_text("{}", encoding="utf-8")
    _write_controller_checkpoint(initial, ["r0", "r1"])
    context = ContinuationContext(base=object(), source_document={})
    calls = 0
    monkeypatch.setattr(continuation_module, "prepare_context", lambda **_kwargs: context)

    def crash_second(*, initial_output: Path, output: Path, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected crash")
        _write_controller_checkpoint(output, ["r1"])
        return {
            "hp_schedule": {"deferred_record_ids": ["r1"]},
            "distinct_exact_target_descriptors": [],
            "continuation": {"no_progress": False, "pending_start_ordinals": []},
        }

    monkeypatch.setattr(continuation_module, "continue_result", crash_second)
    with pytest.raises(RuntimeError, match="injected crash"):
        run_controller(
            runtime=tmp_path,
            source=source,
            source_sha256="a" * 64,
            initial_output=initial,
            output=output,
            seconds=60.0,
            cpu=0,
            cpus=(0, 1),
            seed=0,
        )

    committed = json.loads((output / "controller-state.json").read_text(encoding="utf-8"))
    assert committed["status"] == "running"
    assert committed["windows_completed"] == 1
    assert Path(committed["active_output"]) == output / "window-001"
    assert not (output / "window-002" / "RESULT.json").exists()


def test_continuation_controller_retries_transient_resource_contention(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial = tmp_path / "initial"
    output = tmp_path / "controller"
    source = tmp_path / "problem.json"
    source.write_text("{}", encoding="utf-8")
    _write_controller_checkpoint(initial, ["r0"])
    context = ContinuationContext(base=object(), source_document={})
    calls = 0
    monkeypatch.setattr(continuation_module, "prepare_context", lambda **_kwargs: context)

    def contend_then_progress(*, output: Path, **_kwargs):
        nonlocal calls
        calls += 1
        deferred = ["r0"] if calls == 1 else []
        _write_controller_checkpoint(output, deferred)
        return {
            "hp_schedule": {"deferred_record_ids": deferred},
            "distinct_exact_target_descriptors": [],
            "continuation": {
                "no_progress": calls == 1,
                "retryable_resource_contention": calls == 1,
                "resource_busy_deferred_count": 1 if calls == 1 else 0,
                "pending_start_ordinals": [],
            },
        }

    monkeypatch.setattr(continuation_module, "continue_result", contend_then_progress)
    state = run_controller(
        runtime=tmp_path,
        source=source,
        source_sha256="a" * 64,
        initial_output=initial,
        output=output,
        seconds=60.0,
        cpu=0,
        cpus=(0,),
        seed=0,
    )

    assert calls == 2
    assert state["windows_completed"] == 2
    assert state["windows"][0]["retryable_resource_contention"] is True
    assert state["windows"][0]["stalled"] is False


def test_adaptive_batches_are_exactly_64_starts_and_respect_safety_reserve() -> None:
    assert extension_batch_end(256) == 320
    assert extension_batch_end(320) == 384
    assert has_safe_extension_window(12.0) is True
    assert has_safe_extension_window(11.999) is False


def test_adaptive_stability_requires_answer_then_two_empty_batches() -> None:
    answer_found, empty, stable = update_extension_stability(
        descriptors_before=0,
        descriptors_after=1,
        answer_found=False,
        consecutive_empty_batches=0,
    )
    assert (answer_found, empty, stable) == (True, 0, False)

    answer_found, empty, stable = update_extension_stability(
        descriptors_before=1,
        descriptors_after=1,
        answer_found=answer_found,
        consecutive_empty_batches=empty,
    )
    assert (answer_found, empty, stable) == (True, 1, False)

    answer_found, empty, stable = update_extension_stability(
        descriptors_before=1,
        descriptors_after=1,
        answer_found=answer_found,
        consecutive_empty_batches=empty,
    )
    assert (answer_found, empty, stable) == (True, 2, True)


@dataclass(frozen=True)
class FakePolicy:
    points: tuple[np.ndarray, ...]
    local_origins: tuple[np.ndarray, ...]
    local_scales: tuple[np.ndarray, ...]
    sources: tuple[str, ...]
    scale_exponents: tuple[int, ...]


class PrefixBase:
    corrupt_extension = False

    def materialize_policy(self, document, *, source_sha256, starts, seed):
        del document, source_sha256
        points = tuple(np.asarray([seed, ordinal], dtype=float) for ordinal in range(starts))
        if self.corrupt_extension and starts > 4:
            points = (np.asarray([seed, 999.0]), *points[1:])
        return FakePolicy(
            points=points,
            local_origins=tuple(point.copy() for point in points),
            local_scales=tuple(np.maximum(1.0, np.abs(point)) for point in points),
            sources=tuple("literal" for _ in points),
            scale_exponents=tuple(0 for _ in points),
        )


def test_adaptive_extension_proves_cross_prefix_identity_or_fails_closed() -> None:
    digest = verify_policy_prefix_extension(
        PrefixBase(),
        {},
        source_sha256="a" * 64,
        seed=0,
        previous_starts=4,
        extended_starts=8,
    )
    assert len(digest) == 64

    corrupted = PrefixBase()
    corrupted.corrupt_extension = True
    with pytest.raises(RuntimeError, match="changed an existing start ordinal"):
        verify_policy_prefix_extension(
            corrupted,
            {},
            source_sha256="a" * 64,
            seed=0,
            previous_starts=4,
            extended_starts=8,
        )


def test_search_checkpoint_chunks_end_on_champion_start_boundaries() -> None:
    assert _checkpoint_chunks(7, 43) == ((7, 23), (23, 39), (39, 43))
    assert _checkpoint_chunks(7, 11, width=1) == (
        (7, 8),
        (8, 9),
        (9, 10),
        (10, 11),
    )


def _accepted_search_artifact(callbacks: int = 600) -> dict:
    return {
        "completed": True,
        "arm": "precision_isolated_retained_then_strict_nearroot_restart_direct_broyden_ruiz_tr_lm",
        "source_sha256": "a" * 64,
        "source_bytes_unchanged": True,
        "source_evaluator_compiled_from_original_document": True,
        "source_semantics_modified": False,
        "all_source_variables_and_equations_retained": True,
        "explicit_source_bounds_only": True,
        "added_or_inferred_search_bounds": False,
        "gauge_or_symmetry_reduction": False,
        "candidate_received_case_id_family_truth_or_target_count": False,
        "truth_used": False,
        "completeness_claim": False,
        "seed": 0,
        "cpu_affinity": [2],
        "thread_environment": {
            "OMP_NUM_THREADS": "1",
            "OMP_THREAD_LIMIT": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        },
        "completed_start_ordinals": [7],
        "optimized_shard": {
            "ordinal_start": 7,
            "ordinal_end": 8,
            "total_prefix_starts": 256,
            "callbacks_per_start": 600,
            "persistent_worker": True,
            "stable_ordinal_replay": True,
        },
        "budget": {
            "starts": 256,
            "callbacks_per_start": 600,
            "aggregate_callback_cap": 600,
        },
        "work": {
            "callbacks": callbacks,
            "finite_callbacks": callbacks,
            "invalid_callbacks": 0,
            "guard_failed_callbacks": 0,
            "lanes_started": 1,
            "lane_callbacks_min": callbacks,
            "lane_callbacks_max": callbacks,
        },
        "literal_prefix": {
            "sources": ["literal"],
            "scale_exponents": [0],
            "full_prefix_sha256": "b" * 64,
            "selected_proposal_points_sha256": "c" * 64,
        },
        "endpoints": [{"lane": 7, "point": [0.0]}],
        "endpoints_validated": 1,
        "safe_endpoint_count": 1,
    }


def test_search_admission_rejects_impossible_callback_accounting() -> None:
    arguments = {
        "source_sha256": "a" * 64,
        "seed": 0,
        "chunk": (7, 8),
        "starts": 256,
        "callbacks_per_start": 600,
        "cpus": (2,),
    }
    assert _accepted(_accepted_search_artifact(), **arguments)
    assert not _accepted(_accepted_search_artifact(10**12), **arguments)
    missing_environment = _accepted_search_artifact()
    missing_environment["thread_environment"] = {}
    assert not _accepted(missing_environment, **arguments)


def test_search_claim_is_durably_requeued_after_worker_crash(tmp_path: Path) -> None:
    queue = tmp_path / "queue.json"
    queue.write_text('{"next":7,"retry":[],"leased":{}}', encoding="ascii")

    assert _claim(queue, 10, 2) == 7
    assert _requeue_crashed_lease(queue, 2) is True
    assert _claim(queue, 10, 3) == 7
    _release(queue, 3, 7)
    assert _claim(queue, 10, 3) == 8


def test_restarted_replay_coordinator_keeps_committed_endpoint() -> None:
    committed = {
        "optimized_shard": {"stable_ordinal_replay": True},
        "endpoints": [{"lane": 7, "point": [1.0, 2.0]}],
        "endpoints_validated": 1,
        "safe_endpoint_count": 1,
    }
    assert _replay_action(committed) == "keep"
    assert committed["endpoints"] == [{"lane": 7, "point": [1.0, 2.0]}]
    assert (
        _replay_action(
            {
                "optimized_shard": {"stable_ordinal_replay": False},
                "_unvalidated_endpoint_points": [[1.0, 2.0]],
            }
        )
        == "replay"
    )


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


class CheckpointBase:
    SELECTION_RESERVE_SECONDS = 3.0
    ReplayCandidate = CompleteCandidate

    def __init__(self) -> None:
        self.replays = 0

    def _fresh_replay_candidates(self, document, endpoints, *, hard_deadline):
        del document, endpoints, hard_deadline
        self.replays += 1
        return Reservoir(
            (
                CompleteCandidate((0.0,), "0" * 64, 1e-9, record_id="r0"),
                CompleteCandidate((1.0,), "1" * 64, 2e-9, record_id="r1"),
            ),
            (
                CompleteCandidate(
                    (2.0,),
                    "2" * 64,
                    3e-4,
                    record_id="r2",
                    admission_role="DEADLINE_BACKLOG",
                    semantic_verified=False,
                ),
            ),
        )


def test_continuation_checkpoint_preserves_frozen_suffix_and_attempt_characterization(
    tmp_path: Path,
) -> None:
    search = {
        "arm": "frozen",
        "seed": 0,
        "endpoints": [{"lane": 0, "point": [0.0]}],
        "literal_prefix": {"full_prefix_sha256": "a" * 64},
        "optimized_parallel_search": {"completed_start_ordinals": [0]},
        "work": {"lanes_started": 1, "callbacks": 600},
        "budget": {"starts": 256, "callbacks_per_start": 600},
    }
    result = {"hp_schedule": {"deferred_record_ids": ["r1", "r2"]}}
    checkpoint = tmp_path / "candidate-reservoir.json"
    base = CheckpointBase()

    replayed = _pending_candidates(
        base,
        {},
        search,
        result,
        time.monotonic() + 30,
        source_sha256="f" * 64,
        checkpoint_input=tmp_path / "missing.json",
        checkpoint_output=checkpoint,
    )
    cached = _pending_candidates(
        base,
        {},
        search,
        result,
        time.monotonic() + 30,
        source_sha256="f" * 64,
        checkpoint_input=checkpoint,
        checkpoint_output=tmp_path / "copied.json",
    )

    def characterization(reservoir):
        ordered = tuple(reservoir) + tuple(reservoir.deadline_backlog)
        return {
            "attempt_order": [candidate.record_id for candidate in ordered],
            "descriptor_order": [candidate.endpoint_sha256 for candidate in ordered],
            "callback_accounting": [candidate.discovery_ordinal for candidate in ordered],
            "deferred_suffix": [candidate.record_id for candidate in ordered],
        }

    assert base.replays == 1
    assert (
        characterization(cached)
        == characterization(replayed)
        == {
            "attempt_order": ["r1", "r2"],
            "descriptor_order": ["1" * 64, "2" * 64],
            "callback_accounting": [0, 0],
            "deferred_suffix": ["r1", "r2"],
        }
    )


def test_initial_adapter_commits_exact_reservoir_for_cross_process_continuation(
    tmp_path: Path,
) -> None:
    search = {
        "arm": "frozen",
        "seed": 0,
        "endpoints": [{"lane": 0, "point": [0.0]}],
        "literal_prefix": {"full_prefix_sha256": "a" * 64},
        "optimized_parallel_search": {"completed_start_ordinals": [0]},
        "work": {"lanes_started": 1, "callbacks": 600},
        "budget": {"starts": 256, "callbacks_per_start": 600},
    }
    (tmp_path / "search.json").write_text(json.dumps(search), encoding="utf-8")
    expected = Reservoir(
        (CompleteCandidate((0.0,), "0" * 64, 1e-9, record_id="r0"),),
        (
            CompleteCandidate(
                (1.0,),
                "1" * 64,
                2e-4,
                record_id="r1",
                admission_role="DEADLINE_BACKLOG",
                semantic_verified=False,
            ),
        ),
    )

    class Base:
        ReplayCandidate = CompleteCandidate

        @staticmethod
        def _fresh_replay_candidates(*_args, **_kwargs):
            return expected

    base = Base()
    checkpoint = tmp_path / "candidate-reservoir.json"
    install_reservoir_checkpoint(base, checkpoint, "f" * 64)
    observed = base._fresh_replay_candidates({}, [], hard_deadline=time.monotonic() + 1)
    restored = load_checkpoint(
        checkpoint,
        expected_binding=search_binding("f" * 64, search),
        candidate_type=CompleteCandidate,
        reservoir_type=Reservoir,
    )
    assert observed is expected
    assert restored is not None
    assert [candidate.record_id for candidate in restored] == ["r0"]
    assert [candidate.record_id for candidate in restored.deadline_backlog] == ["r1"]
    assert restored.deadline_backlog[0].semantic_verified is False


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


def test_parallel_time_budget_preserves_candidate_reserve(tmp_path: Path) -> None:
    class RecordingBase(ParallelBase):
        def __init__(self) -> None:
            super().__init__()
            self.budget_counts: list[int] = []

        def _wave_attempt_seconds(self, remaining, count, cap):
            del remaining
            self.budget_counts.append(count)
            return cap

        def _run_hp_candidate(self, *, candidate, cpu, **kwargs):
            del cpu, kwargs
            return {
                "record_id": candidate.record_id,
                "authority_pass": True,
                "descriptor": {
                    "minimal_polynomial_high_to_low": [1, -candidate.cluster_ordinal],
                    "selected_real_root_index": candidate.cluster_ordinal,
                },
            }

    base = RecordingBase()
    candidates = tuple(Candidate(f"r{ordinal}", f"{ordinal:064x}", ordinal) for ordinal in range(7))
    service_candidates_parallel(
        base=base,
        source=tmp_path / "problem.json",
        source_sha256="a" * 64,
        candidates=candidates,
        output=tmp_path,
        hard_deadline=time.monotonic() + 10,
        cpus=(1, 3, 5),
    )
    assert base.budget_counts == [7, 6, 5, 4, 3, 2, 1]


def test_inner_capacity_does_not_drop_deferred_outer_candidates(tmp_path: Path) -> None:
    class ShrinkingBase(ParallelBase):
        @staticmethod
        def _primary_tranche_capacity(remaining, count):
            del remaining, count
            return 1

    candidates = tuple(Candidate(f"r{ordinal}", f"{ordinal:064x}", ordinal) for ordinal in range(3))
    _attempts, _descriptors, statistics = service_candidates_parallel(
        base=ShrinkingBase(),
        source=tmp_path / "problem.json",
        source_sha256="a" * 64,
        candidates=candidates,
        output=tmp_path,
        hard_deadline=time.monotonic() + 10,
        cpus=(1, 2),
    )
    assert statistics["primary_attempted"] == 1
    assert statistics["primary_deferred_unknown_count"] == 2
    assert statistics["primary_wave_complete"] is False


def test_resumed_primary_reapplies_window_capacity_instead_of_reserving_every_deferred(
    tmp_path: Path,
) -> None:
    class WindowBase(ParallelBase):
        @staticmethod
        def _primary_tranche_capacity(remaining, count):
            del remaining, count
            return 1

    class ReadyPool:
        @staticmethod
        def ensure() -> None:
            return None

    candidates = tuple(
        Candidate(f"r{ordinal}", f"{ordinal:064x}", ordinal) for ordinal in range(40)
    )
    checkpoint = {
        "schema_version": "geotarget.hp-wave-checkpoint/v1",
        "stage": "primary",
        "batch_record_ids": [candidate.record_id for candidate in candidates],
        "pending_primary_record_ids": [candidate.record_id for candidate in candidates],
        "pending_alternate_record_ids": [],
        "pending_restoration_record_ids": [],
        "failed_primaries": [],
    }
    checkpoint = create_wave_checkpoint(
        stage="primary",
        batch_record_ids=checkpoint["batch_record_ids"],
        pending_primary_record_ids=checkpoint["pending_primary_record_ids"],
        pending_alternate_record_ids=(),
        pending_restoration_record_ids=(),
        failed_primaries=(),
    )

    attempts, _descriptors, statistics = resume_candidates_parallel(
        base=WindowBase(),
        source=tmp_path / "problem.json",
        source_sha256="a" * 64,
        all_candidates=candidates,
        output=tmp_path / "continued",
        hard_deadline=time.monotonic() + 10,
        cpus=(2,),
        checkpoint=checkpoint,
        pool=ReadyPool(),
    )

    assert len(attempts) == 1
    assert statistics["durable_wave_checkpoint"]["pending_primary_record_ids"] == [
        candidate.record_id for candidate in candidates[1:]
    ]


def test_resource_busy_primary_remains_pending_in_durable_checkpoint(tmp_path: Path) -> None:
    class BusyBase(ParallelBase):
        def _run_hp_candidate(self, *, candidate, **kwargs):
            del kwargs
            return {
                "record_id": candidate.record_id,
                "endpoint_float64_sha256": candidate.endpoint_sha256,
                "status": "MEMORY_BUSY_DEFERRED",
                "resource_busy_deferred": True,
                "authority_pass": False,
                "descriptor": None,
            }

    candidate = Candidate("r0", "0" * 64, 0)
    _attempts, descriptors, statistics = service_candidates_parallel(
        base=BusyBase(),
        source=tmp_path / "problem.json",
        source_sha256="a" * 64,
        candidates=(candidate,),
        output=tmp_path,
        hard_deadline=time.monotonic() + 10,
        cpus=(2,),
    )

    assert descriptors == {}
    assert statistics["durable_wave_checkpoint"]["stage"] == "primary"
    assert statistics["durable_wave_checkpoint"]["pending_primary_record_ids"] == ["r0"]


def test_interrupted_primary_retains_restoration_and_resumes_exact_wave(
    tmp_path: Path,
) -> None:
    class InterruptedBase(ParallelBase):
        THREAD_ENVIRONMENT: dict[str, str] = {}

        def __init__(self) -> None:
            super().__init__()
            self.budget_calls = 0
            self.resumed = False
            self.restored: list[str] = []

        def _wave_attempt_seconds(self, remaining, count, cap):
            del remaining, count
            self.budget_calls += 1
            if not self.resumed and self.budget_calls > 1:
                return 0.0
            return cap

        def _run_hp_candidate(self, *, candidate, **kwargs):
            del kwargs
            if candidate.record_id == "r0":
                return {"record_id": "r0", "authority_pass": False, "descriptor": None}
            return {
                "record_id": candidate.record_id,
                "authority_pass": True,
                "descriptor": {
                    "minimal_polynomial_high_to_low": [1, -2],
                    "selected_real_root_index": 0,
                },
            }

        def _run_restoration_candidate(self, *, candidate, failed_authority_artifact, **kwargs):
            del kwargs
            self.restored.append(candidate.record_id)
            assert failed_authority_artifact.name == "authority.json"
            return {
                "record_id": candidate.record_id,
                "authority_pass": True,
                "descriptor": {
                    "minimal_polynomial_high_to_low": [1, -252],
                    "selected_real_root_index": 0,
                },
            }

    class ReadyPool:
        @staticmethod
        def ensure() -> None:
            return None

    base = InterruptedBase()
    candidates = (
        Candidate("r0", "0" * 64, 0),
        Candidate("r1", "1" * 64, 1),
    )
    attempts, descriptors, statistics = service_candidates_parallel(
        base=base,
        source=tmp_path / "problem.json",
        source_sha256="a" * 64,
        candidates=candidates,
        output=tmp_path / "initial",
        hard_deadline=time.monotonic() + 10,
        cpus=(2,),
        pool=ReadyPool(),
    )
    checkpoint = statistics["durable_wave_checkpoint"]
    assert len(attempts) == 1
    assert descriptors == {}
    assert checkpoint["stage"] == "primary"
    assert checkpoint["pending_primary_record_ids"] == ["r1"]
    assert [row["record_id"] for row in checkpoint["failed_primaries"]] == ["r0"]

    base.resumed = True
    resumed_attempts, resumed_descriptors, resumed_statistics = resume_candidates_parallel(
        base=base,
        source=tmp_path / "problem.json",
        source_sha256="a" * 64,
        all_candidates=candidates,
        output=tmp_path / "continued",
        hard_deadline=time.monotonic() + 10,
        cpus=(2,),
        checkpoint=checkpoint,
        pool=ReadyPool(),
    )
    assert len(resumed_attempts) == 2
    assert base.restored == ["r0"]
    assert sorted(resumed_descriptors) == ["0"]
    assert resumed_statistics["durable_wave_checkpoint"]["stage"] == "complete"


@pytest.mark.parametrize("cpus", [(0,), (0, 1), (0, 1, 2, 3)])
def test_continuation_installs_same_34_second_authority_cap_for_all_core_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cpus: tuple[int, ...]
) -> None:
    class Base:
        HP_BRIDGE = None

        @staticmethod
        def _source_contract(source, source_sha256):
            del source, source_sha256
            return b"{}", {}

    observed: list[tuple[tuple[int, ...], float]] = []
    monkeypatch.setattr(continuation_module, "_load_frozen", lambda _runtime: Base())
    monkeypatch.setattr(
        continuation_module,
        "install_parallel",
        lambda _base, values, *, post_search_seconds: observed.append(
            (tuple(values), post_search_seconds)
        ),
    )
    continuation_module.prepare_context(
        runtime=tmp_path,
        source=tmp_path / "problem.json",
        source_sha256="a" * 64,
        cpus=cpus,
    )
    assert observed == [(cpus, 34.0)]
