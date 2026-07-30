from __future__ import annotations

import math
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from interval_rescue import (  # noqa: E402
    Expr,
    Interval,
    Problem,
    RescueConfig,
    Var,
    applicability,
    discover,
    portfolio_plan,
    unsupported,
)


def test_regular_1d_root_emits_proposal_but_never_answer() -> None:
    x = Var(0)
    result = discover(Problem((x**2 - 2.0,), ((1.0, 2.0),)))
    assert result.applicability.applicable
    assert result.proposals
    proposal = result.proposals[0]
    assert abs(proposal.point[0] - math.sqrt(2.0)) < 0.2
    assert proposal.certificate_kind == "krawczyk-strict-inclusion"
    assert proposal.authority is False
    assert proposal.requires_local_solver is True
    assert proposal.requires_canonical_source_replay is True
    assert result.answer_promotions == 0


def test_regular_coupled_2d_root_is_proposed() -> None:
    x, y = Var(0), Var(1)
    problem = Problem((x + y - 3.0, x - y - 1.0), ((1.5, 2.5), (0.5, 1.5)))
    result = discover(problem)
    assert len(result.proposals) == 1
    px, py = result.proposals[0].point
    assert abs(px - 2.0) < 1.0e-10
    assert abs(py - 1.0) < 1.0e-10


def test_singular_root_and_nonunique_manifold_do_not_promote() -> None:
    x, y = Var(0), Var(1)
    singular = discover(
        Problem((x**2,), ((-0.25, 0.25),)),
        RescueConfig(max_boxes=15, max_depth=4),
    )
    assert singular.proposals == ()
    assert singular.singular_midpoints > 0
    assert singular.answer_promotions == 0

    nonunique = discover(Problem((x + y,), ((-1.0, 1.0), (-1.0, 1.0))))
    assert not nonunique.applicability.applicable
    assert nonunique.reason == "nonsquare-system"
    assert nonunique.boxes_visited == 0


def test_boundary_root_fails_strict_inclusion() -> None:
    x = Var(0)
    result = discover(
        Problem((x,), ((0.0, 1.0),)),
        RescueConfig(max_boxes=15, max_depth=4),
    )
    assert result.applicability.applicable
    assert result.proposals == ()
    assert result.answer_promotions == 0

    guarded = discover(
        Problem((x,), ((0.0, 1.0),), strict_guard_state="boundary")
    )
    assert guarded.status == "inapplicable"
    assert guarded.reason == "strict-guard-not-interior"
    assert guarded.boxes_visited == 0


def test_transcendental_branch_and_opaque_paths_fallback_before_work() -> None:
    x = Var(0)
    fixtures = (
        Problem((unsupported("sin", x),), ((-1.0, 1.0),)),
        Problem((x,), ((-1.0, 1.0),), branch_state="crossing"),
        Problem((x,), ((-1.0, 1.0),), opaque_callbacks=True),
    )
    reasons = (
        "unsupported-transcendental-op:sin",
        "branch-crossing-or-unknown",
        "validated-dag-unavailable",
    )
    for problem, reason in zip(fixtures, reasons):
        result = discover(problem)
        assert result.status == "inapplicable"
        assert result.reason == reason
        assert result.boxes_visited == 0
        assert result.proposals == ()
        plan = portfolio_plan(result)
        assert plan.baseline_slots == 8
        assert plan.interval_slots == 0


def test_division_must_be_smooth_on_entire_box() -> None:
    x = Var(0)
    unsafe = applicability(Problem((1.0 / x,), ((-1.0, 1.0),)))
    safe = applicability(Problem((1.0 / x - 0.5,), ((1.0, 3.0),)))
    assert not unsafe.applicable
    assert unsafe.reason == "interval-domain-not-validated"
    assert safe.applicable


def test_outward_arithmetic_encloses_sampled_real_operations() -> None:
    left = Interval(-1.25, 2.5)
    right = Interval(0.5, 1.75)
    samples_left = (-1.25, -0.125, 2.5)
    samples_right = (0.5, 1.0, 1.75)
    operations = (
        (left + right, lambda a, b: a + b),
        (left - right, lambda a, b: a - b),
        (left * right, lambda a, b: a * b),
        (left / right, lambda a, b: a / b),
    )
    for enclosure, operation in operations:
        assert all(
            enclosure.contains(operation(a, b))
            for a in samples_left
            for b in samples_right
        )
    squared = left.pow_int(2)
    assert all(squared.contains(value**2) for value in samples_left + (0.0,))


def test_malformed_or_overflowing_dag_safely_falls_back() -> None:
    x = Var(0)
    fixtures = (
        (Problem((Expr("add", (x,)),), ((-1.0, 1.0),)), "malformed-arity:add"),
        (Problem((x * 1.0e308,), ((1.0, 2.0),)), "interval-domain-not-validated"),
    )
    for problem, reason in fixtures:
        result = discover(problem)
        assert result.status == "inapplicable"
        assert result.reason == reason
        assert result.boxes_visited == 0
        assert result.proposals == ()


def test_dimension_width_volume_and_power_caps_are_truth_blind() -> None:
    x, y, z = Var(0), Var(1), Var(2)
    fixtures = (
        (Problem((x, y, z), ((-1.0, 1.0),) * 3), "dimension-outside-cap"),
        (Problem((x,), ((-3.0, 3.0),)), "box-width-cap"),
        (Problem((x**7,), ((-1.0, 1.0),)), "unsupported-power"),
    )
    for problem, reason in fixtures:
        gate = applicability(problem)
        assert not gate.applicable
        assert gate.reason == reason
    volume_limited = applicability(
        Problem((x + y, x - y), ((-2.0, 2.0), (-2.0, 2.0))),
        RescueConfig(max_box_volume=12.0),
    )
    assert not volume_limited.applicable
    assert volume_limited.reason == "box-volume-cap"


def test_box_cap_is_hard_and_baseline_quota_survives() -> None:
    x = Var(0)
    config = RescueConfig(max_boxes=3, max_depth=20, total_launch_slots=8)
    result = discover(Problem((x**2,), ((-0.25, 0.25),)), config)
    assert result.status == "work-cap"
    assert result.boxes_visited == 3
    assert result.boxes_visited <= result.work_cap
    plan = portfolio_plan(result, config)
    assert plan.minimum_baseline_slots == 2
    assert plan.baseline_slots >= plan.minimum_baseline_slots
    assert plan.baseline_slots + plan.interval_slots == 8


def test_time_cap_can_fire_before_any_interval_box() -> None:
    x = Var(0)
    ticks = iter((0.0, 0.1))
    result = discover(
        Problem((x**2 - 2.0,), ((1.0, 2.0),)),
        RescueConfig(max_seconds=0.01),
        clock=lambda: next(ticks),
    )
    assert result.status == "time-cap"
    assert result.boxes_visited == 0
    assert result.proposals == ()


def test_interval_proposals_are_capped_and_baseline_leads_every_pair() -> None:
    x = Var(0)
    result = discover(
        Problem((x**2 - 2.0,), ((-2.0, 2.0),)),
        RescueConfig(max_boxes=32, max_depth=8, max_proposals=4),
    )
    assert len(result.proposals) == 2
    plan = portfolio_plan(result)
    assert plan.interval_slots == 2
    assert plan.baseline_slots == 6
    assert all(plan.launches[index].kind == "baseline" for index in range(0, 8, 2))
    assert all(
        launch.proposal is None or launch.proposal.requires_canonical_source_replay
        for launch in plan.launches
    )


def test_source_contains_no_truth_or_case_specific_router() -> None:
    source = (HERE / "interval_rescue.py").read_text(encoding="utf-8")
    forbidden = ("gold_target", "known_answer", "case_id", "family_id", "problem_id")
    assert all(term not in source for term in forbidden)
