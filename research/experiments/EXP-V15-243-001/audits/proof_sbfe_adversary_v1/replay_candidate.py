#!/usr/bin/env python3
"""Hash-pinned replay adapter for the fixed proof-SBFE adversary corpus."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, Mapping

from oracle import FIXED_RUNS, validate_observation, validate_relations


class RevealProbe:
    def __init__(self, tape: Mapping[str, Mapping[str, object]]) -> None:
        self._tape = tape
        self.calls: list[str] = []

    def __call__(self, leaf: str) -> tuple[bool, float]:
        if leaf not in self._tape:
            raise AssertionError(f"candidate requested undeclared leaf: {leaf}")
        if leaf in self.calls:
            raise AssertionError(f"candidate requested shared leaf twice: {leaf}")
        self.calls.append(leaf)
        item = self._tape[leaf]
        return bool(item["outcome"]), float(item["actual_cost"])


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path):
    specification = importlib.util.spec_from_file_location("proof_sbfe_adversary_candidate", path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def _execute(candidate, case: Mapping[str, Any]) -> dict[str, Any]:
    public = candidate.PublicCase(
        descriptors=case["descriptors"],
        leaves={
            name: candidate.Leaf(
                probability_true=float(item["probability_true"]),
                estimated_cost=float(item["estimated_cost"]),
            )
            for name, item in case["leaves"].items()
        },
        total_budget=float(case["total_budget"]),
        baseline_fraction=float(case["baseline_fraction"]),
        graph_fraction_cap=float(case["graph_fraction_cap"]),
    )
    reveal = RevealProbe(case["tape"])
    raw = asdict(candidate.run(public, reveal, strategy="sbfe"))
    baseline_bytes = raw.pop("baseline_bytes")
    raw["baseline_sha256"] = hashlib.sha256(baseline_bytes).hexdigest()
    raw["reveal_calls"] = tuple(reveal.calls)
    return raw


def run(candidate_path: Path, expected_sha256: str) -> dict[str, Any]:
    observed_sha256 = _sha256(candidate_path)
    if observed_sha256 != expected_sha256:
        raise RuntimeError(
            f"candidate snapshot mismatch: expected {expected_sha256}, got {observed_sha256}"
        )
    candidate = _load(candidate_path)
    observations = {name: _execute(candidate, case) for name, case in FIXED_RUNS.items()}
    failures = [
        failure
        for name, case in FIXED_RUNS.items()
        for failure in validate_observation(name, case, observations[name])
    ]
    failures.extend(validate_relations(observations))
    return {
        "schema": "geotarget.proof-sbfe-adversary/v1",
        "candidate_sha256": observed_sha256,
        "cpu": 15,
        "formal_dev_validation_sealed_truth_scorer_used": False,
        "fixed_run_count": len(FIXED_RUNS),
        "failure_count": len(failures),
        "failures": failures,
        "aggregate": {
            "certificate_count": sum(len(value["certificates"]) for value in observations.values()),
            "failed_descriptor_count": sum(
                len(value["failed_descriptors"]) for value in observations.values()
            ),
            "unresolved_descriptor_count": sum(
                len(value["unresolved_descriptors"]) for value in observations.values()
            ),
            "selected_leaf_count": sum(len(value["selections"]) for value in observations.values()),
            "deadline_late_count": sum(len(value["deadline_late"]) for value in observations.values()),
            "decision": "PASS" if not failures else "COUNTEREXAMPLE_FOUND",
        },
    }


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
