"""Run generated D0 only; no formal corpus, truth, or scorer is imported."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from candidate import route_for_start, solve_attempt
from generated_cases import GeneratedCase, negative_cases, positive_cases


HERE = Path(__file__).resolve().parent


def root_is_known(case: GeneratedCase, endpoint: np.ndarray) -> bool:
    return any(np.linalg.norm(endpoint - root, ord=np.inf) <= 3e-5 for root in case.exact_roots)


def main() -> None:
    cases = positive_cases() + negative_cases()
    families: dict[str, dict[str, int]] = {}
    wins = losses = false = extra = activations = 0
    baseline_callbacks = candidate_callbacks = 0
    callback_mismatches = 0
    nonzero_epsilon_f = nonzero_epsilon_j = 0
    stable_rank_activations = tangential_activations = 0

    for case in cases:
        baseline = solve_attempt(
            case.residual_factory(),
            case.start,
            route="baseline",
            smooth=case.smooth,
            variable_scale=case.variable_scale,
        )
        candidate = solve_attempt(
            case.residual_factory(),
            case.start,
            route="noise_sqp",
            smooth=case.smooth,
            variable_scale=case.variable_scale,
        )
        baseline_correct = baseline.verified and root_is_known(case, baseline.endpoint)
        candidate_correct = candidate.verified and root_is_known(case, candidate.endpoint)
        wins += int(candidate_correct and not baseline_correct)
        losses += int(baseline_correct and not candidate_correct)
        false += int(candidate.verified and not candidate_correct)
        extra += int(not case.exact_roots and candidate.verified)
        activations += candidate.activations
        baseline_callbacks += baseline.callbacks
        candidate_callbacks += candidate.callbacks
        callback_mismatches += int(baseline.callbacks != candidate.callbacks)
        nonzero_epsilon_f += int(any(state.epsilon_f > 0.0 for state in candidate.states))
        nonzero_epsilon_j += int(any(state.epsilon_j > 0.0 for state in candidate.states))
        stable_rank_activations += sum(
            int(state.activated and state.coarse_rank == state.fine_rank)
            for state in candidate.states
        )
        tangential_activations += sum(
            int(state.activated and state.tangential_norm > 0.0)
            for state in candidate.states
        )
        row = families.setdefault(case.family, {
            "cases": 0,
            "wins": 0,
            "losses": 0,
            "false": 0,
            "activations": 0,
        })
        row["cases"] += 1
        row["wins"] += int(candidate_correct and not baseline_correct)
        row["losses"] += int(baseline_correct and not candidate_correct)
        row["false"] += int(candidate.verified and not candidate_correct)
        row["activations"] += candidate.activations

    routes = [route_for_start(index) for index in range(100)]
    aggregate = {
        "candidate": "noise_aware_rank_sqp_v1",
        "mechanism_hash": hashlib.sha256((HERE / "candidate.py").read_bytes()).hexdigest(),
        "generated_cases": len(cases),
        "generated_families": len(families),
        "wins": wins,
        "losses": losses,
        "false": false,
        "extra": extra,
        "activations": activations,
        "stable_rank_activations": stable_rank_activations,
        "tangential_activations": tangential_activations,
        "nonzero_epsilon_f_cases": nonzero_epsilon_f,
        "nonzero_epsilon_j_cases": nonzero_epsilon_j,
        "baseline_callbacks": baseline_callbacks,
        "candidate_callbacks": candidate_callbacks,
        "callback_mismatches": callback_mismatches,
        "callback_ratio": candidate_callbacks / baseline_callbacks,
        "portfolio_baseline_share": routes.count("baseline") / len(routes),
        "portfolio_side_share": routes.count("noise_sqp") / len(routes),
        "families": families,
        "truth_or_formal_scorer_read": False,
    }
    print(json.dumps(aggregate, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
