from __future__ import annotations

import math
import unittest

from btf_polynomial_pipeline import (
    detect_btf_polynomial_plan,
    run_btf_polynomial_side_route,
)
from polynomial_side_route import PolynomialLimits, detect_polynomial_plan


def mixed_chain():
    return {
        "task": "solve",
        "variables": {"names": ["x", "y", "z", "w"]},
        "construction": [],
        "constraints": [
            {"def": "x**2", "value": 1},
            {"def": "y", "value": "x"},
            {"def": "sin(z)", "value": 0},
            {"def": "w", "value": "z"},
        ],
        "guards": [],
    }


def canonical_mixed(point):
    x, y, z, w = point
    residuals = (x * x - 1.0, y - x, math.sin(z), w - z)
    return all(math.isfinite(value) for value in point) and max(map(abs, residuals)) < 1e-12


class BTFPolynomialPipelineTests(unittest.TestCase):
    def test_btf_reopens_small_polynomial_block_when_whole_gate_is_closed(self):
        formulation = mixed_chain()
        self.assertEqual(detect_polynomial_plan(formulation).reason, "dimension_cap")
        plan = detect_btf_polynomial_plan(formulation)
        self.assertTrue(plan.applicable)
        self.assertEqual(len(plan.active_blocks), 1)
        self.assertEqual(plan.active_blocks[0].polynomial_plan.variable_names, ("x",))

        result = run_btf_polynomial_side_route(
            formulation,
            (0.8, 1.0, 0.0, 0.0),
            canonical_mixed,
            total_starts=16,
            timeout_seconds=1.0,
        )
        self.assertEqual(result.status, "complete")
        self.assertEqual(result.allocation.baseline_starts, 12)
        self.assertEqual(result.allocation.symbolic_slots, 4)
        self.assertEqual(len(result.proposals), 2)
        self.assertEqual(result.verifier_calls, 2)
        self.assertEqual(result.verified, ((1.0, 1.0, 0.0, 0.0),))

    def test_irreducible_system_falls_back_with_all_baseline_starts(self):
        formulation = {
            "variables": {"names": ["x", "y"]},
            "construction": [],
            "constraints": [
                {"def": "x + y", "value": 1},
                {"def": "x - y", "value": 0},
            ],
            "guards": [],
        }
        result = run_btf_polynomial_side_route(
            formulation,
            (0.0, 0.0),
            lambda _point: self.fail("irreducible fallback cannot verify a side proposal"),
            total_starts=17,
        )
        self.assertEqual(result.plan.reason, "btf_irreducible")
        self.assertEqual(result.status, "baseline_only")
        self.assertEqual(result.allocation.baseline_starts, 17)
        self.assertEqual(result.allocation.symbolic_slots, 0)

    def test_all_nonpolynomial_blocks_fall_back(self):
        formulation = {
            "variables": {"names": ["x", "y"]},
            "construction": [],
            "constraints": [
                {"def": "sin(x)", "value": 0},
                {"def": "cos(y)", "value": 1},
            ],
            "guards": [],
        }
        result = run_btf_polynomial_side_route(
            formulation,
            (0.0, 0.0),
            lambda _point: self.fail("non-polynomial fallback cannot verify a side proposal"),
            total_starts=16,
        )
        self.assertEqual(result.plan.reason, "no_strict_polynomial_block")
        self.assertEqual(result.status, "baseline_only")
        self.assertEqual(result.allocation.baseline_starts, 16)

    def test_degree_cap_survives_block_projection(self):
        formulation = {
            "variables": {"names": ["x", "y"]},
            "construction": [],
            "constraints": [
                {"def": "x**5", "value": 1},
                {"def": "sin(y)", "value": 0},
            ],
            "guards": [],
        }
        plan = detect_btf_polynomial_plan(formulation)
        self.assertFalse(plan.applicable)
        self.assertEqual(
            tuple(gate.polynomial_plan.reason for gate in plan.block_gates),
            ("degree_cap", "nonpolynomial_or_branch_ast"),
        )

    def test_block_count_and_cartesian_caps_fail_closed(self):
        formulation = {
            "variables": {"names": ["a", "b", "c", "d"]},
            "construction": [],
            "constraints": [
                {"def": f"{name}**2", "value": 1}
                for name in ("a", "b", "c", "d")
            ],
            "guards": [],
        }
        block_capped = run_btf_polynomial_side_route(
            formulation,
            (0.0, 0.0, 0.0, 0.0),
            lambda _point: self.fail("block cap cannot emit a proposal"),
            total_starts=16,
            maximum_symbolic_blocks=3,
        )
        self.assertEqual(block_capped.status, "symbolic_block_cap")
        self.assertEqual(block_capped.allocation.baseline_starts, 16)

        cartesian_capped = run_btf_polynomial_side_route(
            formulation,
            (0.0, 0.0, 0.0, 0.0),
            lambda _point: self.fail("cartesian cap cannot emit a proposal"),
            total_starts=16,
            maximum_cartesian_proposals=8,
            timeout_seconds=2.0,
        )
        self.assertEqual(cartesian_capped.status, "cartesian_cap")
        self.assertEqual(cartesian_capped.proposals, ())
        self.assertEqual(cartesian_capped.allocation.baseline_starts, 16)

    def test_every_full_proposal_returns_to_canonical_verifier(self):
        observed = []

        def reject(point):
            observed.append(tuple(point))
            return False

        result = run_btf_polynomial_side_route(
            mixed_chain(),
            (0.8, 1.0, 0.0, 0.0),
            reject,
            total_starts=16,
            timeout_seconds=1.0,
        )
        self.assertEqual(result.verifier_calls, len(result.proposals))
        self.assertEqual(observed, list(result.proposals))
        self.assertEqual(result.verified, ())

    def test_invalid_template_and_tiny_timeout_emit_nothing(self):
        invalid = run_btf_polynomial_side_route(
            mixed_chain(),
            (math.nan, 1.0, 0.0, 0.0),
            lambda _point: self.fail("invalid template cannot verify"),
            total_starts=16,
        )
        self.assertEqual(invalid.status, "invalid_template")
        self.assertEqual(invalid.allocation.baseline_starts, 16)

        timed = run_btf_polynomial_side_route(
            mixed_chain(),
            (0.8, 1.0, 0.0, 0.0),
            lambda _point: self.fail("timeout cannot verify"),
            total_starts=16,
            timeout_seconds=0.000001,
        )
        self.assertEqual(timed.status, "symbolic_timeout")
        self.assertEqual(timed.proposals, ())
        self.assertEqual(timed.allocation.baseline_starts, 16)

    def test_alias_projection_is_exact_and_outside_dependency_fails_gate(self):
        formulation = {
            "variables": {"names": ["x", "y"]},
            "construction": [
                {"name": "twice_x", "expr": "2*x"},
                {"name": "outside", "expr": "x + y"},
            ],
            "constraints": [
                {"def": "twice_x", "value": 2},
                {"def": "y", "value": "x"},
            ],
            "guards": [],
        }
        plan = detect_btf_polynomial_plan(formulation)
        self.assertTrue(plan.applicable)
        first, second = plan.block_gates
        self.assertEqual(first.formulation["construction"], [{"name": "twice_x", "expr": "2*x"}])
        self.assertTrue(first.polynomial_plan.applicable)
        self.assertEqual(second.polynomial_plan.reason, "unknown_symbol")

    def test_polynomial_limits_are_not_relaxed(self):
        limits = PolynomialLimits(maximum_variables=1, maximum_total_degree=1)
        plan = detect_btf_polynomial_plan(mixed_chain(), limits)
        self.assertFalse(plan.applicable)
        self.assertEqual(plan.block_gates[0].polynomial_plan.reason, "degree_cap")


if __name__ == "__main__":
    unittest.main()
