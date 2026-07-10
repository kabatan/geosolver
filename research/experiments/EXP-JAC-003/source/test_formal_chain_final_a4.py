from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import formal_chain_final_a4 as guard  # noqa: E402


ROOT = Path(__file__).resolve().parents[4]
AMENDMENT_PATH = (
    ROOT / "research/experiments/EXP-JAC-003/formal-chain-final-amendment-a4.json"
)
CHECKER_PATH = ROOT / "research/experiments/EXP-JAC-003/source/formal_chain_final_a4.py"


class BarrierTests(unittest.TestCase):
    def test_enter_waits_for_first_complete_sample(self) -> None:
        calls: list[float] = []

        class FakeA3:
            @staticmethod
            def _monitor_rows(_amendment, _paths):
                calls.append(time.monotonic())
                if len(calls) == 2:
                    time.sleep(0.03)
                return [{"path": "f", "sha256": "a", "size": 1}]

        window = guard.BarrierSourceWindow(
            FakeA3(), {"monitor": {"interval_seconds": 1.0}}, {}
        )
        started = time.monotonic()
        with window:
            entered = time.monotonic()
            self.assertGreaterEqual(len(calls), 2)
        self.assertGreaterEqual(entered - started, 0.025)
        self.assertTrue(window.receipt()["barrier_completed"])

    def test_mutation_at_final_snapshot_fails(self) -> None:
        calls = 0

        class FakeA3:
            @staticmethod
            def _monitor_rows(_amendment, _paths):
                nonlocal calls
                calls += 1
                marker = "b" if calls >= 3 else "a"
                return [{"path": "f", "sha256": marker, "size": 1}]

        window = guard.BarrierSourceWindow(
            FakeA3(), {"monitor": {"interval_seconds": 10.0}}, {}
        )
        with self.assertRaises(guard.FinalChainError):
            with window:
                pass


class ReceiptTests(unittest.TestCase):
    def test_source_observation_requires_a4_authority(self) -> None:
        authority = {"amendment_sha256": "a", "checker_sha256": "b"}
        valid = {
            "formal_chain_final_amendment_a4_sha256": "a",
            "formal_chain_final_checker_a4_sha256": "b",
            "formal_chain_final_pre_audit_sha256": "c",
            "outcomes_inspected": False,
        }
        guard._require_source_fields(valid, authority, "c")
        invalid = dict(valid)
        invalid["formal_chain_final_pre_audit_sha256"] = "x"
        with self.assertRaises(guard.FinalChainError):
            guard._require_source_fields(invalid, authority, "c")

    def test_publication_inputs_bind_the_same_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            result = repo / "research/results"
            result.mkdir(parents=True)
            source = {
                "formal_chain_final_amendment_a4_sha256": "a",
                "formal_chain_final_checker_a4_sha256": "b",
                "formal_chain_final_pre_audit_sha256": "c",
                "outcomes_inspected": False,
            }
            (result / "EXP-JAC-003-development-source-observation.json").write_text(
                json.dumps(source), encoding="utf-8"
            )
            host_path = repo / "host.json"
            host_path.write_text(
                json.dumps(
                    {
                        "host_contention_event_count": 0,
                        "lease_loss_count": 0,
                        "all_formal_pids_ended": True,
                        "outcomes_inspected": False,
                    }
                ),
                encoding="utf-8",
            )
            (result / "EXP-JAC-003-development-formal-run-audit.json").write_text(
                json.dumps({"outcome": "completed", "exit_code": 0, "error": None}),
                encoding="utf-8",
            )
            payloads, hashes, documents = guard._publication_inputs(
                {"repo": repo, "host_receipt": host_path},
                {"amendment_sha256": "a", "checker_sha256": "b"},
                "c",
            )
            self.assertEqual(set(payloads), {"source", "host", "outer"})
            self.assertEqual(set(hashes), set(payloads))
            self.assertEqual(documents["outer"]["outcome"], "completed")

    def test_existing_assessment_intent_blocks_before_any_launch(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            intent = root / "intent.json"
            intent.write_text("{}", encoding="utf-8")
            paths = {
                "assessment_intent": intent,
                "assessment_receipt": root / "final.json",
            }
            context = ({}, paths, {}, object(), {}, {}, {}, object())
            with mock.patch.object(guard, "_context", return_value=context):
                with self.assertRaisesRegex(guard.FinalChainError, "retry forbidden"):
                    guard.assess(root / "amendment.json")


class FrozenPlanTests(unittest.TestCase):
    def test_checker_hash_and_a3_hashes_are_frozen(self) -> None:
        amendment = json.loads(AMENDMENT_PATH.read_bytes())
        checker_sha = hashlib.sha256(CHECKER_PATH.read_bytes()).hexdigest()
        self.assertEqual(amendment["checker"]["sha256"], checker_sha)
        a3_amendment = ROOT / amendment["a3_authority"]["amendment_relative_path"]
        a3_checker = ROOT / amendment["a3_authority"]["checker_relative_path"]
        self.assertEqual(
            amendment["a3_authority"]["amendment_sha256"],
            hashlib.sha256(a3_amendment.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            amendment["a3_authority"]["checker_sha256"],
            hashlib.sha256(a3_checker.read_bytes()).hexdigest(),
        )

    def test_a4_archive_receipt_is_outside_official_archive(self) -> None:
        amendment = json.loads(AMENDMENT_PATH.read_bytes())
        path = Path(amendment["execution"]["archive_receipt_path"])
        self.assertEqual(path.parent, Path(r"C:\solver\research\results\EXP-JAC-003"))
        self.assertNotIn("development-abba-v0", str(path))

    def test_all_exact_phase_commands_are_absolute_and_unique(self) -> None:
        amendment = json.loads(AMENDMENT_PATH.read_bytes())
        for phase in ("pre", "publish", "archive", "assess"):
            tokens = amendment["execution"][f"exact_{phase}_command_tokens"]
            self.assertTrue(Path(tokens[0]).is_absolute())
            self.assertTrue(Path(tokens[1]).is_absolute())
            self.assertEqual(tokens[2], phase)
            self.assertEqual(tokens.count("--amendment"), 1)


if __name__ == "__main__":
    unittest.main()
