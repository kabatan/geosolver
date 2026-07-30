from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from candidate import attempt_source
from generated_cases import NEGATIVES, POSITIVES, reversed_endpoint_hints
from or_connector import ruler_compass_or_baseline
from verifier import VerificationFailure, verify_source


def _write(root, name, document):
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    source = root / f"{name}.json"; source.write_bytes(raw)
    return source, hashlib.sha256(raw).hexdigest()


class RulerCompassTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def run_case(self, name, document):
        source, digest = _write(self.root, name, document)
        return source, digest, attempt_source(source=source, source_sha256=digest)

    def test_circle_circle_line_circle_line_line(self):
        for name, document in POSITIVES.items():
            source, digest, certificate = self.run_case(name, document)
            self.assertTrue(certificate["authority_pass"])
            self.assertTrue(certificate["all_branches_exactly_replayed"])
            self.assertEqual(certificate["branches_examined_exactly"], certificate["branches_generated"])
            self.assertTrue(verify_source(source=source, source_sha256=digest, certificate=certificate)["verified"])

    def test_endpoint_only_changes_trial_order_never_authority(self):
        for name, document in POSITIVES.items():
            _s1, _d1, first = self.run_case(f"{name}-first", document)
            _s2, _d2, second = self.run_case(f"{name}-reordered", reversed_endpoint_hints(document))
            self.assertEqual(first["raw_target_exact_set"], second["raw_target_exact_set"])
            self.assertEqual(first["branches_accepted"], second["branches_accepted"])
            self.assertEqual(first["endpoint_role"], "BRANCH_TRIAL_ORDER_ONLY_NOT_AUTHORITY")

    def test_branch_cap_near_zero_and_operation_escape(self):
        expected = {
            "branch-cap": "branch-cap-exceeded",
            "near-zero-orientation": "near-zero-orientation",
            "operation-escape": "source-operation-escape",
        }
        for name, document in NEGATIVES.items():
            _source, _digest, result = self.run_case(name, document)
            self.assertFalse(result["authority_pass"])
            self.assertEqual(result["failure_reason"], expected[name])

    def test_independent_verifier_rejects_branch_and_target_mutation(self):
        source, digest, certificate = self.run_case("mutation", POSITIVES["anonymous-circle-circle"])
        target = deepcopy(certificate); target["raw_target_exact_set"] = ["4"]
        branch = deepcopy(certificate); branch["branches_generated"] = 1
        coordinate = deepcopy(certificate); coordinate["accepted_realizations"][0]["points"]["C"][0] = "3"
        for mutation in (target, branch, coordinate):
            with self.assertRaises(VerificationFailure):
                verify_source(source=source, source_sha256=digest, certificate=mutation)

    def test_baseline_first_identity_and_quota(self):
        source, digest = _write(self.root, "connector", POSITIVES["anonymous-line-line"])
        authority = {"authority_pass": True}
        calls = []
        result = ruler_compass_or_baseline(
            source=source, source_sha256=digest, baseline=lambda: authority,
            side_attempt=lambda **kwargs: calls.append(kwargs),
        )
        self.assertIs(result, authority); self.assertEqual(calls, [])
        miss = {"authority_pass": False}
        result = ruler_compass_or_baseline(source=source, source_sha256=digest, baseline=lambda: miss)
        self.assertTrue(result["authority_pass"])
        self.assertGreaterEqual(result["budget"]["baseline_minimum_fraction"], .75)


if __name__ == "__main__": unittest.main()
