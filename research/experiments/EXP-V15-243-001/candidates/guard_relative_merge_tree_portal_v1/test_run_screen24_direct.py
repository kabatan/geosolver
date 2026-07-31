from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import run_screen24_direct as runner


class RunnerContainmentTests(unittest.TestCase):
    def test_leaf_and_sha_shapes_reject_path_routing(self):
        self.assertIsNotNone(runner.LEAF_RE.fullmatch("017-generated_case"))
        self.assertIsNone(runner.LEAF_RE.fullmatch("../017-generated_case"))
        self.assertIsNone(runner.LEAF_RE.fullmatch("017/generated_case"))
        self.assertIsNotNone(runner.SHA256_RE.fullmatch("a" * 64))
        self.assertIsNone(runner.SHA256_RE.fullmatch("A" * 64))

    def test_resolved_path_cannot_escape_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "root"
            root.mkdir()
            self.assertEqual(
                runner._contained(root, root / "seed-0" / "x"),
                (root / "seed-0" / "x").resolve(),
            )
            with self.assertRaises(SystemExit):
                runner._contained(root, root / ".." / "escape")

    def test_candidate_sidecar_is_bound_to_exact_result_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "search.json"
            output.write_text('{"completed":true}\n', encoding="utf-8")
            sidecar = output.with_name(output.name + ".guard-merge-portal.json")
            sidecar.write_text(
                json.dumps(
                    {
                        "schema_version": runner.PORTAL_SIDECAR_SCHEMA,
                        "search_result_sha256": hashlib.sha256(
                            output.read_bytes()
                        ).hexdigest(),
                        "individual_observations_emitted": False,
                    }
                ),
                encoding="utf-8",
            )
            runner._portal_sidecar(output)
            output.write_text('{"completed":false}\n', encoding="utf-8")
            with self.assertRaises(ValueError):
                runner._portal_sidecar(output)

    def test_pair_directory_cannot_be_resumed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "already-created" / "search.json"
            output.parent.mkdir()
            with self.assertRaises(SystemExit):
                runner._run_one(
                    runner.CONTROL,
                    root / "unused-source.json",
                    "a" * 64,
                    output,
                    0,
                )


if __name__ == "__main__":
    unittest.main()
