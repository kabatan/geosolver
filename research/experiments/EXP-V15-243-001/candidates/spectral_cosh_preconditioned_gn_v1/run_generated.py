"""Run the candidate-specific generated D0 and write one compact aggregate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from candidate import route_for_start, solve_attempt
from generated_cases import GeneratedCase, near_miss_cases, negative_cases, positive_cases


HERE = Path(__file__).resolve().parent


def root_is_known(case: GeneratedCase, endpoint: np.ndarray) -> bool:
    return any(np.linalg.norm(endpoint - root, ord=np.inf) <= 2e-7 for root in case.exact_roots)


def main() -> None:
    positives = positive_cases()
    negatives = negative_cases()
    near_misses = near_miss_cases()
    outcomes = []
    family = {}
    false = 0
    extra = 0
    activations = 0
    baseline_callbacks = 0
    candidate_callbacks = 0

    for case in positives + negatives + near_misses:
        baseline = solve_attempt(
            case.residual, case.jacobian, case.start, route="baseline", smooth=case.smooth,
            guards=case.guards,
        )
        candidate = solve_attempt(
            case.residual, case.jacobian, case.start, route="spectral_cosh", smooth=case.smooth,
            guards=case.guards,
        )
        baseline_correct = baseline.verified and root_is_known(case, baseline.endpoint)
        candidate_correct = candidate.verified and root_is_known(case, candidate.endpoint)
        if candidate.verified and not candidate_correct:
            false += 1
        if not case.exact_roots and candidate.verified:
            extra += 1
        win = int(candidate_correct and not baseline_correct)
        loss = int(baseline_correct and not candidate_correct)
        item = family.setdefault(case.family, {"cases": 0, "wins": 0, "losses": 0, "candidate_verified": 0})
        item["cases"] += 1
        item["wins"] += win
        item["losses"] += loss
        item["candidate_verified"] += int(candidate.verified)
        activations += candidate.activations
        baseline_callbacks += baseline.callbacks
        candidate_callbacks += candidate.callbacks
        outcomes.append({
            "family": case.family,
            "baseline_correct": baseline_correct,
            "candidate_correct": candidate_correct,
            "win": win,
            "loss": loss,
            "candidate_activations": candidate.activations,
            "candidate_fallback": candidate.fallback_reason,
        })

    wins = sum(item["win"] for item in outcomes)
    losses = sum(item["loss"] for item in outcomes)
    routes = [route_for_start(index) for index in range(40)]
    mechanism_hash = hashlib.sha256((HERE / "candidate.py").read_bytes()).hexdigest()
    aggregate = {
        "candidate": "spectral_cosh_preconditioned_gn_v1",
        "mechanism_hash": mechanism_hash,
        "generated_cases": len(outcomes),
        "positive_cases": len(positives),
        "negative_cases": len(negatives),
        "near_miss_cases": len(near_misses),
        "wins": wins,
        "losses": losses,
        "false": false,
        "extra": extra,
        "activations": activations,
        "baseline_callbacks": baseline_callbacks,
        "candidate_callbacks": candidate_callbacks,
        "callback_ratio": candidate_callbacks / baseline_callbacks,
        "portfolio_baseline_share": routes.count("baseline") / len(routes),
        "portfolio_side_share": routes.count("spectral_cosh") / len(routes),
        "families": family,
    }
    print(json.dumps(aggregate, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
