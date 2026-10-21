"""Pipeline contracts and numerical regressions."""

import importlib
import time
from dataclasses import asdict, fields, replace
from inspect import signature

import pytest
from mpmath import mp

from geosolver.engine.standard.contracts.candidate_record import (
    RefinedCandidate,
    RefinementBatchResult,
)
from geosolver.engine.standard.contracts.external_pipeline_config import ExternalPipelineConfig
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.interpreter.context.geometry import _get_geometry_context
from geosolver.engine.standard.interpreter.guards.compile import GuardIR
from geosolver.engine.standard.orchestration.assemble_exact_results import assemble_exact_results
from geosolver.engine.standard.orchestration.run_external_pipeline import _build_refinement_refiner
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.refinement.refiner_config import RefinerConfig
from geosolver.runtime.deadline import runtime_session


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


def test_retired_options_and_records_are_not_part_of_runtime_contracts():
    assert "dedup_answer_tolerance" not in asdict(RefinerConfig())
    with pytest.raises(TypeError):
        RefinerConfig(dedup_answer_tolerance=1)
    assert not signature(_get_geometry_context).parameters
    assert "attempted_box_count" not in {f.name for f in fields(RefinementBatchResult)}
    assert "bounds_hints" not in {f.name for f in fields(GuardIR)}


def test_refiner_factory_preserves_requested_config():
    config = ExternalPipelineConfig.standard_tier()
    custom = replace(config.refiner_config, max_stage_iters=7)
    assert _build_refinement_refiner(replace(config, refiner_config=custom)).config is custom


def test_refiner_initialization_error_is_not_retried_with_default_config(monkeypatch):
    module = importlib.import_module(_build_refinement_refiner.__module__)
    calls = []

    def failing_refiner(**kwargs):
        calls.append(kwargs)
        raise TypeError("initialization failure")

    monkeypatch.setattr(module, "MpmathRefiner", failing_refiner)
    config = ExternalPipelineConfig.standard_tier()
    with pytest.raises(TypeError, match="initialization failure"):
        _build_refinement_refiner(config)
    assert calls == [{"config": config.refiner_config}]
