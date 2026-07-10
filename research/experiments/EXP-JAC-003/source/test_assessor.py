from __future__ import annotations

import math
import unittest

import assess_development as assessor


class ComparisonClosureTests(unittest.TestCase):
    def test_dense_colored_equality_boundary_passes(self) -> None:
        dense = [[0.0]]
        tolerance = assessor.DENSE_COLOR_ATOL
        colored = [[tolerance]]
        self.assertEqual(
            assessor._entry_mismatches(
                colored,
                dense,
                atol=assessor.DENSE_COLOR_ATOL,
                rtol=assessor.DENSE_COLOR_RTOL,
                scale_right_only=True,
            ),
            0,
        )

    def test_dense_colored_strict_excess_fails(self) -> None:
        dense = [[0.0]]
        tolerance = assessor.DENSE_COLOR_ATOL
        colored = [[math.nextafter(tolerance, math.inf)]]
        self.assertEqual(
            assessor._entry_mismatches(
                colored,
                dense,
                atol=assessor.DENSE_COLOR_ATOL,
                rtol=assessor.DENSE_COLOR_RTOL,
                scale_right_only=True,
            ),
            1,
        )

    def test_nonfinite_and_shape_fail(self) -> None:
        self.assertEqual(
            assessor._entry_mismatches(
                [[math.nan]],
                [[0.0]],
                atol=1.0,
                rtol=1.0,
                scale_right_only=True,
            ),
            1,
        )
        self.assertEqual(
            assessor._entry_mismatches(
                [[0.0, 0.0]],
                [[0.0]],
                atol=1.0,
                rtol=1.0,
                scale_right_only=True,
            ),
            1,
        )

    def test_analytic_equality_boundary_passes(self) -> None:
        analytic = [[0.0]]
        tolerance = assessor.DENSE_ANALYTIC_ATOL
        self.assertEqual(assessor._analytic_mismatch([[tolerance]], analytic), 0)

    def test_route_boundary_is_dense(self) -> None:
        n, colors, nonzeros = 10, 8, 8
        self.assertFalse(colors < n and 40 * n * colors + 5 * nonzeros <= 32 * n * n)


class GoldClosureTests(unittest.TestCase):
    @staticmethod
    def _attempt() -> dict[str, object]:
        return {
            "started": True,
            "replay_completed_within_deadline": True,
            "final": [1.0, 2.0],
            "replay_status": "EVAL_OK",
            "replay_residual_count": 2,
            "replay_residual_infinity": 1.0e-8,
            "replay_branch_keys": ["nonnegative"],
        }

    @staticmethod
    def _truth() -> dict[str, object]:
        return {
            "gold_configuration": [1.0, 2.0],
            "gold_target": 2.0,
            "gold_branch_label": "nonnegative",
        }

    @staticmethod
    def _candidate() -> dict[str, object]:
        return {"residual_count": 2, "scales": [1.0, 1.0]}

    def test_all_equalities_pass(self) -> None:
        valid, configuration_error, target_error = assessor._gold_valid(
            self._attempt(), self._truth(), self._candidate()
        )
        self.assertTrue(valid)
        self.assertEqual(configuration_error, 0.0)
        self.assertEqual(target_error, 0.0)

    def test_post_deadline_replay_fails(self) -> None:
        attempt = self._attempt()
        attempt["replay_completed_within_deadline"] = False
        self.assertFalse(
            assessor._gold_valid(attempt, self._truth(), self._candidate())[0]
        )

    def test_branch_mismatch_fails_without_margin_exception(self) -> None:
        attempt = self._attempt()
        attempt["replay_branch_keys"] = ["negative"]
        self.assertFalse(
            assessor._gold_valid(attempt, self._truth(), self._candidate())[0]
        )

    def test_nonpositive_scale_fails(self) -> None:
        candidate = self._candidate()
        candidate["scales"] = [1.0, 0.0]
        self.assertFalse(
            assessor._gold_valid(self._attempt(), self._truth(), candidate)[0]
        )


if __name__ == "__main__":
    unittest.main()
