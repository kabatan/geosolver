from __future__ import annotations

import hashlib
import importlib.util
import json
import unittest
from pathlib import Path
from typing import Any


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = EXPERIMENT_ROOT.parents[2]
SOURCE_ROOT = EXPERIMENT_ROOT / "source"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


generator = _load_module("jac3_generator_test", SOURCE_ROOT / "generator.py")
assessor = _load_module("jac3_assessor_test", SOURCE_ROOT / "assessor.py")
materializer = _load_module("jac3_materializer_test", SOURCE_ROOT / "materialize_development.py")


def _walk_keys(value: Any):
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key).lower()
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_keys(child)


class PreimplementationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.candidate = generator.build_candidate_document()
        cls.assessment = assessor.build_assessor_document(cls.candidate)

    def test_allocation_and_determinism(self) -> None:
        self.assertEqual(self.candidate["case_count"], 64)
        self.assertEqual(self.candidate["starts_per_case"], 32)
        self.assertEqual(self.candidate, generator.build_candidate_document())
        ids = [case["opaque_case_id"] for case in self.candidate["cases"]]
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(len(set(ids)), 64)
        self.assertTrue(all(len(case["starts"]) == 32 for case in self.candidate["cases"]))

    def test_candidate_payload_has_no_assessor_fields(self) -> None:
        keys = set(_walk_keys(self.candidate))
        self.assertFalse(keys & materializer.FORBIDDEN_CANDIDATE_KEYS)
        serialized = json.dumps(self.candidate, sort_keys=True).lower()
        for family in (
            "jac3-trig-tree",
            "jac3-rational-hypergraph",
            "jac3-hex-ring-stencil",
            "jac3-dense-branch-control",
        ):
            self.assertNotIn(family, serialized)

    def test_candidate_typed_graph_matches_black_box_supports(self) -> None:
        materializer._validate_candidate(self.candidate)

    def test_independent_assessor_join_and_known_roots(self) -> None:
        candidate_ids = [case["opaque_case_id"] for case in self.candidate["cases"]]
        assessor_ids = [item["opaque_case_id"] for item in self.assessment["assessments"]]
        self.assertEqual(candidate_ids, assessor_ids)
        self.assertEqual(len(assessor_ids), 64)
        self.assertTrue(
            all(item["known_root_residual_infinity"] <= 1.0e-15 for item in self.assessment["assessments"])
        )
        self.assertTrue(
            all(len(item["analytic_jacobian_traces"]) == 32 for item in self.assessment["assessments"])
        )

    def test_seed_blocks_are_exact_and_do_not_parse_prior_artifacts(self) -> None:
        materializer._validate_seeds(self.assessment)
        generator_source = (SOURCE_ROOT / "generator.py").read_text(encoding="utf-8").lower()
        assessor_source = (SOURCE_ROOT / "assessor.py").read_text(encoding="utf-8").lower()
        for token in ("inputjac002", "exp-jac-001", "exp-jac-002", "locked-input-manifest"):
            self.assertNotIn(token, generator_source)
            self.assertNotIn(token, assessor_source)

    def test_baseline_contract_covers_exact_product_tree(self) -> None:
        contract = json.loads((EXPERIMENT_ROOT / "baseline-contract.json").read_text(encoding="utf-8"))
        declared = contract["product_sources"]
        actual = {
            path.relative_to(REPOSITORY_ROOT).as_posix()
            for path in (REPOSITORY_ROOT / "julia" / "GeoTargetCore" / "src").glob("*.jl")
        }
        self.assertEqual(set(declared), actual)
        for relative, expected in declared.items():
            digest = hashlib.sha256((REPOSITORY_ROOT / relative).read_bytes()).hexdigest()
            self.assertEqual(digest, expected)

    def test_materializer_refuses_before_lock_and_baseline_snapshot(self) -> None:
        lock_path = EXPERIMENT_ROOT / "preimplementation-lock.json"
        snapshot_path = EXPERIMENT_ROOT / "public-baseline-snapshot.json"
        if lock_path.exists():
            self.assertTrue(snapshot_path.exists())
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            self.assertEqual(lock["status"], "frozen-before-one-shot-materialization")
        else:
            self.assertFalse(snapshot_path.exists())


if __name__ == "__main__":
    unittest.main()
