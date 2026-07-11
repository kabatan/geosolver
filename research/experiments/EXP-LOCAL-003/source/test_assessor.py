from __future__ import annotations

import copy
import hashlib
import json
import math
import struct
import sys
import unittest
from pathlib import Path
from typing import Any

import jsonschema

SOURCE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = SOURCE_ROOT.parents[3]
sys.path.insert(0, str(REPOSITORY_ROOT / "python" / "src"))
sys.path.insert(0, str(SOURCE_ROOT))

import assessor  # noqa: E402
import bootstrap_indices  # noqa: E402


DEVELOPMENT_SHA256 = "e8fc7c8491a11a89b5c1f27cfb68989d0f13fe45e4da5bcba7e8aeb69afb2173"
LOCKED_SHA256 = "401a3991806cfb32f1a4678dbdb7c777e099c7397b89b2ba499c5abcefe1b594"
LOCAL_OPTIONS_SHA256 = (
    "3c3cd79f568d7ce6abd188d74269d9bf5e4e8b1daab7f1df5c5ad3f129c1df58"
)
_BOOTSTRAP_CACHE: dict[str, bytes] = {}


def _bootstrap(stage: str) -> bytes:
    if stage not in _BOOTSTRAP_CACHE:
        _BOOTSTRAP_CACHE[stage] = bootstrap_indices.bootstrap_index_bytes(stage)
    return _BOOTSTRAP_CACHE[stage]


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("ascii")).hexdigest()


def _calibration(residual_count: int = 1) -> dict[str, Any]:
    scale = [(1.0).hex()] * residual_count
    return {
        "observation_evaluation_costs": [2] * 64,
        "valid_vector_count": 64,
        "nearest_rank_hex": [(1.0).hex()] * residual_count,
        "model_scale_hex": scale,
        "model_scale_sha256": assessor.model_scale_sha256(scale),
        "joint_fallback_reason": None,
        "clamp_reasons": [
            {"lower": False, "upper": False} for _ in range(residual_count)
        ],
        "nonfinite_q_count": 0,
        "nonfinite_q_misclassification_count": 0,
    }


def _attempt(start: int, successes: int) -> dict[str, Any]:
    success = start < successes
    return {
        "start_index": start,
        "iterations": 3,
        "accepted": success,
        "local_observation_evaluation_costs": [2, 2, 2],
        "canonical_replay": {
            "valid": success,
            "configuration_hex": [(0.0).hex()] if success else None,
            "target_hex": (0.0).hex() if success else None,
            "branch_label": "interior" if success else None,
            "evaluation_cost": 2,
        },
    }


def _variant(variant: str, successes: int) -> dict[str, Any]:
    return {
        "variant_id": variant,
        "local_options_sha256": LOCAL_OPTIONS_SHA256,
        "calibration": _calibration()
        if variant in assessor.MODEL_SCALE_VARIANTS
        else None,
        "attempts": [_attempt(start, successes) for start in range(32)],
        "semantic_or_wire_drift_count": 0,
        "identity_access_count": 0,
    }


def _documents(blob: bytes) -> tuple[dict[str, Any], dict[str, Any]]:
    input_sha = _digest("candidate input")
    truth_cases: list[dict[str, Any]] = []
    candidate_cases: list[dict[str, Any]] = []
    for family_ordinal, family in enumerate(bootstrap_indices.FAMILY_IDS):
        for group in range(2):
            group_key = _digest(f"group/{family_ordinal}/{group}")
            for representation in (
                *assessor.PRIMARY_REPRESENTATIONS,
                assessor.SAFETY_REPRESENTATION,
            ):
                opaque = _digest(f"case/{family_ordinal}/{group}/{representation}")
                problem_sha = _digest(f"problem/{opaque}")
                calibration_sha = _digest(f"calibration/{opaque}")
                starts_sha = _digest(f"starts/{opaque}")
                truth_cases.append(
                    {
                        "opaque_case_key": opaque,
                        "family_id": family,
                        "family_ordinal": family_ordinal,
                        "latent_group_index": group,
                        "latent_group_key": group_key,
                        "representation": representation,
                        "expected_invariant": representation
                        in assessor.PRIMARY_REPRESENTATIONS,
                        "scale_from_base": [0]
                        if representation in assessor.PRIMARY_REPRESENTATIONS
                        else None,
                        "problem_sha256": problem_sha,
                        "calibration_points_sha256": calibration_sha,
                        "starts_sha256": starts_sha,
                        "variable_count": 1,
                        "residual_count": 1,
                        "logical_evaluation_cost": 2,
                        "gold_solutions": [
                            {
                                "configuration_hex": [(0.0).hex()],
                                "target_hex": (0.0).hex(),
                                "configuration_abs_tolerance_hex": (0.0).hex(),
                                "target_abs_tolerance_hex": (0.0).hex(),
                                "branch_label": "interior",
                            }
                        ],
                        "expected_calibration": _calibration(),
                    }
                )
                candidate_cases.append(
                    {
                        "opaque_case_key": opaque,
                        "problem_sha256": problem_sha,
                        "calibration_points_sha256": calibration_sha,
                        "starts_sha256": starts_sha,
                        "variable_count": 1,
                        "residual_count": 1,
                        "logical_evaluation_cost": 2,
                        "variants": [
                            _variant(assessor.CONTROL, 16),
                            _variant("LX-BOUNDS", 20),
                            _variant("LR-MODEL", 20),
                            _variant("LXR-BOUNDS-MODEL", 20),
                        ],
                    }
                )
    truth = {
        "schema_version": assessor.ASSESSOR_TRUTH_SCHEMA,
        "stage": "development",
        "candidate_input_sha256": input_sha,
        "bootstrap_sha256": hashlib.sha256(blob).hexdigest(),
        "local_options_sha256": LOCAL_OPTIONS_SHA256,
        "locked_decision": None,
        "cases": truth_cases,
    }
    raw = {
        "schema_version": assessor.CANDIDATE_OUTPUT_SCHEMA,
        "stage": "development",
        "candidate_input_sha256": input_sha,
        "candidate_process": {
            "runner_source_path": "research/harness/candidate_runner.jl",
            "runner_source_sha256": _digest("runner"),
            "observation_complete": True,
            "source_manifest_sha256": "",
            "loaded_sources": [
                {
                    "path": "julia/GeoTargetCore/src/LocalSolve.jl",
                    "sha256": _digest("LocalSolve source"),
                },
                {
                    "path": "research/harness/candidate_runner.jl",
                    "sha256": _digest("runner"),
                },
            ],
            "opened_artifacts": [
                {
                    "path": "candidate/development-input.json",
                    "sha256": _digest("candidate artifact"),
                }
            ],
        },
        "cases": candidate_cases,
        "report_only_times": {
            "process_cpu_seconds": 1.0,
            "end_to_end_cpu_seconds": 2.0,
            "formal_wall_seconds": None,
            "host_exclusion_passed": False,
        },
    }
    raw["candidate_process"]["source_manifest_sha256"] = (
        assessor._source_manifest_sha256(raw["candidate_process"]["loaded_sources"])
    )
    return raw, truth


def _execution_lock(raw: dict[str, Any], truth: dict[str, Any]) -> dict[str, Any]:
    process = raw["candidate_process"]
    return {
        "schema_version": assessor.EXECUTION_LOCK_SCHEMA,
        "card_sha256": assessor.CARD_SHA256,
        "stage": truth["stage"],
        "candidate_input_sha256": truth["candidate_input_sha256"],
        "local_options_sha256": truth["local_options_sha256"],
        "stage_input_anchor_sha256": _digest("stage input vault anchor"),
        "stage_input_anchor_commit": "c" * 40,
        "runner_source_path": process["runner_source_path"],
        "runner_source_sha256": process["runner_source_sha256"],
        "source_manifest_sha256": process["source_manifest_sha256"],
        "allowed_sources": copy.deepcopy(process["loaded_sources"]),
        "allowed_candidate_artifacts": copy.deepcopy(process["opened_artifacts"]),
    }


def _locked_documents(blob: bytes) -> tuple[dict[str, Any], dict[str, Any]]:
    raw, truth = _documents(_bootstrap("development"))
    truth["stage"] = "locked"
    raw["stage"] = "locked"
    locked_input_sha = _digest("locked candidate input")
    truth["candidate_input_sha256"] = locked_input_sha
    raw["candidate_input_sha256"] = locked_input_sha
    truth["bootstrap_sha256"] = hashlib.sha256(blob).hexdigest()
    truth["locked_decision"] = {
        "candidate_id": "LX-BOUNDS",
        "development_path": "recall",
        "development_assessment_sha256": _digest("development assessment"),
        "development_decision_record_sha256": _digest("development decision"),
    }
    raw_by_key = {case["opaque_case_key"]: case for case in raw["cases"]}
    primary_truth = [
        case
        for case in truth["cases"]
        if case["representation"] in assessor.PRIMARY_REPRESENTATIONS
    ]
    primary_raw = [
        copy.deepcopy(raw_by_key[case["opaque_case_key"]]) for case in primary_truth
    ]
    cloned_truth: list[dict[str, Any]] = []
    cloned_raw: list[dict[str, Any]] = []
    for new_group, source_group in ((2, 0), (3, 1)):
        for source_truth in primary_truth:
            if source_truth["latent_group_index"] != source_group:
                continue
            clone_truth = copy.deepcopy(source_truth)
            old_key = clone_truth["opaque_case_key"]
            clone_truth["latent_group_index"] = new_group
            clone_truth["latent_group_key"] = _digest(
                f"locked/group/{clone_truth['family_ordinal']}/{new_group}"
            )
            new_key = _digest(
                "locked/case/"
                f"{clone_truth['family_ordinal']}/{new_group}/"
                f"{clone_truth['representation']}"
            )
            clone_truth["opaque_case_key"] = new_key
            clone_raw = copy.deepcopy(raw_by_key[old_key])
            clone_raw["opaque_case_key"] = new_key
            cloned_truth.append(clone_truth)
            cloned_raw.append(clone_raw)
    truth["cases"] = primary_truth + cloned_truth
    raw["cases"] = primary_raw + cloned_raw
    for raw_case in raw["cases"]:
        raw_case["variants"] = [
            variant
            for variant in raw_case["variants"]
            if variant["variant_id"] in {assessor.CONTROL, "LX-BOUNDS"}
        ]
    raw["candidate_process"]["opened_artifacts"][0]["path"] = (
        "candidate/locked-input.json"
    )
    return raw, truth


def _case(
    raw: dict[str, Any],
    truth: dict[str, Any],
    family: int,
    group: int,
    representation: str,
):
    truth_case = next(
        item
        for item in truth["cases"]
        if item["family_ordinal"] == family
        and item["latent_group_index"] == group
        and item["representation"] == representation
    )
    raw_case = next(
        item
        for item in raw["cases"]
        if item["opaque_case_key"] == truth_case["opaque_case_key"]
    )
    return raw_case, truth_case


def _result(raw_case: dict[str, Any], variant: str) -> dict[str, Any]:
    return next(item for item in raw_case["variants"] if item["variant_id"] == variant)


class BootstrapContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.development = _bootstrap("development")
        cls.locked = _bootstrap("locked")

    def test_exact_headers_lengths_payload_prefixes_and_hashes(self) -> None:
        expected_development_header = b"GTLOCAL3BOOT1\0D" + struct.pack(
            ">III", 100_000, 8, 2
        )
        expected_locked_header = b"GTLOCAL3BOOT1\0L" + struct.pack(
            ">III", 100_000, 8, 4
        )
        self.assertEqual(self.development[:27], expected_development_header)
        self.assertEqual(self.locked[:27], expected_locked_header)
        self.assertEqual(len(self.development), 27 + 100_000 * 8 * 2)
        self.assertEqual(len(self.locked), 27 + 100_000 * 8 * 4)
        self.assertEqual(
            self.development[27:59].hex(),
            "0000010101000000000000000001000001010100000101010100010100000100",
        )
        self.assertEqual(
            self.locked[27:59].hex(),
            "0202030100010002030102030301020000020301030303000301020301000203",
        )
        self.assertEqual(
            hashlib.sha256(self.development).hexdigest(), DEVELOPMENT_SHA256
        )
        self.assertEqual(hashlib.sha256(self.locked).hexdigest(), LOCKED_SHA256)
        self.assertEqual(
            bootstrap_indices.bootstrap_sha256("development"), DEVELOPMENT_SHA256
        )
        self.assertEqual(bootstrap_indices.bootstrap_sha256("locked"), LOCKED_SHA256)

    def test_parser_rejects_header_payload_and_digest_drift(self) -> None:
        table = bootstrap_indices.parse_bootstrap_index_bytes(
            self.development,
            expected_stage="development",
            expected_sha256=DEVELOPMENT_SHA256,
        )
        self.assertEqual(table.groups_per_family, 2)
        self.assertEqual(table.index(0, 0, 0), 0)
        self.assertEqual(table.index(0, 0, 1), 0)
        corrupt_header = bytearray(self.development)
        corrupt_header[14] = ord("L")
        with self.assertRaises(bootstrap_indices.BootstrapFormatError):
            bootstrap_indices.parse_bootstrap_index_bytes(
                bytes(corrupt_header), expected_stage="development"
            )
        corrupt_payload = bytearray(self.development)
        corrupt_payload[27] = 2
        with self.assertRaises(bootstrap_indices.BootstrapFormatError):
            bootstrap_indices.parse_bootstrap_index_bytes(
                bytes(corrupt_payload), expected_stage="development"
            )
        with self.assertRaises(bootstrap_indices.BootstrapFormatError):
            bootstrap_indices.parse_bootstrap_index_bytes(
                self.development,
                expected_stage="development",
                expected_sha256="0" * 64,
            )


class NumericContractTests(unittest.TestCase):
    def test_extended_real_rules_and_strict_json(self) -> None:
        self.assertEqual(assessor.ert_reduction(math.inf, 4.0), 1.0)
        self.assertEqual(assessor.ert_reduction(math.inf, math.inf), 0.0)
        self.assertEqual(assessor.ert_reduction(4.0, math.inf), -math.inf)
        self.assertEqual(assessor.ert_reduction(4.0, 3.0), 0.25)
        self.assertEqual(assessor.ert_ratio(math.inf, 4.0), 0.0)
        self.assertEqual(assessor.ert_ratio(math.inf, math.inf), math.inf)
        self.assertEqual(assessor.ert_ratio(4.0, math.inf), math.inf)
        encoded = assessor.strict_json_dumps({"plus": math.inf, "minus": -math.inf})
        self.assertEqual(encoded, '{"minus":"-Inf","plus":"+Inf"}')
        self.assertEqual(assessor.decode_extended_real("+Inf"), math.inf)
        self.assertEqual(assessor.decode_extended_real("-Inf"), -math.inf)
        for token in ("NaN", "Infinity", "-Infinity"):
            with self.assertRaises(assessor.InterfaceError):
                assessor.strict_json_loads('{"x":' + token + "}")
        with self.assertRaisesRegex(assessor.InterfaceError, "duplicate"):
            assessor.strict_json_loads('{"x":1,"x":1}')
        with self.assertRaises(assessor.InterfaceError):
            assessor.strict_json_dumps({"bad": math.nan})

    def test_nearest_rank_items_are_exact_and_thresholds_are_inclusive(self) -> None:
        values = [float(value) for value in range(100_000, 0, -1)]
        self.assertEqual(assessor.nearest_rank_bounds(values), (5_000.0, 95_000.0))
        rows = []
        for prefix in assessor.PREFIXES:
            rows.append(
                {
                    "prefix": prefix,
                    "recall_delta": 0.05,
                    "recall_lower": -0.02 if prefix != 32 else 0.0,
                    "ert_ratio": 1.10,
                    "ert_reduction_lower": 0.20,
                    "families": [
                        {
                            "recall_delta": 0.01 if index < 3 else -0.02,
                            "ert_reduction": 0.01,
                        }
                        for index in range(8)
                    ],
                }
            )
        paths = assessor._evaluate_paths(rows, hard_safety_passed=True)
        self.assertTrue(paths["recall"]["passed"])
        self.assertTrue(paths["efficiency"]["passed"])

    def test_path_specific_positive_family_strictness(self) -> None:
        row = {
            "families": [
                {"recall_delta": 0.0, "ert_reduction": 0.2},
                {"recall_delta": -0.02, "ert_reduction": 0.0},
                {"recall_delta": -0.02, "ert_reduction": 0.1},
            ]
        }
        self.assertEqual(assessor._positive_family_count(row, "recall"), 0)
        self.assertEqual(assessor._positive_family_count(row, "efficiency"), 2)


class TopologyAndFormulaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.blob = _bootstrap("development")
        cls.raw, cls.truth = _documents(cls.blob)
        cls.execution_lock = _execution_lock(cls.raw, cls.truth)
        cls.full_outcome = assessor.assess(
            cls.raw, cls.truth, cls.blob, cls.execution_lock
        )

    @staticmethod
    def _assessed(raw: dict[str, Any], truth_document: dict[str, Any]):
        candidate, truth, _ = assessor.validate_topology(
            raw, truth_document, _execution_lock(raw, truth_document)
        )
        raw_results = assessor._variant_results_by_case(candidate)
        truth_by_key = {case["opaque_case_key"]: case for case in truth["cases"]}
        cases_by_key = {case["opaque_case_key"]: case for case in candidate["cases"]}
        assessed = {}
        for key, case in cases_by_key.items():
            for variant in assessor.ALL_VARIANTS:
                assessed[(key, variant)] = assessor._assess_case_variant(
                    case, truth_by_key[key], raw_results[(key, variant)]
                )
        return truth, raw_results, assessed

    def test_closed_projections_join_only_by_opaque_key(self) -> None:
        candidate, truth, _ = assessor.validate_topology(
            self.raw, self.truth, self.execution_lock
        )
        self.assertEqual(len(candidate["cases"]), 64)
        self.assertEqual(len(truth["cases"]), 64)
        candidate_text = json.dumps(candidate, sort_keys=True)
        for family in bootstrap_indices.FAMILY_IDS:
            self.assertNotIn(family, candidate_text)
        self.assertNotIn("latent_group_index", candidate_text)
        self.assertNotIn("representation", candidate_text)
        self.assertNotIn("gold_solutions", candidate_text)

    def test_leaks_bad_topology_and_assessor_import_are_rejected(self) -> None:
        leaked = copy.deepcopy(self.raw)
        leaked["candidate_process"]["loaded_sources"] = [
            {"path": "research/assessor/runner.py", "sha256": _digest("leak")}
        ]
        with self.assertRaisesRegex(assessor.InterfaceError, "identity-bearing"):
            assessor.validate_topology(leaked, self.truth, self.execution_lock)

        leaked_filename = copy.deepcopy(self.raw)
        leaked_filename["candidate_process"]["loaded_sources"] = [
            {
                "path": "research/experiments/EXP-LOCAL-003/source/assessor.py",
                "sha256": _digest("leak filename"),
            }
        ]
        with self.assertRaisesRegex(assessor.InterfaceError, "identity-bearing"):
            assessor.validate_topology(leaked_filename, self.truth, self.execution_lock)

        leaked_compound = copy.deepcopy(self.raw)
        leaked_compound["candidate_process"]["loaded_sources"] = [
            {
                "path": "research/private/gold_truth_helpers.py",
                "sha256": _digest("leak compound"),
            }
        ]
        with self.assertRaisesRegex(assessor.InterfaceError, "identity-bearing"):
            assessor.validate_topology(leaked_compound, self.truth, self.execution_lock)
        opened_gold = copy.deepcopy(self.raw)
        opened_gold["candidate_process"]["opened_artifacts"] = [
            {"path": "gold/development.json", "sha256": _digest("gold")}
        ]
        with self.assertRaisesRegex(assessor.InterfaceError, "non-candidate"):
            assessor.validate_topology(opened_gold, self.truth, self.execution_lock)
        bad_truth = copy.deepcopy(self.truth)
        bad_truth["cases"][0]["family_ordinal"] = 7
        with self.assertRaises(assessor.InterfaceError):
            assessor.validate_topology(self.raw, bad_truth, self.execution_lock)
        missing = copy.deepcopy(self.raw)
        missing["cases"].pop()
        with self.assertRaisesRegex(assessor.InterfaceError, "opaque join"):
            assessor.validate_topology(missing, self.truth, self.execution_lock)

    def test_json_schemas_and_semantic_validators_reject_shape_drift(self) -> None:
        candidate_schema = json.loads(
            (SOURCE_ROOT / "candidate-output.schema.json").read_text(encoding="utf-8")
        )
        truth_schema = json.loads(
            (SOURCE_ROOT / "assessor-truth.schema.json").read_text(encoding="utf-8")
        )
        execution_schema = json.loads(
            (SOURCE_ROOT / "candidate-execution-lock.schema.json").read_text(
                encoding="utf-8"
            )
        )
        assessment_schema = json.loads(
            (SOURCE_ROOT / "assessment.schema.json").read_text(encoding="utf-8")
        )
        decision_schema = json.loads(
            (SOURCE_ROOT / "development-decision-record.schema.json").read_text(
                encoding="utf-8"
            )
        )
        final_schema = json.loads(
            (SOURCE_ROOT / "final-connection.schema.json").read_text(encoding="utf-8")
        )
        jsonschema.Draft202012Validator.check_schema(candidate_schema)
        jsonschema.Draft202012Validator.check_schema(truth_schema)
        jsonschema.Draft202012Validator.check_schema(execution_schema)
        jsonschema.Draft202012Validator.check_schema(assessment_schema)
        jsonschema.Draft202012Validator.check_schema(decision_schema)
        jsonschema.Draft202012Validator.check_schema(final_schema)
        jsonschema.validate(self.raw, candidate_schema)
        jsonschema.validate(self.truth, truth_schema)
        jsonschema.validate(self.execution_lock, execution_schema)
        jsonschema.validate(self.full_outcome, assessment_schema)
        assessor.validate_assessment_document(self.full_outcome)

        legacy_execution_lock = copy.deepcopy(self.execution_lock)
        legacy_execution_lock["c1_vault_anchor_sha256"] = legacy_execution_lock.pop(
            "stage_input_anchor_sha256"
        )
        legacy_execution_lock["c1_vault_anchor_commit"] = legacy_execution_lock.pop(
            "stage_input_anchor_commit"
        )
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(legacy_execution_lock, execution_schema)
        with self.assertRaisesRegex(assessor.InterfaceError, "keys differ"):
            assessor.validate_execution_lock(legacy_execution_lock, self.truth)

        extra = copy.deepcopy(self.raw)
        extra["cases"][0]["family_id"] = "SCALE-LADDER"
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(extra, candidate_schema)
        with self.assertRaises(assessor.InterfaceError):
            assessor.validate_topology(extra, self.truth, self.execution_lock)

        missing = copy.deepcopy(self.truth)
        del missing["cases"][0]["gold_solutions"]
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(missing, truth_schema)
        with self.assertRaises(assessor.InterfaceError):
            assessor.validate_topology(self.raw, missing, self.execution_lock)

    def test_variable_and_residual_counts_are_distinct_for_overdetermined_cases(
        self,
    ) -> None:
        raw = copy.deepcopy(self.raw)
        truth = copy.deepcopy(self.truth)
        selected = [
            case
            for case in truth["cases"]
            if case["family_ordinal"] == 3 and case["latent_group_index"] == 0
        ]
        selected_keys = {case["opaque_case_key"] for case in selected}
        for truth_case in selected:
            truth_case["variable_count"] = 3
            truth_case["residual_count"] = 6
            truth_case["scale_from_base"] = (
                list(range(6))
                if truth_case["representation"] in assessor.PRIMARY_REPRESENTATIONS
                else None
            )
            truth_case["gold_solutions"][0]["configuration_hex"] = [(0.0).hex()] * 3
            truth_case["expected_calibration"] = _calibration(6)
        for raw_case in raw["cases"]:
            if raw_case["opaque_case_key"] not in selected_keys:
                continue
            raw_case["variable_count"] = 3
            raw_case["residual_count"] = 6
            for variant in raw_case["variants"]:
                if variant["calibration"] is not None:
                    variant["calibration"] = _calibration(6)
                for attempt in variant["attempts"]:
                    if attempt["canonical_replay"]["configuration_hex"] is not None:
                        attempt["canonical_replay"]["configuration_hex"] = [
                            (0.0).hex()
                        ] * 3
        candidate, checked_truth, _ = assessor.validate_topology(
            raw, truth, _execution_lock(raw, truth)
        )
        raw_case = next(
            case
            for case in candidate["cases"]
            if case["opaque_case_key"] in selected_keys
        )
        truth_case = next(
            case
            for case in checked_truth["cases"]
            if case["opaque_case_key"] == raw_case["opaque_case_key"]
        )
        self.assertEqual(
            (raw_case["variable_count"], raw_case["residual_count"]), (3, 6)
        )
        self.assertEqual(len(truth_case["expected_calibration"]["model_scale_hex"]), 6)

    def test_gold_is_independent_of_solver_status_and_branch_is_checked(self) -> None:
        raw_case, truth_case = _case(self.raw, self.truth, 0, 0, "base")
        attempt = _result(raw_case, assessor.CONTROL)["attempts"][0]
        self.assertTrue(assessor._gold_valid(attempt, truth_case))
        wrong_branch = copy.deepcopy(attempt)
        wrong_branch["canonical_replay"]["branch_label"] = "boundary"
        self.assertFalse(assessor._gold_valid(wrong_branch, truth_case))
        rejected = copy.deepcopy(attempt)
        rejected["accepted"] = False
        self.assertFalse(assessor._gold_valid(rejected, truth_case))

    def test_exact_work_formula_uses_full_failure_budget_and_excludes_cpu(self) -> None:
        raw_case, truth_case = _case(self.raw, self.truth, 0, 0, "base")
        control = _result(raw_case, assessor.CONTROL)
        record = assessor._assess_case_variant(raw_case, truth_case, control)
        self.assertEqual(record.attempts[0].successful_work, 8)
        self.assertEqual(record.attempts[31].failure_work, 4_002)
        pool8 = assessor._prefix_pool(record, 8)
        self.assertEqual(pool8, assessor.Pool(work=64, successes=8))
        pool32 = assessor._prefix_pool(record, 32)
        self.assertEqual(pool32.work, 16 * 8 + 16 * 4_002)
        model = _result(raw_case, "LR-MODEL")
        model_record = assessor._assess_case_variant(raw_case, truth_case, model)
        self.assertEqual(model_record.calibration_work, 128)
        model_pool8 = assessor._prefix_pool(model_record, 8)
        self.assertEqual(model_pool8.work, 128 + 8 * 8)
        # Changing report-only CPU cannot enter the oracle-work formula.
        changed = copy.deepcopy(self.raw)
        changed["report_only_times"]["process_cpu_seconds"] = 1.0e9
        changed_case, _ = _case(changed, self.truth, 0, 0, "base")
        changed_record = assessor._assess_case_variant(
            changed_case, truth_case, _result(changed_case, assessor.CONTROL)
        )
        self.assertEqual(assessor._prefix_pool(changed_record, 32), pool32)

        overrun = copy.deepcopy(control)
        overrun["attempts"][0]["iterations"] = 251
        overrun_record = assessor._assess_case_variant(raw_case, truth_case, overrun)
        self.assertTrue(overrun_record.attempts[0].budget_overrun)
        overrun["attempts"][0]["iterations"] = 250
        overrun["attempts"][0]["local_observation_evaluation_costs"] = [0] * 2_001
        overrun_record = assessor._assess_case_variant(raw_case, truth_case, overrun)
        self.assertTrue(overrun_record.attempts[0].budget_overrun)

    def test_primary_disagreement_is_hard_but_safety16_is_report_only(self) -> None:
        primary = copy.deepcopy(self.raw)
        raw_case, _ = _case(primary, self.truth, 0, 0, "signed-permutation")
        _result(raw_case, "LX-BOUNDS")["attempts"][0] = _attempt(0, 0)
        truth, raw_results, assessed = self._assessed(primary, self.truth)
        safety = assessor._variant_safety(assessed, raw_results, truth, "LX-BOUNDS")
        self.assertEqual(safety["primary_representation_disagreement_count"], 1)

        orthogonal = copy.deepcopy(self.raw)
        raw_case, _ = _case(
            orthogonal, self.truth, 0, 0, assessor.SAFETY_REPRESENTATION
        )
        _result(raw_case, "LX-BOUNDS")["attempts"][0] = _attempt(0, 0)
        truth, raw_results, assessed = self._assessed(orthogonal, self.truth)
        control_safety = assessor._variant_safety(
            assessed, raw_results, truth, assessor.CONTROL
        )
        candidate_safety = assessor._variant_safety(
            assessed, raw_results, truth, "LX-BOUNDS"
        )
        self.assertEqual(
            candidate_safety["primary_representation_disagreement_count"],
            0,
        )
        self.assertEqual(
            candidate_safety["orthogonal_safety_disagreement_count"],
            1,
        )
        self.assertTrue(
            assessor._global_hard_safety_passes(
                {assessor.CONTROL: control_safety, "LX-BOUNDS": candidate_safety}
            )
        )
        self.assertNotIn(
            "orthogonal_safety_disagreement_count", assessor._HARD_SAFETY_COUNTS
        )

    def test_full_assessment_uses_latent_groups_and_lexicographic_champion(
        self,
    ) -> None:
        outcome = self.full_outcome
        self.assertEqual(outcome["bootstrap_sha256"], DEVELOPMENT_SHA256)
        self.assertEqual(outcome["bootstrap_replicates"], 100_000)
        self.assertTrue(outcome["stage_passed"])
        self.assertTrue(outcome["locked_materialization_eligible"])
        self.assertFalse(outcome["product_connection_allowed"])
        self.assertEqual(outcome["selected_path"], "recall")
        # Equal recall effects: LX wins because its charged ERT excludes no work
        # but, unlike LR/LXR, it executes no 64-observation calibration.
        self.assertEqual(outcome["selected_variant"], "LX-BOUNDS")
        for variant in assessor.CANDIDATES:
            row = outcome["candidates"][variant]
            self.assertEqual([item["prefix"] for item in row["prefixes"]], [8, 16, 32])
            self.assertEqual(row["prefixes"][-1]["recall_delta"], 0.125)
            self.assertEqual(row["prefixes"][-1]["recall_lower"], 0.125)
            self.assertEqual(row["prefixes"][-1]["recall_upper"], 0.125)

    def test_any_candidate_hard_failure_kills_the_whole_development_stage(self) -> None:
        raw = copy.deepcopy(self.raw)
        raw_case, _ = _case(raw, self.truth, 0, 0, "base")
        _result(raw_case, "LXR-BOUNDS-MODEL")["semantic_or_wire_drift_count"] = 1
        outcome = assessor.assess(
            raw, self.truth, self.blob, _execution_lock(raw, self.truth)
        )
        self.assertFalse(outcome["global_hard_safety_passed"])
        self.assertFalse(outcome["stage_passed"])
        self.assertIsNone(outcome["selected_variant"])
        self.assertTrue(
            all(
                not row["paths"][path]["passed"]
                for row in outcome["candidates"].values()
                for path in ("recall", "efficiency")
            )
        )

    def test_sparse_or_manually_forged_assessment_cannot_authorize_locked(self) -> None:
        forged = {
            "schema_version": assessor.ASSESSMENT_SCHEMA,
            "card_sha256": assessor.CARD_SHA256,
            "stage": "development",
            "stage_passed": True,
            "locked_materialization_eligible": True,
            "selected_variant": "LX-BOUNDS",
            "selected_path": "recall",
        }
        with self.assertRaises(assessor.InterfaceError):
            assessor.build_development_decision_record(
                forged,
                self.raw,
                self.truth,
                self.blob,
                self.execution_lock,
                "d" * 40,
            )

        inconsistent = copy.deepcopy(self.full_outcome)
        inconsistent["global_hard_safety_passed"] = False
        with self.assertRaisesRegex(assessor.InterfaceError, "hard-safety"):
            assessor.validate_assessment_document(inconsistent)

    def test_input_digests_and_local_options_are_hard_bound(self) -> None:
        raw = copy.deepcopy(self.raw)
        raw["cases"][0]["starts_sha256"] = _digest("wrong starts")
        outcome = assessor.assess(
            raw, self.truth, self.blob, _execution_lock(raw, self.truth)
        )
        self.assertFalse(outcome["global_hard_safety_passed"])
        self.assertGreater(
            sum(
                row["calibration_audit_failure_count"]
                for row in outcome["safety"].values()
            ),
            0,
        )

        wrong_options = copy.deepcopy(self.raw)
        wrong_options["cases"][0]["variants"][0]["local_options_sha256"] = _digest(
            "different options"
        )
        with self.assertRaisesRegex(assessor.InterfaceError, "local_options"):
            assessor.validate_topology(wrong_options, self.truth, self.execution_lock)

    def test_calibration_formula_rejects_cross_field_drift_and_covers_clamps(
        self,
    ) -> None:
        context = "synthetic calibration"
        normal = _calibration()
        assessor._validate_calibration(normal, 1, context)

        insufficient = _calibration()
        insufficient["valid_vector_count"] = 7
        insufficient["joint_fallback_reason"] = "insufficient-valid-vectors"
        assessor._validate_calibration(insufficient, 1, context)
        wrong_reason = copy.deepcopy(insufficient)
        wrong_reason["joint_fallback_reason"] = None
        with self.assertRaisesRegex(assessor.InterfaceError, "fallback_reason"):
            assessor._validate_calibration(wrong_reason, 1, context)

        for nearest, expected, lower, upper in (
            (math.ldexp(1.0, -41), assessor.LOWER_MODEL_SCALE, True, False),
            (assessor.LOWER_MODEL_SCALE, assessor.LOWER_MODEL_SCALE, False, False),
            (assessor.UPPER_MODEL_SCALE, assessor.UPPER_MODEL_SCALE, False, False),
            (math.ldexp(1.0, 41), assessor.UPPER_MODEL_SCALE, False, True),
        ):
            calibration = _calibration()
            calibration["nearest_rank_hex"] = [nearest.hex()]
            calibration["model_scale_hex"] = [expected.hex()]
            calibration["model_scale_sha256"] = assessor.model_scale_sha256(
                calibration["model_scale_hex"]
            )
            calibration["clamp_reasons"] = [{"lower": lower, "upper": upper}]
            assessor._validate_calibration(calibration, 1, context)

        bad_scale = _calibration()
        bad_scale["model_scale_hex"] = [(2.0).hex()]
        bad_scale["model_scale_sha256"] = assessor.model_scale_sha256(
            bad_scale["model_scale_hex"]
        )
        with self.assertRaisesRegex(assessor.InterfaceError, "frozen clamp"):
            assessor._validate_calibration(bad_scale, 1, context)

    def test_locked_topology_is_exactly_96_primary_cases_without_safety32(self) -> None:
        blob = _bootstrap("locked")
        raw, truth = _locked_documents(blob)
        decision = assessor.build_development_decision_record(
            self.full_outcome,
            self.raw,
            self.truth,
            self.blob,
            self.execution_lock,
            "d" * 40,
        )
        jsonschema.validate(
            decision,
            json.loads(
                (SOURCE_ROOT / "development-decision-record.schema.json").read_text(
                    encoding="utf-8"
                )
            ),
        )
        truth["locked_decision"] = {
            "candidate_id": decision["selected_variant"],
            "development_path": decision["selected_path"],
            "development_assessment_sha256": decision["development_assessment_sha256"],
            "development_decision_record_sha256": hashlib.sha256(
                assessor.canonical_bytes(decision)
            ).hexdigest(),
        }
        lock = _execution_lock(raw, truth)
        candidate, checked_truth, _ = assessor.validate_topology(raw, truth, lock)
        self.assertEqual(len(candidate["cases"]), 96)
        self.assertEqual(len(checked_truth["cases"]), 96)
        self.assertTrue(
            all(
                case["representation"] in assessor.PRIMARY_REPRESENTATIONS
                for case in checked_truth["cases"]
            )
        )
        outcome = assessor.assess(raw, truth, blob, lock)
        self.assertTrue(outcome["stage_passed"])
        self.assertFalse(outcome["locked_materialization_eligible"])
        self.assertFalse(outcome["product_connection_allowed"])
        final = assessor.finalize_product_connection(
            self.full_outcome,
            outcome,
            decision,
            development_raw_document=self.raw,
            development_assessor_truth=self.truth,
            development_bootstrap_bytes=self.blob,
            development_execution_lock=self.execution_lock,
            locked_raw_document=raw,
            locked_assessor_truth=truth,
            locked_bootstrap_bytes=blob,
            locked_execution_lock=lock,
        )
        jsonschema.validate(
            final,
            json.loads(
                (SOURCE_ROOT / "final-connection.schema.json").read_text(
                    encoding="utf-8"
                )
            ),
        )
        self.assertEqual(final["experiment_id"], "EXP-LOCAL-003")
        self.assertTrue(final["development_safety16_clear"])
        self.assertTrue(final["locked_stage_passed"])
        self.assertTrue(final["product_connection_allowed"])

    def test_scale_permutation_and_calibration_truth_are_independent_hard_audits(
        self,
    ) -> None:
        raw = copy.deepcopy(self.raw)
        raw_case, _ = _case(raw, self.truth, 0, 0, "base")
        calibration = _result(raw_case, "LR-MODEL")["calibration"]
        calibration["observation_evaluation_costs"][0] = 3
        truth, raw_results, assessed = self._assessed(raw, self.truth)
        control_safety = assessor._variant_safety(
            assessed, raw_results, truth, assessor.CONTROL
        )
        candidate_safety = assessor._variant_safety(
            assessed, raw_results, truth, "LR-MODEL"
        )
        self.assertGreater(candidate_safety["calibration_audit_failure_count"], 0)
        self.assertFalse(
            assessor._global_hard_safety_passes(
                {assessor.CONTROL: control_safety, "LR-MODEL": candidate_safety}
            )
        )


if __name__ == "__main__":
    unittest.main()
