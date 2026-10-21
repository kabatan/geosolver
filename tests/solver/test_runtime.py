"""Runtime contracts and numerical regressions."""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
from mpmath import mp

from geosolver import GeometryProblem, SolveOptions, solve
from geosolver.engine import EngineCancelled, EngineFailure, EngineRunner
from geosolver.engine.runner import EngineTimedOut
from geosolver.engine.standard.contracts.candidate_record import (
    FloatCandidate,
    RefinedCandidate,
)
from geosolver.engine.standard.contracts.runtime_budget import RuntimeBudget
from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.orchestration.assemble_exact_results import assemble_exact_results
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.refinement.mpmath_refiner import _integer_target_tuple_candidate_id
from geosolver.exact import assemble_exact_answers
from geosolver.runtime.artifact_commit import atomic_write, read_receipt
from geosolver.runtime.artifact_records import expand_artifact, normalize_artifact
from geosolver.runtime.protocol import WorkerArtifact, WorkerRequest
from geosolver.runtime.worker import execute


def test_revised_coordinates_and_answer_are_kept_together():
    evaluator = build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x"]},
                "constraints": ["x-2"],
                "answer": "x+1",
            }
        )
    )
    with mp.workdps(180):
        old = RefinedCandidate(
            (mp.mpf(2) + mp.mpf("1e-40"),),
            mp.mpf("1e-40"),
            mp.mpf(999),
            "stalled",
            (),
            candidate_id=41,
        )
        result = assemble_exact_results(refined_candidates=(old,), evaluator=evaluator)
        candidate = result.accepted_candidates[0]
        assert candidate.revision >= 1 and candidate.x_hp == (mp.mpf(2),)
        assert candidate.answer_hp == 3 and result.answer_values == ("3",)
        cached = assemble_exact_results(refined_candidates=(old,), evaluator=evaluator)
        assert cached.candidate_records[0] is result.candidate_records[0]


def test_inner_deadline_returns_completed_no_answer(monkeypatch):
    from geosolver.runtime import worker
    from geosolver.runtime.protocol import WorkerRequest

    def timeout(*args, **kwargs):
        raise TimeoutError("inner deadline")

    monkeypatch.setattr(worker, "run_external_pipeline", timeout)
    request = WorkerRequest(engine_document={}, deadline_monotonic=time.monotonic() + 5)
    artifact = worker.execute(request)
    assert artifact.status == "completed" and artifact.answers == []
    assert artifact.termination_reason == "time_limit_reached"


def test_candidate_artifact_preserves_precision_outside_work_context():
    from geosolver.runtime.worker import _json_value

    with mp.workdps(500):
        value = mp.sqrt(2) + mp.mpf("1e-400")
    with mp.workdps(15):
        saved = _json_value({"coordinate": value})
    with mp.workdps(500):
        assert mp.mpf(saved["coordinate"]) == value


def test_timeout_keeps_measured_counters_and_phase_timings(monkeypatch):
    from geosolver.runtime import worker
    from geosolver.runtime.deadline import count_event, timed_phase
    from geosolver.runtime.protocol import WorkerRequest

    @timed_phase("audit_stage")
    def timeout(*args, **kwargs):
        count_event("audit_evaluations", 7)
        raise TimeoutError("injected timeout after real telemetry")

    monkeypatch.setattr(worker, "run_external_pipeline", timeout)
    artifact = worker.execute(
        WorkerRequest(engine_document={}, deadline_monotonic=time.monotonic() + 5)
    )
    assert artifact.status == "completed"
    assert artifact.termination_reason == "time_limit_reached"
    assert artifact.counters["audit_evaluations"] == 7
    assert artifact.phase_timings["audit_stage"] >= 0


def test_outer_timeout_retains_completed_descriptors_and_their_verified_revision(monkeypatch):
    from dataclasses import replace

    from geosolver.engine.standard.contracts.candidate_record import RefinedCandidate
    from geosolver.engine.standard.orchestration.assemble_exact_results import (
        assemble_exact_results,
    )
    from geosolver.runtime import worker
    from geosolver.runtime.deadline import retain_candidates
    from geosolver.runtime.protocol import WorkerRequest

    def interrupted(*args, **kwargs):
        ev = build_ir_evaluator(
            load_problem_bundle(
                {
                    "task": "solve",
                    "variables": {"names": ["x"]},
                    "constraints": ["x-2"],
                    "answer": "x+1",
                }
            )
        )
        old = RefinedCandidate((mp.mpf(2),), mp.mpf(0), mp.mpf(999), "stalled", (), candidate_id=41)
        result = assemble_exact_results(refined_candidates=(old,), evaluator=ev)
        accepted = result.accepted_candidates[0]
        assert accepted.answer_hp == 3
        # Later drafts must never replace the coordinates that justified 3.
        retain_candidates(
            (
                replace(
                    accepted, x_hp=(mp.mpf(4),), answer_hp=mp.mpf(5), revision=accepted.revision + 1
                ),
                replace(old, candidate_id=42),
            )
        )
        raise TimeoutError("injected after exact descriptor completion")

    monkeypatch.setattr(worker, "run_external_pipeline", interrupted)
    artifact = worker.execute(
        WorkerRequest(engine_document={}, deadline_monotonic=time.monotonic() + 10)
    )
    assert artifact.status == "completed" and artifact.public_solved
    assert artifact.termination_reason == "time_limit_reached"
    assert artifact.exact_candidates == ["3"] and len(artifact.answers) == 1
    records = {record["candidate_id"]: record for record in artifact.candidate_records}
    assert records[41]["accepted"] and mp.mpf(records[41]["x_hp"][0]) == 2
    assert mp.mpf(records[41]["answer_hp"]) == 3
    assert not records[42]["accepted"]


def test_runtime_budget_uses_one_absolute_deadline_without_double_counting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = {"now": 10.0}
    monkeypatch.setattr(
        "geosolver.engine.standard.contracts.runtime_budget.time.monotonic",
        lambda: clock["now"],
    )
    budget = RuntimeBudget(
        total_budget_sec=5.0,
        started_at_monotonic=10.0,
        deadline_monotonic=15.0,
    )

    budget.reserve_or_fail(4.0)
    assert budget.remaining_sec() == 5.0
    clock["now"] = 13.5
    assert budget.remaining_sec() == 1.5
    with pytest.raises(RuntimeError):
        budget.reserve_or_fail(2.0)


def test_worker_finishes_an_expired_inner_deadline_without_answers() -> None:
    artifact = execute(
        WorkerRequest(
            engine_document={},
            deadline_monotonic=time.monotonic() - 1,
            effective_cores=1,
        )
    )

    assert artifact.status == "completed"
    assert artifact.error is None
    assert artifact.termination_reason == "time_limit_reached"
    assert artifact.answers == []


def test_worker_protocol_v3_rejects_old_and_extra_fields() -> None:
    with pytest.raises(ValueError):
        WorkerRequest.model_validate(
            {
                "protocol_version": 1,
                "engine_document": {},
                "deadline_monotonic": time.monotonic() + 10,
            }
        )
    with pytest.raises(ValueError):
        WorkerRequest.model_validate(
            {
                "engine_document": {},
                "deadline_monotonic": time.monotonic() + 10,
                "prefer_fast": True,
            }
        )


def _candidate():
    return FloatCandidate(
        (0.0,),
        0,
        0,
        True,
        EvaluationStatus.OK,
        4,
        2,
        candidate_id=17,
        origin_backend="fixture",
        origin_evaluation_index=1,
    )


def test_large_integer_targets_remain_exact_and_artifacts_stay_serializable():
    from geosolver.engine.standard.contracts.candidate_record import candidate_record
    from geosolver.engine.standard.refinement.mpmath_refiner import (
        build_integer_constraint_closures_from_targets,
    )
    from geosolver.runtime.worker import _json_value

    targets = tuple((-1) ** i * (10**250 + i) for i in range(8))
    specs = tuple(SimpleNamespace(constraint_index=i, inner_expression="x") for i in range(8))
    with mp.workdps(15):
        closures = build_integer_constraint_closures_from_targets(
            specs=specs, target_integers=targets
        )
        assert tuple(int(c.target_integer) for c in closures) == targets
        stored_targets = tuple(c.target_integer for c in closures)
        rebuilt = build_integer_constraint_closures_from_targets(
            specs=specs, target_integers=stored_targets
        )
        assert tuple(int(c.target_integer) for c in rebuilt) == targets
        display = _integer_target_tuple_candidate_id(1, targets)
        assert _integer_target_tuple_candidate_id(1, stored_targets) == display
        assert len(str(display)) < 400
        candidate = RefinedCandidate(
            (),
            mp.mpf(0),
            None,
            "draft",
            (),
            _candidate(),
            candidate_id=display,
            derivation_kind="integer_closure",
            constraint_indices=tuple(range(8)),
            target_integers=tuple(int(c.target_integer) for c in closures),
        )
        assert candidate.candidate_key.targets == targets
        record = _json_value(candidate_record(candidate))
        # The previous display encoding exceeded Python's JSON integer digit limit.
        artifact = WorkerArtifact(status="completed", candidate_records=[record])
        json.dumps(normalize_artifact(artifact.model_dump(mode="json")))


@pytest.mark.parametrize("saved_at,read_at,valid", [(9, 11, True), (11, 11, False)])
def test_runner_accepts_only_saves_completed_by_deadline(monkeypatch, saved_at, read_at, valid):
    clock = [0]
    monkeypatch.setattr("geosolver.engine.runner.time.monotonic", lambda: clock[0])

    class Process:
        pid = 123456
        returncode = 0

        def poll(self):
            return 0

        def communicate(self):
            clock[0] = read_at
            return "", ""

    def spawn(command, **kwargs):
        request = json.loads(Path(command[command.index("--input") + 1]).read_text())
        path = Path(command[command.index("--output") + 1])
        clock[0] = saved_at
        atomic_write(path, WorkerArtifact(status="completed", request_id=request["request_id"]))
        return Process()

    monkeypatch.setattr("geosolver.engine.runner.spawn_process", spawn)
    monkeypatch.setattr("geosolver.engine.runner.set_affinity", lambda *args: None)
    if valid:
        assert (
            EngineRunner().run({}, seed=0, cores=1, time_limit_seconds=10).artifact.status
            == "completed"
        )
    else:
        with pytest.raises(EngineTimedOut):
            EngineRunner().run({}, seed=0, cores=1, time_limit_seconds=10)


def test_commit_receipt_binds_payload_and_request(tmp_path):
    path = tmp_path / "result.json"
    atomic_write(path, WorkerArtifact(status="completed", request_id="request-A"))
    receipt = read_receipt(path)
    assert receipt.verify_bytes(path.read_bytes())
    assert not receipt.verify_bytes(path.read_bytes() + b" ")
    assert receipt.matches("request-A", receipt.committed_monotonic)
    assert not receipt.matches("request-B", receipt.committed_monotonic)


def test_v4_normalization_retains_different_revisions_and_reads_v3():
    candidate = {"x_hp": ["1"], "candidate_uid": "a", "revision": 1, "accepted": True}
    payload = WorkerArtifact(
        status="completed",
        candidate_records=[
            candidate,
            {**candidate, "revision": 2, "x_hp": ["2"], "accepted": False},
        ],
        diagnostics={"exact": candidate},
    ).model_dump(mode="json")
    wire = normalize_artifact(payload)
    assert len(wire["record_tables"]["candidates"]) == 2
    assert expand_artifact(wire) == payload
    assert WorkerArtifact.model_validate(wire).model_dump(mode="json") == payload
    assert WorkerArtifact.model_validate({**payload, "protocol_version": 3}).protocol_version == 3
    wire["record_tables"]["candidates"].clear()
    with pytest.raises(ValueError):
        WorkerArtifact.model_validate(wire)


@pytest.mark.parametrize("corruption", ["hash", "request", "missing", "none"])
def test_running_worker_at_deadline_requires_a_matching_completed_save(monkeypatch, corruption):
    clock = [0]
    monkeypatch.setattr("geosolver.engine.runner.time.monotonic", lambda: clock[0])

    class Process:
        pid = 123456
        returncode = 0

        def poll(self):
            return None

        def communicate(self):
            return "", ""

    def spawn(command, **kwargs):
        request = json.loads(Path(command[command.index("--input") + 1]).read_text())
        path = Path(command[command.index("--output") + 1])
        clock[0] = 9
        atomic_write(
            path,
            WorkerArtifact(
                status="completed",
                request_id=(request["request_id"] if corruption != "request" else "other"),
            ),
        )
        if corruption == "hash":
            path.write_bytes(path.read_bytes() + b" ")
        if corruption == "missing":
            path.with_name(path.name + ".commit.json").unlink()
        clock[0] = 11
        return Process()

    def terminate(process):
        process.returncode = -15

    monkeypatch.setattr("geosolver.engine.runner.spawn_process", spawn)
    monkeypatch.setattr("geosolver.engine.runner.set_affinity", lambda *args: None)
    monkeypatch.setattr("geosolver.engine.runner.terminate_process_tree", terminate)
    if corruption == "none":
        assert (
            EngineRunner().run({}, seed=0, cores=1, time_limit_seconds=10).artifact.status
            == "completed"
        )
    else:
        from geosolver.engine import EngineFailure

        with pytest.raises(EngineFailure):
            EngineRunner().run({}, seed=0, cores=1, time_limit_seconds=10)


def test_worker_never_marks_an_unverified_revision_accepted(monkeypatch):
    import time

    from geosolver.engine.standard.contracts.pipeline_result import ExactIdentificationResult
    from geosolver.exact.descriptors import describe_exact
    from geosolver.runtime.protocol import WorkerRequest
    from geosolver.runtime.worker import execute

    source = _candidate()
    draft = RefinedCandidate(
        (mp.mpf(2),), mp.mpf(0), mp.mpf(2), "target_reached", (), source=source, revision=2
    )
    exact = ExactIdentificationResult(
        "identified", "fixture", 180, (1, -1), 1, "1", mp.mpf(0), None, describe_exact(1)
    )
    result = SimpleNamespace(
        status="success",
        summary={},
        exact_results=(exact,),
        accepted_answers=(mp.mpf(1),),
        refined_candidates=(draft,),
        accepted_candidate_uids=(draft.candidate_uid,),
        accepted_candidate_revisions=((draft.candidate_uid, 1),),
    )
    monkeypatch.setattr("geosolver.runtime.worker.run_external_pipeline", lambda *a, **k: result)
    artifact = execute(WorkerRequest(engine_document={}, deadline_monotonic=time.monotonic() + 180))
    assert artifact.status == "completed"
    assert artifact.answers[0].canonical_key() == exact.descriptor.canonical_key()
    assert artifact.candidate_records[0]["revision"] == 2
    assert artifact.candidate_records[0]["accepted"] is False


def problem_with_value(value: int | float | str = 1) -> GeometryProblem:
    return GeometryProblem(
        id="positive-dimensional",
        variables=["x"],
        constructions=[],
        conditions=[{"left": "x", "operator": "=", "right": value}],
        target="x",
    )


def options() -> SolveOptions:
    return SolveOptions(time_limit_seconds=180, cores=1)


@pytest.mark.parametrize("code", ["artifact_missing", "artifact_invalid", "worker_exception"])
def test_worker_protocol_failures_are_never_reported_as_no_answer(code: str) -> None:
    class FailedRunner:
        def run(self, *args: object, **kwargs: object) -> object:
            raise EngineFailure(code, "worker failed")

    result = solve(problem_with_value(), options(), runner=FailedRunner())  # type: ignore[arg-type]

    assert result.status == "engine_error"
    assert result.error is not None and result.error.code == code


def test_no_progress_is_an_immediate_engine_error() -> None:
    class NoProgressRunner:
        calls = 0

        def run(self, *args: object, **kwargs: object) -> object:
            self.calls += 1
            raise EngineFailure("no_progress", "checkpoint did not advance")

    runner = NoProgressRunner()
    result = solve(problem_with_value(), options(), runner=runner)  # type: ignore[arg-type]

    assert runner.calls == 1
    assert result.status == "engine_error"
    assert result.termination_reason == "no_progress"


def test_cancelling_one_session_does_not_cancel_another() -> None:
    class SessionRunner:
        def __init__(self, cancelled: bool) -> None:
            self.cancelled = cancelled

        def run(self, *args: object, **kwargs: object) -> SimpleNamespace:
            if self.cancelled:
                raise EngineCancelled
            return SimpleNamespace(
                artifact=WorkerArtifact(
                    status="completed",
                    solver_status="success",
                    exact_candidates=["1"],
                    answers=assemble_exact_answers(["1"])[0],
                )
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        cancelled = executor.submit(
            solve, problem_with_value(), options(), runner=SessionRunner(True)
        )
        completed = executor.submit(
            solve, problem_with_value(), options(), runner=SessionRunner(False)
        )

    assert cancelled.result().status == "cancelled"
    assert completed.result().status == "solved"


def test_worker_restores_global_mpmath_precision(monkeypatch: pytest.MonkeyPatch) -> None:
    original = mp.dps

    def precision_leaking_solver(*args: object, **kwargs: object) -> SimpleNamespace:
        mp.dps = 333
        return SimpleNamespace(
            status="success",
            summary={},
            exact_results=[SimpleNamespace(selected_exact_value="1", descriptor=None)],
            accepted_answers=[1],
            refined_candidates=[],
            accepted_candidate_ids=[],
            accepted_candidate_uids=[],
            accepted_candidate_revisions=[],
        )

    monkeypatch.setattr("geosolver.runtime.worker.run_external_pipeline", precision_leaking_solver)
    request = WorkerRequest(
        engine_document={},
        seed=0,
        deadline_monotonic=time.monotonic() + 180,
        effective_cores=1,
    )
    artifact = execute(request)

    assert artifact.status == "completed"
    assert mp.dps == original
