from __future__ import annotations

from dataclasses import replace
import unittest

import numpy as np

from candidate import DEFAULT, portfolio_trace, solve, solve_small_dense_qp
from generated_cases import (
    NEGATIVE_FAMILIES,
    POSITIVE_FAMILIES,
    isolated_invalid_near_root,
    nonconvex_cell,
    nonfinite_or_opaque,
    rotated_wedge,
    strict_boundary_root,
    transformed,
)


class CandidateTest(unittest.TestCase):
    def test_dense_qp_enforces_box_and_cut(self) -> None:
        hessian = np.eye(2)
        gradient = np.asarray((-2.0, -1.0))
        inequalities = np.asarray(
            (
                (1.0, 0.0),
                (-1.0, 0.0),
                (0.0, 1.0),
                (0.0, -1.0),
                (1.0, 1.0),
            )
        )
        bounds = np.asarray((1.0, 1.0, 1.0, 1.0, 0.5))
        point = solve_small_dense_qp(hessian, gradient, inequalities, bounds)
        self.assertIsNotNone(point)
        assert point is not None
        self.assertTrue(np.all(inequalities @ point <= bounds + 1.0e-9))
        self.assertAlmostEqual(float(point.sum()), 0.5, places=7)

    def test_portfolio_keeps_three_quarters_ordinary(self) -> None:
        trace = portfolio_trace(20)
        self.assertEqual(trace.count("baseline"), 15)
        self.assertEqual(trace.count("side"), 5)
        self.assertGreaterEqual(trace.count("baseline") / len(trace), DEFAULT.baseline_fraction)

    def test_positive_families_gain_without_loss(self) -> None:
        for factory in POSITIVE_FAMILIES:
            with self.subTest(factory=factory.__name__):
                problem = factory(0)
                control = solve(problem, problem.start, callback_cap=100, arm="control")
                other = factory(0)
                candidate = solve(other, other.start, callback_cap=100, arm="candidate")
                self.assertFalse(control.solved)
                self.assertTrue(candidate.solved)
                self.assertEqual(control.callbacks, candidate.callbacks)
                self.assertGreater(candidate.cuts_learned, 0)

    def test_negative_and_near_miss_never_promote(self) -> None:
        for factory in NEGATIVE_FAMILIES:
            with self.subTest(factory=getattr(factory, "__name__", "lambda")):
                problem = factory(0)
                outcome = solve(problem, problem.start, callback_cap=100, arm="candidate")
                self.assertFalse(outcome.solved)

    def test_strict_boundary_root_requires_canonical_replay(self) -> None:
        problem = strict_boundary_root(0)
        outcome = solve(problem, problem.start, callback_cap=100, arm="candidate")
        self.assertFalse(outcome.solved)
        self.assertGreater(outcome.canonical_replays, 0)

    def test_isolated_invalid_pocket_fails_closed(self) -> None:
        problem = isolated_invalid_near_root(0)
        outcome = solve(problem, problem.start, callback_cap=40, arm="candidate")
        self.assertFalse(outcome.solved)
        self.assertEqual(outcome.cuts_learned, 0)
        self.assertEqual(outcome.status, "isolated-invalid-pocket")

    def test_nonfinite_and_opaque_fail_closed(self) -> None:
        for opaque in (False, True):
            problem = nonfinite_or_opaque(0, opaque=opaque)
            outcome = solve(problem, problem.start, callback_cap=40, arm="candidate")
            self.assertFalse(outcome.solved)
            self.assertEqual(outcome.cuts_learned, 0)
            self.assertIn("fail-closed", outcome.status)

    def test_strongly_nonconvex_unresolved_bundle_fails_closed(self) -> None:
        problem = nonconvex_cell(0)
        outcome = solve(problem, problem.start, callback_cap=100, arm="candidate")
        self.assertFalse(outcome.solved)
        self.assertGreater(outcome.cuts_learned, 0)
        self.assertIn("fail-closed", outcome.status)

    def test_branch_rank_and_scaling_changes_discard_side_state(self) -> None:
        for kind in ("branch", "rank", "scaling"):
            with self.subTest(kind=kind):
                base = rotated_wedge(0)

                class ChangedContext:
                    dimension = base.dimension
                    residual_dimension = base.residual_dimension

                    def observe(self, point):
                        observation = base.observe(point)
                        if np.array_equal(np.asarray(point), base.start):
                            return observation
                        if kind == "branch":
                            return replace(observation, branch_token="other-branch")
                        if kind == "rank":
                            return replace(observation, rank=observation.rank - 1)
                        return replace(observation, scaling=observation.scaling * 1.1)

                    def canonical_replay(self, point):
                        return base.canonical_replay(point)

                outcome = solve(
                    ChangedContext(), base.start, callback_cap=30, arm="candidate"
                )
                self.assertFalse(outcome.solved)
                self.assertEqual(outcome.cuts_learned, 0)
                self.assertIn("branch-rank-scaling", outcome.status)

    def test_material_accepted_move_retires_local_cut_bundle(self) -> None:
        problem = rotated_wedge(0)
        outcome = solve(problem, problem.start, callback_cap=100, arm="candidate")
        self.assertTrue(outcome.solved)
        self.assertGreater(outcome.cuts_learned, 0)
        self.assertGreater(outcome.cut_flushes, 0)

    def test_permutation_scale_reflection_and_guard_order(self) -> None:
        base_problem = rotated_wedge(0)
        base = solve(base_problem, base_problem.start, callback_cap=100, arm="candidate")
        self.assertTrue(base.solved)
        for kind in ("permutation", "scale", "reflection", "guard-order"):
            with self.subTest(kind=kind):
                problem = transformed(base_problem, kind)
                outcome = solve(problem, problem.start, callback_cap=100, arm="candidate")
                self.assertEqual(outcome.solved, base.solved)


if __name__ == "__main__":
    unittest.main()
