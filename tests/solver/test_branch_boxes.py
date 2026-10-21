"""Branch boxes contracts and numerical regressions."""

from dataclasses import replace

import pytest
import sympy as sp
from mpmath import mp

from geosolver.engine.standard.search.algebraic_branch_boxes import (
    accepted_within_origin_box,
    certified_branch_boxes,
)
from geosolver.engine.standard.search.algebraic_branches import discover_polynomial_branches
from tests.helpers.algebraic import outcome, pipeline, refined, source
from tests.helpers.capabilities import requires_cpu_timer


def test_exact_boxes_enclose_rational_function_images_of_rootof():
    x = sp.Symbol("x")
    roots = sp.Poly(x**3 - x - 1, x).real_roots(radicals=False)
    solutions = [[r, 1 / (r + 2), sp.sqrt(2)] for r in roots]
    points = [[str(sp.N(v, 180)) for v in row] for row in solutions]
    boxes = certified_branch_boxes(solutions, points)
    assert boxes is not None
    assert len(boxes) == 1
    for value, (left, right) in zip(solutions[0], boxes[0], strict=True):
        assert sp.Rational(left) < value < sp.Rational(right)


@requires_cpu_timer
def test_disjoint_boxes_separate_close_repeated_roots_exactly():
    data = discover_polynomial_branches(
        {
            "variables": ["x"],
            "construction": [],
            "constraints": ["(x-1)**2*(x-1-1/10**20)**2"],
            "targets": [0],
        }
    )
    assert data is not None
    first, second = data["branch_boxes"]
    assert sp.Rational(first[0][1]) < sp.Rational(second[0][0])
    assert data["retained_root_indices"] == [0, 1]
    assert data["original_root_count"] == 2


@requires_cpu_timer
def test_branch_indices_survive_proven_guard_exclusion():
    data = discover_polynomial_branches(
        {
            "variables": ["x"],
            "construction": [],
            "constraints": ["x*x-1"],
            "targets": [0],
            "guards": ["x>0"],
        }
    )
    assert data is not None
    assert data["retained_root_indices"] == [1]
    assert data["excluded_roots"] == [{"root_index": 0, "guard_index": 0}]
    assert data["original_root_count"] == 2


def test_migrated_refinement_does_not_cover_originating_root():
    a, b = source(1), source(2)
    migrated = replace(refined(a), x_hp=(mp.mpf(2),))
    accepted = refined(b)
    primary = pipeline._OrderedSearchAttemptDescriptor("primary", "primary", None, None)
    state = outcome(primary, (a, b), (migrated, accepted), ("7", "7")).completed_stage_state
    assert pipeline._algebraic_provenance_incomplete(state)


def test_uncertainty_crossing_box_boundary_does_not_cover_root():
    a = source(1)
    assert accepted_within_origin_box(refined(a), a)
    assert not accepted_within_origin_box(
        replace(refined(a), coordinate_uncertainty=(mp.mpf(".3"),)), a
    )
    assert not accepted_within_origin_box(replace(refined(a), coordinate_uncertainty=()), a)


@pytest.mark.parametrize("error", [mp.inf, mp.nan, mp.mpf(-1)])
def test_nonfinite_or_negative_uncertainty_declines_coverage(error):
    a = source(1)
    assert not accepted_within_origin_box(replace(refined(a), coordinate_uncertainty=(error,)), a)


def test_accepted_interval_comparison_does_not_round_at_ambient_precision():
    with mp.workdps(200):
        coordinate = mp.mpf(1) + mp.mpf("1e-100")
        error = mp.mpf("1e-150")
    a = replace(source(1), originating_branch_box=(("0", "1"),))
    with mp.workdps(15):
        assert not accepted_within_origin_box(
            replace(refined(a), x_hp=(coordinate,), coordinate_uncertainty=(error,)), a
        )


def test_unproved_coordinate_interval_declines_entire_box_set():
    with pytest.raises(ValueError, match="unsupported exact algebraic"):
        certified_branch_boxes([[sp.sin(1)]], [[str(sp.N(sp.sin(1), 180))]])
