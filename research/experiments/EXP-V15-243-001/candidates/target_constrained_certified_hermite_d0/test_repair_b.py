from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest

from generated_repair_cases import NEGATIVE, POSITIVE
from hard_child_runner import run_hard_child, verify_guard_pins
from repair_b_connector import hermite_or_existing_exact_coordinate


def _source(root: Path, document: dict) -> tuple[Path, str]:
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    path = root / "SOURCE.json"
    path.write_bytes(raw)
    return path, hashlib.sha256(raw).hexdigest()


class HardChildTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        document, self.descriptor, self.endpoint = POSITIVE["anonymous-stratum-a-degree1-ge-ne"]
        self.source, self.source_sha256 = _source(self.root, document)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_fault(self, fault: str, seconds: float = 2.0, late_marker: Path | None = None):
        return run_hard_child(
            source=self.source,
            source_sha256=self.source_sha256,
            descriptor=self.descriptor,
            endpoint=self.endpoint,
            output_dir=self.root / fault,
            cpu=15,
            side_seconds=seconds,
            fault=fault,
            late_marker=late_marker,
        )

    def test_guard_closure_is_digest_pinned(self):
        self.assertEqual(len(verify_guard_pins()), 4)

    def test_real_child_authority_has_both_independent_checks(self):
        result = run_hard_child(
            source=self.source,
            source_sha256=self.source_sha256,
            descriptor=self.descriptor,
            endpoint=self.endpoint,
            output_dir=self.root / "positive",
            cpu=15,
            side_seconds=4.0,
        )
        self.assertEqual(result["process"]["classification"], "SUCCESS")
        self.assertTrue(result["authority"]["independent_verification"]["verified"])
        self.assertTrue(result["authority"]["untouched_source_replay"]["verified"])
        self.assertEqual(result["authority"]["descriptor"], self.descriptor)

    def test_partial_json_is_rejected_despite_zero_exit(self):
        result = self.run_fault("partial-json")
        self.assertEqual(result["process"]["classification"], "SUCCESS")
        self.assertIsNone(result["authority"])
        self.assertEqual(result["failure_reason"], "partial-or-malformed-artifact")
        self.assertFalse((self.root / "partial-json" / "RESULT.json").exists())

    def test_timeout_hard_kills_child(self):
        result = self.run_fault("sleep", seconds=0.70)
        self.assertEqual(result["process"]["classification"], "TIMEOUT")
        self.assertTrue(result["process"]["timeout"])
        self.assertIsNone(result["authority"])

    def test_output_cap_is_hard_failure(self):
        result = self.run_fault("output")
        self.assertEqual(result["process"]["classification"], "OUTPUT_LIMIT_EXCEEDED")
        self.assertTrue(result["process"]["output_cap_exceeded"])
        self.assertIsNone(result["authority"])

    def test_closure_rss_cap_is_hard_failure(self):
        result = self.run_fault("rss")
        self.assertEqual(result["process"]["classification"], "RSS_LIMIT_EXCEEDED")
        self.assertTrue(result["process"]["rss_cap_exceeded"])
        self.assertIsNone(result["authority"])

    def test_descendant_leak_cannot_publish_late_artifact(self):
        marker = self.root / "late-marker"
        result = self.run_fault("leak-late-artifact", late_marker=marker)
        self.assertEqual(result["process"]["classification"], "DESCENDANT_LEAK")
        self.assertTrue(result["process"]["descendant_leak"])
        self.assertIsNone(result["authority"])
        time.sleep(1.25)
        self.assertFalse(marker.exists())

    def test_backend_cap_failure_never_becomes_authority(self):
        document, descriptor, endpoint, _reason = NEGATIVE["phase-sheet-unsupported"]
        source, source_sha256 = _source(self.root, document)
        result = run_hard_child(
            source=source,
            source_sha256=source_sha256,
            descriptor=descriptor,
            endpoint=endpoint,
            output_dir=self.root / "unsupported",
            cpu=15,
            side_seconds=3.0,
        )
        self.assertEqual(result["process"]["classification"], "SUCCESS")
        self.assertIsNone(result["authority"])
        self.assertEqual(result["failure_reason"], "child-authority-rejected")

    def test_non_cpu15_fails_before_launch(self):
        result = run_hard_child(
            source=self.source,
            source_sha256=self.source_sha256,
            descriptor=self.descriptor,
            endpoint=self.endpoint,
            output_dir=self.root / "wrong-cpu",
            cpu=14,
            side_seconds=2.0,
        )
        self.assertIsNone(result["process"])
        self.assertIn("restricted-to-cpu15", result["failure_reason"])


class ConnectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        document, descriptor, self.endpoint = POSITIVE["anonymous-stratum-a-degree1-ge-ne"]
        self.source, self.source_sha256 = _source(self.root, document)
        self.ordinary = {
            "status": "TARGET_AUTHORITY_READY",
            "authority_pass": True,
            "descriptor": descriptor,
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def call(self, *, ordinary=None, route_kind="ordinary-exact-outer", baseline=None, child=None):
        baseline = {"status": "EXACT_CONFIRMATION_REJECTED", "authority_pass": False} if baseline is None else baseline
        child = (lambda **_kwargs: {"authority": None}) if child is None else child
        return hermite_or_existing_exact_coordinate(
            route_kind=route_kind,
            ordinary=self.ordinary if ordinary is None else ordinary,
            source=self.source,
            source_sha256=self.source_sha256,
            endpoint=self.endpoint,
            cpu=15,
            output_dir=self.root,
            confirmation_budget_seconds=10.0,
            existing_exact_coordinate=lambda: baseline,
            child_runner=child,
        )

    def test_ineligible_route_returns_exact_baseline_object_without_child(self):
        sentinel = object()
        called = []
        result = self.call(
            route_kind="zero-dimensional-existing-route",
            baseline=sentinel,
            child=lambda **kwargs: called.append(kwargs),
        )
        self.assertIs(result, sentinel)
        self.assertEqual(called, [])

    def test_child_failure_returns_exact_baseline_object(self):
        sentinel = {"status": "EXACT_CONFIRMATION_REJECTED", "authority_pass": False}
        self.assertIs(self.call(baseline=sentinel), sentinel)

    def test_child_exception_returns_exact_baseline_object(self):
        sentinel = {"status": "EXACT_CONFIRMATION_REJECTED", "authority_pass": False}

        def explode(**_kwargs):
            raise RuntimeError("generated child seam exception")

        self.assertIs(self.call(baseline=sentinel, child=explode), sentinel)

    def test_existing_exact_authority_wins_and_is_byte_identity_preserved(self):
        sentinel = {"status": "TARGET_AUTHORITY_READY", "authority_pass": True, "descriptor": {"baseline": True}}
        repair = {"status": "TARGET_AUTHORITY_READY", "authority_pass": True, "descriptor": self.ordinary["descriptor"]}
        self.assertIs(self.call(baseline=sentinel, child=lambda **_kwargs: {"authority": repair}), sentinel)

    def test_hermite_is_only_or_after_existing_confirmation_miss(self):
        repair = {
            "status": "TARGET_AUTHORITY_READY",
            "authority_pass": True,
            "descriptor": self.ordinary["descriptor"],
        }
        result = self.call(child=lambda **_kwargs: {"authority": repair})
        self.assertTrue(result["existing_exact_coordinate_was_called"])
        self.assertLessEqual(result["confirmation_budget"]["hermite_fraction"], 0.25)
        self.assertGreaterEqual(result["confirmation_budget"]["baseline_minimum_fraction"], 0.75)

    def test_real_child_smoke_through_connector(self):
        result = hermite_or_existing_exact_coordinate(
            route_kind="ordinary-exact-outer",
            ordinary=self.ordinary,
            source=self.source,
            source_sha256=self.source_sha256,
            endpoint=self.endpoint,
            cpu=15,
            output_dir=self.root,
            confirmation_budget_seconds=20.0,
            existing_exact_coordinate=lambda: {"status": "EXACT_CONFIRMATION_REJECTED", "authority_pass": False},
        )
        self.assertEqual(result["status"], "TARGET_AUTHORITY_READY")
        self.assertTrue(result["independent_verification"]["verified"])
        self.assertTrue(result["untouched_source_replay"]["verified"])


if __name__ == "__main__":
    unittest.main()
