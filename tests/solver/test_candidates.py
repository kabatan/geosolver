"""Candidates contracts and numerical regressions."""

import importlib
from dataclasses import replace
from types import SimpleNamespace

import pytest
from mpmath import mp

from geosolver.engine.standard.contracts.candidate_record import (
    FloatCandidate,
    RefinedCandidate,
    SearchBatchResult,
    assert_candidate_id_consistency,
    candidate_attempt,
)
from geosolver.engine.standard.contracts.pipeline_result import ExactIdentificationResult
from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
from geosolver.engine.standard.evaluation.final_verifier import FinalVerificationResult
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.evaluation.search_point import evaluate_search_point
from geosolver.engine.standard.orchestration.assemble_exact_results import (
    assemble_exact_results,
)
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.refinement.mpmath_refiner import _integer_target_tuple_candidate_id
from geosolver.engine.standard.search.build_guard_feasible_ledger import (
    build_guard_feasible_ledger,
)
from geosolver.engine.standard.search.coordinate_distance import normalized_distance


def _ledger_candidate(index: int, *, x: tuple[float, float] | None = None) -> FloatCandidate:
    point = x if x is not None else ((index * 0.37) % 1.0, (index * 0.61) % 1.0)
    return FloatCandidate(
        x_float=point,
        score=float(index % 5),
        residual_norm_float=float(index % 5),
        guard_ok=True,
        evaluation_status=EvaluationStatus.OK,
        origin_seed=index % 3,
        origin_start_point_index=index,
        candidate_id=index,
        hard_feasible=True,
        origin_backend="fixture",
        origin_evaluation_index=index,
    )


def _reference_prefix(
    records: tuple[FloatCandidate, ...],
    bounds: list[tuple[float, float]],
    count: int,
) -> tuple[FloatCandidate, ...]:
    ordered = sorted(records, key=lambda item: (item.score, item.candidate_id))
    selected = [ordered[0]]
    remaining = list(ordered[1:])
    while remaining and len(selected) < count:
        keys = [
            (
                min(
                    normalized_distance(
                        first=candidate.x_float,
                        second=chosen.x_float,
                        bounds=bounds,
                    )
                    for chosen in selected
                ),
                -candidate.score,
                -candidate.candidate_id,
            )
            for candidate in remaining
        ]
        index = max(range(len(keys)), key=keys.__getitem__)
        selected.append(remaining.pop(index))
    return tuple(selected)


def test_incremental_farthest_ledger_preserves_reference_order() -> None:
    records = tuple(_ledger_candidate(index) for index in range(25))
    bounds = [(0.0, 1.0), (0.0, 1.0)]

    _compact, ledger = build_guard_feasible_ledger(
        all_records=records,
        bounds=bounds,
        compact_keep_count=7,
        prefix_count=18,
    )

    assert ledger == _reference_prefix(records, bounds, 18)


@pytest.mark.parametrize(
    ("first", "second", "bounds"),
    [
        ((), (), []),
        ((1.0, -2.0), (0.0, 7.0), [(0.0, 2.0), (-10.0, 10.0)]),
        ((1e-100, 2e-30), (0.0, 0.0), [(0.0, 1e-99), (0.0, 0.0)]),
        ((1e100, -1e100), (0.0, 0.0), [(-1e101, 1e101), (-1e101, 1e101)]),
    ],
)
def test_shared_distance_preserves_original_float_operation_order(first, second, bounds):
    total = 0.0
    for index, (low, high) in enumerate(bounds):
        width = max(high - low, 1e-12)
        diff = (first[index] - second[index]) / width
        total += diff * diff
    expected = total**0.5
    actual = normalized_distance(first=first, second=second, bounds=bounds)
    assert actual.hex() == expected.hex()


def test_coverage_rescue_and_dedup_share_the_same_distance():
    for name in (
        "build_guard_feasible_ledger",
        "select_rescue_boxes",
        "deduplicate_search_candidates",
    ):
        module = importlib.import_module(f"geosolver.engine.standard.search.{name}")
        assert module.normalized_distance is normalized_distance


def _exact_candidate() -> RefinedCandidate:
    return RefinedCandidate(
        x_hp=(mp.mpf("1"),),
        residual_norm_hp=mp.mpf("0"),
        answer_hp=mp.mpf("1"),
        refinement_status="target_reached",
        phase_history=("fixture",),
        candidate_id=1,
        hard_feasible=True,
    )


def _exact_evaluator():
    return SimpleNamespace(
        exact_candidate_cache={}, bundle=SimpleNamespace(spec=SimpleNamespace(answer_expr="1"))
    )


def test_numeric_feasible_candidate_is_not_public_when_exactification_fails(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "geosolver.engine.standard.orchestration.assemble_exact_results.verify_final_candidate",
        lambda **_kwargs: FinalVerificationResult(
            normalized_residual=mp.mpf(0),
            precision_dps=180,
            hard_feasible=True,
            verified=True,
            residual_norm=mp.mpf(0),
            min_margin=None,
            status="verified",
            hard_failure_tags=(),
            values=(mp.mpf(1),),
            answer_hp=mp.mpf(1),
            answer_uncertainty=mp.mpf(0),
        ),
    )
    monkeypatch.setattr(
        "geosolver.engine.standard.orchestration.assemble_exact_results.identify_answer",
        lambda **_kwargs: ExactIdentificationResult(
            exact_status="failed",
            identification_method="none",
            input_precision_dps=120,
            minimal_polynomial=None,
            polynomial_degree=None,
            selected_exact_value=None,
            verification_residual=None,
            numeric_fallback_value=mp.mpf("1"),
        ),
    )

    result = assemble_exact_results(
        refined_candidates=(_exact_candidate(),), evaluator=_exact_evaluator()
    )

    assert len(result.numeric_feasible_candidates) == 1
    assert result.accepted_candidates == ()
    assert result.answer_values == ()
    assert result.candidate_records[0].candidate.candidate_id == 1
    assert result.rejection_tags == ("exactification_failed",)


def test_exactification_does_not_start_after_deadline(monkeypatch) -> None:
    monkeypatch.setattr(
        "geosolver.engine.standard.orchestration.assemble_exact_results.verify_final_candidate",
        lambda **_kwargs: FinalVerificationResult(
            normalized_residual=mp.mpf(0),
            precision_dps=180,
            hard_feasible=True,
            verified=True,
            residual_norm=mp.mpf(0),
            min_margin=None,
            status="verified",
            hard_failure_tags=(),
            values=(mp.mpf(1),),
            answer_hp=mp.mpf(1),
            answer_uncertainty=mp.mpf(0),
        ),
    )
    calls: list[object] = []
    monkeypatch.setattr(
        "geosolver.engine.standard.orchestration.assemble_exact_results.identify_answer",
        lambda **kwargs: calls.append(kwargs),
    )
    monotonic_values = iter((0.0, 2.0))
    monkeypatch.setattr(
        "geosolver.engine.standard.orchestration.assemble_exact_results.time.monotonic",
        lambda: next(monotonic_values),
    )

    result = assemble_exact_results(
        refined_candidates=(_exact_candidate(),),
        evaluator=_exact_evaluator(),
        deadline_monotonic=1.0,
    )

    assert calls == []
    assert len(result.numeric_feasible_candidates) == 1
    assert result.numeric_feasible_candidates[0].revision == 1
    assert result.answer_values == ()
    assert "deadline_before_exactification" in result.rejection_tags


def _contract_candidate():
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

    candidate = _contract_candidate()
    batch = SearchBatchResult((candidate,), 1, 0, guard_feasible_ledger=(candidate,))
    assert _build_candidate_ledger(batch)[0]["hard_feasible"] is None


def _contract_evaluator(constraints=("x*x-1", "y-2"), guards=("x>0",)):
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

    evaluator = _contract_evaluator(constraints=("IsInteger(x)", "y-2"), guards=())
    refiner = MpmathRefiner()
    source = replace(_contract_candidate(), x_float=(1.0, 2.0))
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
        a = _contract_candidate()
    with candidate_attempt(2):
        b = _contract_candidate()
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


@pytest.mark.parametrize("values", [(0.2, 1.1), (-0.2, 1.1), (0.0, 0.0)])
def test_search_point_preserves_precision_and_hard_guard_results(values):
    ev = _contract_evaluator()
    with mp.workdps(180):
        residual = ev.evaluate_float_residual(values)
        hard = ev.evaluate_float_hard_feasibility(values, include_margins=False)
        guard = ev.evaluate_guard(values)
        result = evaluate_search_point(evaluator=ev, values=values, smooth_penalty=True)
        assert result.residual == residual
        assert result.hard == hard
        assert (result.guard_ok, result.guard_violations) == guard
        assert mp.dps == 180


def _provenance_candidate(index: int, *, x: tuple[float, float]) -> FloatCandidate:
    return FloatCandidate(
        x_float=x,
        score=0.0,
        residual_norm_float=0.0,
        guard_ok=True,
        evaluation_status=EvaluationStatus.OK,
        origin_seed=0,
        origin_start_point_index=index,
        candidate_id=index,
        hard_feasible=True,
        origin_backend="fixture",
        origin_evaluation_index=index,
    )


def test_candidate_identity_collision_is_not_silently_merged() -> None:
    first = _provenance_candidate(7, x=(0.1, 0.2))
    second = replace(first, x_float=(0.8, 0.9), origin_phase="rescue")

    with pytest.raises(RuntimeError, match="candidate ID collision"):
        assert_candidate_id_consistency((first, second))


def test_candidate_uid_contains_full_provenance() -> None:
    candidate = replace(
        _provenance_candidate(3, x=(0.2, 0.4)),
        origin_phase="rescue",
        origin_backend="nomad",
        origin_attempt=2,
        origin_box_index=4,
        origin_evaluation_index=11,
    )

    assert candidate.candidate_uid == "rescue/nomad/2/4/0/3/11"
