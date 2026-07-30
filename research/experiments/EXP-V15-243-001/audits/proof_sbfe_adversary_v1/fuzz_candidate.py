#!/usr/bin/env python3
"""Disposable fixed-seed 1,024-trace property run for proof-SBFE."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import random
from pathlib import Path
from typing import Any, Mapping

from oracle import validate_observation
from replay_candidate import _execute, _load, _sha256


SEED = 20260731
TRIALS = 256
TRACE_VARIANTS = 4
LEAF_NAMES = ("s", "a", "b", "c", "t", "u", "v")
DESCRIPTOR_NAMES = ("factor", "shared", "terminal")


def _leaf(name: str) -> dict[str, str]:
    return {"leaf": name}


def _expanded_descriptors() -> dict[str, Any]:
    return {
        "factor": {
            "or": [
                {"and": [_leaf("s"), _leaf("a")]},
                {"and": [_leaf("s"), _leaf("b")]},
            ]
        },
        "shared": {"and": [_leaf("s"), _leaf("c")]},
        "terminal": {
            "or": [_leaf("t"), {"and": [_leaf("u"), _leaf("v")]}]
        },
    }


def _factored_descriptors() -> dict[str, Any]:
    descriptors = _expanded_descriptors()
    descriptors["factor"] = {
        "and": [_leaf("s"), {"or": [_leaf("a"), _leaf("b")]}]
    }
    return descriptors


def _rename_node(node: Mapping[str, Any], names: Mapping[str, str]) -> dict[str, Any]:
    if "leaf" in node:
        return {"leaf": names[str(node["leaf"])]}
    for operator in ("and", "or"):
        if operator in node:
            return {
                operator: [
                    _rename_node(child, names) for child in reversed(node[operator])
                ]
            }
    raise ValueError("unknown node")


def _make_case(rng: random.Random, trial: int) -> dict[str, Any]:
    leaves: dict[str, dict[str, float]] = {}
    tape: dict[str, dict[str, object]] = {}
    for index, name in enumerate(LEAF_NAMES):
        probability = round(0.15 + 0.75 * rng.random() + index * 1.0e-7, 8)
        estimated = round(0.5 + 5.5 * rng.random() + index * 1.0e-6, 8)
        actual = round(estimated * (0.5 + rng.random()), 8)
        leaves[name] = {
            "probability_true": probability,
            "estimated_cost": estimated,
        }
        tape[name] = {"outcome": rng.random() < 0.58, "actual_cost": actual}
    if trial % 4 == 0:
        late_leaf = ("s", "a", "t", "u")[(trial // 4) % 4]
        tape[late_leaf]["actual_cost"] = round(26.0 + 8.0 * rng.random(), 8)
    return {
        "total_budget": 100.0,
        "baseline_fraction": 0.75,
        "graph_fraction_cap": 0.25,
        "descriptors": _expanded_descriptors(),
        "leaves": leaves,
        "tape": tape,
    }


def _factored(case: Mapping[str, Any]) -> dict[str, Any]:
    answer = deepcopy(case)
    answer["descriptors"] = _factored_descriptors()
    return answer


def _permuted(
    case: Mapping[str, Any], rng: random.Random
) -> tuple[dict[str, Any], dict[str, str], dict[str, str]]:
    leaf_tokens = [f"leaf_{index:02d}" for index in range(len(LEAF_NAMES))]
    descriptor_tokens = [f"descriptor_{index:02d}" for index in range(len(DESCRIPTOR_NAMES))]
    rng.shuffle(leaf_tokens)
    rng.shuffle(descriptor_tokens)
    leaf_map = dict(zip(LEAF_NAMES, leaf_tokens, strict=True))
    descriptor_map = dict(zip(DESCRIPTOR_NAMES, descriptor_tokens, strict=True))
    answer = deepcopy(case)
    answer["descriptors"] = {
        descriptor_map[name]: _rename_node(case["descriptors"][name], leaf_map)
        for name in reversed(DESCRIPTOR_NAMES)
    }
    answer["leaves"] = {
        leaf_map[name]: deepcopy(case["leaves"][name]) for name in reversed(LEAF_NAMES)
    }
    answer["tape"] = {
        leaf_map[name]: deepcopy(case["tape"][name]) for name in reversed(LEAF_NAMES)
    }
    return answer, leaf_map, descriptor_map


def _normal(
    observation: Mapping[str, Any],
    leaf_inverse: Mapping[str, str] | None = None,
    descriptor_inverse: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    leaf_inverse = leaf_inverse or {name: name for name in LEAF_NAMES}
    descriptor_inverse = descriptor_inverse or {
        name: name for name in DESCRIPTOR_NAMES
    }
    return {
        "certificates": tuple(
            sorted(descriptor_inverse[name] for name in observation["certificates"])
        ),
        "failed": tuple(
            sorted(
                descriptor_inverse[name] for name in observation["failed_descriptors"]
            )
        ),
        "unresolved": tuple(
            sorted(
                descriptor_inverse[name]
                for name in observation["unresolved_descriptors"]
            )
        ),
        "witnesses": {
            descriptor_inverse[name]: tuple(
                sorted(leaf_inverse[leaf] for leaf in witness)
            )
            for name, witness in observation["proof_witnesses"].items()
        },
        "selections": tuple(leaf_inverse[name] for name in observation["selections"]),
        "revealed": {
            leaf_inverse[name]: value for name, value in observation["revealed"].items()
        },
        "not_run": tuple(
            sorted(leaf_inverse[name] for name in observation["not_run"])
        ),
        "deadline_late": tuple(
            leaf_inverse[name] for name in observation["deadline_late"]
        ),
        "graph_spent": observation["graph_spent"],
        "graph_cap": observation["graph_cap"],
        "baseline_spent": observation["baseline_spent"],
        "baseline_reserved": observation["baseline_reserved"],
        "baseline_sha256": observation["baseline_sha256"],
        "first_served": observation["descriptors_first_served"],
        "eligible": observation["eligible_descriptors"],
        "shared_hits": observation["shared_resolution_hits"],
    }


def _future_twin(
    case: Mapping[str, Any], base: Mapping[str, Any], rng: random.Random
) -> tuple[dict[str, Any], int]:
    answer = deepcopy(case)
    selections = tuple(base["selections"])
    preserve = min(2, len(selections))
    preserved = set(selections[:preserve])
    for name in LEAF_NAMES:
        if name in preserved:
            continue
        old = answer["tape"][name]
        old["outcome"] = not bool(old["outcome"])
        old_cost = float(old["actual_cost"])
        old["actual_cost"] = round(
            27.0 + rng.random() if old_cost <= 25.0 else 1.0 + rng.random(), 8
        )
    return answer, preserve


def _relation_failures(
    trial: int,
    base: Mapping[str, Any],
    factored: Mapping[str, Any],
    permuted: Mapping[str, Any],
    future: Mapping[str, Any],
    leaf_map: Mapping[str, str],
    descriptor_map: Mapping[str, str],
    preserve: int,
) -> list[str]:
    failures: list[str] = []
    if _normal(base) != _normal(factored):
        failures.append(f"trial-{trial}:factoring-invariance")
    inverse_leaf = {value: key for key, value in leaf_map.items()}
    inverse_descriptor = {value: key for key, value in descriptor_map.items()}
    if _normal(base) != _normal(permuted, inverse_leaf, inverse_descriptor):
        failures.append(f"trial-{trial}:id-insertion-permutation")
    base_selections = tuple(base["selections"])
    future_selections = tuple(future["selections"])
    compare = preserve + int(preserve < len(base_selections))
    if future_selections[:compare] != base_selections[:compare]:
        failures.append(f"trial-{trial}:hidden-future-prefix")
    if preserve == len(base_selections) and future_selections != base_selections:
        failures.append(f"trial-{trial}:terminal-future-resurrection")
    return failures


def run(candidate_path: Path, expected_sha256: str) -> dict[str, Any]:
    observed_sha256 = _sha256(candidate_path)
    if observed_sha256 != expected_sha256:
        raise RuntimeError(
            f"candidate snapshot mismatch: expected {expected_sha256}, got {observed_sha256}"
        )
    candidate = _load(candidate_path)
    rng = random.Random(SEED)
    failure: dict[str, Any] | None = None
    property_checks = 0
    totals = {"certificate": 0, "failed": 0, "unresolved": 0, "selected": 0, "late": 0}

    for trial in range(TRIALS):
        base_case = _make_case(rng, trial)
        factored_case = _factored(base_case)
        permuted_case, leaf_map, descriptor_map = _permuted(base_case, rng)
        base = _execute(candidate, base_case)
        factored = _execute(candidate, factored_case)
        permuted = _execute(candidate, permuted_case)
        future_case, preserve = _future_twin(base_case, base, rng)
        future = _execute(candidate, future_case)
        runs = {
            "expanded": (base_case, base),
            "factored": (factored_case, factored),
            "permuted": (permuted_case, permuted),
            "future": (future_case, future),
        }
        failures = [
            item
            for variant, (case, observation) in runs.items()
            for item in validate_observation(f"trial-{trial}:{variant}", case, observation)
        ]
        failures.extend(
            _relation_failures(
                trial, base, factored, permuted, future,
                leaf_map, descriptor_map, preserve,
            )
        )
        property_checks += 56
        for _variant, (_case_value, observation) in runs.items():
            totals["certificate"] += len(observation["certificates"])
            totals["failed"] += len(observation["failed_descriptors"])
            totals["unresolved"] += len(observation["unresolved_descriptors"])
            totals["selected"] += len(observation["selections"])
            totals["late"] += len(observation["deadline_late"])
        if failures:
            failure = {
                "trial": trial,
                "failures": failures,
                "bounded_schema": base_case,
                "normalized": {
                    "expanded": _normal(base),
                    "factored": _normal(factored),
                    "permuted": _normal(
                        permuted,
                        {value: key for key, value in leaf_map.items()},
                        {value: key for key, value in descriptor_map.items()},
                    ),
                    "future": _normal(future),
                },
            }
            break

    traces = TRIALS * TRACE_VARIANTS if failure is None else (failure["trial"] + 1) * 4
    result = {
        "schema": "geotarget.proof-sbfe-property-fuzz/v1",
        "seed": SEED,
        "candidate_sha256": observed_sha256,
        "cpu": 15,
        "formal_dev_validation_sealed_truth_scorer_used": False,
        "trace_count": traces,
        "property_check_count": property_checks,
        "failure_count": 0 if failure is None else len(failure["failures"]),
        "aggregate": {
            "certificate_count": totals["certificate"],
            "failed_descriptor_count": totals["failed"],
            "unresolved_descriptor_count": totals["unresolved"],
            "selected_leaf_count": totals["selected"],
            "deadline_late_count": totals["late"],
            "decision": "PASS" if failure is None else "COUNTEREXAMPLE_FOUND",
        },
    }
    if failure is not None:
        result["first_counterexample"] = failure
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    arguments = parser.parse_args()
    result = run(arguments.candidate, arguments.sha256)
    print(json.dumps(result, indent=2, sort_keys=True))
    return int(result["failure_count"] != 0)


if __name__ == "__main__":
    raise SystemExit(main())
