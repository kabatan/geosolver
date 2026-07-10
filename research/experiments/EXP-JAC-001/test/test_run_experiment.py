from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "run_experiment.py"
SPEC = importlib.util.spec_from_file_location("exp_jac_run", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
RUN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUN)


def worker(variant: str, candidate: bool) -> dict:
    families = ("SPARSE-A", "SPARSE-B", "DENSE-C")
    attempts = []
    for family in families:
        for case in range(2):
            for start in range(1, 3):
                attempts.append(
                    {
                        "case_id": f"{family}-{case}",
                        "family_id": family,
                        "generator_id": "test-v1",
                        "start_index": start,
                        "variant": variant,
                        "dimension": 2,
                        "factors": {"boundary_distance": 0.0},
                        "gold_valid": True,
                        "false_candidate": False,
                        "budget_overrun": False,
                        "oracle_work": 70 if candidate else 100,
                        "jacobian_callbacks": 10 if candidate else 20,
                        "wall_seconds": 1.01 if candidate else 1.0,
                        "fallback_groups": 0,
                        "color_groups_evaluated": 10 if candidate else 0,
                    }
                )
    return {
        "attempts": attempts,
        "cold": [
            {"case_id": f"{family}-{case}", "coloring_seconds": 0.001}
            for family in families
            for case in range(2)
        ],
        "preflight": {
            "dense_colored_mismatch_count": 0,
            "dense_outside_pattern_count": 0,
            "fallback_control_failure_count": 0,
            "per_instance": [],
        },
    }


class AnalysisTests(unittest.TestCase):
    def test_mechanical_promotion_gate(self) -> None:
        contract = {
            "sparse_development_families": ["SPARSE-A", "SPARSE-B"],
            "dense_development_family": "DENSE-C",
            "bootstrap_seed": 3001,
            "bootstrap_resamples": 100,
            "bootstrap_method": "test clustered bootstrap",
            "one_sided_lower_quantile": 0.05,
        }
        gate, rows, plan = RUN.evaluate_gate(
            worker("J0-DENSE-CENTRAL", False),
            worker("J1-GREEDY-COLOR", True),
            {"analysis_contract": contract, "prefixes": [1, 2]},
        )
        self.assertEqual(len(rows), 12)
        self.assertTrue(gate["promotion_gate_passed"])
        self.assertFalse(gate["kill_gate_fired"])
        self.assertGreater(gate["sparse_bootstrap"]["one_sided_95_lower"], 0)
        self.assertEqual(len(plan["draws"]), 100)

    def test_j2_trigger_is_structural_and_requires_three_families(self) -> None:
        rows = [
            {"family_id": family, "relative_gap": gap}
            for family, gap in (
                ("A", 0.21),
                ("B", 0.25),
                ("C", 0.19),
            )
        ]
        self.assertFalse(RUN.j2_trigger({"per_instance": rows})["triggered"])
        rows[-1]["relative_gap"] = 0.201
        self.assertTrue(RUN.j2_trigger({"per_instance": rows})["triggered"])

    def test_bootstrap_plan_is_replayable(self) -> None:
        rows = RUN.paired_rows(
            worker("J0-DENSE-CENTRAL", False),
            worker("J1-GREEDY-COLOR", True),
        )
        contract = {
            "sparse_development_families": ["SPARSE-A", "SPARSE-B"],
            "bootstrap_seed": 3001,
            "bootstrap_resamples": 20,
            "bootstrap_method": "test clustered bootstrap",
            "one_sided_lower_quantile": 0.05,
        }
        first = RUN.bootstrap_sparse_reduction(rows, contract)
        second = RUN.bootstrap_sparse_reduction(rows, contract)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
