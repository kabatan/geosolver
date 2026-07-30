#!/usr/bin/env python3
"""Static, source-only audit for the semantic cut-bundle connector gate.

This program intentionally does not import or execute the solver.  It reads the
hash-bound current-campaign composition and reports whether the already
existing local-attempt and aggregate-telemetry seams can support the D0
candidate without inferring hidden state from evaluator point order.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Mapping


HERE = Path(__file__).resolve().parent
CANDIDATES = HERE.parent
TARGET = CANDIDATES / "archive_progressive_hybrid_exact_outer_v1"
PROGRESSIVE = CANDIDATES / "progressive_adaptive_hybrid_v1"
RUNTIME = Path(
    os.environ.get(
        "GEOTARGET_ARCHIVE_EXACT_OUTER_RUNTIME_ROOT",
        "/home/kabatan/work/solver-experiment-runtime/solver",
    )
).resolve()

PATHS = {
    "target_worker": TARGET / "worker.py",
    "target_scheduler_shim": TARGET / "scheduler_shim.py",
    "progressive_search_adapter": PROGRESSIVE / "search_adapter.py",
    "progressive_search_worker": PROGRESSIVE / "search_worker.py",
    "deep_search_adapter": (
        RUNTIME
        / "research/experiments/EXP-V15-243-001/candidates/"
        "deep_scheduler/search_adapter.py"
    ),
    "current_local_adapter": (
        RUNTIME
        / "research/experiments/EXP-REAL61-008/"
        "hybrid_direct_broyden_tr_lm_v9/"
        "corrective_nearroot_strict_restart_v2/adapter.py"
    ),
    "current_local_kernel": (
        RUNTIME
        / "research/experiments/EXP-REAL61-008/"
        "hybrid_direct_broyden_tr_lm_v9/"
        "corrective_nearroot_strict_restart_v2/candidate.py"
    ),
    "retained_local_kernel": (
        RUNTIME
        / "research/experiments/EXP-REAL61-008/"
        "hybrid_direct_broyden_tr_lm_v9/"
        "corrective_accepted_invalid_v1/candidate.py"
    ),
    "ordinary_local_kernel": (
        RUNTIME
        / "research/experiments/EXP-REAL61-008/"
        "hybrid_direct_broyden_tr_lm_v9/candidate.py"
    ),
    "source_state_kernel": (
        RUNTIME
        / "research/experiments/EXP-REAL61-006/analytic_jacobian/candidate.py"
    ),
}

EXPECTED_SHA256 = {
    "target_worker": "6948cdb468601b53c6a2034ee3b4fd92971898f79899bb0a025be5abafe5c9a8",
    "target_scheduler_shim": "b3b9df6062dc0aa603fc5da02ae2eefa0947721eafe9069bf545af75747350e0",
    "progressive_search_adapter": "4b386e3706df0e2dc3cf0b14df4ca8e7427316ab3c17fb690983ba897657f4ea",
    "progressive_search_worker": "a19339445c55542bd849c861dc179c6a225c60d2c12e49c90e3f338c80356ce6",
    "deep_search_adapter": "1cd81d7011fc1da07f31540c64e44d4e669775873bd2432e1e61bdbdf76eecad",
    "current_local_adapter": "cda4e348ce1bb848af84afaba062c931ec5f1ebf882bdb8cf122df0366e75dc2",
    "current_local_kernel": "d2904af6e1f0f0dbc8432dfb2adf3039e28c502131df45ffdd3bfde42f7acafc",
    "retained_local_kernel": "3575d816897fafe0e696141f20c063ae338cfc51e7aebe610cd1a625d63fdc2b",
    "ordinary_local_kernel": "e9c9bd7fc950baafdb90b8899c86ef6286da539b868f6fd0e00664b709dd0caa",
    "source_state_kernel": "9b1a8117c39d93e2c0b72b2fd1f18b49976730630ab664d0b45843d1ee90e35d",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_sources() -> tuple[dict[str, str], dict[str, str]]:
    observed = {
        name: _sha256(path) if path.is_file() else "MISSING"
        for name, path in PATHS.items()
    }
    if observed != EXPECTED_SHA256:
        raise RuntimeError("current-campaign source closure changed")
    return observed, {
        name: path.read_text(encoding="utf-8") for name, path in PATHS.items()
    }


def _all(source: str, needles: tuple[str, ...]) -> bool:
    return all(needle in source for needle in needles)


def collect_audit() -> Mapping[str, object]:
    observed, source = _read_sources()
    ordinary = source["ordinary_local_kernel"]
    retained = source["retained_local_kernel"]
    state = source["source_state_kernel"]
    deep = source["deep_search_adapter"]
    target = source["target_worker"]
    progressive = source["progressive_search_adapter"]

    local_fields = {
        "accepted_anchor_object": _all(
            ordinary,
            (
                "current = _ROW._AD._make_state",
                "current = trial",
                "accepted, reason = _ROW._ROW._raw_nonmonotone_accept",
            ),
        ),
        "ordinary_gn_lm_trial_object": _all(
            ordinary,
            (
                "trial = _ROW._AD._make_state",
                "step, rank = _RUIZ._linear_step",
                "damping",
            ),
        ),
        "semantic_valid_boolean": _all(
            state,
            ("semantics_valid: bool", "observation.semantics_valid"),
        ),
        "jacobian_and_residual": _all(
            ordinary,
            ("direct_model", "current.augmented", "current.relation_inf"),
        ),
        "trust_radius": "trust_radius" in ordinary,
        "rank": "step, rank = _RUIZ._linear_step" in ordinary,
        "start_local_scale": "variable_scale" in ordinary,
        "same_attempt_attribution": _all(
            ordinary,
            ("def solve_local(", "current = trial", "trial = _ROW._AD._make_state"),
        ),
        # Neither the source observation/state nor this local attempt receives
        # a branch/guard token.  Source text mentioning that branches are
        # retained in a manifest is not a runtime token.
        "branch_token": "branch_token" in ordinary or "branch_token" in state,
    }

    aggregate_required = (
        "accepted_anchor_semantics_valid",
        "ordinary_trial_semantics_valid",
        "accepted_anchor_sequence",
        "ordinary_trial_sequence",
        "anonymous_graph_stratum",
        "anonymous_guard_stratum",
        "same_callback_additional_source_valid_proposals",
    )
    aggregate_present = {
        field: field in deep for field in aggregate_required
    }
    endpoint_only = _all(
        deep,
        (
            "self.has_assessment",
            "self.semantics_valid",
            "self.point",
            "def assessed_endpoint(",
        ),
    )
    counter_only = _all(
        ordinary,
        ("semantic_invalid_trials", "semantic_invalid_refresh_requests"),
    )
    repeated_churn_attributable = all(aggregate_present.values())
    qualifying_strata = 0 if not repeated_churn_attributable else None

    authority = {
        "positive_dimensional_final_mode": (
            "CONFIRM_ALL_AUTHORITIES" if "CONFIRM_ALL_AUTHORITIES" in target else None
        ),
        "ordinary_hp_installed_boundary": (
            "BASE._run_hp_candidate is not OUTER._run_exact_outer" in target
        ),
        "zero_dimensional_source_authority_preserved": _all(
            target,
            (
                "zero_dimensional_route_uses_existing_source_exact_authority",
                "progressive_search_invoked_for_zero_dimensional_route\": False",
                "exact_outer_invoked_for_zero_dimensional_route\": False",
            ),
        ),
    }
    quota = {
        "ordinary_baseline_at_least_0_75": (
            "if arm == CONTROL" in progressive
            and "return BASE.run_local_arm(BASE.CONTROL" in progressive
        ),
        "side_connector_created": False,
        "side_fraction": 0.0,
        "maximum_cuts": 0,
    }
    fixed_cap_caveat = {
        "invalid_evaluation_reduction_observable": counter_only,
        "same_callback_additional_source_valid_proposal_observable": aggregate_present[
            "same_callback_additional_source_valid_proposals"
        ],
        "promotion_claim_allowed": False,
    }
    blockers = []
    if not local_fields["branch_token"]:
        blockers.append("existing local-attempt seam has no branch token")
    if not repeated_churn_attributable:
        blockers.append(
            "aggregate telemetry cannot attribute repeated valid-to-invalid ordinary trials"
        )
    if qualifying_strata == 0:
        blockers.append("zero qualifying anonymous graph/guard strata are provable")
    if not fixed_cap_caveat["same_callback_additional_source_valid_proposal_observable"]:
        blockers.append(
            "D0 fixed-cap caveat cannot be closed by additional-valid-proposal telemetry"
        )

    return {
        "schema_version": "geotarget.exp-v15-243.semantic-cut-bundle-seam-audit/v1",
        "status": "STOP_BEFORE_CONNECTOR",
        "source_only_static_audit": True,
        "formal_cpu_used": False,
        "execute_or_scorer_or_truth_used": False,
        "individual_result_artifact_used": False,
        "current_campaign_target": "archive_progressive_hybrid_exact_outer_v1",
        "source_sha256": observed,
        "local_attempt_fields": local_fields,
        "aggregate_callback_structure": {
            "latest_assessed_endpoint_only": endpoint_only,
            "semantic_invalid_counter_only": counter_only,
            "required_fields_present": aggregate_present,
            "repeated_valid_to_invalid_churn_attributable": repeated_churn_attributable,
            "qualifying_anonymous_graph_guard_strata": qualifying_strata,
            "minimum_required_strata": 2,
        },
        "fixed_cap_caveat": fixed_cap_caveat,
        "quota": quota,
        "authority": authority,
        "blockers": blockers,
        "connector": {
            "created": False,
            "reason": "mandatory source seam and activation gates failed",
        },
        "reopen_gate": [
            "an existing candidate-private local-attempt seam supplies a stable branch token",
            "source-only aggregate telemetry attributes accepted-anchor to ordinary-trial transitions",
            "repeated valid-to-invalid churn is present in at least two anonymous graph/guard strata",
            "the same callback ledger reports additional source-valid proposals versus ordinary path",
        ],
    }


def main() -> None:
    print(json.dumps(collect_audit(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
