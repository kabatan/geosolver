from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from candidate import attempt_source
from generated_cases import NEGATIVES, POSITIVES, permuted, reflected, rotated
from or_connector import gram_or_baseline
from verifier import VerificationFailure, verify_source


def _write(root: Path, name: str, document: dict):
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    path = root / f"{name}.json"
    path.write_bytes(raw)
    return path, hashlib.sha256(raw).hexdigest()


class GramChirotopeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def certify(self, name, document):
        source, digest = _write(self.root, name, document)
        certificate = attempt_source(source=source, source_sha256=digest)
        return source, digest, certificate

    def test_three_positive_families_independently_verify(self):
        for name, document in POSITIVES.items():
            with self.subTest(name=name):
                source, digest, certificate = self.certify(name, document)
                self.assertTrue(certificate["authority_pass"])
                self.assertLessEqual(certificate["gram_rank"], 2)
                self.assertTrue(certificate["all_3x3_gram_minors_zero"])
                verified = verify_source(source=source, source_sha256=digest, certificate=certificate)
                self.assertTrue(verified["verified"])

    def test_three_negative_families_and_absolute_escape_fail_closed(self):
        expected = {
            "rank3-gram": "rank3-or-higher-gram",
            "same-edm-mirror-ambiguity": "mirror-ambiguity-no-orientation-choice",
            "near-zero-orientation": "near-zero-orientation",
            "absolute-coordinate-guard": "source-escape:absolute_coordinate_guards",
        }
        for name, document in NEGATIVES.items():
            with self.subTest(name=name):
                _source, _digest, result = self.certify(name, document)
                self.assertFalse(result["authority_pass"])
                self.assertEqual(result["failure_reason"], expected[name])
                self.assertIsNone(result.get("descriptor"))

    def test_bound_raw_scalar_and_noninvariant_escapes_fail_closed(self):
        base = POSITIVES["anonymous-rational-triangle"]
        escapes = {
            "bounds": ["x in [0,1]"],
            "raw_scalar_uses": ["x"],
            "non_invariant_operations": ["coordinate-x"],
        }
        for field, value in escapes.items():
            document = deepcopy(base)
            document[field] = value
            _source, _digest, result = self.certify(f"escape-{field}", document)
            self.assertFalse(result["authority_pass"])
            self.assertEqual(result["failure_reason"], f"source-escape:{field}")

    def test_point_permutation_rotation_reflection_for_each_family(self):
        for name, base in POSITIVES.items():
            _, _, base_certificate = self.certify(f"{name}-base", base)
            for transform_name, transformed in (
                ("permutation", permuted(name)),
                ("rotation", rotated(name)),
                ("reflection", reflected(name)),
            ):
                with self.subTest(name=name, transform=transform_name):
                    source, digest, certificate = self.certify(f"{name}-{transform_name}", transformed)
                    self.assertTrue(certificate["authority_pass"])
                    self.assertEqual(certificate["raw_target_exact"], base_certificate["raw_target_exact"])
                    self.assertTrue(verify_source(source=source, source_sha256=digest, certificate=certificate)["verified"])

    def test_same_edm_reflection_flips_exact_chirotope_and_selector(self):
        name = "anonymous-rational-triangle"
        _s1, _d1, first = self.certify("mirror-first", POSITIVES[name])
        _s2, _d2, second = self.certify("mirror-second", reflected(name))
        self.assertEqual(first["distance_matrix"], second["distance_matrix"])
        self.assertEqual(first["orientation_ledger"][0]["sign"], -second["orientation_ledger"][0]["sign"])
        self.assertNotEqual(first["selector_ledger"][0]["bit"], second["selector_ledger"][0]["bit"])

    def test_independent_verifier_rejects_authority_mutations(self):
        source, digest, certificate = self.certify("mutations", POSITIVES["anonymous-rational-triangle"])
        mutations = []
        target = deepcopy(certificate); target["raw_target_exact"] = "4"; mutations.append(target)
        rank = deepcopy(certificate); rank["gram_rank"] = 1; mutations.append(rank)
        edm = deepcopy(certificate); edm["distance_matrix"][0][1] = "10"; mutations.append(edm)
        coordinates = deepcopy(certificate); coordinates["qqbar_realization"][1][0] = "4"; mutations.append(coordinates)
        for mutation in mutations:
            with self.assertRaises(VerificationFailure):
                verify_source(source=source, source_sha256=digest, certificate=mutation)

    def test_baseline_identity_and_quota(self):
        source, digest = _write(self.root, "connector", POSITIVES["anonymous-rational-triangle"])
        miss = {"authority_pass": False, "status": "BASELINE_MISS"}
        result = gram_or_baseline(
            source=source,
            source_sha256=digest,
            total_confirmation_seconds=10.0,
            baseline=lambda: miss,
        )
        self.assertTrue(result["authority_pass"])
        self.assertTrue(result["baseline_was_called"])
        self.assertGreaterEqual(result["budget"]["baseline_minimum_fraction"], 0.75)
        self.assertLessEqual(result["budget"]["side_maximum_fraction"], 0.25)
        failure = gram_or_baseline(
            source=source,
            source_sha256="0" * 64,
            total_confirmation_seconds=10.0,
            baseline=lambda: miss,
        )
        self.assertIs(failure, miss)

    def test_baseline_authority_runs_first_and_suppresses_side(self):
        source, digest = _write(self.root, "baseline-first", POSITIVES["anonymous-rational-triangle"])
        baseline_authority = {"authority_pass": True, "status": "BASELINE_AUTHORITY"}
        side_calls = []

        def side(**kwargs):
            side_calls.append(kwargs)
            raise AssertionError("side must not run after baseline authority")

        result = gram_or_baseline(
            source=source,
            source_sha256=digest,
            total_confirmation_seconds=10.0,
            baseline=lambda: baseline_authority,
            side_attempt=side,
        )
        self.assertIs(result, baseline_authority)
        self.assertEqual(side_calls, [])


if __name__ == "__main__":
    unittest.main()
