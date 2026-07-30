"""Run the prospective source-only breadth screen and write aggregate evidence."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import numpy as np

from breadth_cases import prospective_cases
from candidate import Configuration, integration_contract, solve


HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "BREADTH_AGGREGATE.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_root(case: object, point: np.ndarray) -> bool:
    observation = case.evaluator(np.asarray(point, dtype=float).copy())
    residual = np.asarray(observation.residual, dtype=float)
    return bool(
        observation.finite
        and observation.source_valid
        and residual.size
        and np.all(np.isfinite(residual))
        and np.linalg.norm(residual, ord=np.inf) <= 1.0e-9
    )


def main() -> None:
    grouped: defaultdict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    callbacks: defaultdict[tuple[str, str], list[int]] = defaultdict(list)
    positive_family_gains: Counter[str] = Counter()
    false_promotions = 0
    control_roots = 0
    candidate_roots = 0
    total = 0

    for case in prospective_cases(12):
        total += 1
        control = _source_root(case, case.start)
        outcome = solve(
            case.evaluator,
            start=case.start,
            scale=case.scale,
            lower=case.lower,
            upper=case.upper,
        )
        candidate = _source_root(case, outcome.endpoint)
        key = (case.family, case.role)
        grouped[key][outcome.status] += 1
        grouped[key]["control_roots"] += int(control)
        grouped[key]["candidate_roots"] += int(candidate)
        callbacks[key].append(outcome.counters.callbacks)
        control_roots += int(control)
        candidate_roots += int(candidate)
        if case.role == "positive" and candidate and not control:
            positive_family_gains[case.family] += 1
        if case.role != "positive" and candidate:
            false_promotions += 1

    summary: dict[str, dict[str, object]] = {}
    for (family, role), counts in sorted(grouped.items()):
        values = callbacks[(family, role)]
        summary.setdefault(family, {})[role] = {
            "cases": sum(counts[status] for status in counts if status not in {"control_roots", "candidate_roots"}),
            "control_roots": counts["control_roots"],
            "candidate_roots": counts["candidate_roots"],
            "status_counts": {
                status: count
                for status, count in sorted(counts.items())
                if status not in {"control_roots", "candidate_roots"}
            },
            "callbacks_median": float(np.median(values)),
            "callbacks_p95": float(np.percentile(values, 95)),
        }

    improving_families = sorted(
        family for family, gains in positive_family_gains.items() if gains > 0
    )
    gate = {
        "at_least_two_gain_families": len(improving_families) >= 2,
        "false_promotions_zero": false_promotions == 0,
        "all_positive_instances_gain": sum(positive_family_gains.values()) == 36,
    }
    payload = {
        "schema_version": "geotarget.guard-equation-swap-prospective-breadth/v1",
        "scope": "generated-source-only; no target, truth, formal, validation, or holdout",
        "candidate_sha256": _sha256(HERE / "candidate.py"),
        "breadth_cases_sha256": _sha256(HERE / "breadth_cases.py"),
        "configuration": asdict(Configuration()),
        "integration_contract": integration_contract(),
        "aggregate": {
            "cases": total,
            "control_source_roots": control_roots,
            "candidate_source_roots": candidate_roots,
            "positive_gain_instances": sum(positive_family_gains.values()),
            "positive_gain_families": improving_families,
            "false_promotions": false_promotions,
        },
        "gate": gate,
        "decision": "D0_PASS" if all(gate.values()) else "STOP_D0",
        "summary": summary,
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
