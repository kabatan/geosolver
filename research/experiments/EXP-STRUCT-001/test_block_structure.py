from __future__ import annotations

import itertools
import unittest

from block_structure import (
    allocate_portfolio,
    analyze_relation_supports,
    extract_v15_structure,
    solve_candidate,
)


class BlockStructureTests(unittest.TestCase):
    def test_chain_decomposes_in_dependency_order(self):
        plan = analyze_relation_supports(((0,), (0, 1), (1, 2), (0, 2, 3)), 4)
        self.assertTrue(plan.applicable)
        self.assertEqual(tuple(block.variable_indices for block in plan.blocks), ((0,), (1,), (2,), (3,)))
        self.assertEqual(plan.maximum_block_size, 1)
        self.assertEqual(plan.block_factor_work, 4)
        self.assertEqual(plan.dense_factor_work, 64)
        self.assertTrue(all(
            predecessor < block_index
            for block_index, block in enumerate(plan.blocks)
            for predecessor in block.predecessor_blocks
        ))

    def test_irreducible_cycle_falls_back(self):
        plan = analyze_relation_supports(((0, 1), (1, 2), (0, 2)), 3)
        self.assertFalse(plan.applicable)
        self.assertEqual(plan.reason, "irreducible")
        self.assertEqual(plan.maximum_block_size, 3)
        self.assertEqual(allocate_portfolio(plan, 17).baseline_starts, 17)

    def test_relation_permutation_preserves_block_partition(self):
        supports = ((0,), (0, 1), (1, 2), (0, 2, 3))
        signatures = set()
        for order in itertools.permutations(range(4)):
            plan = analyze_relation_supports((supports[index] for index in order), 4)
            signatures.add(
                (
                    plan.applicable,
                    tuple(sorted(len(block.variable_indices) for block in plan.blocks)),
                    plan.factor_work_ratio,
                )
            )
        self.assertEqual(signatures, {(True, (1, 1, 1, 1), 0.0625)})

    def test_non_square_and_structurally_singular_fall_back(self):
        self.assertEqual(analyze_relation_supports(((0,),), 2).reason, "non_square")
        singular = analyze_relation_supports(((0,), (0,), (1, 2)), 3)
        self.assertEqual(singular.reason, "no_perfect_matching")
        self.assertFalse(singular.applicable)

    def test_portfolio_retains_baseline_quota(self):
        plan = analyze_relation_supports(((0,), (0, 1), (1, 2), (2, 3)), 4)
        allocation = allocate_portfolio(plan, 9, baseline_quota=0.5)
        self.assertEqual(allocation.baseline_starts, 5)
        self.assertEqual(allocation.block_starts, 4)

    def test_v15_support_extraction_is_name_based_and_truth_free(self):
        formulation = {
            "answer": "must-not-be-read",
            "variables": {"names": ["u", "v", "w"]},
            "construction": [
                {"name": "A", "expr": "Point(u, 0)"},
                {"name": "B", "expr": "Point(v, w)"},
            ],
            "constraints": [
                {"def": "Coordinate(A)", "value": 1},
                {"def": "First(B)", "value": "Coordinate(A)"},
                {"def": "Second(B)", "value": 2},
            ],
            "guards": ["Bound(u, (0, 2), inclusive=False)"],
        }
        structure = extract_v15_structure(formulation)
        self.assertEqual(structure.relation_supports, ((0,), (0, 1, 2), (1, 2)))
        self.assertEqual(structure.guard_supports, ((0,),))
        self.assertFalse(structure.polynomial_scalar_candidate)

    def test_every_numerical_candidate_reaches_canonical_verifier(self):
        supports = ((0,), (0, 1), (1, 2))
        plan = analyze_relation_supports(supports, 3)

        def residual(point):
            return (
                point[0] - 1.0,
                point[1] - point[0] - 1.0,
                point[2] - point[1] - 1.0,
            )

        verifier_calls = []

        def verifier(point):
            verifier_calls.append(tuple(point))
            return max(map(abs, residual(point))) <= 1.0e-8

        block = solve_candidate(residual, (8.0, -3.0, 2.0), plan, verifier, use_block_route=True)
        baseline = solve_candidate(residual, (8.0, -3.0, 2.0), plan, verifier, use_block_route=False)
        self.assertTrue(block.accepted)
        self.assertTrue(baseline.accepted)
        self.assertEqual(len(verifier_calls), 2)
        self.assertLess(block.linear_work, baseline.linear_work)

    def test_canonical_rejection_cannot_be_overridden(self):
        plan = analyze_relation_supports(((0,), (0, 1)), 2)
        attempt = solve_candidate(
            lambda point: (point[0] - 1.0, point[1] - point[0]),
            (0.0, 0.0),
            plan,
            lambda point: False,
            use_block_route=True,
        )
        self.assertFalse(attempt.accepted)
        self.assertEqual(attempt.failure, "canonical_rejected")


if __name__ == "__main__":
    unittest.main()
