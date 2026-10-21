"""Independent regressions for worker protocol and numerical contracts."""

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from mpmath import mp

from geosolver.engine import EngineRunner
from geosolver.engine.runner import EngineTimedOut
from geosolver.engine.standard.contracts.branch_box import BranchBox
from geosolver.engine.standard.contracts.candidate_record import (
    FloatCandidate,
    RefinedCandidate,
    SearchBatchResult,
    candidate_attempt,
)
from geosolver.engine.standard.contracts.external_pipeline_config import ExternalPipelineConfig
from geosolver.engine.standard.contracts.runtime_budget import RuntimeBudget
from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.evaluation.search_point import evaluate_search_point
from geosolver.engine.standard.evaluation.snapshots import evaluation_session
from geosolver.engine.standard.evaluation.verification_numerics import linearization
from geosolver.engine.standard.orchestration.run_initial_probe import run_initial_probe
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.refinement.mpmath_refiner import _integer_target_tuple_candidate_id
from geosolver.runtime.artifact_commit import atomic_write, read_receipt
from geosolver.runtime.artifact_records import expand_artifact, normalize_artifact
from geosolver.runtime.protocol import WorkerArtifact


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


def test_candidate_ledger_preserves_unchecked_hard_state():
    from geosolver.engine.standard.orchestration.build_pipeline_summary import (
        _build_candidate_ledger,
    )

    candidate = _candidate()
    batch = SearchBatchResult((candidate,), 1, 0, guard_feasible_ledger=(candidate,))
    assert _build_candidate_ledger(batch)[0]["hard_feasible"] is None


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


def _evaluator(constraints=("x*x-1", "y-2"), guards=("x>0",)):
    return build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x", "y"]},
                "bounds": [[-3, 3], [-3, 3]],
                "construction": [{"name": "P", "expr": "Point(x,y)"}],
                "constraints": list(constraints),
                "guards": list(guards),
                "answer": "x+y",
            }
        )
    )


@pytest.mark.parametrize("status", ["target_reached", "deadline_reached"])
def test_automatic_closure_and_explicit_integer_retry_have_distinct_keys(monkeypatch, status):
    from geosolver.engine.standard.refinement.mpmath_refiner import (
        MpmathRefiner,
        build_integer_constraint_closures_from_targets,
        build_integer_constraint_specs,
    )

    evaluator = _evaluator(constraints=("IsInteger(x)", "y-2"), guards=())
    refiner = MpmathRefiner()
    source = replace(_candidate(), x_float=(1.0, 2.0))
    point = [mp.mpf(1), mp.mpf(2)]
    monkeypatch.setattr(
        MpmathRefiner, "_run_integer_closure_path", lambda self, **kw: (status, point, 80, ())
    )
    monkeypatch.setattr(
        MpmathRefiner,
        "_apply_post_lm_closure_polish",
        lambda self, **kw: (kw["point"], kw["phase_history"], kw["stage_status"], kw["answer_dps"]),
    )
    closures = build_integer_constraint_closures_from_targets(
        specs=build_integer_constraint_specs(bundle=evaluator.bundle), target_integers=(1,)
    )
    automatic = refiner._build_refined_candidate(
        bundle=evaluator.bundle,
        evaluator=evaluator,
        candidate=source,
        point=point,
        phase_history=(),
        stage_status=status,
        candidate_id=-18,
        answer_dps=80,
        integer_closures=closures,
    )
    explicit = refiner.refine_candidate_with_integer_targets(
        bundle=evaluator.bundle,
        evaluator=evaluator,
        candidate=source,
        target_integers=(1,),
        start_point=tuple(point),
    )
    assert automatic.candidate_key.targets == explicit.candidate_key.targets == (1,)
    assert automatic.candidate_key.parent == explicit.candidate_key.parent
    assert automatic.candidate_key != explicit.candidate_key


def test_identity_is_independent_of_display_id_and_contains_derivation():
    with candidate_attempt(1):
        a = _candidate()
    with candidate_attempt(2):
        b = _candidate()
    assert a.candidate_key != b.candidate_key
    assert a.candidate_key == replace(a, candidate_id=999).candidate_key
    assert a.hard_feasible is None
    keys = set()
    for targets in ((1, 0), (0, 1000003), (-1, 10**60), (10**60, -1)):
        r = RefinedCandidate(
            (mp.mpf(0),),
            mp.mpf(0),
            None,
            "draft",
            (),
            a,
            derivation_kind="integer_closure",
            constraint_indices=(0, 2),
            target_integers=targets,
        )
        keys.add(r.candidate_key)
        assert r.candidate_key.parent == a.candidate_key
    assert len(keys) == 4
    assert _integer_target_tuple_candidate_id(17, (1, 0)) != _integer_target_tuple_candidate_id(
        17, (0, 1000003)
    )
    assert a.candidate_key.derived("a").derived("b") != a.candidate_key.derived("b")


def test_probe_reuse_keeps_attempt_identity_and_recomputes_scales():
    ev = _evaluator(("1e10*x", "y"))
    bounds = [(-3.0, 3.0), (-3.0, 3.0)]
    with candidate_attempt(0):
        a = run_initial_probe(evaluator=ev, bounds=bounds, seeds=(0,), points_per_seed=5)
    with candidate_attempt(1):
        b = run_initial_probe(evaluator=ev, bounds=bounds, seeds=(0, 1), points_per_seed=5)
    fresh = run_initial_probe(
        evaluator=_evaluator(("1e10*x", "y")), bounds=bounds, seeds=(0, 1), points_per_seed=5
    )
    assert b.metrics["reused_random_points"] == 5
    assert b.constraint_scales == fresh.constraint_scales
    assert [c.score for c in b.candidates] == [c.score for c in fresh.candidates]
    assert a.candidates[0].candidate_key != b.candidates[0].candidate_key
    assert all(c.hard_feasible is None for c in b.candidates)


@pytest.mark.parametrize("precision", [80, 180, 500])
@pytest.mark.parametrize(
    "constraints",
    [
        ("x*x-1", "y-2", "x+y-3"),
        ("abs(x)", "min(abs(x),abs(y))", "Distance(P,Point(0,0))"),
        ("Distance(Intersect(Line(Point(-3,y),Point(3,y)),Circle(Point(0,0),2),n=1),P)-1", "x-y"),
        ("sqrt(x)", "sqrt(-x)", "y"),
    ],
)
def test_batched_linearization_matches_scalar_values_errors_and_traces(precision, constraints):
    ev = _evaluator(constraints)
    with mp.workdps(precision), high_precision_mode(), evaluation_session(ev):
        point = (mp.mpf("0.2"), mp.mpf("0.4"))
        bases_a, bases_b = [], []
        args = (ev.verification_equations, point, ev.bundle.var_names, (mp.mpf(3),) * 2, precision)
        a = linearization(*args, batch=False, base_samples=bases_a)
        b = linearization(*args, batch=True, base_samples=bases_b)

        def same(left, right):
            if isinstance(left, list | tuple):
                return len(left) == len(right) and all(
                    same(x, y) for x, y in zip(left, right, strict=True)
                )
            if isinstance(left, mp.mpf) and mp.isnan(left):
                return mp.isnan(right)
            return left == right

        assert same(a, b)
        assert same(bases_a, bases_b)


@pytest.mark.parametrize("values", [(0.2, 1.1), (-0.2, 1.1), (0.0, 0.0)])
def test_search_point_preserves_precision_and_hard_guard_results(values):
    ev = _evaluator()
    with mp.workdps(180):
        residual = ev.evaluate_float_residual(values)
        hard = ev.evaluate_float_hard_feasibility(values, include_margins=False)
        guard = ev.evaluate_guard(values)
        result = evaluate_search_point(evaluator=ev, values=values, smooth_penalty=True)
        assert result.residual == residual
        assert result.hard == hard
        assert (result.guard_ok, result.guard_violations) == guard
        assert mp.dps == 180


def test_rescue_shares_time_and_rolls_unused_time_forward(monkeypatch):
    import geosolver.engine.standard.orchestration.run_rescue_search as module

    clock = [0.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    boxes = tuple(BranchBox(i, (0.0,), (-1.0,), (1.0,), (), 1, "search_rescue") for i in range(6))
    monkeypatch.setattr(module, "select_rescue_boxes", lambda *args: boxes)
    deadlines = []

    def optimize(adapter, *args):
        deadlines.append(adapter.deadline_monotonic)
        if len(deadlines) == 1:
            clock[0] += 0.5  # first box returns before its one-second allocation
        else:
            clock[0] = adapter.deadline_monotonic
        point = SimpleNamespace(size=lambda: 1, get_coord=lambda i: 0, setBBO=lambda b: None)
        if clock[0] >= adapter.deadline_monotonic:
            assert adapter(point) == 0  # callback stops even for sub-second MAX_TIME

    monkeypatch.setattr(
        module,
        "_import_pynomad",
        lambda: SimpleNamespace(setSeed=lambda seed: None, optimize=optimize),
    )
    config = replace(
        ExternalPipelineConfig.production_baseline_tier(seed=0, total_time_budget_sec=20),
        rescue_time_budget_sec=6,
    )
    result = module.run_rescue_search(
        bundle=None,
        evaluator=None,
        bounds=[(-1, 1)],
        search_result=SearchBatchResult((), 0, 0),
        pipeline_config=config,
        runtime_budget=RuntimeBudget(20, started_at_monotonic=0),
    )
    assert len(result.box_runs) == 6
    assert result.box_runs[0]["quota_seconds"] == 1
    assert result.box_runs[1]["quota_seconds"] == pytest.approx(1.1)
    assert deadlines[-1] == pytest.approx(6)


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


def test_descriptor_reuse_rechecks_the_new_answer_and_rejects_ambiguity(monkeypatch):
    import sympy as sp

    from geosolver.engine.standard.contracts.pipeline_result import ExactIdentificationResult
    from geosolver.engine.standard.exact_assembly.identify_answer import identify_answer
    from geosolver.exact.descriptors import describe_exact

    with mp.workdps(120):
        prior = ExactIdentificationResult(
            "identified",
            "fixture",
            100,
            (1, -1),
            1,
            "1",
            mp.mpf(0),
            None,
            describe_exact(1),
            discovery_precision_dps=60,
        )
        result = identify_answer(
            answer_hp=1 + mp.mpf("1e-90"),
            tier="strict",
            input_precision_dps=100,
            answer_uncertainty=mp.mpf("1e-80"),
            reusable_results=(prior,),
        )
        assert result.identification_method == "verified_descriptor_reuse"
        assert 0 < result.verification_residual < mp.mpf("1e-80")
        assert result.descriptor.canonical_key() == prior.descriptor.canonical_key()
        other_value = 1 + sp.Rational(1, 10**70)
        other = replace(
            prior, selected_exact_value=str(other_value), descriptor=describe_exact(other_value)
        )
        calls = []

        def propose(**kwargs):
            calls.append(kwargs)
            return replace(prior, selected_exact_value=None, descriptor=None)

        monkeypatch.setattr(
            "geosolver.engine.standard.exact_assembly.identify_answer._identify_answer_proposal",
            propose,
        )
        for value, uncertainty, bank in (
            (mp.mpf(1), mp.mpf("1e-60"), (prior, other)),
            (mp.mpf(2), mp.mpf("1e-80"), (prior,)),
        ):
            result = identify_answer(
                answer_hp=value,
                tier="strict",
                input_precision_dps=100,
                answer_uncertainty=uncertainty,
                reusable_results=bank,
            )
            assert result.identification_method != "verified_descriptor_reuse"
        assert len(calls) == 2


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


@pytest.mark.parametrize("entry", ["residual", "guard", "hard"])
def test_scipy_evaluation_helpers_do_not_swallow_solve_deadline(entry):
    import numpy as np

    from geosolver.engine.standard.search import scipy_multistart_backend as backend

    def timed_out(*args, **kwargs):
        raise TimeoutError("injected solve deadline")

    ev = SimpleNamespace(
        evaluate_float_residual=timed_out,
        evaluate_guard=timed_out,
        evaluate_float_hard_feasibility=timed_out,
    )
    with pytest.raises(TimeoutError):
        if entry == "residual":
            backend._evaluate_float_residual_norm(
                evaluator=ev, values=np.array([0.0]), telemetry=backend._SearchTelemetry()
            )
        elif entry == "hard":
            backend._evaluate_hard_feasibility_penalty(evaluator=ev, values=np.array([0.0]))
        else:
            ev.evaluate_float_residual = lambda *args: SimpleNamespace(
                evaluation_status=EvaluationStatus.OK, is_finite=True, residual_vector=[0.0]
            )
            backend._rank_bounded_trf_starts(
                evaluator=ev, starts=[np.array([0.0])], telemetry=backend._SearchTelemetry()
            )


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
