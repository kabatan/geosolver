from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent


def _load():
    name = "geotarget_semantic_cut_bundle_connector_static_audit"
    specification = importlib.util.spec_from_file_location(name, HERE / "audit_seam.py")
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


AUDIT = _load()


def test_local_attempt_has_all_fields_except_branch_token() -> None:
    result = AUDIT.collect_audit()
    fields = result["local_attempt_fields"]
    assert fields == {
        "accepted_anchor_object": True,
        "ordinary_gn_lm_trial_object": True,
        "semantic_valid_boolean": True,
        "jacobian_and_residual": True,
        "trust_radius": True,
        "rank": True,
        "start_local_scale": True,
        "same_attempt_attribution": True,
        "branch_token": False,
    }


def test_aggregate_cannot_establish_two_strata_or_fixed_cap_conversion() -> None:
    result = AUDIT.collect_audit()
    aggregate = result["aggregate_callback_structure"]
    assert aggregate["latest_assessed_endpoint_only"] is True
    assert aggregate["semantic_invalid_counter_only"] is True
    assert aggregate["repeated_valid_to_invalid_churn_attributable"] is False
    assert aggregate["qualifying_anonymous_graph_guard_strata"] == 0
    assert aggregate["minimum_required_strata"] == 2
    assert not any(aggregate["required_fields_present"].values())
    assert (
        result["fixed_cap_caveat"][
            "same_callback_additional_source_valid_proposal_observable"
        ]
        is False
    )


def test_stop_does_not_weaken_exact_outer_or_zero_dimensional_authority() -> None:
    result = AUDIT.collect_audit()
    assert result["status"] == "STOP_BEFORE_CONNECTOR"
    assert result["connector"]["created"] is False
    assert result["quota"]["side_fraction"] == 0.0
    assert result["quota"]["maximum_cuts"] == 0
    assert result["authority"]["positive_dimensional_final_mode"] == (
        "CONFIRM_ALL_AUTHORITIES"
    )
    assert result["authority"]["ordinary_hp_installed_boundary"] is True
    assert result["authority"]["zero_dimensional_source_authority_preserved"] is True


def test_audit_is_source_only_and_uses_no_result_artifact() -> None:
    result = AUDIT.collect_audit()
    assert result["source_only_static_audit"] is True
    assert result["formal_cpu_used"] is False
    assert result["execute_or_scorer_or_truth_used"] is False
    assert result["individual_result_artifact_used"] is False
    assert all("results" not in str(path) for path in AUDIT.PATHS.values())


def test_frozen_audit_and_arm_hash_match_entrypoint() -> None:
    frozen = json.loads((HERE / "SEAM_AUDIT.json").read_text(encoding="utf-8"))
    arm = json.loads((HERE / "arm.json").read_text(encoding="utf-8"))
    assert frozen == AUDIT.collect_audit()
    assert arm["status"] == frozen["status"]
    assert arm["connector_created"] is False
    assert arm["mechanism_hash"] == hashlib.sha256(
        (HERE / arm["entrypoint"]).read_bytes()
    ).hexdigest()
