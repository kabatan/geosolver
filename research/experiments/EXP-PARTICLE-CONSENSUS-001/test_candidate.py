from __future__ import annotations

import unittest

import numpy as np

from candidate import NumericalProblem, replay_valid, solve_portfolio
from run_generated import fixtures, run


class ParticleConsensusTests(unittest.TestCase):
    def test_equal_callback_budget_and_baseline_floor(self) -> None:
        for fixture in fixtures(range(2)):
            control = solve_portfolio(fixture.problem, "control")
            candidate = solve_portfolio(fixture.problem, "candidate")
            self.assertEqual(control.callbacks, 512)
            self.assertEqual(candidate.callbacks, 512)
            self.assertEqual(control.callbacks, candidate.callbacks)
            self.assertGreaterEqual(candidate.baseline_callbacks / candidate.callbacks, 0.75)

    def test_opaque_fallback_is_identical(self) -> None:
        for fixture in fixtures(range(2)):
            if fixture.problem.smooth_numeric_jacobian:
                continue
            control = solve_portfolio(fixture.problem, "control")
            candidate = solve_portfolio(fixture.problem, "candidate")
            self.assertEqual(control.activation["mode"], "opaque_numeric_fallback")
            self.assertEqual(len(control.proposals), len(candidate.proposals))
            for left, right in zip(control.proposals, candidate.proposals):
                np.testing.assert_array_equal(left, right)

    def test_source_replay_rejects_inconsistent_systems(self) -> None:
        for fixture in fixtures(range(2)):
            if fixture.truth:
                continue
            result = solve_portfolio(fixture.problem, "candidate")
            self.assertEqual(replay_valid(fixture.problem, result.proposals), [])

    def test_no_hidden_routing_fields(self) -> None:
        fields = set(NumericalProblem.__dataclass_fields__)
        forbidden = {"id", "family", "truth", "target", "case", "source", "score"}
        self.assertFalse(fields & forbidden)

    def test_generated_gate(self) -> None:
        aggregate = run()
        self.assertEqual(aggregate["safety_false_extra"], 0)
        self.assertTrue(aggregate["callback_parity_512"])
        self.assertGreaterEqual(aggregate["baseline_quota_min"], 0.75)
        self.assertTrue(aggregate["metamorphic_pass"])
        self.assertEqual(aggregate["totals"]["loss"], 0)
        self.assertGreater(aggregate["totals"]["gain"], 0)
        self.assertGreater(aggregate["activation"]["force_events"], 0)


if __name__ == "__main__":
    unittest.main()

