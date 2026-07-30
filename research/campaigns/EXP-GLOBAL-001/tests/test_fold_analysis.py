from __future__ import annotations

import importlib.util
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
SPEC = importlib.util.spec_from_file_location(
    "exp_global_001_fold_analysis", CAMPAIGN / "fold_analysis.py"
)
assert SPEC is not None and SPEC.loader is not None
FOLDS = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = FOLDS
SPEC.loader.exec_module(FOLDS)


ROWS = (
    "alpha(A)",
    "alpha(B)",
    "beta(A)",
    "beta(B)",
    "gamma(C)",
    "delta(D)",
    "epsilon(E)",
    "zeta(F)",
)


def write_run(root: Path, *, candidate: bool, reverse: bool = False) -> None:
    score_rows = []
    telemetry_rows = []
    ordered = list(enumerate(ROWS, 1))
    if reverse:
        ordered.reverse()
    for ordinal, problem_id in ordered:
        if candidate:
            exact = problem_id != "zeta(F)"
            if problem_id == "epsilon(E)":
                exact = False
            status = "WORKER_NOT_ACCEPTED" if problem_id == "zeta(F)" else (
                "EXACT_SET_EQUAL" if exact else "MISSING"
            )
            accepted = problem_id != "zeta(F)"
            wall = None if problem_id == "gamma(C)" else 5.0
            cpu = None if problem_id in {"delta(D)", "epsilon(E)"} else 4.0
            outer_cpu = 4.0 if problem_id == "delta(D)" else None
        else:
            exact = problem_id == "zeta(F)"
            status = "EXACT_SET_EQUAL" if exact else "MISSING"
            accepted = True
            wall = 10.0
            cpu = None if problem_id == "epsilon(E)" else 8.0
            outer_cpu = None
        score_rows.append(
            {
                "index": ordinal,
                "problem_id": problem_id,
                "worker_accepted": accepted,
                "worker_elapsed_wall_seconds": wall,
                "worker_elapsed_cpu_seconds": cpu,
                "status": status,
                "exact_set_equal": exact,
            }
        )
        telemetry_row = {
            "ordinal": ordinal,
            "accepted": accepted,
            "outer_elapsed_seconds": 5.0 if candidate else 10.0,
        }
        if outer_cpu is not None:
            telemetry_row["outer_cpu_seconds"] = outer_cpu
        telemetry_rows.append(telemetry_row)
    root.mkdir(parents=True)
    (root / "OFFLINE_SCORE.json").write_text(
        json.dumps({"rows": score_rows}), encoding="utf-8"
    )
    (root / "TELEMETRY.json").write_text(
        json.dumps({"rows": telemetry_rows}), encoding="utf-8"
    )


class FoldAnalysisTests(unittest.TestCase):
    def test_family_disjoint_deterministic_balanced_assignment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            control_root = root / "control"
            reversed_root = root / "control-reversed"
            write_run(control_root, candidate=False)
            write_run(reversed_root, candidate=False, reverse=True)
            left = FOLDS.load_run(control_root)
            right = FOLDS.load_run(reversed_root)
            assignment = FOLDS.assign_folds(left)
            self.assertEqual(assignment, FOLDS.assign_folds(right))
            self.assertEqual(assignment["alpha(A)"], assignment["alpha(B)"])
            self.assertEqual(assignment["beta(A)"], assignment["beta(B)"])
            counts = [sum(fold == index for fold in assignment.values()) for index in range(3)]
            self.assertLessEqual(max(counts) - min(counts), 2)

    def test_summary_counts_times_safety_and_hides_identities(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            control_root = root / "control"
            candidate_root = root / "candidate"
            write_run(control_root, candidate=False)
            write_run(candidate_root, candidate=True)
            report = FOLDS.build_analysis(control_root, candidate_root)
            self.assertEqual(sum(fold["case_count"] for fold in report["folds"]), 8)
            self.assertEqual(report["overall"]["wins"], 6)
            self.assertEqual(report["overall"]["losses"], 1)
            self.assertEqual(report["overall"]["ties"], 1)
            self.assertTrue(
                report["cross_fold_gate"][
                    "wins_exceed_losses_in_at_least_2_folds"
                ]
            )
            candidate = report["overall"]["candidate"]
            self.assertEqual(candidate["accepted_count"], 7)
            self.assertEqual(candidate["not_accepted_count"], 1)
            self.assertEqual(candidate["safety_failure_count"], 1)
            self.assertEqual(candidate["safety_status_counts"], {"WORKER_NOT_ACCEPTED": 1})
            wall = report["overall"]["time"]["wall"]
            self.assertAlmostEqual(wall["candidate_over_control_geometric_mean"], 0.5)
            self.assertEqual(wall["candidate_time_sources"]["outer_censored"], 1)
            cpu = report["overall"]["time"]["cpu"]
            self.assertAlmostEqual(cpu["candidate_over_control_geometric_mean"], 0.5)
            self.assertEqual(cpu["available_pair_count"], 7)
            self.assertEqual(cpu["unavailable_pair_count"], 1)
            self.assertEqual(cpu["candidate_time_sources"]["outer_censored"], 1)
            serialized = json.dumps(report, sort_keys=True)
            for identity in ROWS:
                self.assertNotIn(identity, serialized)
                self.assertNotIn(FOLDS.family(identity), serialized)

    def test_score_or_telemetry_path_resolves_same_pair(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "control"
            write_run(root, candidate=False)
            expected = FOLDS.load_run(root)
            self.assertEqual(expected, FOLDS.load_run(root / "OFFLINE_SCORE.json"))
            self.assertEqual(expected, FOLDS.load_run(root / "TELEMETRY.json"))

    def test_holdout_like_path_is_rejected_before_read(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "sealed-run"
            with self.assertRaisesRegex(ValueError, "holdout-like"):
                FOLDS.load_run(path)

    def test_missing_cpu_is_reported_not_replaced_with_wall(self) -> None:
        pairs = [
            (
                FOLDS.CaseObservation(
                    "a(A)", "a", False, True, "MISSING", 2.0, "worker", None, "unavailable"
                ),
                FOLDS.CaseObservation(
                    "a(A)", "a", False, True, "MISSING", 1.0, "worker", None, "unavailable"
                ),
            )
        ]
        summary = FOLDS._timing_summary(pairs, metric="cpu")
        self.assertEqual(summary["available_pair_count"], 0)
        self.assertIsNone(summary["candidate_over_control_geometric_mean"])

    def test_cli_writes_identity_free_report_and_checksum(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            control_root = root / "control"
            candidate_root = root / "candidate"
            output = root / "summary.json"
            write_run(control_root, candidate=False)
            write_run(candidate_root, candidate=True)
            arguments = [
                "fold_analysis.py",
                "--control",
                str(control_root),
                "--candidate",
                str(candidate_root),
                "--output",
                str(output),
            ]
            stdout = io.StringIO()
            with mock.patch.object(sys, "argv", arguments), mock.patch(
                "sys.stdout", stdout
            ):
                self.assertEqual(FOLDS.main(), 0)
            payload = output.read_bytes()
            checksum = output.with_suffix(".json.sha256").read_text().split()[0]
            self.assertEqual(checksum, hashlib.sha256(payload).hexdigest())
            combined = payload.decode("utf-8") + stdout.getvalue()
            for identity in ROWS:
                self.assertNotIn(identity, combined)
                self.assertNotIn(FOLDS.family(identity), combined)


if __name__ == "__main__":
    unittest.main()
