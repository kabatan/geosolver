from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "development_analysis.py"
SPEC = importlib.util.spec_from_file_location("exp_local_002_development_analysis", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)


class DevelopmentInputTests(unittest.TestCase):
    def test_frozen_manifest_has_complete_grid(self) -> None:
        manifest = analysis.load_json(analysis.INPUT_MANIFEST)
        instances = analysis.validate_input_manifest(manifest)
        self.assertEqual(len(instances), 48)
        self.assertEqual({value["start_count"] for value in instances.values()}, {32})
        observed = {
            stratum
            for value in instances.values()
            for stratum in value["strata"]
        }
        self.assertEqual(observed, set(analysis.STRATA))

    def test_deterministic_gzip_json_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.json.gz"
            second = Path(directory) / "second.json.gz"
            value = {"families": ["b", "a"], "indices": [[1, 0], [0, 0]]}
            analysis.write_json_gzip(first, value)
            analysis.write_json_gzip(second, value)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(analysis.load_json_gzip(first), value)


class BootstrapContractTests(unittest.TestCase):
    def test_pairing_is_equal_family_weighted_and_replayable(self) -> None:
        values = [
            analysis.PairedValue("large", "a", 1.0, 0.0),
            analysis.PairedValue("large", "b", 1.0, 0.0),
            analysis.PairedValue("small", "c", 0.0, 1.0),
        ]
        plan = analysis.make_bootstrap_plan(["large", "small"], resamples=200, seed=17)
        report = analysis.paired_interval(values, ["a", "b", "c"], plan)
        self.assertEqual(report["estimate"], 0.0)
        self.assertEqual(report["family_count"], 2)
        self.assertEqual(report["plan_checksum"], plan.checksum)
        self.assertEqual(report["family_effects"], {"large": 1.0, "small": -1.0})

    def test_rmn_and_strict_mechanical_rules(self) -> None:
        def paired(candidate: str, control: str, metric: str, upper: float, lower: float = 0.0):
            return {
                "candidate": candidate,
                "control": control,
                "metric": metric,
                "prefix": 32,
                "slice_kind": "overall",
                "slice": "overall",
                "upper_95": upper,
                "lower_95": lower,
                "estimate": 0.0,
                "positive_family_count": 4,
            }

        paired_reports = [
            paired("NLS-RMN", "NLS-TR", "p_local_gold", 0.04),
            paired("NLS-RMN", "NLS-TR", "relative_work_saving", 0.03),
            paired("NLS-RMN", "NLS-TR", "p_full_target", 0.0),
            paired("NLS-TR-STRICT", "NLS-TR", "p_local_gold", 0.0),
            paired("NLS-TR-STRICT", "NLS-TR", "p_full_target", 0.0),
            paired("NLS-TR-STRICT", "NLS-TR", "bad_residual_reduction", 0.0),
            paired("NLS-TR-STRICT", "NLS-TR", "relative_work_saving", 0.0),
            paired("NLS-TR", "LXR-LMQR", "p_local_gold", 0.2, lower=0.01),
        ]

        def aggregate(variant: str, kind: str, label: str, p_local: float, p_full: float, work: int):
            return {
                "variant": variant,
                "prefix": 32,
                "slice_kind": kind,
                "slice": label,
                "p_local_gold": p_local,
                "p_full_target": p_full,
                "charged_work": work,
                "unsafe_accepted_count": 0,
            }

        aggregates = [
            aggregate("NLS-TR", "overall", "overall", 0.8, 0.8, 80),
            aggregate("LXR-LMQR", "overall", "overall", 0.6, 0.7, 100),
        ]
        for family in ("NEAR-RANK-DEFICIENT", "TANGENT-CIRCLE-LINE", "MULTIROOT-WARPED"):
            aggregates.append(aggregate("NLS-TR", "family", family, 0.8, 0.8, 80))
            aggregates.append(aggregate("LXR-LMQR", "family", family, 0.6, 0.8, 100))
        decision = analysis.mechanical_decisions(aggregates, paired_reports)
        self.assertTrue(decision["rmn_kill_gate"]["triggered"])
        self.assertTrue(decision["strict_threshold"]["no_improvement"])
        self.assertEqual(decision["strict_threshold"]["freeze_candidate"], "NLS-TR")
        self.assertEqual(decision["next_freeze_candidate"], "NLS-TR")
        self.assertEqual(decision["promotion_decision"], "not-evaluated-development-only")


if __name__ == "__main__":
    unittest.main()
