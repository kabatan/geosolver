"""Keep the reduced pipeline surface and its active numerical behavior intact."""

import importlib
from dataclasses import asdict, fields, replace
from inspect import signature

import pytest
from mpmath import mp

from geosolver.engine.standard.contracts.candidate_record import RefinementBatchResult
from geosolver.engine.standard.contracts.external_pipeline_config import ExternalPipelineConfig
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.interpreter.context.geometry import _get_geometry_context
from geosolver.engine.standard.interpreter.guards.compile import GuardIR
from geosolver.engine.standard.orchestration.run_external_pipeline import _build_refinement_refiner
from geosolver.engine.standard.precision.type_guards.boundary_float_to_mpf import (
    BoundaryOrigin,
    boundary_float_to_mpf,
)
from geosolver.engine.standard.precision.type_guards.high_precision_contamination_error import (
    HighPrecisionContaminationError,
)
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.refinement.refiner_config import RefinerConfig
from geosolver.engine.standard.search.coordinate_distance import normalized_distance
from geosolver.engine.standard.search.sampling.manifold import augment_with_manifold_samples
from geosolver.problem.adapter import to_engine_document
from geosolver.problem.models import GeometryProblem


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


def test_precision_boundary_still_rejects_float_contamination_and_restores_context():
    value = boundary_float_to_mpf(0.1, origin=BoundaryOrigin.INITIAL_POINT)
    assert value == mp.mpf(0.1)
    with high_precision_mode():
        with pytest.raises(HighPrecisionContaminationError):
            mp.mpf(0.1)
        with pytest.raises(HighPrecisionContaminationError):
            boundary_float_to_mpf(0.1, origin=BoundaryOrigin.INITIAL_POINT)
        with high_precision_mode(), pytest.raises(HighPrecisionContaminationError):
            mp.mpf(1) + 0.1
        with pytest.raises(HighPrecisionContaminationError):
            mp.mpf(0.1)
    assert mp.mpf(0.1) == value


def test_manifold_samples_keep_candidates_and_one_canonical_metrics_location():
    bundle = load_problem_bundle(
        to_engine_document(
            GeometryProblem(
                id="cleanup-manifold",
                variables=["x", "y"],
                constructions=[
                    {"name": "O", "expression": "Point(0, 0)"},
                    {"name": "P", "expression": "Point(x, y)"},
                ],
                conditions=[{"left": "Distance(O, P)", "operator": "=", "right": 1}],
                target="x",
            )
        )
    )
    candidates, metrics = augment_with_manifold_samples(
        bundle=bundle,
        evaluator=build_ir_evaluator(bundle),
        bounds=[(-2.0, 2.0), (-2.0, 2.0)],
        candidates=(),
        metrics={"total_probe_points": 0},
    )
    assert len(candidates) == 12
    assert [c.candidate_id for c in candidates] == list(range(1, 13))
    assert set(metrics) == {"total_probe_points", "manifold_sampling"}
    sampling = metrics["manifold_sampling"]["distance_circle_manifold"]
    assert set(sampling) == {
        "total_points",
        "finite_ratio",
        "guard_pass_ratio",
        "best_residual",
        "best_point",
    }
    assert sampling["total_points"] == 12
    assert sampling["guard_pass_ratio"] == 1
