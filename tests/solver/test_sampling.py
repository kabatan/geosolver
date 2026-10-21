"""Sampling contracts and numerical regressions."""

import importlib
import math
from types import SimpleNamespace

import pytest

from geosolver import GeometryProblem
from geosolver.engine.standard.contracts.candidate_record import FloatCandidate, SearchBatchResult
from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.orchestration.run_initial_probe import InitialProbeResult
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.search.nomad_config import NomadConfig
from geosolver.engine.standard.search.sampling.affine_guards import (
    AffineGuardSampler,
    affine_guard_rows,
    affine_interior_points,
)
from geosolver.engine.standard.search.sampling.manifold import (
    DEFAULT_MANIFOLD_SAMPLE_STRATEGIES,
    augment_with_manifold_samples,
)
from geosolver.problem.adapter import to_engine_document


def test_default_portfolio_does_not_run_positive_radius_projection_or_brackets():
    identifiers = {strategy.strategy_id for strategy in DEFAULT_MANIFOLD_SAMPLE_STRATEGIES}
    assert "positive_radius_contact_manifold" not in identifiers
    assert "affine_guard_interior" in identifiers


@pytest.mark.parametrize("allow_integer_shortcuts", [False, True])
@pytest.mark.parametrize("search_mode", ["disco_mads", "scipy_multistart", "hybrid_legacy_nomad"])
def test_production_search_preserves_ordinary_four_variable_candidates(
    monkeypatch, allow_integer_shortcuts, search_mode
):
    from geosolver.engine.standard.search import scale_chart

    module = importlib.import_module("geosolver.engine.standard.orchestration.run_search")
    problem = {
        "id": "ordinary-four-variable-search",
        "variables": ["x", "y", "z", "w"],
        "constructions": [],
        "conditions": [{"left": "x+y+z+w", "operator": "=", "right": 5}],
        "target": "x",
    }
    bundle = load_problem_bundle(to_engine_document(GeometryProblem.model_validate(problem)))
    evaluator = build_ir_evaluator(bundle)
    point = (-10001.0, 10001.0, -9998.0, 10003.0)
    original = FloatCandidate(point, 0, 0, True, EvaluationStatus.OK, 0, 0, 123, hard_feasible=True)
    baseline = SearchBatchResult((original,), 1, 0, (original,), (original,))
    calls = []

    def run(**kwargs):
        calls.append(kwargs)
        return baseline

    monkeypatch.setattr(scale_chart, "search_positive_scale_chart", lambda **kwargs: None)
    monkeypatch.setattr(
        module, "_build_search_backend", lambda **kwargs: SimpleNamespace(run_search=run)
    )
    monkeypatch.setattr(module, "NomadBackend", lambda **kwargs: SimpleNamespace(run_search=run))
    monkeypatch.setattr(
        module,
        "_run_supplemental_search_pass",
        lambda **kwargs: module._empty_search_batch_result(),
    )
    result = module.run_search(
        bundle=bundle,
        evaluator=evaluator,
        bounds=[(-1000000.0, 1000000.0)] * 4,
        initial_probe_result=InitialProbeResult((original,), {}),
        config=NomadConfig(max_bb_eval=1000, seed_values=(0,)),
        search_mode=search_mode,
        allow_integer_shortcuts=allow_integer_shortcuts,
    )
    assert len(calls) == 1
    assert original in result.candidates
    assert original in result.all_records
    assert original in result.guard_feasible_ledger


@pytest.mark.parametrize("factor", ["1e-300", "1", "1e300"])
def test_affine_inequalities_keep_same_interior_at_extreme_units(factor):
    points = affine_interior_points(
        variables=("u", "v"),
        constructions=(),
        guards=(f"AssumeGt(({factor})*(u-v),0)", f"AssumeGt(({factor})*v,0)"),
        bounds=((0, 2), (0, 2)),
        count=12,
        seed=19,
    )
    assert len(points) == 12
    assert all(0 < v < u < 2 and all(math.isfinite(x) for x in (u, v)) for u, v in points)


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


@pytest.mark.parametrize("representation", [False, True])
@pytest.mark.parametrize("seed", [0, 17, 81])
def test_pi_ordered_polytope_is_sampled_after_renaming_and_positive_scaling(representation, seed):
    variables = ("u", "v", "w") if representation else ("a", "b", "c")
    a, b, c = variables
    guards = [
        f"AssumeGt({a},0)",
        f"AssumeGt({b}-{a},0)",
        f"AssumeGt({c}-{b},0)",
        f"AssumeGt(2*pi-{c},0)",
    ]
    if representation:
        guards = [f"AssumeGt(7*({source[9:-3]}),0)" for source in reversed(guards)]
    arguments = dict(
        variables=variables,
        constructions=(),
        guards=tuple(guards),
        bounds=[(-20.0, 20.0)] * 3,
        count=24,
        seed=seed,
    )
    points = affine_interior_points(**arguments)
    assert len(points) == 24
    assert all(0 < x < y < z < 2 * math.pi for x, y, z in points)
    assert len(set(points)) > 12
    assert points == affine_interior_points(**arguments)


@pytest.mark.parametrize(
    "guards,bounds",
    [
        (("AssumeGt(x,0)", "AssumeLt(x,0)"), [(-1.0, 1.0)]),
        (("AssumeGe(x,0)", "AssumeLe(x,0)"), [(-1.0, 1.0)]),
        (("AssumeGt(x,2)", "AssumeLt(x,1)"), [(-5.0, 5.0)]),
        (("AssumeGt(0,1)", "AssumeGt(x,0)", "AssumeLt(x,1)"), [(-5.0, 5.0)]),
        (("AssumeGt(x,0)", "AssumeLt(x,1)"), [(-math.inf, math.inf)]),
        (("AssumeGt(x,0)", "AssumeLt(x,1)"), [(0.0, 0.0)]),
        (("AssumeGt(sin(x),0)", "AssumeGt(x*x,0)"), [(-5.0, 5.0)]),
    ],
)
def test_empty_boundary_unbounded_or_unsupported_models_safely_return_no_new_starts(guards, bounds):
    assert (
        affine_interior_points(variables=("x",), constructions=(), guards=guards, bounds=bounds)
        == ()
    )


def test_unbounded_original_guard_region_can_use_a_finite_heuristic_box():
    points = affine_interior_points(
        variables=("x", "y"),
        constructions=(),
        guards=("AssumeGt(x,0)", "AssumeGt(y-x,0)"),
        bounds=[(-10.0, 10.0)] * 2,
    )
    assert points and all(0 < x < y < 10 for x, y in points)


def test_scalar_aliases_and_negative_inequality_sides_are_equivalent():
    rows = affine_guard_rows(("x", "y"), (("s", "3*x+6"),), ("AssumeLt(-s,0)", "AssumeGt(2*y-x,4)"))
    assert rows == (((3.0, 0.0), 6.0), ((-1.0, 2.0), -4.0))


class OriginalEvaluator:
    def evaluate_float_residual(self, point):
        return SimpleNamespace(
            evaluation_status=EvaluationStatus.OK,
            residual_vector=(point[0] + point[1] - 1.0,),
            residual_norm_float=abs(point[0] + point[1] - 1.0),
        )

    def evaluate_guard(self, point):
        # A nonlinear original guard is intentionally absent from the LP.
        return (0 < point[0] < point[1] and point[0] * point[1] < 3.0), ()


@pytest.mark.parametrize("inconsistent", [False, True])
def test_sampler_keeps_original_candidates_and_checks_nonlinear_guards(inconsistent):
    spec = SimpleNamespace(construction=(), guards=["AssumeGt(x,0)", "AssumeGt(y-x,0)"])
    if inconsistent:
        spec.guards += ["AssumeLt(x,-1)"]
    bundle = SimpleNamespace(var_names=("x", "y"), spec=spec)
    original = FloatCandidate((-2.0, -1.0), 9.0, 3.0, False, EvaluationStatus.OK, 17, 0, 42)
    merged, metrics = augment_with_manifold_samples(
        bundle=bundle,
        evaluator=OriginalEvaluator(),
        bounds=[(-4.0, 4.0)] * 2,
        candidates=(original,),
        metrics={"retained": True},
        strategies=(AffineGuardSampler(),),
    )
    assert merged[0] is original
    assert metrics["retained"]
    if inconsistent:
        assert merged == (original,)
    else:
        assert len(merged) > 1
        assert all(OriginalEvaluator().evaluate_guard(c.x_float)[0] for c in merged[1:])


def test_feasible_existing_starts_skip_the_optional_lp(monkeypatch):
    from geosolver.engine.standard.search.sampling import affine_guards

    def fail(**kwargs):
        raise AssertionError("LP must not run for a probe with feasible starts")

    monkeypatch.setattr(affine_guards, "affine_interior_points", fail)
    existing = FloatCandidate((1.0, 2.0), 0.0, 0.0, True, EvaluationStatus.OK, 0, 0, 0)
    result = AffineGuardSampler().sample(
        bundle=None, evaluator=None, bounds=None, existing_candidates=(existing,)
    )
    assert result.candidates == ()
