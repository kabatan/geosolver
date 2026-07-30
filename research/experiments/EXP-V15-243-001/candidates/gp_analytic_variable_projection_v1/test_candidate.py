from __future__ import annotations

import unittest

import numpy as np

from candidate import (
    analytic_reduced_model,
    canonical_source_replay,
    route_trace,
    run_portfolio,
    solve_analytic_varpro,
    solve_fd_projected_varpro,
)
from generated_cases import generated_suite, rotate_nonlinear_coordinates, two_rate_case


class AnalyticVariableProjectionTest(unittest.TestCase):
    def test_analytic_reduced_jacobian_matches_central_difference(self) -> None:
        for case in generated_suite()[:12]:
            x = case.start[:1]
            model = analytic_reduced_model(case.problem, x)
            step = 1.0e-6
            plus = analytic_reduced_model(case.problem, x + step)
            minus = analytic_reduced_model(case.problem, x - step)
            finite_difference = (plus.residual - minus.residual) / (2.0 * step)
            np.testing.assert_allclose(model.jacobian[:, 0], finite_difference, rtol=3.0e-5, atol=3.0e-7)

    def test_positive_proposals_replay(self) -> None:
        for case in generated_suite()[:12]:
            result = solve_analytic_varpro(case.problem, case.start)
            if result.solved:
                self.assertTrue(canonical_source_replay(case.problem, result.point))

    def test_rank_deficient_and_ill_conditioned_fail_closed(self) -> None:
        for case in (item for item in generated_suite() if item.family == "rank_near_miss"):
            result = solve_analytic_varpro(case.problem, case.start)
            self.assertFalse(result.activated)
            self.assertIn("linear_block_fallback", result.reason)

    def test_nonaffine_and_opaque_fallback(self) -> None:
        nonaffine, opaque = generated_suite()[-2:]
        self.assertEqual(solve_analytic_varpro(nonaffine.problem, nonaffine.start).reason, "nonaffine_fallback")
        self.assertEqual(solve_analytic_varpro(opaque.problem, opaque.start).reason, "opaque_fallback")

    def test_portfolio_preserves_baseline_start_and_quota(self) -> None:
        case = generated_suite()[0]
        result = run_portfolio(case.problem, case.start)
        self.assertEqual(result.baseline_digest_before, result.baseline_digest_after)
        self.assertEqual(result.route_trace.count("baseline"), 12)
        self.assertEqual(result.route_trace.count("analytic_varpro"), 4)
        self.assertEqual(route_trace(16), result.route_trace)

    def test_coordinate_and_equation_scale_covariance(self) -> None:
        case = generated_suite()[0]
        base = solve_analytic_varpro(case.problem, case.start)
        self.assertTrue(base.solved)
        original_operator = case.problem.operator
        scale = 17.0

        def scaled_operator(x):
            state = original_operator(x)
            from candidate import OperatorState
            return OperatorState(scale * state.matrix, scale * state.matrix_derivative, scale * state.rhs, scale * state.rhs_derivative, scale * state.outer_residual, scale * state.outer_jacobian)

        from dataclasses import replace
        scaled_problem = replace(
            case.problem,
            operator=scaled_operator,
            full_residual=lambda point: scale * case.problem.full_residual(point),
            full_jacobian=lambda point: scale * case.problem.full_jacobian(point),
        )
        scaled = solve_analytic_varpro(scaled_problem, case.start)
        self.assertTrue(scaled.solved)
        np.testing.assert_allclose(scaled.point, base.point, atol=2.0e-7)

    def test_fd_control_has_same_recall_but_more_inner_solves(self) -> None:
        for case in generated_suite()[:14]:
            analytic = solve_analytic_varpro(case.problem, case.start)
            control = solve_fd_projected_varpro(case.problem, case.start)
            self.assertEqual(analytic.solved, control.solved)
            if analytic.solved:
                self.assertLess(analytic.inner_solves, control.inner_solves)

    def test_nonlinear_rotation_covariance(self) -> None:
        case = two_rate_case("rotation", np.asarray([-0.65, 0.75]), np.asarray([0.3, -0.5]))
        angle = 0.63
        rotation = np.asarray([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
        rotated = rotate_nonlinear_coordinates(case, rotation)
        base = solve_analytic_varpro(case.problem, case.start)
        transformed = solve_analytic_varpro(rotated.problem, rotated.start)
        self.assertEqual(base.solved, transformed.solved)
        self.assertTrue(base.solved)
        mapped = np.concatenate((rotation @ transformed.point[:2], transformed.point[2:]))
        np.testing.assert_allclose(mapped, base.point, atol=5.0e-6)


if __name__ == "__main__":
    unittest.main()
