#!/usr/bin/env python3
"""Static, source-only audit for a current-campaign AMS connector seam.

No solver, case, scorer, truth, or formal runner is imported or executed.
The audit asks only whether already-existing candidate-private code can expose
the *current champion map's* complete local checkpoint in one process.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Mapping


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[4]
RUNTIME_ROOT = Path(
    os.environ.get(
        "GEOTARGET_EXPERIMENT_RUNTIME",
        "/home/kabatan/work/solver-experiment-runtime/solver",
    )
).resolve()

LOCAL_PROGRESSIVE = (
    HERE.parent / "progressive_local_budget_v1/search_adapter.py"
)
LOCAL_ADAPTIVE = (
    HERE.parent / "progressive_adaptive_hybrid_v1/search_adapter.py"
)
LOCAL_FULL_WRAPPER = (
    HERE.parent / "progressive_adaptive_hybrid_v1/full_wrapper.py"
)
LOCAL_EXACT_OUTER_ARCHIVE = (
    HERE.parent / "archive_progressive_hybrid_exact_outer_v1/worker.py"
)
RUNTIME_CANDIDATES = (
    RUNTIME_ROOT / "research/experiments/EXP-V15-243-001/candidates"
)
DEEP_ADAPTER = RUNTIME_CANDIDATES / "deep_scheduler/search_adapter.py"
WAVE10_KERNEL = RUNTIME_CANDIDATES / "wave10_checkpoint_kernel/checkpoint_kernel.py"
STATEFUL_ADAPTER = RUNTIME_CANDIDATES / "stateful_halving_scheduler/v15_adapter.py"
STATEFUL_KERNEL = RUNTIME_CANDIDATES / "stateful_halving_scheduler/candidate.py"
STATEFUL_DECISION = RUNTIME_CANDIDATES / "stateful_halving_scheduler/STOP_DECISION.md"
PRIOR_SEAM_PROBE = (
    RUNTIME_CANDIDATES
    / "wave18_projector_unordered_portal_g3_connection/probe_existing_seam.py"
)
CURRENT_NEARROOT = (
    RUNTIME_ROOT
    / "research/experiments/EXP-REAL61-008/hybrid_direct_broyden_tr_lm_v9/"
    "corrective_nearroot_strict_restart_v2/candidate.py"
)

EXPECTED_SHA256 = {
    "local_progressive": "244c6125ce7a51d03368bc514ab5f99f1e3e0dffa989a678c70fe0ffc5e30d94",
    "local_adaptive": "4b386e3706df0e2dc3cf0b14df4ca8e7427316ab3c17fb690983ba897657f4ea",
    "local_full_wrapper": "4c4640a3bce5719d66f577c0093eabe93916476e319b8a595003a16f73dfb9b4",
    "deep_adapter": "1cd81d7011fc1da07f31540c64e44d4e669775873bd2432e1e61bdbdf76eecad",
    "wave10_kernel": "da66047b399f01c5ee5ec6b042e4ae6ec279a5e43b982d82d103cf43daa210f4",
    "current_nearroot": "d2904af6e1f0f0dbc8432dfb2adf3039e28c502131df45ffdd3bfde42f7acafc",
    "stateful_adapter": "7a56d011b92bf1dcede9b39c017aae6a4f805e6462ae09d6cf06464702159c64",
    "stateful_kernel": "fad048ac15cbc6ffba03c6d1169e154f81a1c7be26211775b92c020e410d6c84",
}
WAVE10_MATURE_SHA256 = (
    "e9c9bd7fc950baafdb90b8899c86ef6286da539b868f6fd0e00664b709dd0caa"
)
CURRENT_NEARROOT_PATCHED_SOURCE_SHA256 = (
    "036f48e5b737779ed75e77a531b63da9c954a86f30be27b9d216328188181a5c"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _has_all(text: str, tokens: tuple[str, ...]) -> bool:
    return all(token in text for token in tokens)


def audit() -> Mapping[str, object]:
    paths = {
        "local_progressive": LOCAL_PROGRESSIVE,
        "local_adaptive": LOCAL_ADAPTIVE,
        "local_full_wrapper": LOCAL_FULL_WRAPPER,
        "deep_adapter": DEEP_ADAPTER,
        "wave10_kernel": WAVE10_KERNEL,
        "current_nearroot": CURRENT_NEARROOT,
        "stateful_adapter": STATEFUL_ADAPTER,
        "stateful_kernel": STATEFUL_KERNEL,
    }
    hashes = {name: _sha256(path) for name, path in paths.items()}
    hash_binding_valid = hashes == EXPECTED_SHA256
    progressive = _read(LOCAL_PROGRESSIVE)
    adaptive = _read(LOCAL_ADAPTIVE)
    deep = _read(DEEP_ADAPTER)
    wave10 = _read(WAVE10_KERNEL)
    nearroot = _read(CURRENT_NEARROOT)
    stateful_adapter = _read(STATEFUL_ADAPTER)
    stateful_kernel = _read(STATEFUL_KERNEL)
    stateful_decision = _read(STATEFUL_DECISION)
    exact_outer = _read(LOCAL_EXACT_OUTER_ARCHIVE)
    prior_probe = _read(PRIOR_SEAM_PROBE)

    current_search_declares_no_checkpoint = bool(
        _has_all(
            progressive,
            (
                '"current_checkpoint_support": False',
                '"current_resume_mode": "charged original-start prefix reexecution"',
            ),
        )
        and _has_all(
            adaptive,
            (
                '"current_checkpoint_support": False',
                '"current_resume_mode": "charged original-start reexecution"',
            ),
        )
    )
    deep_rejects_and_drops_checkpoint = _has_all(
        deep,
        (
            "if checkpoint is not None:",
            'raise AssertionError("frozen v15 binding cannot resume opaque state")',
            "checkpoint=None",
            "checkpoint_resumable=False",
            '"current_checkpoint_support": False',
            '"original-start prefix reexecution; every callback charged"',
        ),
    )
    deep_child_returns_complete_state = bool(
        "CheckpointState" in deep
        or "direct_model" in deep
        or "pending_trial_x" in deep
    )
    wave10_has_complete_state = _has_all(
        wave10,
        (
            "class CheckpointState:",
            "def advance_one(state: CheckpointState)",
            "current: object | None",
            "best: object | None",
            "direct_model: np.ndarray | None",
            "trust_radius: float",
            "damping: float",
            "pending_trial_x: np.ndarray | None",
            "rng: np.random.Generator | None",
        ),
    )
    wave10_bound_to_old_mature = bool(
        f'MATURE_SHA256 = "{WAVE10_MATURE_SHA256}"' in wave10
    )
    current_map_is_transformed = _has_all(
        nearroot,
        (
            "corrective_accepted_invalid_v1/candidate.py",
            "nearroot_strict_restart_attempts",
            "PATCHED_SOURCE_SHA256",
            "_STRICT_SOLVE_LOCAL",
        ),
    )
    wave10_represents_current_map = bool(
        wave10_has_complete_state
        and CURRENT_NEARROOT_PATCHED_SOURCE_SHA256 in wave10
    )
    prior_probe_agrees = _has_all(
        prior_probe,
        (
            'decision = "READY_G3" if connected else "HOLD_MISSING_COMPLETE_MAP_SEAM"',
            '"represents_current_champion_complete_map"',
            '"restart_one_iteration_accepted_as_complete_map": False',
        ),
    )
    stateful_is_not_wave10_hook = bool(
        "wave10_checkpoint_kernel" not in stateful_adapter
        and "wave10_checkpoint_kernel" not in stateful_kernel
        and "class LaneCheckpoint:" in stateful_kernel
        and "SCHEDULER.run_scheduler" in stateful_adapter
    )
    stateful_is_prohibited_stopped_lineage = bool(
        "STOPPED / NOT ADOPTED" in stateful_decision
        and "successive halving" in stateful_kernel.lower()
    )
    exact_outer_authority_exists = _has_all(
        exact_outer,
        (
            'CONFIRM_ALL_AUTHORITIES = "CONFIRM_ALL_AUTHORITIES"',
            "BASE._run_hp_candidate is not OUTER._run_exact_outer",
            "zero-dimensional source authority changed",
        ),
    )

    connector_possible_without_new_kernel_or_framework = bool(
        hash_binding_valid
        and not current_search_declares_no_checkpoint
        and not deep_rejects_and_drops_checkpoint
        and deep_child_returns_complete_state
        and wave10_represents_current_map
    )
    decision = (
        "READY_THIN_CONNECTOR"
        if connector_possible_without_new_kernel_or_framework
        else "HOLD_MISSING_CURRENT_MAP_CHECKPOINT_SEAM"
    )
    return {
        "schema_version": "geotarget.checkpoint-genealogical-ams-current-seam-audit/v1",
        "decision": decision,
        "hash_binding_valid": hash_binding_valid,
        "audited_sha256": hashes,
        "current_progressive_search": {
            "declares_checkpoint_support": not current_search_declares_no_checkpoint,
            "resume_mode": "charged original-start prefix reexecution",
            "deep_binding_rejects_supplied_checkpoint": deep_rejects_and_drops_checkpoint,
            "disposable_child_returns_complete_checkpoint_state": (
                deep_child_returns_complete_state
            ),
        },
        "wave10_checkpoint": {
            "has_complete_checkpoint_state": wave10_has_complete_state,
            "checkpointed_parent_sha256": WAVE10_MATURE_SHA256,
            "bound_to_old_mature_parent": wave10_bound_to_old_mature,
            "current_champion_nearroot_file_sha256": hashes["current_nearroot"],
            "current_champion_patched_source_sha256": (
                CURRENT_NEARROOT_PATCHED_SOURCE_SHA256
            ),
            "current_map_is_accepted_invalid_plus_nearroot_restart": (
                current_map_is_transformed
            ),
            "represents_current_champion_complete_map": wave10_represents_current_map,
        },
        "prior_candidate_surfaces": {
            "prior_static_seam_probe_agrees": prior_probe_agrees,
            "stateful_halving_uses_separate_lane_checkpoint_not_wave10": (
                stateful_is_not_wave10_hook
            ),
            "stateful_halving_is_stopped_prohibited_lineage": (
                stateful_is_prohibited_stopped_lineage
            ),
        },
        "authority_and_lifecycle": {
            "archive_exact_outer_confirm_all_authorities_exists": (
                exact_outer_authority_exists
            ),
            "zero_dimensional_authority_present": exact_outer_authority_exists,
            "historical_or_common_base_lifecycle_modified": False,
            "connector_created": False,
        },
        "connector_possible_without_new_kernel_or_framework": (
            connector_possible_without_new_kernel_or_framework
        ),
        "formal_cpus_0_through_6_used": False,
        "real_case_scorer_truth_validation_or_sealed_used": False,
        "source_or_target_emission_executed": False,
        "reopen_gate": [
            (
                "an independently motivated common-private fixed BASE exposes an "
                "in-process current-map checkpoint accepting and returning current/best, "
                "raw residual+guard state, partial/fresh J, direct Broyden model, trust "
                "radius, LM damping, pending transition, acceptance windows, refresh "
                "state, callback ledger, and RNG"
            ),
            (
                "that checkpoint kernel passes uninterrupted-versus-every-callback-cut "
                "parity for both accepted-invalid retention and the strict near-root "
                "restart, with source binding and callback/deadline accounting"
            ),
            (
                "the fixed current search binding advertises true checkpoint support "
                "without original-start reexecution and owns process lifecycle; the AMS "
                "connector only allocates <=25% and emits replayed endpoints"
            ),
            (
                "fresh replay then exact_outer CONFIRM_ALL_AUTHORITIES is proven for all "
                "positive-dimensional emissions while the existing zero-dimensional "
                "route remains object-identical"
            ),
        ],
    }


def main() -> None:
    print(json.dumps(audit(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
