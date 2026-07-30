from __future__ import annotations

import current_campaign_seam_audit as seam


def test_current_campaign_connector_is_held_without_new_infrastructure() -> None:
    result = seam.audit()
    assert result["decision"] == "HOLD_MISSING_CURRENT_MAP_CHECKPOINT_SEAM"
    assert result["hash_binding_valid"] is True
    assert result["connector_possible_without_new_kernel_or_framework"] is False
    assert result["authority_and_lifecycle"]["connector_created"] is False
    assert result["authority_and_lifecycle"][
        "historical_or_common_base_lifecycle_modified"
    ] is False


def test_current_progressive_binding_is_endpoint_only_reexecution() -> None:
    result = seam.audit()["current_progressive_search"]
    assert result["declares_checkpoint_support"] is False
    assert result["deep_binding_rejects_supplied_checkpoint"] is True
    assert result["disposable_child_returns_complete_checkpoint_state"] is False
    assert result["resume_mode"] == "charged original-start prefix reexecution"


def test_wave10_checkpoint_is_complete_but_not_current_champion_map() -> None:
    result = seam.audit()["wave10_checkpoint"]
    assert result["has_complete_checkpoint_state"] is True
    assert result["bound_to_old_mature_parent"] is True
    assert result["current_map_is_accepted_invalid_plus_nearroot_restart"] is True
    assert result["represents_current_champion_complete_map"] is False


def test_stopped_stateful_lineage_is_not_a_wave10_hook() -> None:
    result = seam.audit()["prior_candidate_surfaces"]
    assert result["prior_static_seam_probe_agrees"] is True
    assert result["stateful_halving_uses_separate_lane_checkpoint_not_wave10"] is True
    assert result["stateful_halving_is_stopped_prohibited_lineage"] is True


def test_authority_is_present_but_was_not_connected_or_executed() -> None:
    result = seam.audit()
    authority = result["authority_and_lifecycle"]
    assert authority["archive_exact_outer_confirm_all_authorities_exists"] is True
    assert authority["zero_dimensional_authority_present"] is True
    assert result["formal_cpus_0_through_6_used"] is False
    assert result["real_case_scorer_truth_validation_or_sealed_used"] is False
    assert result["source_or_target_emission_executed"] is False
    assert len(result["reopen_gate"]) == 4
