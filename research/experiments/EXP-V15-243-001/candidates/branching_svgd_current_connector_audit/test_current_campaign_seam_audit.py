from __future__ import annotations

from pathlib import Path

import current_campaign_seam_audit as seam


def test_current_hash_bound_audit_stops_before_connector() -> None:
    result = seam.audit()
    assert result["hash_binding_valid"] is True
    assert result["decision"] == "STOP_BEFORE_CONNECTOR"
    assert result["connector_created"] is False
    assert result["kernel_or_population_framework_created"] is False
    assert result["activation_gate"]["observed_anonymous_static_strata"] == 0
    assert result["activation_gate"]["development_or_formal_sources_opened"] is False


def test_missing_raw_state_and_tail_hook_are_the_blockers() -> None:
    result = seam.audit()
    current = result["current_progressive_adaptive_seam"]
    assert current["scalar_source_replay_present"] is True
    assert current["raw_residual_jacobian_bounds_guard_token_exposed"] is False
    assert current["bindings_declare_no_checkpoint"] is True
    assert current["deep_returns_endpoint_and_scalar_assessment_only"] is True
    assert current["deep_returns_complete_branching_state"] is False
    assert current["baseline_completed_then_surplus_tail_hook_present"] is False
    assert current["current_adaptive_rebinds_search_instead_of_postbaseline_tail"] is True


def test_authorities_exist_but_have_no_side_route() -> None:
    result = seam.audit()
    authority = result["replay_and_authority_gate"]
    assert authority["exact_outer_confirm_all_authorities_available"] is True
    assert authority["zero_dimensional_source_exact_authority_available"] is True
    assert authority["same_callback_replay_available_to_side"] is False
    assert authority["all_positive_dimensional_side_emissions_proven_exact_authority"] is False


def test_hash_tamper_fails_closed(tmp_path: Path) -> None:
    paths = dict(seam.PATHS)
    replacement = tmp_path / "progressive.py"
    replacement.write_text("# changed\n", encoding="utf-8")
    paths["progressive_adapter"] = replacement
    result = seam.audit(paths)
    assert result["hash_binding_valid"] is False
    assert result["decision"] == "STOP_BEFORE_CONNECTOR"


def test_d0_mechanics_and_reopen_gate_are_frozen() -> None:
    result = seam.audit()
    assert result["d0"]["mechanism_sha256"] == (
        "7304dad59cad99b9d7cd29f839b14d5fd931eea2db1dd3accf037f18c9b1ad9a"
    )
    mechanics = set(result["d0"]["fixed_mechanics"])
    assert {
        "roles:E/O/S",
        "role-specific-offspring",
        "old-particle-retention",
        "uniform-unique-spine",
        "deaths:0",
        "count-matched-immigration-control",
    } == mechanics
    assert result["excluded_noncurrent_tail"]["commit"] == (
        "742e7f4dec0efbc46a90b38d6c6ff444cb9ffb4a"
    )
    assert "not role-coloured Branching SVGD" in result["excluded_noncurrent_tail"][
        "reason"
    ]
    assert len(result["reopen_gate"]) == 5
