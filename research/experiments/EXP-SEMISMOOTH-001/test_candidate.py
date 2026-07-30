from __future__ import annotations

import inspect

import numpy as np

from candidate import Configuration, Node, Program, constant, input_node, op, propose_active_strata
from run_generated import FAMILIES, make_system, run_arm, transformed


def test_abs_tangency_enumerates_both_branch_consistent_proposals() -> None:
    system = make_system("abs_tangency", "positive", 3)
    result = propose_active_strata(system.program, system.start, system.scale, semantic=system.semantic)
    assert result.status == "ok"
    assert result.active_sites == 1
    assert result.models_considered == 2
    assert len(result.proposals) == 2
    assert run_arm(system, True)["roots"] == [0, 1]


def test_min_max_intersection_discards_inconsistent_singular_models() -> None:
    system = make_system("min_max_intersection", "positive", 4)
    result = propose_active_strata(system.program, system.start, system.scale, semantic=system.semantic)
    assert result.active_sites == 2
    assert result.models_considered == 4
    assert len(result.proposals) == 2
    assert run_arm(system, False)["roots"] == []
    assert run_arm(system, True)["roots"] == [0, 1]


def test_coincident_piecewise_cse_is_one_site_not_row_cartesian_product() -> None:
    system = make_system("coincident_piecewise_branch", "positive", 5)
    result = propose_active_strata(system.program, system.start, system.scale, semantic=system.semantic)
    assert result.active_sites == 1
    assert result.models_considered == 2
    assert len(result.proposals) == 2


def test_smooth_and_opaque_sources_fall_back_without_proposals() -> None:
    smooth = make_system("smooth_control", "positive", 1)
    smooth_result = propose_active_strata(smooth.program, smooth.start, smooth.scale)
    assert smooth_result.status == "smooth_or_inactive_fallback"
    assert smooth_result.proposals == ()

    opaque = make_system("opaque_c0_fallback", "positive", 1)
    opaque_result = propose_active_strata(opaque.program, opaque.start, opaque.scale)
    assert opaque_result.status == "opaque_or_unsupported_fallback"
    assert opaque_result.proposals == ()
    assert run_arm(opaque, False)["roots"] == run_arm(opaque, True)["roots"]


def test_too_many_active_strata_fails_closed_without_order_selection() -> None:
    nodes = tuple(op("abs", input_node(index)) for index in range(4))
    program = Program(4, nodes)
    result = propose_active_strata(
        program,
        np.zeros(4),
        np.ones(4),
        configuration=Configuration(maximum_active_models=8),
    )
    assert result.status == "too_many_active_strata_fallback"
    assert result.models_considered == 16
    assert result.proposals == ()


def test_strict_near_miss_never_emits_the_invalid_adjacent_branch() -> None:
    system = make_system("abs_tangency", "near_miss", 7)
    result = propose_active_strata(system.program, system.start, system.scale, semantic=system.semantic)
    assert all(system.semantic(point) for point in result.proposals)
    assert run_arm(system, True)["roots"] == [0]


def test_branch_order_cse_permutation_and_scale_metamorphic_parity() -> None:
    for family in FAMILIES:
        system = make_system(family, "positive", 2)
        expected = run_arm(system, True)["roots"]
        for mode in (
            "branch_order",
            "cse_rebuild",
            "residual_permutation",
            "redundant_row",
            "equation_scale",
            "variable_permutation",
        ):
            assert run_arm(transformed(system, mode), True)["roots"] == expected


def test_candidate_boundary_has_no_case_truth_or_outcome_inputs() -> None:
    parameters = set(inspect.signature(propose_active_strata).parameters)
    forbidden = {
        "case_id",
        "problem_id",
        "family",
        "truth",
        "target",
        "answer",
        "prior_outcome",
    }
    assert parameters.isdisjoint(forbidden)


def test_side_lane_is_fixed_at_ten_percent() -> None:
    system = make_system("abs_tangency", "positive", 0)
    assert run_arm(system, True)["baseline_lane_fraction"] == 0.9
