from __future__ import annotations

import unittest

import numpy as np

from candidate import canonical_source_replay, discover_exceptional_proposals, route_trace, run_portfolio
from generated_cases import (
    cusp_case,
    dimension_jump_case,
    fold_case,
    generated_suite,
    opaque_case,
    stable_nonexceptional_case,
    truth_contains,
)


class ExceptionalStratumFibreProductTest(unittest.TestCase):
    def test_positive_families_gain_with_source_replay(self) -> None:
        positives = [case for case in generated_suite() if case.role == "positive"]
        self.assertGreaterEqual(len({case.family for case in positives}), 3)
        for case in positives:
            result = run_portfolio(case.problem, case.baseline, case.unstable_cluster)
            self.assertTrue(result.evidence.activated, case.name)
            self.assertGreater(len(result.proposals), len(case.baseline), case.name)
            self.assertTrue(all(canonical_source_replay(case.problem, p) for p in result.proposals))
            self.assertTrue(all(truth_contains(case, p) for p in result.proposals))

    def test_dimension_jump_activates_but_collapses_to_source_root(self) -> None:
        case = dimension_jump_case()
        result = run_portfolio(case.problem, case.baseline, case.unstable_cluster)
        self.assertTrue(result.evidence.activated)
        self.assertIn("fibre_rank_drop", result.evidence.signatures)
        self.assertEqual(len(result.proposals), 1)
        self.assertTrue(truth_contains(case, result.proposals[0]))

    def test_negative_and_near_miss_families_never_emit_false_or_extra(self) -> None:
        controls = [case for case in generated_suite() if case.role != "positive"]
        self.assertGreaterEqual(len({case.family for case in controls if case.role == "negative"}), 3)
        self.assertGreaterEqual(len({case.family for case in controls if case.role == "near_miss"}), 3)
        for case in controls:
            result = run_portfolio(case.problem, case.baseline, case.unstable_cluster)
            self.assertTrue(all(canonical_source_replay(case.problem, p) for p in result.proposals), case.name)
            self.assertTrue(all(truth_contains(case, p) for p in result.proposals), case.name)

    def test_source_coordinate_and_equation_scaling_are_covariant(self) -> None:
        base = fold_case()
        transformed = fold_case(
            name="scaled_reflected_x",
            family="test",
            x_factor=-3.5,
            equation_scale=17.0,
        )
        base_result = run_portfolio(base.problem, base.baseline, base.unstable_cluster)
        transformed_result = run_portfolio(
            transformed.problem, transformed.baseline, transformed.unstable_cluster
        )
        self.assertEqual(
            sorted(base.normalize(point) for point in base_result.proposals),
            sorted(transformed.normalize(point) for point in transformed_result.proposals),
        )

    def test_parameter_reflection_and_axis_swap_preserve_recovery(self) -> None:
        base = fold_case()
        reflected = fold_case(reflected_parameter=True)
        base_result = run_portfolio(base.problem, base.baseline, base.unstable_cluster)
        reflected_result = run_portfolio(
            reflected.problem, reflected.baseline, reflected.unstable_cluster
        )
        self.assertEqual(
            sorted(base.normalize(point) for point in base_result.proposals),
            sorted(reflected.normalize(point) for point in reflected_result.proposals),
        )
        cusp = cusp_case()
        swapped = cusp_case(swapped_parameters=True)
        cusp_result = run_portfolio(cusp.problem, cusp.baseline, cusp.unstable_cluster)
        swapped_result = run_portfolio(swapped.problem, swapped.baseline, swapped.unstable_cluster)
        self.assertEqual(
            sorted(cusp.normalize(point) for point in cusp_result.proposals),
            sorted(swapped.normalize(point) for point in swapped_result.proposals),
        )

    def test_stable_and_opaque_fallback_before_unneeded_sampling(self) -> None:
        stable = stable_nonexceptional_case()
        stable_result = run_portfolio(stable.problem, stable.baseline, stable.unstable_cluster)
        self.assertFalse(stable_result.evidence.activated)
        self.assertEqual(stable_result.evidence.reason, "stable_endpoint_fallback")
        opaque = opaque_case()
        opaque_result = run_portfolio(opaque.problem, opaque.baseline, opaque.unstable_cluster)
        self.assertFalse(opaque_result.evidence.activated)
        self.assertEqual(opaque_result.evidence.reason, "opaque_fallback")
        self.assertEqual(opaque._calls["fibre"], 0)

    def test_baseline_quota_and_digest_are_immutable(self) -> None:
        trace = route_trace(16)
        self.assertEqual(trace.count("baseline"), 12)
        self.assertEqual(trace.count("exceptional_stratum"), 4)
        case = fold_case()
        result = run_portfolio(case.problem, case.baseline, case.unstable_cluster)
        self.assertEqual(result.baseline_digest_before, result.baseline_digest_after)

    def test_perturbed_endpoints_are_never_authority(self) -> None:
        case = fold_case()
        proposals, evidence = discover_exceptional_proposals(case.problem, case.unstable_cluster)
        self.assertTrue(evidence.activated)
        self.assertTrue(proposals)
        self.assertTrue(all(canonical_source_replay(case.problem, point) for point in proposals))
        self.assertNotEqual(evidence.exceptional_parameter, tuple(case.problem.source_parameter))


if __name__ == "__main__":
    unittest.main()
