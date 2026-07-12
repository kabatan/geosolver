from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).parents[1] / "aggregate_t0.py"
SPEC = importlib.util.spec_from_file_location("exp_local_015_aggregate_t0", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _work_for_arm(arm: str) -> dict[str, int]:
    if arm == MODULE.E4:
        return {}
    if arm in {
        MODULE.FLOAT_DIAGNOSTIC,
        MODULE.WEAK,
        MODULE.ISOTROPIC,
        MODULE.WEAK_NO_EMIT,
    }:
        return {"float64": 8}
    if arm == MODULE.REFERENCE:
        return {"512": 5}
    if arm == MODULE.ADAPTED:
        return {"256": 2, "512": 1}
    if arm == MODULE.COMBINED:
        return {"float64": 8, "256": 2, "512": 1}
    raise AssertionError(arm)


def _candidate_input(start: int) -> dict[str, object]:
    return {
        "callback_cost": 1,
        "capability": "C2",
        "dimension": 2,
        "endpoint": [start / 100.0, -start / 200.0],
        "lower_bounds": [-1.0, -1.0],
        "prefilter": {
            "condition_estimate": 1.0e12,
            "model_agreement": True,
            "numerical_rank": 1,
        },
        "residual_dimension": 2,
        "semantics": {"branch_stable": True, "margin": 0.25},
        "upper_bounds": [1.0, 1.0],
    }


def _adaptive_diagnostics(*, confirmed: bool, dimension: int = 2) -> dict[str, object]:
    result: dict[str, object] = {
        "confirmation_site": "same_source_model",
        "cross_tier_confirmed": confirmed,
        "refined_endpoint_high_precision_confirmed": False,
        "same_source_model_confirmed": confirmed,
    }
    if confirmed:
        result.update(
            {
                "confirmation_numerical_rank": dimension,
                "confirmation_precision_bits": 512,
                "correction_stable": True,
                "cross_tier_correction_disagreement": "1.0e-30",
                "cross_tier_correction_tolerance": "1.0e-20",
                "cross_tier_jacobian_disagreement": "1.0e-30",
                "cross_tier_jacobian_tolerance": "1.0e-20",
                "cross_tier_residual_disagreement": "1.0e-30",
                "cross_tier_residual_tolerance": "1.0e-20",
                "rank_stable": True,
                "selected_numerical_rank": dimension,
                "selected_precision_bits": 256,
            }
        )
    else:
        result.update(
            {
                "confirmation_numerical_rank": None,
                "confirmation_precision_bits": None,
                "correction_stable": False,
                "cross_tier_correction_disagreement": None,
                "cross_tier_correction_tolerance": None,
                "cross_tier_jacobian_disagreement": None,
                "cross_tier_jacobian_tolerance": None,
                "cross_tier_residual_disagreement": None,
                "cross_tier_residual_tolerance": None,
                "rank_stable": False,
                "selected_numerical_rank": None,
                "selected_precision_bits": None,
            }
        )
    return result


def _row(arm: str, start: int, *, safety: bool) -> dict[str, object]:
    counts = _work_for_arm(arm)
    callbacks = sum(counts.values())
    weighted = sum(
        count * MODULE.PRECISION_WEIGHTS[tier] for tier, count in counts.items()
    )
    adapted_activation = arm == MODULE.ADAPTED and start == 1 and not safety
    weak_activation = (
        arm
        in {
            MODULE.WEAK,
            MODULE.WEAK_NO_EMIT,
        }
        and start == 2
        and not safety
    )
    combined_activation = arm == MODULE.COMBINED and start == 1 and not safety
    activated = adapted_activation or weak_activation or combined_activation
    if adapted_activation or combined_activation:
        emission = "refinement_seed"
    elif arm == MODULE.WEAK and weak_activation:
        emission = "bracket_seed"
    else:
        emission = "none"
    valid = emission != "none" and not safety
    matched = (
        f"root-{start}"
        if valid and arm not in {MODULE.WEAK, MODULE.ISOTROPIC, MODULE.WEAK_NO_EMIT}
        else None
    )
    if arm == MODULE.E4 and start == 3 and not safety:
        matched = "root-3"
    candidate_input = _candidate_input(start)
    shared_counts = {"float64": 1 + 4 * int(candidate_input["dimension"])}
    shared_callbacks = sum(shared_counts.values())
    shared_work = sum(
        count * MODULE.PRECISION_WEIGHTS[tier] for tier, count in shared_counts.items()
    )
    if arm in {MODULE.WEAK, MODULE.ISOTROPIC, MODULE.WEAK_NO_EMIT}:
        activation_observables = {
            "rank_evidence_activated": True,
            "strict_bracket_detected": activated,
        }
    elif arm == MODULE.ADAPTED:
        activation_observables = {
            "cross_tier_confirmed": adapted_activation,
            "newton_step_accepted": adapted_activation,
            "tier_started": adapted_activation,
        }
    elif arm == MODULE.COMBINED:
        activation_observables = {
            "adaptive_attempt_started": combined_activation,
            "cross_tier_confirmed": combined_activation,
            "strict_bracket_detected": combined_activation,
        }
    elif arm == MODULE.FLOAT_DIAGNOSTIC:
        activation_observables = {"rank_or_condition_trigger": activated}
    elif arm == MODULE.REFERENCE:
        activation_observables = {"factorization_performed": activated}
    else:
        activation_observables = {"mechanism_activated": activated}
    emitted_coordinates = (
        [[start / 100.0, -start / 200.0]] if emission != "none" else []
    )
    emitted_brackets = (
        [
            {
                "lower_parameter": -0.01,
                "lower_projected_residual": -1.0,
                "midpoint_coordinates": emitted_coordinates[0],
                "unit_direction": [1.0, 0.0],
                "upper_parameter": 0.01,
                "upper_projected_residual": 1.0,
            }
        ]
        if emission == "bracket_seed"
        else []
    )
    if arm == MODULE.ADAPTED:
        mechanism_diagnostics = _adaptive_diagnostics(
            confirmed=adapted_activation,
            dimension=int(candidate_input["dimension"]),
        )
    elif arm == MODULE.COMBINED:
        attempts = (
            [
                _adaptive_diagnostics(
                    confirmed=True,
                    dimension=int(candidate_input["dimension"]),
                )
            ]
            if combined_activation
            else []
        )
        mechanism_diagnostics = {
            "adaptive_attempt_count": len(attempts),
            "adaptive_attempt_observables": attempts,
            "adaptive_attempt_started": bool(attempts),
            "confirmation_site": "same_source_model",
            "cross_tier_confirmed": combined_activation,
            "refined_endpoint_high_precision_confirmed": False,
            "same_source_model_confirmed": combined_activation,
        }
    else:
        mechanism_diagnostics = {}
    return {
        "activation_observables": activation_observables,
        "arm": arm,
        "assessor": {
            "matched_isolated_root_classes": [] if matched is None else [matched],
            "safety_control": safety,
            "valid_refinement_seed": valid,
        },
        "budget_exhausted": False,
        "candidate_input": candidate_input,
        "charged_callback_count": callbacks,
        "charged_weighted_work": weighted,
        "emission_kind": emission,
        "emitted_brackets": emitted_brackets,
        "emitted_seed_coordinates": emitted_coordinates,
        "exception": None,
        "mechanism_diagnostics": mechanism_diagnostics,
        "observed_callback_count": callbacks,
        "observed_precision_counts": dict(counts),
        "observed_weighted_work": weighted,
        "reason": "seed_ready" if emission != "none" else "no_seed",
        "reported_callback_count": callbacks,
        "reported_weighted_work": weighted,
        "requested_precision_counts": dict(counts),
        "shared_callback_count": shared_callbacks,
        "shared_observed_callback_count": shared_callbacks,
        "shared_observed_precision_counts": dict(shared_counts),
        "shared_observed_weighted_work": shared_work,
        "shared_requested_precision_counts": dict(shared_counts),
        "shared_weighted_work": shared_work,
        "start_index": start,
        "status": "seed_ready" if emission != "none" else "unknown",
        "total_callback_count": shared_callbacks + callbacks,
        "total_weighted_work": shared_work + weighted,
        "truth_free_replay_digest": MODULE.candidate_input_digest(candidate_input),
    }


def good_documents() -> list[dict[str, object]]:
    documents: list[dict[str, object]] = []
    case_index = 0
    for class_index in range(1, MODULE.REPRESENTATION_CLASS_COUNT + 1):
        safety = class_index >= 19
        for representation in MODULE.REPRESENTATIONS:
            case_index += 1
            documents.append(
                {
                    "arm_order": list(MODULE.ARMS),
                    "case": {
                        "representation": representation,
                        "representation_class_id": f"class-{class_index:02d}",
                        "stratum_id": f"stratum-{(class_index - 1) % 7 + 1}",
                    },
                    "case_count": MODULE.CASE_COUNT,
                    "case_index": case_index,
                    "corpus_checksum": "2" * 64,
                    "experiment_id": MODULE.EXPERIMENT_ID,
                    "nonpromotional_t0": True,
                    "preregistration": {
                        "path": "research/experiments/EXP-LOCAL-015/preregistration.json",
                        "sha256": "3" * 64,
                    },
                    "revision": {"git_dirty": False, "git_head": "1" * 40},
                    "rows": [
                        _row(arm, start, safety=safety)
                        for arm in MODULE.ARMS
                        for start in range(1, MODULE.START_COUNT + 1)
                    ],
                    "runtime_contract": {
                        "active_project_path": MODULE.FORMAL_PROJECT_PATH,
                        "julia_version": "1.12.6",
                        "manifest_sha256": "6" * 64,
                        "project_sha256": "7" * 64,
                    },
                    "schema_version": MODULE.RAW_SCHEMA,
                    "shared_prefilter_physical_evaluations": MODULE.START_COUNT,
                    "thread_contract": {
                        "assigned_cpu": (case_index - 1) % 16,
                        "blas_threads": 1,
                        "julia_threads": 1,
                        "mkl_env_threads": 1,
                        "omp_env_threads": 1,
                        "openblas_env_threads": 1,
                        "solver_worker_count": 1,
                        "within_case_parallelism": False,
                    },
                }
            )
    assert case_index == MODULE.CASE_COUNT
    return documents


def _find_row(document: dict[str, object], arm: str, start: int) -> dict[str, object]:
    rows = document["rows"]
    assert isinstance(rows, list)
    return next(
        row
        for row in rows
        if isinstance(row, dict) and row["arm"] == arm and row["start_index"] == start
    )


def _write_documents(root: Path, documents: list[dict[str, object]]) -> list[Path]:
    paths: list[Path] = []
    for index, document in enumerate(documents, start=1):
        path = root / f"case-{index:02d}.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        paths.append(path)
    return paths


def test_good_63_shard_fixture_recomputes_all_primary_ledgers() -> None:
    result = MODULE.aggregate_documents(good_documents())

    assert result["case_count"] == 63
    assert result["representation_class_count"] == 21
    assert result["trial_count"] == 63 * 16 * len(MODULE.ARMS)
    assert result["t0_conformance_zero"] is True
    assert not any(result["accounting"].values())
    assert result["candidate_safety_emission_count"] == 0
    assert result["control_safety_emission_count"] == 0
    assert result["unsupported_seed_count"] == 0
    assert result["representation_disagreement_count"] == 0
    assert MODULE.ISOTROPIC not in result["exact_representation_gate_arms"]
    assert (
        result["isotropic_representation_diagnostic"]["exact_per_start_gate"] is False
    )
    assert result["arm_metrics"][MODULE.ADAPTED]["trial_count"] == 1_008
    assert result["arm_metrics"][MODULE.ADAPTED]["activation_count"] == 54
    assert result["arm_metrics"][MODULE.ADAPTED]["valid_refinement_seed_count"] == 54
    assert result["arm_metrics"][MODULE.WEAK]["activation_count"] == 54
    assert result["arm_metrics"][MODULE.ISOTROPIC]["activation_count"] == 0
    assert (
        result["arm_metrics"][MODULE.ADAPTED]["total_case_weighted_work"]
        > result["arm_metrics"][MODULE.ADAPTED]["trial_count"] * 9
    )
    assert (
        result["contrasts"]["adapted_vs_float_diagnostic"][
            "candidate_only_activation_trials"
        ]
        == 54
    )
    assert (
        result["contrasts"]["weak_emission_vs_no_emit"][
            "candidate_only_valid_seed_trials"
        ]
        == 54
    )
    assert all(
        decision["causal_classification"] == "INCONCLUSIVE"
        for decision in result["candidate_decisions"].values()
    )
    assert "BOUNDED" not in MODULE.canonical_json(result)


def test_path_loader_rejects_missing_and_duplicate_one_case_shards(
    tmp_path: Path,
) -> None:
    paths = _write_documents(tmp_path, good_documents())
    with pytest.raises(ValueError, match="expected 63 one-case shard paths"):
        MODULE.aggregate(paths[:-1])
    with pytest.raises(ValueError, match="case indices must be exactly"):
        MODULE.aggregate([paths[0], *paths[:-1]])


def test_representation_and_arm_start_closure_are_structural(tmp_path: Path) -> None:
    documents = good_documents()
    documents[2]["case"]["representation"] = "base"  # type: ignore[index]
    with pytest.raises(ValueError, match="lacks base/signed/orthogonal closure"):
        MODULE.aggregate_documents(documents)

    documents = good_documents()
    documents[0]["rows"].pop()  # type: ignore[union-attr]
    with pytest.raises(ValueError, match="16 starts x eight frozen arms"):
        MODULE.aggregate_documents(documents)

    documents = good_documents()
    documents[0]["shared_prefilter_physical_evaluations"] = 128
    with pytest.raises(ValueError, match="physically evaluated once per start"):
        MODULE.aggregate_documents(documents)

    documents = good_documents()
    row = _find_row(documents[0], MODULE.ADAPTED, 1)
    row["emitted_seed_coordinates"] = []
    with pytest.raises(ValueError, match="emission kind and emitted seed coordinates"):
        MODULE.aggregate_documents(documents)

    paths = _write_documents(tmp_path, good_documents())
    first = json.loads(paths[0].read_text(encoding="utf-8"))
    first["arm_order"] = list(reversed(first["arm_order"]))
    paths[0].write_text(json.dumps(first), encoding="utf-8")
    with pytest.raises(ValueError, match="frozen arm order differs"):
        MODULE.aggregate(paths)


def test_top_level_corpus_preregistration_and_thread_contract_are_exact() -> None:
    documents = good_documents()
    documents[0]["unexpected"] = True
    with pytest.raises(ValueError, match="top-level contract differs"):
        MODULE.aggregate_documents(documents)

    documents = good_documents()
    documents[0]["corpus_checksum"] = "4" * 64
    with pytest.raises(ValueError, match="one corpus checksum"):
        MODULE.aggregate_documents(documents)

    documents = good_documents()
    documents[0]["preregistration"]["sha256"] = "5" * 64  # type: ignore[index]
    with pytest.raises(ValueError, match="one preregistration"):
        MODULE.aggregate_documents(documents)

    documents = good_documents()
    documents[0]["thread_contract"]["blas_threads"] = 2  # type: ignore[index]
    with pytest.raises(ValueError, match="blas_threads must equal one"):
        MODULE.aggregate_documents(documents)

    documents = good_documents()
    documents[0]["thread_contract"]["omp_env_threads"] = 2  # type: ignore[index]
    with pytest.raises(ValueError, match="omp_env_threads must equal one"):
        MODULE.aggregate_documents(documents)

    documents = good_documents()
    documents[0]["runtime_contract"][  # type: ignore[index]
        "active_project_path"
    ] = "wrong/Project.toml"
    with pytest.raises(ValueError, match="formal EXP-LOCAL-002 project"):
        MODULE.aggregate_documents(documents)

    documents = good_documents()
    documents[0]["runtime_contract"]["julia_version"] = "9.9.9"  # type: ignore[index]
    with pytest.raises(ValueError, match="Julia must equal 1.12.6"):
        MODULE.aggregate_documents(documents)

    result = MODULE.aggregate_documents(good_documents())
    assert result["corpus_checksum"] == "2" * 64
    assert result["preregistration"]["sha256"] == "3" * 64
    assert result["thread_contract"]["within_case_parallelism"] is False
    assert result["thread_contract"]["openblas_env_threads"] == 1
    assert result["runtime_contract"]["solver_julia"]["julia_version"] == "1.12.6"
    assert result["runtime_contract"]["aggregate_python_version"]


def test_weight_and_callback_tampering_is_independently_recomputed() -> None:
    documents = good_documents()
    row = _find_row(documents[0], MODULE.ADAPTED, 1)
    row["charged_callback_count"] = int(row["charged_callback_count"]) + 1
    row["reported_weighted_work"] = 601

    result = MODULE.aggregate_documents(documents)
    assert result["accounting"]["callback_charge_mismatches"] == 1
    assert result["accounting"]["weighted_work_mismatches"] == 1
    assert result["accounting"]["weighted_work_cap_violations"] == 1
    assert result["t0_conformance_zero"] is False
    assert all(
        decision["causal_classification"] == "INVALID_RUN"
        for decision in result["candidate_decisions"].values()
    )


def test_shared_and_total_ledgers_are_recomputed_and_paired_across_arms() -> None:
    documents = good_documents()
    row = _find_row(documents[0], MODULE.ADAPTED, 1)
    row["shared_callback_count"] = int(row["shared_callback_count"]) + 1
    row["total_weighted_work"] = int(row["total_weighted_work"]) + 1

    result = MODULE.aggregate_documents(documents)
    accounting = result["accounting"]
    assert accounting["shared_callback_mismatches"] == 1
    assert accounting["shared_ledger_pairing_mismatches"] == 1
    assert accounting["total_weighted_work_mismatches"] == 1
    assert accounting["weighted_work_cap_violations"] == 0
    assert result["t0_conformance_zero"] is False

    malformed = good_documents()
    row = _find_row(malformed[0], MODULE.ADAPTED, 1)
    row["shared_requested_precision_counts"] = {"float64": 8}
    with pytest.raises(ValueError, match="complete Float64 1\\+4n stencil"):
        MODULE.aggregate_documents(malformed)


def test_physical_observed_precision_ledgers_are_independent_authority() -> None:
    documents = good_documents()
    row = _find_row(documents[0], MODULE.ADAPTED, 1)
    row["observed_precision_counts"]["float64"] = 1  # type: ignore[index]

    result = MODULE.aggregate_documents(documents)
    accounting = result["accounting"]
    assert accounting["precision_count_mismatches"] == 1
    assert accounting["callback_charge_mismatches"] == 1
    assert accounting["weighted_work_mismatches"] == 1
    assert accounting["total_callback_mismatches"] == 1
    assert accounting["total_weighted_work_mismatches"] == 1
    assert result["t0_conformance_zero"] is False

    documents = good_documents()
    row = _find_row(documents[0], MODULE.ADAPTED, 1)
    row["shared_observed_precision_counts"] = {"float64": 8}
    result = MODULE.aggregate_documents(documents)
    accounting = result["accounting"]
    assert accounting["shared_precision_count_mismatches"] == 1
    assert accounting["shared_observed_callback_mismatches"] == 1
    assert accounting["shared_observed_weighted_work_mismatches"] == 1
    assert result["t0_conformance_zero"] is False


def test_reference_rescue_600_allows_case_total_above_600() -> None:
    documents = good_documents()
    for document in documents[:3]:
        row = _find_row(document, MODULE.REFERENCE, 1)
        row["charged_callback_count"] = 60
        row["charged_weighted_work"] = 600
        row["observed_callback_count"] = 60
        row["observed_precision_counts"] = {"512": 60}
        row["observed_weighted_work"] = 600
        row["reported_callback_count"] = 60
        row["reported_weighted_work"] = 600
        row["requested_precision_counts"] = {"512": 60}
        row["total_callback_count"] = 69
        row["total_weighted_work"] = 609

    result = MODULE.aggregate_documents(documents)
    assert result["accounting"]["weighted_work_cap_violations"] == 0
    assert result["accounting"]["total_weighted_work_mismatches"] == 0
    assert result["t0_conformance_zero"] is True


def test_precision_weight_formula_is_exact() -> None:
    counts, callbacks, work = MODULE._precision_ledger(
        {"float64": 2, "128": 3, "256": 4, "512": 5}
    )
    assert counts == {"float64": 2, "128": 3, "256": 4, "512": 5}
    assert callbacks == 14
    assert work == 2 + 3 * 3 + 4 * 5 + 5 * 10
    with pytest.raises(ValueError, match="unknown precision tier"):
        MODULE._precision_ledger({"768": 1})


def test_weak_activation_requires_strict_bracket_not_rank_diagnostic_alone() -> None:
    documents = good_documents()
    weak = _find_row(documents[0], MODULE.WEAK, 1)
    assert weak["activation_observables"] == {
        "rank_evidence_activated": True,
        "strict_bracket_detected": False,
    }
    result = MODULE.aggregate_documents(documents)
    assert result["arm_metrics"][MODULE.WEAK]["activation_count"] == 54

    malformed = good_documents()
    row = _find_row(malformed[0], MODULE.WEAK, 1)
    row["activation_observables"] = {"rank_evidence_activated": True}
    with pytest.raises(ValueError, match="activation_observables must be exactly"):
        MODULE.aggregate_documents(malformed)

    impossible = good_documents()
    row = _find_row(impossible[0], MODULE.WEAK_NO_EMIT, 1)
    row["activation_observables"] = {
        "rank_evidence_activated": False,
        "strict_bracket_detected": True,
    }
    with pytest.raises(ValueError, match="strict bracket requires"):
        MODULE.aggregate_documents(impossible)


def test_full_bracket_contract_is_recomputed_from_raw_fields() -> None:
    malformed = good_documents()
    row = _find_row(malformed[0], MODULE.WEAK, 2)
    row["emitted_brackets"][0]["unit_direction"] = [2.0, 0.0]  # type: ignore[index]
    with pytest.raises(ValueError, match="unit norm"):
        MODULE.aggregate_documents(malformed)

    malformed = good_documents()
    row = _find_row(malformed[0], MODULE.WEAK, 2)
    row["activation_observables"]["strict_bracket_detected"] = False  # type: ignore[index]
    with pytest.raises(ValueError, match="must equal emitted bracket presence"):
        MODULE.aggregate_documents(malformed)

    malformed = good_documents()
    row = _find_row(malformed[0], MODULE.WEAK, 2)
    row["emitted_brackets"][0]["upper_projected_residual"] = -2.0  # type: ignore[index]
    with pytest.raises(ValueError, match="opposite sign"):
        MODULE.aggregate_documents(malformed)

    malformed = good_documents()
    row = _find_row(malformed[0], MODULE.WEAK, 2)
    row["emitted_brackets"][0]["midpoint_coordinates"] = [0.0, 0.0]  # type: ignore[index]
    with pytest.raises(ValueError, match="midpoint is inconsistent"):
        MODULE.aggregate_documents(malformed)

    malformed = good_documents()
    row = _find_row(malformed[0], MODULE.ADAPTED, 1)
    row["emitted_brackets"] = [
        {
            "lower_parameter": -0.01,
            "lower_projected_residual": -1.0,
            "midpoint_coordinates": [0.01, -0.005],
            "unit_direction": [1.0, 0.0],
            "upper_parameter": 0.01,
            "upper_projected_residual": 1.0,
        }
    ]
    with pytest.raises(ValueError, match="may not report emitted brackets"):
        MODULE.aggregate_documents(malformed)


def test_adaptive_mechanism_diagnostics_preserve_same_source_success_evidence() -> None:
    row = _find_row(good_documents()[0], MODULE.ADAPTED, 1)
    validated = MODULE._validate_row(row)
    diagnostics = validated["mechanism_diagnostics"]
    assert diagnostics["confirmation_site"] == "same_source_model"
    assert diagnostics["same_source_model_confirmed"] is True
    assert diagnostics["refined_endpoint_high_precision_confirmed"] is False
    assert diagnostics["selected_precision_bits"] == 256
    assert diagnostics["confirmation_precision_bits"] == 512

    malformed = _find_row(good_documents()[0], MODULE.ADAPTED, 1)
    malformed["mechanism_diagnostics"].pop("cross_tier_jacobian_tolerance")  # type: ignore[union-attr]
    with pytest.raises(ValueError, match="missing success evidence"):
        MODULE._validate_row(malformed)

    malformed = _find_row(good_documents()[0], MODULE.ADAPTED, 1)
    malformed["mechanism_diagnostics"].pop("selected_precision_bits")  # type: ignore[union-attr]
    with pytest.raises(ValueError, match="missing success evidence"):
        MODULE._validate_row(malformed)

    malformed = _find_row(good_documents()[0], MODULE.ADAPTED, 1)
    malformed["mechanism_diagnostics"]["cross_tier_residual_tolerance"] = 1.0  # type: ignore[index]
    with pytest.raises(ValueError, match="must be a nonempty string"):
        MODULE._validate_row(malformed)

    malformed = _find_row(good_documents()[0], MODULE.ADAPTED, 1)
    malformed["mechanism_diagnostics"]["confirmation_site"] = "refined_endpoint"  # type: ignore[index]
    with pytest.raises(ValueError, match="must be same_source_model"):
        MODULE._validate_row(malformed)

    malformed = _find_row(good_documents()[0], MODULE.ADAPTED, 1)
    malformed["mechanism_diagnostics"][  # type: ignore[index]
        "refined_endpoint_high_precision_confirmed"
    ] = True
    with pytest.raises(ValueError, match="may not claim refined-endpoint"):
        MODULE._validate_row(malformed)

    malformed = _find_row(good_documents()[0], MODULE.ADAPTED, 1)
    malformed["mechanism_diagnostics"]["rank_stable"] = False  # type: ignore[index]
    with pytest.raises(ValueError, match="rank_stable must be true"):
        MODULE._validate_row(malformed)

    malformed = _find_row(good_documents()[0], MODULE.ADAPTED, 1)
    malformed["mechanism_diagnostics"]["same_source_model_confirmed"] = False  # type: ignore[index]
    malformed["mechanism_diagnostics"]["cross_tier_confirmed"] = False  # type: ignore[index]
    with pytest.raises(ValueError, match="does not match row status"):
        MODULE._validate_row(malformed)


def test_combined_retains_each_adaptive_attempt_contract() -> None:
    success = _find_row(good_documents()[0], MODULE.COMBINED, 1)
    validated = MODULE._validate_row(success)
    diagnostics = validated["mechanism_diagnostics"]
    assert diagnostics["adaptive_attempt_count"] == 1
    assert len(diagnostics["adaptive_attempt_observables"]) == 1
    assert diagnostics["adaptive_attempt_observables"][0]["same_source_model_confirmed"]

    unknown = _find_row(good_documents()[0], MODULE.COMBINED, 2)
    unknown_attempt = _adaptive_diagnostics(confirmed=False)
    unknown["mechanism_diagnostics"]["adaptive_attempt_count"] = 1  # type: ignore[index]
    unknown["mechanism_diagnostics"]["adaptive_attempt_started"] = True  # type: ignore[index]
    unknown["mechanism_diagnostics"]["adaptive_attempt_observables"] = [  # type: ignore[index]
        unknown_attempt
    ]
    validated_unknown = MODULE._validate_row(unknown)
    assert (
        validated_unknown["mechanism_diagnostics"]["adaptive_attempt_observables"][0][
            "selected_precision_bits"
        ]
        is None
    )

    malformed = _find_row(good_documents()[0], MODULE.COMBINED, 1)
    malformed["mechanism_diagnostics"]["adaptive_attempt_observables"] = []  # type: ignore[index]
    malformed["mechanism_diagnostics"]["adaptive_attempt_count"] = 0  # type: ignore[index]
    malformed["mechanism_diagnostics"]["adaptive_attempt_started"] = False  # type: ignore[index]
    with pytest.raises(ValueError, match="must retain one confirmed adaptive attempt"):
        MODULE._validate_row(malformed)

    malformed = _find_row(good_documents()[0], MODULE.COMBINED, 1)
    attempt = malformed["mechanism_diagnostics"]["adaptive_attempt_observables"][0]  # type: ignore[index]
    attempt.pop("cross_tier_correction_disagreement")
    with pytest.raises(ValueError, match="missing success evidence"):
        MODULE._validate_row(malformed)


def test_mechanism_diagnostics_is_required_but_other_arms_may_use_empty_object() -> (
    None
):
    row = _find_row(good_documents()[0], MODULE.E4, 1)
    assert MODULE._validate_row(row)["mechanism_diagnostics"] == {}

    malformed = _find_row(good_documents()[0], MODULE.E4, 1)
    malformed.pop("mechanism_diagnostics")
    with pytest.raises(ValueError, match="mechanism_diagnostics"):
        MODULE._validate_row(malformed)

    malformed = _find_row(good_documents()[0], MODULE.REFERENCE, 1)
    malformed["mechanism_diagnostics"] = []
    with pytest.raises(ValueError, match="must be an object"):
        MODULE._validate_row(malformed)

    malformed = _find_row(good_documents()[0], MODULE.E4, 1)
    malformed["unexpected_raw_field"] = True
    with pytest.raises(
        ValueError, match="raw row contract differs.*unexpected_raw_field"
    ):
        MODULE._validate_row(malformed)

    malformed = _find_row(good_documents()[0], MODULE.E4, 1)
    malformed["assessor"]["unexpected_assessor_field"] = True  # type: ignore[index]
    with pytest.raises(
        ValueError, match="assessor contract differs.*unexpected_assessor_field"
    ):
        MODULE._validate_row(malformed)

    malformed = _find_row(good_documents()[0], MODULE.E4, 1)
    malformed["activation_observables"]["forged_true"] = True  # type: ignore[index]
    with pytest.raises(ValueError, match="activation_observables must be exactly"):
        MODULE._validate_row(malformed)


def test_candidate_truth_leak_and_digest_poison_are_audited() -> None:
    documents = good_documents()
    leak = _find_row(documents[0], MODULE.WEAK, 2)
    leak["candidate_input"]["family_id"] = "forbidden"  # type: ignore[index]
    leak["truth_free_replay_digest"] = MODULE.candidate_input_digest(
        leak["candidate_input"]
    )
    poison = _find_row(documents[1], MODULE.ADAPTED, 1)
    poison["truth_free_replay_digest"] = "f" * 64

    result = MODULE.aggregate_documents(documents)
    assert result["accounting"]["truth_leak_fields"] == 1
    assert result["accounting"]["replay_digest_mismatches"] == 1
    assert result["accounting"]["paired_candidate_input_mismatches"] == 1
    assert result["t0_conformance_zero"] is False


def test_candidate_digest_uses_recursive_ieee754_bit_normalization() -> None:
    payload = {
        "negative_zero": -0.0,
        "subnormal": float.fromhex("0x0.0000000000001p-1022"),
        "small": 1.0e-6,
        "large": 1.0e300,
        "nested": [True, 7, "plain", {"z": 0.0}],
    }
    normalized = MODULE._normalize_digest_value(payload)
    assert normalized == [
        "dict",
        [
            ["large", ["float64", "7e37e43c8800759c"]],
            ["negative_zero", ["float64", "8000000000000000"]],
            [
                "nested",
                [
                    "list",
                    [
                        ["bool", True],
                        ["int", "7"],
                        ["string", "plain"],
                        ["dict", [["z", ["float64", "0000000000000000"]]]],
                    ],
                ],
            ],
            ["small", ["float64", "3eb0c6f7a0b5ed8d"]],
            ["subnormal", ["float64", "0000000000000001"]],
        ],
    ]
    assert (
        MODULE.candidate_input_digest(payload)
        == "da3ee560375576c5324fd68a358c491c4ea368f25c8094b13b931176b4ca41ca"
    )
    reordered = {key: payload[key] for key in reversed(tuple(payload))}
    assert MODULE.candidate_input_digest(reordered) == MODULE.candidate_input_digest(
        payload
    )

    mutated = dict(payload)
    mutated["small"] = math.nextafter(1.0e-6, math.inf)
    assert MODULE.candidate_input_digest(mutated) != MODULE.candidate_input_digest(
        payload
    )
    assert MODULE.candidate_input_digest({"x": -0.0}) != MODULE.candidate_input_digest(
        {"x": 0.0}
    )
    assert MODULE.candidate_input_digest({"x": 1}) != MODULE.candidate_input_digest(
        {"x": 1.0}
    )
    float_value = {"x": 1.0e-6}
    assert MODULE.candidate_input_digest(float_value) != MODULE.candidate_input_digest(
        {"x": "float64_bits:3eb0c6f7a0b5ed8d"}
    )
    assert MODULE.candidate_input_digest(float_value) != MODULE.candidate_input_digest(
        {"x": ["float64", "3eb0c6f7a0b5ed8d"]}
    )
    assert MODULE.candidate_input_digest(float_value) != MODULE.candidate_input_digest(
        {"x": {"__geotarget_float64_bits__": "3eb0c6f7a0b5ed8d"}}
    )
    with pytest.raises(ValueError, match="must be finite"):
        MODULE.candidate_input_digest({"x": math.inf})


def test_candidate_safety_emission_is_invalid_without_tainting_other_candidates() -> (
    None
):
    documents = good_documents()
    for document in documents[(19 - 1) * 3 : 19 * 3]:
        row = _find_row(document, MODULE.WEAK, 2)
        endpoint = list(row["candidate_input"]["endpoint"])  # type: ignore[index]
        row["activation_observables"] = {
            "rank_evidence_activated": True,
            "strict_bracket_detected": True,
        }
        row["emission_kind"] = "bracket_seed"
        row["emitted_seed_coordinates"] = [endpoint]
        row["emitted_brackets"] = [
            {
                "lower_parameter": -0.01,
                "lower_projected_residual": -1.0,
                "midpoint_coordinates": endpoint,
                "unit_direction": [1.0, 0.0],
                "upper_parameter": 0.01,
                "upper_projected_residual": 1.0,
            }
        ]
        row["status"] = "seeded"
        row["reason"] = "strict_projected_sign_bracket"
        row["assessor"]["valid_refinement_seed"] = False  # type: ignore[index]
        row["assessor"]["matched_isolated_root_classes"] = []  # type: ignore[index]

    result = MODULE.aggregate_documents(documents)
    assert result["candidate_safety_emission_count"] == 3
    assert result["control_safety_emission_count"] == 0
    assert result["arm_metrics"][MODULE.WEAK]["safety_emission_count"] == 3
    assert result["arm_metrics"][MODULE.WEAK]["unsupported_seed_count"] == 3
    assert result["t0_conformance_zero"] is False
    assert (
        result["candidate_decisions"][MODULE.WEAK]["causal_classification"]
        == "INVALID_RUN"
    )
    assert (
        result["candidate_decisions"][MODULE.ADAPTED]["causal_classification"]
        == "INCONCLUSIVE"
    )
    assert (
        result["candidate_decisions"][MODULE.COMBINED]["causal_classification"]
        == "INCONCLUSIVE"
    )


def test_positive_unsupported_seed_is_performance_not_invalid_run() -> None:
    documents = good_documents()
    for document in documents[:3]:
        row = _find_row(document, MODULE.ADAPTED, 1)
        row["assessor"]["valid_refinement_seed"] = False  # type: ignore[index]
        row["assessor"]["matched_isolated_root_classes"] = []  # type: ignore[index]

    result = MODULE.aggregate_documents(documents)
    assert result["unsupported_seed_count"] == 3
    assert result["candidate_safety_emission_count"] == 0
    assert result["arm_metrics"][MODULE.ADAPTED]["unsupported_seed_count"] == 3
    assert result["t0_conformance_zero"] is True
    assert (
        result["candidate_decisions"][MODULE.ADAPTED]["causal_classification"]
        == "INCONCLUSIVE"
    )


def test_control_safety_emission_is_separate_nonpromotional_diagnostic() -> None:
    documents = good_documents()
    document = documents[(19 - 1) * 3]
    row = _find_row(document, MODULE.ISOTROPIC, 2)
    endpoint = list(row["candidate_input"]["endpoint"])  # type: ignore[index]
    row["activation_observables"] = {
        "rank_evidence_activated": True,
        "strict_bracket_detected": True,
    }
    row["emission_kind"] = "bracket_seed"
    row["emitted_seed_coordinates"] = [endpoint]
    row["emitted_brackets"] = [
        {
            "lower_parameter": -0.01,
            "lower_projected_residual": -1.0,
            "midpoint_coordinates": endpoint,
            "unit_direction": [1.0, 0.0],
            "upper_parameter": 0.01,
            "upper_projected_residual": 1.0,
        }
    ]
    row["assessor"]["valid_refinement_seed"] = False  # type: ignore[index]
    row["assessor"]["matched_isolated_root_classes"] = []  # type: ignore[index]

    result = MODULE.aggregate_documents(documents)
    assert result["candidate_safety_emission_count"] == 0
    assert result["control_safety_emission_count"] == 1
    assert result["arm_metrics"][MODULE.ISOTROPIC]["unsupported_seed_count"] == 1
    assert result["t0_conformance_zero"] is True


def test_representation_disagreement_uses_raw_outcome_signature() -> None:
    documents = good_documents()
    orthogonal = documents[2]
    row = _find_row(orthogonal, MODULE.ADAPTED, 1)
    row["reason"] = "representation_specific_reason"

    result = MODULE.aggregate_documents(documents)
    assert result["representation_disagreement_count"] == 1
    disagreement = result["representation_disagreements"][0]
    assert disagreement["arm"] == MODULE.ADAPTED
    assert disagreement["start_index"] == 1
    assert result["t0_conformance_zero"] is False


def test_isotropic_replica_differences_are_aggregate_diagnostics_only() -> None:
    documents = good_documents()
    orthogonal = documents[2]
    row = _find_row(orthogonal, MODULE.ISOTROPIC, 1)
    row["activation_observables"] = {
        "rank_evidence_activated": True,
        "strict_bracket_detected": True,
    }
    row["emission_kind"] = "bracket_seed"
    row["emitted_seed_coordinates"] = [[0.01, -0.005]]
    row["emitted_brackets"] = [
        {
            "lower_parameter": -0.01,
            "lower_projected_residual": -1.0,
            "midpoint_coordinates": [0.01, -0.005],
            "unit_direction": [1.0, 0.0],
            "upper_parameter": 0.01,
            "upper_projected_residual": 1.0,
        }
    ]
    row["assessor"]["valid_refinement_seed"] = True  # type: ignore[index]
    row["assessor"]["matched_isolated_root_classes"] = []  # type: ignore[index]
    row["status"] = "representation_specific_status"

    result = MODULE.aggregate_documents(documents)
    diagnostic = result["isotropic_representation_diagnostic"]
    assert result["representation_disagreement_count"] == 0
    assert result["t0_conformance_zero"] is True
    assert diagnostic["promotion_authority"] is False
    assert diagnostic["activation_count_spread"] == 1
    assert diagnostic["by_representation"]["orthogonal"]["activation_count"] == 1


def test_multi_root_assessor_classes_are_not_collapsed() -> None:
    documents = good_documents()
    for document in documents[:3]:
        row = _find_row(document, MODULE.COMBINED, 1)
        row["assessor"]["matched_isolated_root_classes"] = [  # type: ignore[index]
            "root-1",
            "root-extra",
        ]

    result = MODULE.aggregate_documents(documents)
    metric = result["arm_metrics"][MODULE.COMBINED]
    assert "class-01::root-extra" in metric["matched_isolated_root_classes"]
    assert metric["matched_isolated_root_class_count"] == 19
    assert result["representation_disagreement_count"] == 0

    duplicate = good_documents()
    row = _find_row(duplicate[0], MODULE.COMBINED, 1)
    row["assessor"]["matched_isolated_root_classes"] = ["root-1", "root-1"]  # type: ignore[index]
    with pytest.raises(ValueError, match="must be unique"):
        MODULE.aggregate_documents(duplicate)


@pytest.mark.parametrize(
    ("arm", "start"),
    (
        (MODULE.WEAK, 2),
        (MODULE.ISOTROPIC, 1),
        (MODULE.WEAK_NO_EMIT, 2),
    ),
)
def test_weak_family_has_no_root_recall_authority(arm: str, start: int) -> None:
    row = _find_row(good_documents()[0], arm, start)
    row["assessor"]["matched_isolated_root_classes"] = ["forbidden-root"]  # type: ignore[index]
    with pytest.raises(ValueError, match="may not claim isolated-root recall"):
        MODULE._validate_row(row)

    assert (
        MODULE._class_tokens(
            {
                "arm": arm,
                "assessor": {"matched_isolated_root_classes": ["forbidden-root"]},
                "class_id": "class-guard",
            }
        )
        == set()
    )


def test_nonadvancing_performance_never_becomes_bounded_negative() -> None:
    documents = good_documents()
    for document in documents:
        row = _find_row(document, MODULE.ADAPTED, 1)
        row["activation_observables"] = {
            "cross_tier_confirmed": False,
            "newton_step_accepted": False,
            "tier_started": False,
        }
        row["emission_kind"] = "none"
        row["emitted_seed_coordinates"] = []
        row["status"] = "unknown"
        row["reason"] = "not_applicable"
        row["mechanism_diagnostics"] = _adaptive_diagnostics(confirmed=False)
        row["assessor"]["valid_refinement_seed"] = False  # type: ignore[index]
        row["assessor"]["matched_isolated_root_classes"] = []  # type: ignore[index]

    result = MODULE.aggregate_documents(documents)
    decision = result["candidate_decisions"][MODULE.ADAPTED]
    assert result["t0_conformance_zero"] is True
    assert decision["causal_classification"] == "MECHANISM_UNEXERCISED"
    assert decision["direct_bounded_mechanism_negative_authority"] is False
    assert "BOUNDED" not in MODULE.canonical_json(decision)
