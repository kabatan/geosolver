from __future__ import annotations

import unittest

import numpy as np

from candidate import Config, _svgd_direction, portfolio_trace, run_branching_svgd


class BranchingMechanismTests(unittest.TestCase):
    def test_roles_retention_offspring_and_no_deaths(self) -> None:
        points = np.array([[-0.2, 0.0], [0.0, 0.1], [0.2, -0.1], [0.1, 0.2]])
        result = run_branching_svgd(
            points,
            lambda x: -x,
            lambda x: bool(np.all(np.abs(x) < 20.0)),
            seed=9,
        )
        telemetry = result.telemetry
        self.assertEqual(telemetry.deaths, 0)
        self.assertEqual(telemetry.offspring_attempted["O"], 0)
        self.assertGreater(telemetry.offspring_accepted["E"], 0)
        self.assertGreater(telemetry.offspring_accepted["S"], 0)
        self.assertEqual(telemetry.unique_spine_checks, Config().generations + 1)
        self.assertTrue(all(c == 1 for c in (r["S"] for r in telemetry.role_counts)))
        self.assertGreater(telemetry.old_particles_retained, len(points))
        self.assertEqual(len({p.identity for p in result.particles}), len(result.particles))

    def test_uniform_spine_draw_is_not_position_biased(self) -> None:
        # Generation zero uses rng.integers(n), the same operation as later draws.
        counts = np.zeros(5, dtype=int)
        config = Config(generations=0)
        points = np.arange(5.0)[:, None]
        for seed in range(5000):
            result = run_branching_svgd(
                points,
                lambda x: np.zeros_like(x),
                lambda x: True,
                seed=seed,
                config=config,
            )
            counts[next(i for i, p in enumerate(result.particles) if p.role == "S")] += 1
        self.assertTrue(np.all(counts > 850), counts)
        self.assertTrue(np.all(counts < 1150), counts)

    def test_svgd_direction_permutation_and_reflection_covariance(self) -> None:
        z = np.array([[-1.0, 0.2], [0.1, -0.3], [0.8, 0.7], [1.4, -0.4]])
        score = -z + np.array([0.3, -0.1])
        direction, _ = _svgd_direction(z, score, 0.04)
        transform = np.array([[0.0, -1.0], [1.0, 0.0]])
        transformed, _ = _svgd_direction(z @ transform.T, score @ transform.T, 0.04)
        np.testing.assert_allclose(
            transformed, direction @ transform.T, atol=2e-14, rtol=2e-14
        )

    def test_portfolio_quota_is_exact(self) -> None:
        trace = portfolio_trace(12)
        self.assertEqual(trace.count("baseline"), 9)
        self.assertEqual(trace.count("side"), 3)


if __name__ == "__main__":
    unittest.main()
