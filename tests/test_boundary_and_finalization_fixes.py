"""Forbidden-boundary and Phase B/C handoff regressions (corpus323 audit)."""

import json
import time
from pathlib import Path

import pytest
from mpmath import mp

from geosolver.engine.standard.contracts.candidate_record import RefinedCandidate
from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.orchestration.assemble_exact_results import assemble_exact_results
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.problem.models import GeometryProblem
from geosolver.runtime.deadline import runtime_session

ROOT = Path(__file__).resolve().parents[1]


def evaluator(constraints, *, guards=(), answer="x+y"):
    return build_ir_evaluator(
        load_problem_bundle(
            {
                "task": "solve",
                "variables": {"names": ["x", "y"]},
                "construction": [],
                "constraints": list(constraints),
                "guards": list(guards),
                "answer": answer,
            }
        )
    )


@pytest.mark.parametrize("factor", ["1", "1e-200", "1e200"])
def test_unresolved_cusp_coordinate_is_not_an_exact_free_parameter(factor):
    ev = evaluator([f"{factor}*Distance(Point(x,y),Point(0,y))", "y-7"], guards=["x>0"])
    with mp.workdps(600), runtime_session(None):
        result = verify_final_candidate(evaluator=ev, values=(mp.mpf("1e-502"), mp.mpf(7)))
    assert not result.verified
    assert result.coordinate_uncertainty[0] > 0


def test_saved_hmmt2007_false_answer_seven_is_rejected():
    dsl = json.loads((ROOT / "benchmarks/dsl/HMMT-2007-FEB-GEO-04.json").read_text())
    fixtures = json.loads((ROOT / "tests/fixtures/forbidden-boundary-candidates.json").read_text())
    saved = next(
        c
        for c in fixtures
        if c["candidate_id"] == 9000000000050
    )
    with mp.workdps(600), runtime_session(time.monotonic() + 20):
        ev = build_ir_evaluator(
            load_problem_bundle(GeometryProblem.model_validate(dsl).engine_document())
        )
        result = verify_final_candidate(
            evaluator=ev, values=tuple(mp.mpf(x) for x in saved["x_hp"])
        )
    assert not result.verified
    assert result.coordinate_uncertainty[0] > 0


def test_hmmt2007_true_tangent_configuration_still_gives_seventeen():
    dsl = json.loads((ROOT / "benchmarks/dsl/HMMT-2007-FEB-GEO-04.json").read_text())
    with mp.workdps(600), runtime_session(time.monotonic() + 20):
        # s=17, uv=845/12 follows from BC=7 and tangency; no saved solver point.
        u = (17 - mp.sqrt(mp.mpf(66) / 9)) / 2
        point = (u, 17 - u)
        ev = build_ir_evaluator(
            load_problem_bundle(GeometryProblem.model_validate(dsl).engine_document())
        )
        result = verify_final_candidate(evaluator=ev, values=point)
        assert result.verified, result.hard_failure_tags
        assert abs(result.answer_hp - 17) < mp.mpf("1e-100")


@pytest.mark.parametrize(
    "constraints,point,guards",
    [
        (["y-7"], ("1e-600", "7"), ["x>0"]),
        (["y-x", "2*y-2*x"], ("1e-600", "1e-600"), ["x>0"]),
        (["x*x+y*y-25"], ("3", "4"), ["x>0", "y>0"]),
        (["x*x", "y-7"], ("0", "7"), []),
        (["x-1e-40", "y-7"], ("1e-40", "7"), ["x>0"]),
    ],
)
def test_true_freedom_tangent_and_tiny_positive_values_survive(constraints, point, guards):
    with mp.workdps(600), runtime_session(None):
        result = verify_final_candidate(
            evaluator=evaluator(constraints, guards=guards), values=tuple(mp.mpf(x) for x in point)
        )
    assert result.verified, result.hard_failure_tags


@pytest.mark.parametrize("status", ["max_iters", "deadline_reached", "line_search_failed"])
def test_finite_nonconverged_candidate_reaches_independent_verifier(status):
    with mp.workdps(180), runtime_session(time.monotonic() + 10):
        candidate = RefinedCandidate(
            x_hp=(mp.mpf(1), mp.mpf(2)),
            residual_norm_hp=mp.mpf(0),
            answer_hp=mp.mpf(3),
            refinement_status=status,
            phase_history=(),
            candidate_id=10,
        )
        result = assemble_exact_results(
            refined_candidates=(candidate,), evaluator=evaluator(["x-1", "y-2"])
        )
    assert result.answer_values == ("3",)
    assert result.accepted_candidates[0].refinement_status == status


def test_max_iters_does_not_bypass_final_mathematical_verification():
    with mp.workdps(180), runtime_session(None):
        candidate = RefinedCandidate(
            x_hp=(mp.mpf(0), mp.mpf(2)),
            residual_norm_hp=mp.mpf(0),
            answer_hp=mp.mpf(2),
            refinement_status="max_iters",
            phase_history=(),
            candidate_id=11,
        )
        result = assemble_exact_results(
            refined_candidates=(candidate,), evaluator=evaluator(["x", "y-2"], guards=["x>0"])
        )
    assert not result.answer_values
    assert result.verification_records
    assert all(not row["verified"] for row in result.verification_records)


def test_cutoff_keeps_last_iterate_and_defers_evaluation_to_phase_c():
    from geosolver.engine.standard.refinement.mpmath_refiner import MpmathRefiner
    from geosolver.runtime.deadline import deadline_scope

    with mp.workdps(180), runtime_session(time.monotonic() + 10):
        with deadline_scope(time.monotonic() - 1):
            draft = MpmathRefiner()._build_refined_candidate(
                bundle=None,
                evaluator=None,
                candidate=None,
                point=[mp.mpf(1), mp.mpf(2)],
                phase_history=(),
                stage_status="max_iters",
                candidate_id=17,
                answer_dps=180,
            )
        assert draft.refinement_status == "deadline_reached"
        assert draft.answer_hp is None and draft.residual_norm_hp == mp.inf
        result = assemble_exact_results(
            refined_candidates=(draft,), evaluator=evaluator(["x-1", "y-2"])
        )
    assert result.answer_values == ("3",)
    assert result.accepted_candidates[0].revision > draft.revision


@pytest.mark.parametrize("remaining,reserve", [(178, 30), (100, 20), (1, 0.2), (0, 0)])
def test_finalization_reserve_does_not_charge_or_extend_global_deadline(
    monkeypatch, remaining, reserve
):
    from geosolver.engine.standard.contracts.external_pipeline_config import ExternalPipelineConfig
    from geosolver.engine.standard.contracts.runtime_budget import RuntimeBudget

    monkeypatch.setattr(time, "monotonic", lambda: 10.0)
    budget = RuntimeBudget(remaining, started_at_monotonic=10)
    config = ExternalPipelineConfig.standard_tier()
    assert config.refinement_deadline(budget) == pytest.approx(10 + remaining - reserve)
    assert budget.remaining_sec() == remaining
    assert budget.deadline_monotonic == 10 + remaining


def test_pipeline_reaches_verification_when_refinement_uses_entire_slice(monkeypatch):
    import importlib
    from types import SimpleNamespace

    from geosolver.engine.standard.contracts.external_pipeline_config import ExternalPipelineConfig
    from geosolver.engine.standard.contracts.runtime_budget import RuntimeBudget
    from geosolver.runtime.deadline import current_deadline, deadline_scope

    pipeline = importlib.import_module(
        "geosolver.engine.standard.orchestration.run_external_pipeline"
    )
    clock = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])
    probe = SimpleNamespace(constraint_scales=None)
    monkeypatch.setattr(pipeline, "run_initial_probe", lambda **_: probe)
    monkeypatch.setattr(
        pipeline, "augment_initial_probe_with_exact_distance_samples", lambda **_: probe
    )
    monkeypatch.setattr(pipeline, "run_search", lambda **_: SimpleNamespace(candidates=()))
    deadlines = []

    def refine(**kwargs):
        cutoff = kwargs["deadline_monotonic"]
        with deadline_scope(cutoff):
            assert current_deadline() == cutoff
            clock[0] = cutoff
        deadlines.append(cutoff)
        return SimpleNamespace(candidates=("retained",))

    def assemble(**kwargs):
        assert kwargs["refined_candidates"] == ("retained",)
        assert clock[0] < kwargs["deadline_monotonic"] == current_deadline()
        deadlines.append(kwargs["deadline_monotonic"])
        return "verified"

    monkeypatch.setattr(pipeline, "run_refinement", refine)
    monkeypatch.setattr(pipeline, "assemble_exact_results", assemble)
    with deadline_scope(178):
        stage = pipeline._run_pipeline_stage(
            bundle=None,
            evaluator=None,
            bounds=[],
            seed_base=None,
            refiner=None,
            pipeline_config=ExternalPipelineConfig.standard_tier(),
            runtime_budget=RuntimeBudget(178, started_at_monotonic=0),
        )
    assert deadlines == [148, 178]
    assert stage.exact_assembly_result == "verified"


def test_unresolved_coordinate_uncertainty_reaches_selected_coordinates():
    from geosolver.engine.standard.evaluation.verification_numerics import correction

    with mp.workdps(180):
        _, uncertainty = correction(
            [mp.mpf(0)],
            [[mp.mpf(1), mp.mpf(2)]],
            [[mp.mpf(0), mp.mpf(0)]],
            [mp.mpf(1), mp.mpf(1)],
            180,
            evaluation_scales=[mp.mpf(3)],
        )
        # The selected y column solves x+2y=0. Uncertainty in x must reach y.
        assert uncertainty[0] > 0
        assert uncertainty[1] >= uncertainty[0] / 2


@pytest.mark.parametrize("coordinate", ["nan", "inf", "-inf"])
def test_interrupted_record_with_nonfinite_coordinates_is_not_a_candidate(coordinate):
    candidate = RefinedCandidate(
        x_hp=(mp.mpf(coordinate), mp.mpf(2)),
        residual_norm_hp=mp.inf,
        answer_hp=None,
        refinement_status="deadline_reached",
        phase_history=(),
        candidate_id=18,
    )
    result = assemble_exact_results(
        refined_candidates=(candidate,), evaluator=evaluator(["x-1", "y-2"])
    )
    assert not result.answer_values
    assert result.rejection_tags == ("coordinate_non_finite",)
