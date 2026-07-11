"""Static C0 boundary tests for EXP-LOCAL-003.

These tests inspect preregistered contracts only. They do not generate formal
inputs, execute a candidate, or open an outcome.
"""

from __future__ import annotations

import hashlib
import gzip
import json
import math
import os
import struct
import sys
import time
import unittest
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock
from types import SimpleNamespace

from jsonschema import Draft202012Validator


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = EXPERIMENT_ROOT.parents[2]
PYTHON_SOURCE = REPOSITORY_ROOT / "python" / "src"
if str(PYTHON_SOURCE) not in sys.path:
    sys.path.insert(0, str(PYTHON_SOURCE))
SOURCE_ROOT = EXPERIMENT_ROOT / "source"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from geotarget.canonical import canonical_bytes  # noqa: E402
import materialize_development as materializer  # noqa: E402
import launch_c1  # noqa: E402


CARD_PATH = EXPERIMENT_ROOT.parent / "EXP-LOCAL-003.json"
VISIBILITY_PATH = EXPERIMENT_ROOT / "visibility-contract.json"
NUMERIC_PATH = EXPERIMENT_ROOT / "numeric-json-domain.json"
LOCAL_OPTIONS_PATH = EXPERIMENT_ROOT / "local-options-contract.json"
C2_EQUIVALENCE_SCHEMA_PATH = SOURCE_ROOT / "c2-default-equivalence.schema.json"
CARD_SHA256 = "0caae294a032f6d920c718219836e60e57f20c76fe5d790a615e554a95c6ee3c"


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"{path} is not an object")
    return value


def _bits(value: float) -> str:
    return f"0x{struct.unpack('>Q', struct.pack('>d', value))[0]:016x}"


def _from_bits(value: str) -> float:
    return struct.unpack(">d", int(value, 16).to_bytes(8, "big"))[0]


def _correctly_rounded_fma(a: float, b: float, c: float) -> float:
    exact = Fraction.from_float(a) * Fraction.from_float(b) + Fraction.from_float(c)
    return float(exact)


class MaterializationContractTests(unittest.TestCase):
    def test_contract_binds_frozen_card(self) -> None:
        self.assertEqual(
            hashlib.sha256(CARD_PATH.read_bytes()).hexdigest(), CARD_SHA256
        )
        contract = _load(VISIBILITY_PATH)
        self.assertEqual(contract["card_sha256"], CARD_SHA256)
        self.assertFalse(contract["production_connection"])

    def test_c2_outcome_blind_additions_and_equivalence_schema_are_frozen(self) -> None:
        expected = (
            "julia/GeoTargetCore/src/local_model_transform.jl",
            "research/experiments/EXP-LOCAL-003/source/candidate_runner.jl",
            "julia/GeoTargetCore/test/test_local_model_transform.jl",
            "research/experiments/EXP-LOCAL-003/C2_L0_DEFAULT_EQUIVALENCE.json",
            "research/experiments/EXP-LOCAL-003/candidate-execution-lock.json",
            "research/experiments/EXP-LOCAL-003/locked-candidate-execution-lock.json",
            "research/experiments/EXP-LOCAL-003/development-candidate-inputs",
        )
        self.assertEqual(materializer.FORBIDDEN_MECHANISM_PATHS, expected)
        schema = _load(C2_EQUIVALENCE_SCHEMA_PATH)
        Draft202012Validator.check_schema(schema)

    def test_visibility_preserves_dsl_but_denies_identity_and_gold(self) -> None:
        contract = _load(VISIBILITY_PATH)
        candidate = contract["trees"]["candidate"]  # type: ignore[index]
        forbidden = " ".join(candidate["forbidden_case_material"]).lower()  # type: ignore[index]
        self.assertIn("family", forbidden)
        self.assertIn("latent-group", forbidden)
        self.assertIn("representation", forbidden)
        self.assertIn("gold", forbidden)
        self.assertIn("calibration_key", forbidden)
        self.assertIn(
            "problemspecv1.target", candidate["semantic_target_exception"].lower()
        )  # type: ignore[index]

        route = contract["mandatory_dsl_path"]
        self.assertEqual(route[0], "Python SDK ProblemBuilder")  # type: ignore[index]
        self.assertIn("compile_problem", route)
        self.assertIn("evaluate(compiled, C0)", route)
        self.assertIn("evaluate_canonical and validate_candidate", route)
        self.assertIn("DirectAnalyticProblem", contract["forbidden_shortcuts"])

    def test_numeric_tokens_use_semantic_domain_not_parser_subclass(self) -> None:
        fixture = _load(NUMERIC_PATH)
        payload = json.loads(fixture["canonical_payload_text"])  # type: ignore[arg-type]
        self.assertEqual(
            canonical_bytes(payload).decode("utf-8"), fixture["canonical_payload_text"]
        )
        cases = fixture["cases"]
        for case in cases:  # type: ignore[assignment]
            value = case["json_value"]
            self.assertIsInstance(value, (int, float))
            self.assertNotIsInstance(value, bool)
            if case["semantic_domain"] == "finite_binary64_real":
                normalized = float(value)
                self.assertTrue(math.isfinite(normalized))
                self.assertEqual(_bits(normalized), case["binary64_bits"])

    def test_fraction_fma_matches_frozen_binary64_bits(self) -> None:
        fixture = _load(NUMERIC_PATH)
        for case in fixture["fma_fixture"]:  # type: ignore[index]
            result = _correctly_rounded_fma(
                _from_bits(case["a_bits"]),
                _from_bits(case["b_bits"]),
                _from_bits(case["c_bits"]),
            )
            self.assertEqual(_bits(result), case["result_bits"])

    def test_extended_reals_are_strings(self) -> None:
        values = _load(NUMERIC_PATH)["extended_real_tokens"]
        self.assertEqual(values["positive_infinity"], "+Inf")  # type: ignore[index]
        self.assertEqual(values["negative_infinity"], "-Inf")  # type: ignore[index]
        with self.assertRaises(ValueError):
            json.dumps(float("inf"), allow_nan=False)

    def test_deterministic_gzip_has_platform_independent_header(self) -> None:
        payload = b"EXP-LOCAL-003 deterministic gzip fixture\n"
        compressed = materializer._deterministic_gzip_bytes(payload)
        self.assertEqual(compressed[:10], b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x02\xff")
        self.assertEqual(gzip.decompress(compressed), payload)
        self.assertEqual(
            hashlib.sha256(compressed).hexdigest(),
            "dc552c32bce72c83823b107364fdd21edaa4fff2f847b0d2eb804f8ca8bfaeae",
        )

    def test_fixed_python_environment_ignores_prefix_under_no_site(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            scripts = root / "python" / ".venv" / "Scripts"
            scripts.mkdir(parents=True)
            executable = scripts / "python.exe"
            executable.write_bytes(b"fixed-venv-python")
            with (
                mock.patch.object(materializer, "REPOSITORY_ROOT", root),
                mock.patch.object(materializer.sys, "executable", str(executable)),
                mock.patch.object(
                    materializer.sys, "prefix", r"C:\unrelated-base-runtime"
                ),
            ):
                observed = materializer._fixed_python_environment_root()
            self.assertEqual(observed, (root / "python" / ".venv").resolve())

    def test_c1_launcher_rejects_optimization_and_loaded_site_preclaim(self) -> None:
        flags = SimpleNamespace(
            isolated=1,
            ignore_environment=1,
            no_user_site=1,
            safe_path=True,
            dont_write_bytecode=1,
            no_site=1,
            optimize=1,
        )
        with (
            mock.patch.object(launch_c1.sys, "flags", flags),
            self.assertRaisesRegex(RuntimeError, "-I -B -S"),
        ):
            launch_c1._verify_launcher()

    def test_local_options_contract_binds_source_and_exact_constructor(self) -> None:
        contract = _load(LOCAL_OPTIONS_PATH)
        self.assertEqual(
            hashlib.sha256(
                (REPOSITORY_ROOT / contract["source_path"]).read_bytes()  # type: ignore[operator]
            ).hexdigest(),
            contract["source_sha256"],
        )
        constructor = contract["constructor"]
        self.assertEqual(
            hashlib.sha256(canonical_bytes(constructor)).hexdigest(),
            contract["constructor_sha256"],
        )
        self.assertEqual(constructor["max_iterations"], 250)  # type: ignore[index]
        self.assertEqual(constructor["max_evaluations"], 2000)  # type: ignore[index]

    def test_attempt_claim_and_failure_are_durable_and_refuse_retry(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            attempt = root / "attempt.json"
            failure = root / "failure.json"
            with (
                mock.patch.object(materializer, "ATTEMPT_PATH", attempt),
                mock.patch.object(materializer, "FAILURE_PATH", failure),
            ):
                materializer._claim_c1_attempt()
                with self.assertRaises(FileExistsError):
                    materializer._claim_c1_attempt()
                materializer._record_terminal_failure(
                    RuntimeError("injected mid-stage failure"),
                    lock_commit="a" * 40,
                    lock_sha256="b" * 64,
                )
                self.assertTrue(attempt.is_file())
                self.assertTrue(failure.is_file())
                self.assertFalse(json.loads(attempt.read_text())["rerun_permitted"])
                self.assertFalse(json.loads(failure.read_text())["rerun_permitted"])
        self.assertEqual(
            launch_c1.CLAIM_BYTES,
            canonical_bytes(
                {
                    "schema_version": "exp-local-003-c1-attempt-claim/v1",
                    "card_sha256": CARD_SHA256,
                    "attempt_ordinal": 0,
                    "rerun_permitted": False,
                    "failure_is_terminal": True,
                    "authority_validation_occurs_after_claim": True,
                }
            ),
        )

    def test_direct_materializer_cannot_consume_c1_claim(self) -> None:
        with mock.patch.object(materializer, "_claim_c1_attempt") as claim:
            with self.assertRaisesRegex(materializer.MaterializationError, "launch_c1"):
                materializer.materialize()
        claim.assert_not_called()

    def test_stage_helper_passes_exact_bootstrap_authority(self) -> None:
        bootstrap = b"GTLOCAL3BOOT1-test"
        assessor = SimpleNamespace(
            parse_bootstrap_index_bytes=mock.Mock(return_value=None)
        )
        with (
            mock.patch.object(materializer, "validate_documents"),
            mock.patch.object(
                materializer,
                "_capture_calibration_truth",
                return_value=({"capture": 1}, 17),
            ),
            mock.patch.object(
                materializer, "_build_formal_assessor_truth", return_value={"truth": 1}
            ) as build_truth,
            mock.patch.object(materializer, "_publish_documents") as publish,
        ):
            materializer.materialize_stage_documents(
                documents={
                    "candidate": {},
                    "assessor": {},
                    "generator_private": {},
                },
                stage="development",
                assessor_module=assessor,  # type: ignore[arg-type]
                bootstrap_bytes=bootstrap,
                candidate_publication=Path("candidate"),
                vault_publication=Path("vault"),
                private_vault_publication=Path("private-vault"),
                candidate_final_path=Path("final"),
                group_index_map={0: 0, 1: 1},
                locked_decision=None,
                master_secret=b"s" * 32,
                timing_started=(0, 0, 0),
                lock_sha256="a" * 64,
                lock_commit="b" * 40,
            )
        self.assertIs(build_truth.call_args.args[2], bootstrap)
        self.assertEqual(publish.call_args.args[4], bootstrap)

    def test_formal_julia_environment_is_closed_and_platform_separated(self) -> None:
        with TemporaryDirectory() as temporary:
            depot = Path(temporary) / "depot"
            with (
                mock.patch.object(materializer, "FORMAL_JULIA_DEPOT_PATH", depot),
                mock.patch.dict(
                    os.environ,
                    {
                        "JULIA_LOAD_PATH": "injected",
                        "JULIA_PROJECT": "injected",
                        "JULIA_CPU_TARGET": "injected",
                    },
                ),
            ):
                environment = materializer._formal_julia_environment(
                    Path(temporary) / "runtime" / "bin" / "julia.exe"
                )
        self.assertEqual(
            environment["JULIA_LOAD_PATH"].split(os.pathsep), ["@", "@stdlib"]
        )
        self.assertEqual(environment["JULIA_CPU_TARGET"], "generic")
        self.assertNotIn("injected", environment.values())

    def test_locked_selection_exposes_no_development_or_assessor_hash(self) -> None:
        decision = {
            "schema_version": "geotarget.exp-local-003.development-decision-record/v1",
            "experiment_id": "EXP-LOCAL-003",
            "card_sha256": CARD_SHA256,
            "development_gate_passed": True,
            "selected_variant": "LR-MODEL",
            "selected_path": "recall",
            "safety16_disagreement_count": 0,
            "candidate_input_sha256": "1" * 64,
            "development_assessment_sha256": "2" * 64,
            "decision_commit": "3" * 40,
        }
        documents = {
            "candidate": {"schema_version": "locked-test", "cases": []},
            "assessor": {"schema_version": "truth-test"},
            "generator_private": {"schema_version": "private-test"},
            "generator_assessor_projection": {"schema_version": "projection-test"},
            "calibration_capture": {"schema_version": "capture-test"},
        }
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = root / "candidate"
            vault = root / "vault"
            private_vault = root / "private-vault"
            materializer._publish_documents(
                candidate,
                vault,
                private_vault,
                documents,
                b"bootstrap",
                stage="locked",
                locked_decision=decision,
                candidate_final_path=root / "final",
                timing_started=(
                    time.process_time_ns(),
                    time.perf_counter_ns(),
                    time.time_ns(),
                ),
                lock_sha256="4" * 64,
                lock_commit="5" * 40,
                child_cpu_nanoseconds=17,
            )
            selection = _load(candidate / "locked-selection.json")
            self.assertEqual(selection["selected_variant"], "LR-MODEL")
            self.assertEqual(
                set(selection),
                {
                    "schema_version",
                    "experiment_id",
                    "card_sha256",
                    "stage",
                    "selected_variant",
                    "candidate_input_sha256",
                },
            )
            serialized = canonical_bytes(selection).lower()
            self.assertNotIn(b"assessment", serialized)
            self.assertNotIn(b"decision", serialized)
            self.assertNotIn(b"assessor", serialized)
            manifest = _load(vault / "manifest.json")
            authority = manifest["locked_authority"]
            self.assertEqual(authority["development_assessment_sha256"], "2" * 64)  # type: ignore[index]
            self.assertFalse((vault / "generator-private").exists())
            self.assertTrue(
                (private_vault / "generator-private" / "manifest.json").is_file()
            )
            self.assertFalse((private_vault / "assessor").exists())


if __name__ == "__main__":
    unittest.main()
