from __future__ import annotations

import unittest

import numpy as np

from candidate import (
    canonical_source_replay,
    discover_true_eigenvalues,
    ordinary_regular_proposals,
    route_trace,
    run_portfolio,
)
from generated_cases import generated_suite, regular_near_miss, singular_diagonal_case


class SingularPEPRankCompletionTest(unittest.TestCase):
    def test_singular_pencil_recovers_true_and_filters_fake(self) -> None:
        case = singular_diagonal_case("one", "test", "positive", (0.75,), seed=31)
        result = discover_true_eigenvalues(case.problem)
        self.assertTrue(result.activated)
        self.assertEqual(result.normal_rank, 2)
        self.assertEqual(result.corank, 1)
        self.assertEqual(len(result.proposals), 1)
        self.assertAlmostEqual(result.proposals[0], 0.75, places=6)
        self.assertGreater(result.rejected_fake, 0)

    def test_polynomial_shear_keeps_true_set(self) -> None:
        plain = singular_diagonal_case("plain", "test", "positive", (-0.6, 1.2), seed=32)
        sheared = singular_diagonal_case(
            "sheared", "test", "positive", (-0.6, 1.2), seed=32, polynomial_shear=True
        )
        plain_result = discover_true_eigenvalues(plain.problem)
        sheared_result = discover_true_eigenvalues(sheared.problem)
        np.testing.assert_allclose(plain_result.proposals, (-0.6, 1.2), atol=2.0e-6)
        np.testing.assert_allclose(sheared_result.proposals, plain_result.proposals, atol=2.0e-6)

    def test_left_right_orthogonal_and_equation_scale_invariance(self) -> None:
        first = singular_diagonal_case("a", "test", "positive", (-1.1, 0.4), seed=33, scale=1.0)
        second = singular_diagonal_case("b", "test", "positive", (-1.1, 0.4), seed=34, scale=19.0)
        np.testing.assert_allclose(
            discover_true_eigenvalues(first.problem).proposals,
            discover_true_eigenvalues(second.problem).proposals,
            atol=2.0e-6,
        )

    def test_close_distinct_roots_are_not_merged(self) -> None:
        case = singular_diagonal_case(
            "close", "test", "near_miss", (0.5, 0.5006), seed=35, polynomial_shear=True
        )
        result = discover_true_eigenvalues(case.problem)
        np.testing.assert_allclose(result.proposals, (0.5, 0.5006), atol=3.0e-6)

    def test_complex_and_completion_only_values_are_not_emitted(self) -> None:
        complex_case = singular_diagonal_case("complex", "test", "negative", (1j, -1j), seed=36)
        constant_case = singular_diagonal_case("constant", "test", "negative", (), seed=37)
        self.assertEqual(discover_true_eigenvalues(complex_case.problem).proposals, ())
        self.assertEqual(discover_true_eigenvalues(constant_case.problem).proposals, ())

    def test_regular_and_opaque_fallback(self) -> None:
        regular = regular_near_miss()
        regular_result = discover_true_eigenvalues(regular.problem)
        self.assertFalse(regular_result.activated)
        self.assertEqual(regular_result.reason, "regular_polynomial_fallback")
        np.testing.assert_allclose(ordinary_regular_proposals(regular.problem), (0.5,), atol=2.0e-6)
        opaque = generated_suite()[-1]
        opaque_result = discover_true_eigenvalues(opaque.problem)
        self.assertFalse(opaque_result.activated)
        self.assertEqual(opaque_result.reason, "opaque_fallback")

    def test_every_proposal_replays_and_baseline_is_immutable(self) -> None:
        for case in generated_suite():
            result = run_portfolio(case.problem, ())
            self.assertEqual(result.baseline_digest_before, result.baseline_digest_after)
            for value in result.side.proposals:
                self.assertTrue(canonical_source_replay(case.problem, value, result.side.normal_rank))

    def test_quota_is_exactly_75_25(self) -> None:
        trace = route_trace(16)
        self.assertEqual(trace.count("baseline"), 12)
        self.assertEqual(trace.count("rank_completion"), 4)


if __name__ == "__main__":
    unittest.main()
