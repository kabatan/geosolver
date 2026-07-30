from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest


HERE = Path(__file__).resolve().parent


def _load():
    name = "test_progressive_local_budget_metamorphic_s0"
    path = HERE / "metamorphic_s0.py"
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


S0 = _load()


@pytest.mark.parametrize("profile", S0.PROFILES)
def test_generated_narrow_basin_and_metamorphic_decisions(profile) -> None:
    _base, expected = S0.equivalent_run(profile, "base")
    for variant in (
        "variable_permutation",
        "residual_permutation",
        "affine_scale",
    ):
        _result, observed = S0.equivalent_run(profile, variant)
        assert observed == expected


@pytest.mark.parametrize("profile", S0.PROFILES)
def test_starvation_and_partial_preemption_repromotion(profile) -> None:
    starvation = S0.starvation_run(profile)
    assert starvation["first_service_count"] == starvation["start_count"]
    assert starvation["later_start_serviced"] is True
    assert starvation["deadline_rejected_services"] >= 1
    repromotion = S0.preemption_repromotion_run(profile)
    assert repromotion["partial_evidence_repromoted"] is True
    assert repromotion["services_after_partial_evidence"] == 2


@pytest.mark.parametrize("profile", S0.PROFILES)
def test_work_accounting_faults_fail_closed(profile) -> None:
    taxonomy = S0.work_accounting_failure_taxonomy(profile)
    assert set(taxonomy) == {
        "callback_overcharge",
        "negative_callback_charge",
        "zero_charge_completed_service",
        "malformed_endpoint",
        "proposal_prefix_mutation",
        "insurance_prefix_mismatch",
    }
    assert all(
        value.startswith(("ValueError:", "AssertionError:"))
        for value in taxonomy.values()
    )


def test_complete_evidence_is_truth_free_and_both_profiles_activate() -> None:
    evidence = S0.build_evidence()
    assert evidence["status"] == "PASS"
    assert evidence["truth_used"] is False
    assert evidence["benchmark_truth_used"] is False
    assert evidence["external_case_family_problem_id_or_target_inputs"] is False
    assert evidence["synthetic_target_generated_in_harness"] is True
    assert evidence["generated_only"] is True
    assert set(evidence["profiles"]) == set(S0.PROFILES)
    for profile in evidence["profiles"].values():
        assert profile["all_start_first_service"] is True
        assert profile["narrow_basin_start_reached_deepest_rung"] is True
        assert profile["callbacks_reconciled"] is True
        assert profile["insurance_prefix_floor_holds"] is True
        assert profile["iid_regular_first_service_complete"] is True
        assert profile["each_iid_regular_source_stream_has_deep_solve"] is True
        assert all(
            row["decision_trace_equal"]
            for row in profile["metamorphic"].values()
        )
    frozen = json.loads((HERE / "METAMORPHIC_S0_EVIDENCE.json").read_text())
    assert evidence == frozen
