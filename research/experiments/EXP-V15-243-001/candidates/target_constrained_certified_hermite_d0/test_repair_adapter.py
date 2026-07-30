from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

from exact_outer_or_route import repair_or_unchanged_fallback, verify_outer_pins
from generated_repair_cases import NEGATIVE, POSITIVE, affine_target, renamed
from repair_adapter import attempt_repair


def _source(root: Path, name: str, document: dict) -> tuple[Path, str]:
    path = root / f"{name}.json"
    path.write_text(json.dumps(document, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


class RepairAdapterTests(unittest.TestCase):
    def test_positive_anonymous_strata_and_metamorphics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, (document, descriptor, endpoint) in POSITIVE.items():
                variants = [("base", document, descriptor), ("rename", renamed(document), descriptor)]
                affine_document, affine_descriptor = affine_target(document, descriptor)
                variants.append(("affine", affine_document, affine_descriptor))
                for variant, source_document, source_descriptor in variants:
                    with self.subTest(name=name, variant=variant):
                        source, digest = _source(root, f"{name}-{variant}", source_document)
                        result = attempt_repair(
                            source=source,
                            source_sha256=digest,
                            descriptor=source_descriptor,
                            endpoint=endpoint,
                        )
                        self.assertTrue(result["authority_pass"], result)
                        self.assertEqual(result["descriptor"], source_descriptor)
                        self.assertTrue(result["independent_verification"]["verified"])
                        self.assertTrue(result["untouched_source_replay"]["verified"])
                        self.assertFalse(result["coordinate_exactification"])
                        self.assertFalse(result["witness_cell_seed"]["used_for_routing"])
                        self.assertEqual(result["binding"]["typed_predicates_dropped"], 0)

    def test_negative_and_unsupported_are_false_zero(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, (document, descriptor, endpoint, expected) in NEGATIVE.items():
                with self.subTest(name=name):
                    source, digest = _source(root, name, document)
                    result = attempt_repair(
                        source=source,
                        source_sha256=digest,
                        descriptor=descriptor,
                        endpoint=endpoint,
                    )
                    self.assertFalse(result["authority_pass"])
                    self.assertIsNone(result["descriptor"])
                    self.assertEqual(result["failure_reason"], expected)

    def test_source_digest_mutation_fails_closed(self) -> None:
        document, descriptor, endpoint = POSITIVE["anonymous-stratum-a-degree1-ge-ne"]
        with tempfile.TemporaryDirectory() as directory:
            source, digest = _source(Path(directory), "digest", document)
            result = attempt_repair(
                source=source,
                source_sha256="0" * 64,
                descriptor=descriptor,
                endpoint=endpoint,
            )
            self.assertFalse(result["authority_pass"])
            self.assertEqual(result["failure_reason"], "untouched-source-digest-mismatch")
            self.assertNotEqual(digest, "0" * 64)

    def test_dry_exact_outer_or_route_is_additive(self) -> None:
        verify_outer_pins()
        document, descriptor, endpoint = POSITIVE["anonymous-stratum-b-degree2-strict"]
        with tempfile.TemporaryDirectory() as directory:
            source, digest = _source(Path(directory), "or-positive", document)
            ordinary = {
                "status": "TARGET_AUTHORITY_READY",
                "authority_pass": True,
                "descriptor": descriptor,
            }
            fallback_calls = []

            def fallback():
                fallback_calls.append(True)
                return {"unchanged": True}

            repaired = repair_or_unchanged_fallback(
                route_kind="ordinary-exact-outer",
                ordinary=ordinary,
                source=source,
                source_sha256=digest,
                endpoint=endpoint,
                unchanged_fallback=fallback,
            )
            self.assertTrue(repaired["authority_pass"])
            self.assertEqual(fallback_calls, [])
            self.assertFalse(repaired["baseline_quota_changed"])

            sentinel = {"identity": "fallback"}
            untouched = repair_or_unchanged_fallback(
                route_kind="zero-dimensional",
                ordinary=ordinary,
                source=source,
                source_sha256=digest,
                endpoint=endpoint,
                unchanged_fallback=lambda: sentinel,
            )
            self.assertIs(untouched, sentinel)

    def test_failed_repair_returns_unchanged_fallback_identity(self) -> None:
        document, descriptor, endpoint, _ = NEGATIVE["wrong-sign-strict-guard"]
        with tempfile.TemporaryDirectory() as directory:
            source, digest = _source(Path(directory), "or-negative", document)
            sentinel = {"identity": "ordinary-fallback"}
            result = repair_or_unchanged_fallback(
                route_kind="ordinary-exact-outer",
                ordinary={
                    "status": "TARGET_AUTHORITY_READY",
                    "authority_pass": True,
                    "descriptor": descriptor,
                },
                source=source,
                source_sha256=digest,
                endpoint=endpoint,
                unchanged_fallback=lambda: sentinel,
            )
            self.assertIs(result, sentinel)

    def test_unsupported_exception_is_normalized_not_raised(self) -> None:
        document, descriptor, endpoint = POSITIVE["anonymous-stratum-a-degree1-ge-ne"]
        with tempfile.TemporaryDirectory() as directory:
            source, digest = _source(Path(directory), "attribute-error", document)
            with mock.patch(
                "repair_adapter.load_pinned_semantic_lift",
                side_effect=AttributeError("unsupported Boolean Or"),
            ):
                result = attempt_repair(
                    source=source,
                    source_sha256=digest,
                    descriptor=descriptor,
                    endpoint=endpoint,
                )
            self.assertFalse(result["authority_pass"])
            self.assertIsNone(result["descriptor"])
            self.assertEqual(result["failure_reason"], "unsupported-exception:AttributeError")
            self.assertTrue(result["partial_certificate_discarded"])

    def test_or_seam_contains_unexpected_candidate_exception(self) -> None:
        document, descriptor, endpoint = POSITIVE["anonymous-stratum-b-degree2-strict"]
        with tempfile.TemporaryDirectory() as directory:
            source, digest = _source(Path(directory), "or-exception", document)
            sentinel = {"identity": "fallback-after-exception"}
            with mock.patch(
                "exact_outer_or_route.attempt_repair",
                side_effect=AttributeError("unsupported Boolean Or"),
            ):
                result = repair_or_unchanged_fallback(
                    route_kind="ordinary-exact-outer",
                    ordinary={
                        "status": "TARGET_AUTHORITY_READY",
                        "authority_pass": True,
                        "descriptor": descriptor,
                    },
                    source=source,
                    source_sha256=digest,
                    endpoint=endpoint,
                    unchanged_fallback=lambda: sentinel,
                )
            self.assertIs(result, sentinel)

    def test_post_certificate_exception_discards_partial_artifact(self) -> None:
        document, descriptor, endpoint = POSITIVE["anonymous-stratum-b-degree2-strict"]
        with tempfile.TemporaryDirectory() as directory:
            source, digest = _source(Path(directory), "partial-certificate", document)
            with mock.patch(
                "repair_adapter.verify",
                side_effect=AttributeError("verifier shape failure"),
            ):
                result = attempt_repair(
                    source=source,
                    source_sha256=digest,
                    descriptor=descriptor,
                    endpoint=endpoint,
                )
            self.assertFalse(result["authority_pass"])
            self.assertIsNone(result["descriptor"])
            self.assertNotIn("certificate", result)
            self.assertTrue(result["partial_certificate_discarded"])
            self.assertEqual(result["failure_reason"], "unsupported-exception:AttributeError")

    def test_expired_deadline_emits_no_partial_authority(self) -> None:
        document, descriptor, endpoint = POSITIVE["anonymous-stratum-a-degree1-ge-ne"]
        with tempfile.TemporaryDirectory() as directory:
            source, digest = _source(Path(directory), "deadline", document)
            result = attempt_repair(
                source=source,
                source_sha256=digest,
                descriptor=descriptor,
                endpoint=endpoint,
                deadline_monotonic=time.monotonic() - 1.0,
            )
            self.assertFalse(result["authority_pass"])
            self.assertIsNone(result["descriptor"])
            self.assertNotIn("certificate", result)
            self.assertEqual(result["failure_reason"], "deadline-exceeded:entry")


if __name__ == "__main__":
    unittest.main()
