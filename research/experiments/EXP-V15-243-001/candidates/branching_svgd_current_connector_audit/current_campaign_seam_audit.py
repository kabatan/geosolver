#!/usr/bin/env python3
"""Hash-bound, source-only audit of the current Branching-SVGD connector seam.

No solver, input case, scorer, truth, result, manifest, or formal runner is
imported or executed.  The audit reads only candidate/runtime source bytes.
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

PATHS = {
    "progressive_adapter": HERE.parent / "progressive_local_budget_v1/search_adapter.py",
    "progressive_worker": HERE.parent / "progressive_local_budget_v1/search_worker.py",
    "adaptive_adapter": HERE.parent / "progressive_adaptive_hybrid_v1/search_adapter.py",
    "adaptive_worker": HERE.parent / "progressive_adaptive_hybrid_v1/search_worker.py",
    "adaptive_full_wrapper": HERE.parent / "progressive_adaptive_hybrid_v1/full_wrapper.py",
    "deep_adapter": RUNTIME_ROOT / "research/experiments/EXP-V15-243-001/candidates/deep_scheduler/search_adapter.py",
    "current_map_adapter": RUNTIME_ROOT / (
        "research/experiments/EXP-REAL61-008/hybrid_direct_broyden_tr_lm_v9/"
        "corrective_nearroot_strict_restart_v2/adapter.py"
    ),
    "exact_outer": RUNTIME_ROOT / "research/experiments/EXP-V15-243-001/candidates/exact_outer_decorator/worker.py",
    "exact_authority": RUNTIME_ROOT / "research/experiments/EXP-V15-243-001/candidates/exact_outer_decorator/authority_boundary.py",
    "zero_worker": RUNTIME_ROOT / "research/experiments/EXP-V15-243-001/champion_v2/worker.py",
    "poc_wrapper": RUNTIME_ROOT / (
        "research/experiments/EXP-V15-243-001/candidates/"
        "point_on_circle_periodic_semantics/champion_v2_wrapper.py"
    ),
}

EXPECTED_SHA256 = {
    "progressive_adapter": "244c6125ce7a51d03368bc514ab5f99f1e3e0dffa989a678c70fe0ffc5e30d94",
    "progressive_worker": "c60752971a5e7bd95d8e4b73151123457961874f191cb0ead877bb08de812332",
    "adaptive_adapter": "4b386e3706df0e2dc3cf0b14df4ca8e7427316ab3c17fb690983ba897657f4ea",
    "adaptive_worker": "a19339445c55542bd849c861dc179c6a225c60d2c12e49c90e3f338c80356ce6",
    "adaptive_full_wrapper": "4c4640a3bce5719d66f577c0093eabe93916476e319b8a595003a16f73dfb9b4",
    "deep_adapter": "1cd81d7011fc1da07f31540c64e44d4e669775873bd2432e1e61bdbdf76eecad",
    "current_map_adapter": "cda4e348ce1bb848af84afaba062c931ec5f1ebf882bdb8cf122df0366e75dc2",
    "exact_outer": "05650c1016f3974c0f74845037c76604eb38f2f4a337cc700721f0e148d9d3f7",
    "exact_authority": "a36520a416d0b8c900bca6b79192c7014812c9b1270be09248347f0f19e167e9",
    "zero_worker": "241128047481cc8a428ff99dcb9d840cbc2ade3e87ddb564bb1a920fe10346ca",
    "poc_wrapper": "0fc41efe21ab029e74ab8c3112d42271057d4dfeb808b52fea11500c2ae7003d",
}

D0 = {
    "branch": "codex/exp-branching-svgd-d0",
    "commit": "9cfdabc08de00ae643330ffbf82c00ea3b1532e8",
    "mechanism_sha256": "7304dad59cad99b9d7cd29f839b14d5fd931eea2db1dd3accf037f18c9b1ad9a",
    "fixed_mechanics": [
        "roles:E/O/S",
        "role-specific-offspring",
        "old-particle-retention",
        "uniform-unique-spine",
        "deaths:0",
        "count-matched-immigration-control",
    ],
}

EXCLUDED_NONCURRENT_TAIL = {
    "branch": "codex/exp-progressive-exact-particle-tail",
    "commit": "742e7f4dec0efbc46a90b38d6c6ff444cb9ffb4a",
    "scheduler_sha256": "20e186579a367439ba083c85ee90a5adf0cc3a7d5b95ca9b573144bc6f4c251b",
    "candidate_sha256": "1d24ab131de635ef47c5f9f2230822f3d62a6d7b5787be95e26089d59c924a4e",
    "tail_wrapper_sha256": "029df7d746e5b539c28280ab5e1aaeb2abac9a4942648ec23b62ebe7c9d8c572",
    "reason": (
        "unmerged non-current fixed-particle consensus/equality-force framework; "
        "not role-coloured Branching SVGD and cannot preserve the frozen D0 mechanism"
    ),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _has_all(text: str, tokens: tuple[str, ...]) -> bool:
    return all(token in text for token in tokens)


def audit(paths: Mapping[str, Path] = PATHS) -> dict[str, object]:
    observed = {
        name: (_sha256(path) if path.is_file() else "MISSING")
        for name, path in paths.items()
    }
    hash_binding_valid = observed == EXPECTED_SHA256
    sources = {
        name: (_text(path) if path.is_file() else "") for name, path in paths.items()
    }

    progressive_reports_scalar_replay = _has_all(
        sources["progressive_worker"],
        (
            "evaluate_float_residual",
            "evaluate_guard",
            "evaluate_float_hard_feasibility",
            '"residual_inf"',
            '"guard_ok"',
            '"hard_feasible"',
        ),
    )
    progressive_exposes_vector_jacobian_bounds = _has_all(
        sources["progressive_worker"],
        (
            '"residual_vector"',
            '"jacobian"',
            '"lower_bounds"',
            '"upper_bounds"',
            '"branch_token"',
        ),
    )
    adapters_declare_no_checkpoint = _has_all(
        sources["progressive_adapter"],
        (
            '"current_checkpoint_support": False',
            '"current_resume_mode": "charged original-start prefix reexecution"',
        ),
    ) and _has_all(
        sources["adaptive_adapter"],
        (
            '"current_checkpoint_support": False',
            '"current_resume_mode": "charged original-start reexecution"',
        ),
    )
    deep_returns_endpoint_only = _has_all(
        sources["deep_adapter"],
        (
            "checkpoint=None",
            "checkpoint_resumable=False",
            '"current_checkpoint_support": False',
            '"endpoint": endpoint',
            '"residual_inf": assessment.residual_inf',
        ),
    )
    deep_returns_branching_state = _has_all(
        sources["deep_adapter"],
        (
            '"residual_vector"',
            '"jacobian"',
            '"lower_bounds"',
            '"upper_bounds"',
            '"branch_token"',
            '"rng_state"',
        ),
    )
    baseline_after_tail_hook = _has_all(
        sources["adaptive_full_wrapper"],
        (
            "baseline_runs_to_completion_before_side_tail",
            "def _run_surplus_tail",
            "side_callback_fraction_cap",
            "side_wall_fraction_cap",
        ),
    )
    adaptive_rebinds_search_instead = _has_all(
        sources["adaptive_full_wrapper"],
        (
            "base.SEARCH_WORKER = SEARCH_WORKER",
            "base.SEARCH_ADAPTER = SEARCH_ADAPTER",
            "base.SEARCH_CANDIDATE = SEARCH_CANDIDATE",
        ),
    )

    exact_outer_available = _has_all(
        sources["exact_outer"],
        (
            'CONFIRM_ALL_AUTHORITIES = "CONFIRM_ALL_AUTHORITIES"',
            "MODE = os.environ.get(MODE_ENV, CONFIRM_ALL_AUTHORITIES)",
            "BASE._run_hp_candidate = _run_exact_outer",
            '"ordinary_descriptor_is_final_authority": False',
        ),
    ) and "primitive minimal polynomial" in sources["exact_authority"]
    zero_dimensional_authority_available = _has_all(
        sources["zero_worker"],
        (
            "source-exact zero-dimensional bypass",
            '"zero_dimensional_search_bypass": True',
            "ZERO.run_zero_dimensional_authority",
        ),
    ) and "preserving its zero-dimensional authority verbatim" in sources["poc_wrapper"]

    # A source stratum can only count when the current callable seam itself can
    # supply every BSVGD input without a new kernel.  That prerequisite is false,
    # so reading development inputs could not turn static compatibility into an
    # activation and is deliberately avoided.
    current_callable_seam_complete = bool(
        progressive_exposes_vector_jacobian_bounds
        and deep_returns_branching_state
        and baseline_after_tail_hook
    )
    anonymous_static_activation_strata = 0
    static_activation_gate = anonymous_static_activation_strata >= 2
    same_callback_replay_gate = bool(
        current_callable_seam_complete and progressive_reports_scalar_replay
    )
    quota_gate = baseline_after_tail_hook
    authority_gate = exact_outer_available and zero_dimensional_authority_available
    connector_allowed = bool(
        hash_binding_valid
        and static_activation_gate
        and same_callback_replay_gate
        and quota_gate
        and authority_gate
    )

    return {
        "schema": "geotarget.branching-svgd-current-connector-audit/v1",
        "decision": "READY_THIN_CONNECTOR" if connector_allowed else "STOP_BEFORE_CONNECTOR",
        "d0": D0,
        "excluded_noncurrent_tail": EXCLUDED_NONCURRENT_TAIL,
        "hash_binding_valid": hash_binding_valid,
        "audited_sha256": observed,
        "current_progressive_adaptive_seam": {
            "scalar_source_replay_present": progressive_reports_scalar_replay,
            "raw_residual_jacobian_bounds_guard_token_exposed": (
                progressive_exposes_vector_jacobian_bounds
            ),
            "bindings_declare_no_checkpoint": adapters_declare_no_checkpoint,
            "deep_returns_endpoint_and_scalar_assessment_only": deep_returns_endpoint_only,
            "deep_returns_complete_branching_state": deep_returns_branching_state,
            "baseline_completed_then_surplus_tail_hook_present": baseline_after_tail_hook,
            "current_adaptive_rebinds_search_instead_of_postbaseline_tail": (
                adaptive_rebinds_search_instead
            ),
            "current_callable_seam_complete": current_callable_seam_complete,
        },
        "activation_gate": {
            "required_anonymous_static_strata": 2,
            "observed_anonymous_static_strata": anonymous_static_activation_strata,
            "passed": static_activation_gate,
            "development_or_formal_sources_opened": False,
            "reason": (
                "the callable current seam is incomplete before any source can "
                "qualify; inspecting case inputs cannot repair a missing API"
            ),
        },
        "budget_and_lifecycle_gate": {
            "baseline_minimum": 0.75,
            "side_callback_and_wall_maximum": 0.25,
            "current_hook_proves_baseline_first_and_immutable": quota_gate,
            "passed": quota_gate,
        },
        "replay_and_authority_gate": {
            "same_callback_replay_available_to_side": same_callback_replay_gate,
            "exact_outer_confirm_all_authorities_available": exact_outer_available,
            "zero_dimensional_source_exact_authority_available": (
                zero_dimensional_authority_available
            ),
            "all_positive_dimensional_side_emissions_proven_exact_authority": False,
            "passed": False,
            "reason": "authorities exist, but no current side-emission route reaches them",
        },
        "connector_created": False,
        "kernel_or_population_framework_created": False,
        "count_matched_immigration_connector_run": False,
        "formal_execute_scorer_truth_or_case_results_used": False,
        "cpus_zero_through_six_used": False,
        "reopen_gate": [
            (
                "the hash-bound current progressive/adaptive BASE adds a post-completion "
                "surplus-tail hook that cannot alter the baseline RESULT bytes and enforces "
                "baseline>=75%, side wall/callback<=25%"
            ),
            (
                "that same callback ledger exposes residual vector, Jacobian or score, "
                "semantic validity, source lower/upper bounds, guard/hard feasibility, "
                "and branch token without a second numerical kernel or population framework"
            ),
            (
                "a truth-free static audit through that callable hook activates unchanged "
                "Branching-SVGD D0 in at least two anonymous source strata, while unsupported "
                "sources fail closed before offspring generation"
            ),
            (
                "the same-callback count-matched immigration control is callable with the "
                "identical population schedule and replay/semantic validation"
            ),
            (
                "every positive-dimensional side proposal is fresh-replayed and enters only "
                "global exact_outer CONFIRM_ALL_AUTHORITIES; the champion-v2 zero-dimensional "
                "objects and route remain identity-preserved"
            ),
        ],
    }


def main() -> None:
    print(json.dumps(audit(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
