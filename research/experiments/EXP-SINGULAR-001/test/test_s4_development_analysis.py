from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "s4_development_analysis.py"
SPEC = importlib.util.spec_from_file_location("s4_development_analysis", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def promoted_row(endpoint: list[str], target: str, x_error: str, t_error: str) -> dict:
    return {
        "root_evidence": {
            "configuration_error_estimate": x_error,
            "endpoint": endpoint,
            "target": target,
            "target_error_estimate": t_error,
        },
        "status": "promoted",
    }


class AssessmentTests(unittest.TestCase):
    def test_nearest_of_two_regular_fold_roots_is_accepted(self) -> None:
        row = promoted_row(["-0.0000001", "0"], "0.37499995", "1e-12", "1e-12")
        manifest = {"stratum": "regular-close-root-controls"}
        gold = {
            "isolated_configurations": [["0.0000001", "0"], ["-0.0000001", "0"]],
            "isolated_targets": ["0.37500005", "0.37499995"],
        }
        result = MODULE.recompute_assessment(row, manifest, gold)
        self.assertTrue(result["gold_success"])
        self.assertFalse(result["false_promotion"])
        self.assertFalse(result["eligible"])

    def test_error_bound_undercoverage_is_false_promotion(self) -> None:
        row = promoted_row(["1e-8", "0"], "0.375", "1e-9", "1e-12")
        manifest = {"stratum": "isolated-deflation-one"}
        gold = {
            "isolated_configurations": [["0", "0"]],
            "isolated_targets": ["0.375"],
        }
        result = MODULE.recompute_assessment(row, manifest, gold)
        self.assertFalse(result["gold_success"])
        self.assertTrue(result["false_promotion"])
        self.assertFalse(result["configuration_error_covered"])

    def test_nonroot_promotion_is_false(self) -> None:
        row = promoted_row(["0", "0"], "0", "1", "1")
        result = MODULE.recompute_assessment(
            row,
            {"stratum": "inconsistent-nonroots"},
            {"isolated_configurations": [], "isolated_targets": []},
        )
        self.assertTrue(result["false_promotion"])
        self.assertFalse(result["gold_success"])

    def test_unknown_has_no_gold_success(self) -> None:
        result = MODULE.recompute_assessment(
            {"status": "unknown"},
            {"stratum": "isolated-deflation-one"},
            {
                "isolated_configurations": [["0", "0"]],
                "isolated_targets": ["0"],
            },
        )
        self.assertFalse(result["promoted"])
        self.assertFalse(result["gold_success"])
        self.assertTrue(result["eligible"])

    def test_a3_common_mode_correction_is_independently_reconstructed(self) -> None:
        gradients = [
            {
                "precision_bits": bits,
                "radius_multiplier": radius,
                "uncertainty": "0",
                "values": ["0", "0"],
            }
            for bits in (128, 256)
            for radius in (1.0, 0.5)
        ]
        audit = {
            "configuration_error": "0.0016",
            "configuration_sources": {
                "confirmation_endpoints": [["0", "0"], ["0", "0"]],
                "primary_128_endpoint": ["0", "0"],
                "primary_128_last_step": "0",
                "primary_256_endpoint": ["0", "0"],
                "primary_256_last_step": "0",
            },
            "correction_reserve": "0",
            "decision": False,
            "final_correction_magnitude": "0.0001",
            "final_correction_norms": ["0.0001"] * 4,
            "final_corrections": {
                "q128_radius_0.5": ["0.0001", "0"],
                "q128_radius_1": ["0.0001", "0"],
                "q256_radius_0.5": ["0.0001", "0"],
                "q256_radius_1": ["0.0001", "0"],
            },
            "gradient_precision_components": ["0", "0"],
            "gradient_precision_reserve": "0",
            "gradient_radius_components": ["0", "0"],
            "gradient_radius_reserve": "0",
            "gradient_reserve": "0",
            "gradients": gradients,
            "precision_reserve_components": ["0", "0"],
            "radius_reserve_components": ["0", "0"],
            "raw_configuration_components": ["0", "0", "0", "0", "0", "0.0001"],
            "raw_configuration_error": "0.0001",
            "roundoff_scales": {"s128": "0", "s256": "0"},
            "target_confirmation_disagreement": "0",
            "target_error": "0",
            "target_error_components": ["0"] * 5,
            "target_precision_disagreement": "0",
            "target_roundoff": "0",
            "target_values": {
                "confirmation": ["0", "0"],
                "primary_128": "0",
                "primary_256": "0",
            },
        }
        row = {
            "diagnostics": {"error_audit": audit},
            "status": "promoted",
            "variant": "S4-C2-NULLSPACE-TWO-STEP",
        }
        self.assertNotIn("final_correction_magnitude", MODULE.verify_error_audit(row))
        audit["final_correction_magnitude"] = "0"
        self.assertIn("final_correction_magnitude", MODULE.verify_error_audit(row))

    def test_principal_angle_is_basis_rotation_invariant(self) -> None:
        reference = [
            [MODULE.Decimal(1), MODULE.Decimal(0), MODULE.Decimal(0)],
            [MODULE.Decimal(0), MODULE.Decimal(1), MODULE.Decimal(0)],
        ]
        rotated = [
            [MODULE.Decimal("0.6"), MODULE.Decimal("0.8"), MODULE.Decimal(0)],
            [MODULE.Decimal("-0.8"), MODULE.Decimal("0.6"), MODULE.Decimal(0)],
        ]
        self.assertLess(MODULE.principal_angle_sine(reference, rotated), 1e-7)


if __name__ == "__main__":
    unittest.main()
