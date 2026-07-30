from __future__ import annotations

import unittest

import numpy as np

from candidate import discover_local_orbits, route_trace, run_portfolio
from generated_cases import (
    binomial_case,
    exact_local_witnesses,
    generated_suite,
    opaque_fallback_case,
    regular_fallback_case,
)


def _normalized_points(case, proposals):
    return sorted(
        tuple(round(float(value), 8) for value in case.from_source(point))
        for point in proposals
    )


class LocalMonodromyOrbitTest(unittest.TestCase):
    def test_cusp_has_one_nontrivial_local_orbit(self) -> None:
        case = binomial_case("cusp", "test", fibre_degree=2, projection_power=3)
        ledger = discover_local_orbits(case.problem, directions=(1,))
        self.assertTrue(ledger.activated)
        self.assertEqual([len(orbit) for orbit in ledger.orbits], [2])
        self.assertEqual(ledger.permutations[0], (1, 0))
        self.assertEqual(len(ledger.proposals), 2)

    def test_reducible_node_separates_local_branches(self) -> None:
        case = binomial_case("node", "test", fibre_degree=2, projection_power=2)
        ledger = discover_local_orbits(case.problem, directions=(1,))
        self.assertEqual([len(orbit) for orbit in ledger.orbits], [1, 1])
        self.assertEqual(ledger.permutations[0], (0, 1))

    def test_loop_reversal_inverts_permutation_and_preserves_orbits(self) -> None:
        case = binomial_case("ramified", "test", fibre_degree=4, projection_power=5)
        forward = discover_local_orbits(case.problem, directions=(1,))
        reverse = discover_local_orbits(case.problem, directions=(-1,))
        inverse = [0] * len(forward.permutations[0])
        for left, right in enumerate(forward.permutations[0]):
            inverse[right] = left
        self.assertEqual(tuple(inverse), reverse.permutations[0])
        self.assertEqual([len(x) for x in forward.orbits], [len(x) for x in reverse.orbits])
        self.assertEqual(
            sorted(tuple(round(float(v), 9) for v in p.point) for p in forward.proposals),
            sorted(tuple(round(float(v), 9) for v in p.point) for p in reverse.proposals),
        )

    def test_root_label_permutation_preserves_orbit_sizes_and_proposals(self) -> None:
        case = binomial_case("ramified", "test", fibre_degree=4, projection_power=5)
        plain = discover_local_orbits(case.problem, initial_order=(0, 1, 2, 3))
        relabelled = discover_local_orbits(case.problem, initial_order=(2, 0, 3, 1))
        self.assertEqual(sorted(map(len, plain.orbits)), sorted(map(len, relabelled.orbits)))
        self.assertEqual(
            sorted(tuple(round(float(v), 9) for v in p.point) for p in plain.proposals),
            sorted(tuple(round(float(v), 9) for v in p.point) for p in relabelled.proposals),
        )

    def test_source_permutation_and_scale_are_covariant(self) -> None:
        base = binomial_case("base", "test", fibre_degree=2, projection_power=3)
        transformed = binomial_case(
            "transformed",
            "test",
            fibre_degree=2,
            projection_power=3,
            transform=np.asarray([[0.0, 2.0], [3.0, 0.0]]),
            residual_scale=13.0,
        )
        base_result = discover_local_orbits(base.problem)
        transformed_result = discover_local_orbits(transformed.problem)
        self.assertEqual(
            _normalized_points(base, [p.point for p in base_result.proposals]),
            _normalized_points(transformed, [p.point for p in transformed_result.proposals]),
        )
        self.assertEqual(sorted(map(len, base_result.orbits)), sorted(map(len, transformed_result.orbits)))

    def test_all_generated_proposals_are_exact_local_witnesses(self) -> None:
        for case in generated_suite():
            exact = exact_local_witnesses(case)
            result = run_portfolio(case.problem, exact[:1])
            for proposal in result.proposals:
                self.assertTrue(any(np.linalg.norm(proposal - target) <= 2.0e-8 for target in exact))

    def test_opaque_and_regular_cases_fall_back_without_side_evaluation(self) -> None:
        opaque = opaque_fallback_case()
        baseline = (np.asarray([0.04, np.sin(0.04)]),)
        opaque_result = run_portfolio(opaque.problem, baseline)
        self.assertFalse(opaque_result.ledger.activated)
        self.assertEqual(opaque_result.ledger.reason, "opaque_fallback")
        self.assertEqual(opaque._calls["count"], 0)
        regular = regular_fallback_case()
        regular_exact = exact_local_witnesses(regular)
        regular_result = run_portfolio(regular.problem, regular_exact[:1])
        self.assertFalse(regular_result.ledger.activated)
        self.assertEqual(regular_result.ledger.reason, "regular_germ_fallback")

    def test_baseline_quota_and_digest_are_immutable(self) -> None:
        trace = route_trace(16)
        self.assertEqual(trace.count("baseline"), 12)
        self.assertEqual(trace.count("local_monodromy"), 4)
        case = generated_suite()[0]
        exact = exact_local_witnesses(case)
        result = run_portfolio(case.problem, exact[:1])
        self.assertEqual(result.baseline_digest_before, result.baseline_digest_after)


if __name__ == "__main__":
    unittest.main()
