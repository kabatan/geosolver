from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest import mock


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import formal_execution_closure_a3 as guard  # noqa: E402


AMENDMENT = HERE.parent / "formal-execution-closure-amendment-a3.json"


class SingleReadTests(unittest.TestCase):
    def test_same_bytes_are_hashed_and_parsed(self) -> None:
        payload = b'{"passed":true}'

        class OneReadPath:
            calls = 0

            def read_bytes(self) -> bytes:
                self.calls += 1
                return payload

        path = OneReadPath()
        raw, digest, document = guard._read_once(path, "receipt")  # type: ignore[arg-type]
        self.assertEqual(path.calls, 1)
        self.assertEqual(raw, payload)
        self.assertEqual(digest, hashlib.sha256(payload).hexdigest())
        self.assertTrue(document["passed"])

    def test_opaque_inventory_does_not_parse_segment_json(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            segment = root / "segments" / "segment-0.json"
            segment.parent.mkdir()
            segment.write_bytes(b"not JSON; opaque hash only")
            inventory, captured = guard._inventory_with_bytes(root, set())
        self.assertEqual(inventory["file_count"], 1)
        self.assertEqual(captured, {})
        self.assertEqual(
            inventory["files"][0]["sha256"],
            hashlib.sha256(b"not JSON; opaque hash only").hexdigest(),
        )


class SourceWindowTests(unittest.TestCase):
    @staticmethod
    def _amendment() -> dict[str, object]:
        return {"monitor": {"interval_seconds": 0.001}}

    def test_transient_or_stable_source_mutation_is_terminal(self) -> None:
        calls = 0

        def rows(*_args: object) -> list[dict[str, object]]:
            nonlocal calls
            calls += 1
            return [{"path": "source", "sha256": "a" if calls == 1 else "b"}]

        window = guard.SourceWindow(self._amendment(), {})  # type: ignore[arg-type]
        with mock.patch.object(guard, "_monitor_rows", side_effect=rows):
            window.__enter__()
            time.sleep(0.01)
            with self.assertRaises(guard.ExecutionClosureError):
                window.__exit__(None, None, None)

    def test_clean_window_binds_identical_endpoints(self) -> None:
        rows = [{"path": "source", "sha256": "a"}]
        window = guard.SourceWindow(self._amendment(), {})  # type: ignore[arg-type]
        with mock.patch.object(guard, "_monitor_rows", return_value=rows):
            with window:
                time.sleep(0.003)
        receipt = window.receipt()
        self.assertEqual(receipt["event_count"], 0)
        self.assertEqual(
            receipt["initial_snapshot_sha256"], receipt["final_snapshot_sha256"]
        )

    def test_production_monitor_covers_every_source_lock_file(self) -> None:
        amendment = json.loads(AMENDMENT.read_bytes())
        paths = guard._paths(amendment)
        rows = guard._monitor_rows(amendment, paths)
        direct_paths = {row["path"] for row in rows if "path" in row}
        lock_path = (
            paths["repo"]
            / "research"
            / "experiments"
            / "EXP-JAC-003"
            / "development-source-lock.json"
        )
        lock = json.loads(lock_path.read_bytes())
        expected = {
            str(paths["repo"].joinpath(*relative.split("/")))
            for relative in lock["files"]
        }
        self.assertTrue(expected.issubset(direct_paths))
        self.assertEqual(len(lock["files"]), 58)


class IntentAndHostTests(unittest.TestCase):
    def test_exact_anchor_intent_is_required(self) -> None:
        amendment = json.loads(AMENDMENT.read_bytes())
        intent = amendment["execution"]["exact_finalizer_launch_intent"]
        guard._exact_launch_intent(amendment, {"finalizer_launch_intent": intent})
        changed = json.loads(json.dumps(intent))
        changed["cwd"] = "C:\\wrong"
        with self.assertRaises(guard.ExecutionClosureError):
            guard._exact_launch_intent(amendment, {"finalizer_launch_intent": changed})

    def test_host_binding_requires_every_frozen_field(self) -> None:
        amendment = json.loads(AMENDMENT.read_bytes())
        expected = amendment["host_observer_binding"]
        bindings = {
            "settings": expected["settings"],
            "paths": expected["paths"],
            "backend": {
                **expected["backend"],
                "script_sha256": "a" * 64,
                "capability_probe_pid": 999,
            },
            "observer_source": {
                "path": expected["observer_source"]["path"],
                "sha256": expected["observer_source"]["sha256"],
            },
            "command_tokens": expected["command_tokens"],
            "command_tokens_sha256": expected["command_tokens_sha256"],
        }
        identities = [
            {"pid": pid, "start_ticks": pid * 10} for pid in (101, 201, 202, 203, 204)
        ]
        ready = {
            "schema_version": expected["ready_schema_version"],
            "label": expected["settings"]["label"],
            "observer_pid": 50,
            "inventory_child_pid": 51,
            "observation_started_at_utc": "2026-07-11T00:00:00Z",
            "outcomes_inspected": False,
            "ready": True,
            "bindings": bindings,
        }
        receipt = {
            "schema_version": expected["receipt_schema_version"],
            "label": expected["settings"]["label"],
            "observer": expected["settings"]["observer"],
            "observation_started_at_utc": "2026-07-11T00:00:00Z",
            "observation_ended_at_utc": "2026-07-11T00:01:00Z",
            "inventory_child_pid": 51,
            "bindings": bindings,
            "outer_audit_sha256": "o" * 64,
            "capture_metadata_sha256": "c" * 64,
            "ready_receipt_sha256": "r" * 64,
            "formal_outer_pid": 101,
            "formal_segment_pids": [201, 202, 203, 204],
            "host_contention_event_count": 0,
            "lease_loss_count": 0,
            "all_formal_pids_ended": True,
            "outcomes_inspected": False,
            "template_only": False,
            "excluded_heavy_work": ["fixture"],
            "method": "fixture",
            "contention_events": [],
            "lease_loss_events": [],
            "monitor_failures": [],
            "raw_process_inventory_sha256": "d" * 64,
            "raw_process_inventory_sample_count": 2,
            "poll_gap_max_seconds": 2.1,
            "unexplained_cpu_cores_max": 0.0,
            "formal_process_identity_count": len(identities),
            "formal_process_identities": identities,
            "formal_process_identities_sha256": guard._sha(
                guard._canonical(identities)
            ),
            "formal_clear_snapshot_count": 2,
            "formal_clear_snapshot_ticks": [100, 200],
        }
        guard._host_binding(
            amendment,
            ready,
            receipt,
            ready_sha="r" * 64,
            outer_sha="o" * 64,
            capture_sha="c" * 64,
            outer={"child_pid": 101},
            capture={"child_pids": [201, 202, 203, 204]},
            authority_root=Path(r"C:\solver"),
        )
        receipt["all_formal_pids_ended"] = False
        with self.assertRaises(guard.ExecutionClosureError):
            guard._host_binding(
                amendment,
                ready,
                receipt,
                ready_sha="r" * 64,
                outer_sha="o" * 64,
                capture_sha="c" * 64,
                outer={"child_pid": 101},
                capture={"child_pids": [201, 202, 203, 204]},
                authority_root=Path(r"C:\solver"),
            )
        receipt["all_formal_pids_ended"] = True
        missing = dict(receipt)
        missing.pop("monitor_failures")
        with self.assertRaises(guard.ExecutionClosureError):
            guard._host_binding(
                amendment,
                ready,
                missing,
                ready_sha="r" * 64,
                outer_sha="o" * 64,
                capture_sha="c" * 64,
                outer={"child_pid": 101},
                capture={"child_pids": [201, 202, 203, 204]},
                authority_root=Path(r"C:\solver"),
            )


class BlockadeTests(unittest.TestCase):
    def test_assessor_is_blocked_without_a3_archive_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            paths = {
                "a3_archive": root / "missing-receipt.json",
                "assessment_audit": root / "audit.json",
                "summary": root / "summary.json",
            }
            context = ({}, paths, {}, types.SimpleNamespace())
            with (
                mock.patch.object(guard, "_context", return_value=context),
                self.assertRaises(guard.ExecutionClosureError),
            ):
                guard.assess(root / "amendment.json")

    def test_fail_summary_is_a_valid_completed_decision(self) -> None:
        self.assertEqual(guard._summary_decision({"decision": "PASS"}), "PASS")
        self.assertEqual(guard._summary_decision({"decision": "FAIL"}), "FAIL")
        with self.assertRaises(guard.ExecutionClosureError):
            guard._summary_decision({"decision": "UNKNOWN"})


class PreAndSourceBindingTests(unittest.TestCase):
    def test_pre_embeds_a3_authority_in_a2_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            output = root / "pre.json"
            paths = {
                "source_window": root / "source-window.json",
                "host_ready": root / "ready.json",
                "host_receipt": root / "host.json",
                "a3_archive": root / "archive.json",
                "assessment_audit": root / "assessment.json",
                "summary": root / "summary.json",
                "a2_amendment": root / "a2.json",
            }
            authority = {"checker_sha256": "c" * 64}
            a2 = types.SimpleNamespace(
                build_pre_receipt=mock.Mock(return_value=({"passed": True}, output))
            )
            amendment = {"monitor": {"interval_seconds": 0.1}}
            with mock.patch.object(
                guard,
                "_context",
                return_value=(amendment, paths, authority, a2),
            ):
                document, actual, returned_a2 = guard.build_pre(root / "a3.json")
        self.assertEqual(actual, output)
        self.assertIs(returned_a2, a2)
        self.assertEqual(document["execution_closure_a3"]["authority"], authority)

    def test_source_observation_requires_all_a3_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            pre = root / "pre.json"
            pre.write_bytes(b"pre")
            source = root / "source.json"
            authority = {
                "amendment_sha256": "a" * 64,
                "checker_sha256": "c" * 64,
            }
            document = {
                "formal_execution_closure_amendment_a3_sha256": "a" * 64,
                "formal_execution_closure_checker_a3_sha256": "c" * 64,
                "formal_execution_closure_pre_audit_sha256": hashlib.sha256(
                    b"pre"
                ).hexdigest(),
                "outcomes_inspected": False,
            }
            source.write_text(json.dumps(document), encoding="utf-8")
            amendment = {
                "execution": {"source_observation_relative_path": "source.json"}
            }
            paths = {"repo": root, "v1_pre": pre}
            guard._verify_source_observation(amendment, paths, authority)
            document.pop("formal_execution_closure_checker_a3_sha256")
            source.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(guard.ExecutionClosureError):
                guard._verify_source_observation(amendment, paths, authority)

    def test_existing_unbound_output_is_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            receipt = root / "receipt.json"
            receipt.write_text("{}", encoding="utf-8")
            summary = root / "summary.json"
            summary.write_text("unbound", encoding="utf-8")
            paths = {
                "a3_archive": receipt,
                "assessment_audit": root / "audit.json",
                "summary": summary,
            }
            context = ({}, paths, {}, types.SimpleNamespace())
            with (
                mock.patch.object(guard, "_context", return_value=context),
                self.assertRaises(guard.ExecutionClosureError),
            ):
                guard.assess(root / "amendment.json")


class ArchiveStabilityTests(unittest.TestCase):
    def test_archive_inventory_detects_byte_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            path = root / "capture.json"
            path.write_bytes(b"first")
            before, _ = guard._inventory_with_bytes(root, set())
            path.write_bytes(b"second")
            after, _ = guard._inventory_with_bytes(root, set())
        self.assertNotEqual(before, after)

    def test_archive_inventory_detects_membership_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "capture.json").write_bytes(b"capture")
            before, _ = guard._inventory_with_bytes(root, set())
            (root / "unexpected.json").write_bytes(b"unexpected")
            after, _ = guard._inventory_with_bytes(root, set())
        self.assertNotEqual(before["root_sha256"], after["root_sha256"])


class ProductionPlanTests(unittest.TestCase):
    def test_checker_self_hash_and_a2_hashes_are_frozen(self) -> None:
        amendment = json.loads(AMENDMENT.read_bytes())
        checker = hashlib.sha256(
            (HERE / "formal_execution_closure_a3.py").read_bytes()
        ).hexdigest()
        self.assertEqual(amendment["checker"]["sha256"], checker)
        self.assertEqual(
            amendment["a2_authority"]["checker_sha256"],
            hashlib.sha256(
                (HERE / "formal_publication_guard_a2.py").read_bytes()
            ).hexdigest(),
        )

    def test_production_receipt_and_audit_paths_are_distinct(self) -> None:
        amendment = json.loads(AMENDMENT.read_bytes())
        paths = guard._paths(amendment)
        selected = [
            paths["v1_pre"],
            paths["source_window"],
            paths["anchor"],
            paths["finalizer_execution"],
            paths["host_receipt"],
            paths["a3_archive"],
            paths["summary"],
            paths["assessment_audit"],
        ]
        self.assertEqual(
            len(selected), len({os.path.normcase(str(p)) for p in selected})
        )

    def test_assessor_command_is_exact_one_output_and_four_segments(self) -> None:
        amendment = json.loads(AMENDMENT.read_bytes())
        tokens = amendment["execution"]["exact_assessor_command_tokens"]
        self.assertEqual(tokens.count("--segment"), 4)
        self.assertEqual(tokens.count("--output"), 1)
        self.assertEqual(tokens.count("--candidate"), 1)
        self.assertEqual(tokens.count("--truth"), 1)
        self.assertEqual(tokens.count("--frozen-k0"), 1)

    def test_host_command_and_main_ready_path_are_frozen(self) -> None:
        amendment = json.loads(AMENDMENT.read_bytes())
        host = amendment["host_observer_binding"]
        self.assertEqual(len(host["command_tokens"]), 43)
        self.assertEqual(
            guard._sha(guard._canonical(host["command_tokens"])),
            host["command_tokens_sha256"],
        )
        self.assertEqual(
            host["paths"]["ready"],
            r"C:\solver\research\results\EXP-JAC-003\development-host-observation.ready.json",
        )

    def test_safe_assessment_environment_removes_python_injection(self) -> None:
        amendment = json.loads(AMENDMENT.read_bytes())
        with mock.patch.dict(
            os.environ,
            {"PYTHONPATH": "injected", "PYTHONHOME": "injected"},
            clear=False,
        ):
            environment, audit = guard._assessment_environment(amendment)
        self.assertNotIn("PYTHONPATH", environment)
        self.assertNotIn("PYTHONHOME", environment)
        self.assertEqual(environment["PYTHONDONTWRITEBYTECODE"], "1")
        self.assertEqual(audit["fixed_overrides"]["PYTHONNOUSERSITE"], "1")


if __name__ == "__main__":
    unittest.main()
