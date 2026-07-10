from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "prepare_inputs.py"
SPEC = importlib.util.spec_from_file_location("exp_jac_prepare", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
PREPARE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREPARE)

VALIDATE_PATH = PREPARE.REPO_ROOT / "research" / "validate.py"
VALIDATE_SPEC = importlib.util.spec_from_file_location(
    "research_validate", VALIDATE_PATH
)
assert VALIDATE_SPEC is not None and VALIDATE_SPEC.loader is not None
VALIDATE = importlib.util.module_from_spec(VALIDATE_SPEC)
VALIDATE_SPEC.loader.exec_module(VALIDATE)


class FrozenInputTests(unittest.TestCase):
    def test_deterministic_gzip(self) -> None:
        raw = b'{"answer":42}\n'
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.json.gz"
            second = Path(directory) / "second.json.gz"
            PREPARE.write_gzip_atomic(first, raw)
            PREPARE.write_gzip_atomic(second, raw)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(PREPARE.load_gzip_json(first), {"answer": 42})

    def test_benchmark_manifest_matches_repository_schema(self) -> None:
        artifact = PREPARE.REPO_ROOT / "frozen.json.gz"
        document = {
            "partition": "development",
            "instances": [
                {
                    "case_id": "case-1",
                    "family_id": "JAC-DIAGONAL-BLOCK",
                    "generator_id": "typed-block-v1",
                    "problem_sha256": "a" * 64,
                    "truth_sha256": "b" * 64,
                    "strata": ["S1"],
                }
            ],
        }
        manifest = PREPARE.benchmark_manifest(document, artifact)
        schema = json.loads(
            (
                PREPARE.REPO_ROOT
                / "research"
                / "schemas"
                / "benchmark-manifest.schema.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(VALIDATE.validate_instance(manifest, schema), [])


if __name__ == "__main__":
    unittest.main()
