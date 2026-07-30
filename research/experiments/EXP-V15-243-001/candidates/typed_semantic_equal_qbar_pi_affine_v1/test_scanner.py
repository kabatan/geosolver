from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from scanner import scan


def source(constraints):
    return {
        "task": "solve",
        "variables": {"names": ["x", "y"]},
        "construction": [
            {"name": "A", "expr": "Point(x, y)"},
            {"name": "B", "expr": "Point(0, 0)"},
            {"name": "C", "expr": "Point(1, 0)"},
        ],
        "constraints": constraints,
        # Scanner must ignore every field below.
        "answer": "DO_NOT_READ",
        "target": {"DO_NOT_READ": True},
        "truth": {"DO_NOT_READ": True},
    }


class ScannerTests(unittest.TestCase):
    def test_affine_direct_equality_is_eligible(self):
        document = source([{"def": "sqrt_placeholder*pi + x", "value": "x + pi*sqrt_placeholder"}])
        # An unknown name is intentionally closed/fallback.
        self.assertEqual(scan(document, "value is not exact rational")["eligible_relation_count"], 0)
        document["variables"]["names"].append("sqrt_placeholder")
        result = scan(document, "value is not exact rational")
        self.assertEqual(result["eligible_relation_count"], 1)
        self.assertEqual(len(result["anonymous_structural_signature_sha256"]), 64)

    def test_direct_angle_same_domain_is_eligible_for_angle_failure(self):
        document = source([{"def": "Angle(A, B, C)", "value": "Angle(C, B, A)"}])
        self.assertEqual(scan(document, "scalar is not an exact angle expression")["eligible_relation_count"], 1)
        self.assertEqual(scan(document, "value is not exact rational")["eligible_relation_count"], 0)

    def test_mixed_nonlinear_nested_and_unknown_are_rejected(self):
        constraints = [
            {"def": "pi", "value": "pi + 0"},
            {"def": "pi*pi", "value": "x"},
            {"def": "sin(pi)", "value": 0},
            {"def": "Angle(A, B, C)", "value": "pi"},
        ]
        for failure in ("value is not exact rational", "scalar is not an exact angle expression"):
            self.assertEqual(scan(source(constraints), failure)["eligible_relation_count"], 0)

    def test_canonical_rational_into_qbar_equality_is_eligible_only_at_root(self):
        document = source(
            [
                {"def": "Distance(A, B)", "value": 1},
                {"def": "1", "value": "Distance(A, B)"},
                {"def": "x + 1", "value": "x + 1"},
            ]
        )
        result = scan(document, "value is not exact rational")
        self.assertEqual(result["eligible_relation_count"], 2)

    def test_scanner_output_is_only_count_and_anonymous_hash(self):
        document = source([{"def": "x*pi + y", "value": "y + pi*x"}])
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "opaque-source.json"
            payload = json.dumps(document).encode()
            path.write_bytes(payload)
            completed = subprocess.run(
                [
                    os.environ.get("PYTHON", os.sys.executable),
                    str(Path(__file__).with_name("scanner.py")),
                    "--source",
                    str(path),
                    "--source-sha256",
                    hashlib.sha256(payload).hexdigest(),
                    "--failure-class",
                    "value is not exact rational",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        output = json.loads(completed.stdout)
        self.assertEqual(
            set(output),
            {
                "eligible_relation_count",
                "anonymous_structural_signature_sha256",
                "ineligibility_reason_counts",
                "closed_operator_type_shape_counts",
            },
        )
        self.assertNotIn("DO_NOT_READ", completed.stdout)

    def test_repair_a_reports_only_closed_aggregate_reasons_and_shapes(self):
        document = source(
            [
                {"def": "pi*pi", "value": "x"},
                {"def": "Angle(A, B, C)", "value": "pi"},
                {"def": "sin(pi)", "value": 0},
                {"def": "x", "value": 1},
            ]
        )
        result = scan(document, "scalar is not an exact angle expression")
        self.assertEqual(
            result["ineligibility_reason_counts"],
            {
                "MIXED_CLOSED_TYPES": 1,
                "NONLINEAR_OR_NESTED_PI": 2,
            },
        )
        self.assertTrue(result["closed_operator_type_shape_counts"])
        rendered = json.dumps(result)
        self.assertNotIn("Angle(A", rendered)
        self.assertNotIn("pi*pi", rendered)

    def test_cpu15_only(self):
        self.assertEqual(os.sched_getaffinity(0), {15})


if __name__ == "__main__":
    unittest.main()
