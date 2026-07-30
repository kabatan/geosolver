"""Run the generated-only D0 gate and print a compact JSON artifact."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any, Callable

import sympy as sp

from candidate import CertificationFailure, certify
from generated_cases import NEGATIVE_CASES, POSITIVE_CASES, affine_target, permuted
from verifier import VerificationFailure, verify


ROOT = Path(__file__).resolve().parent


def _sha_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")).hexdigest()


def _timed(function: Callable[[], Any]) -> tuple[Any, float]:
    start = time.perf_counter_ns()
    value = function()
    return value, (time.perf_counter_ns() - start) / 1_000_000


def _positive_record(name: str, variant: str, problem: dict[str, Any]) -> dict[str, Any]:
    certificate, certify_ms = _timed(lambda: certify(problem))
    verification, verify_ms = _timed(lambda: verify(problem, certificate))
    max_nullity = max(query["inertia"]["zero"] for query in certificate["tarski_queries"])
    return {
        "family": name,
        "variant": variant,
        "certified": True,
        "independently_verified": verification["verified"],
        "target_polynomial_degree": certificate["target"]["polynomial_degree"],
        "quotient_dimension": certificate["quotient"]["dimension"],
        "strictly_feasible_real_root_count": certificate["strictly_feasible_real_root_count"],
        "query_count": len(certificate["tarski_queries"]),
        "max_hermite_nullity": max_nullity,
        "coordinate_exactification": certificate["coordinate_exactification"],
        "certify_ms": round(certify_ms, 3),
        "verify_ms": round(verify_ms, 3),
        "certificate_sha256": _sha_json(certificate),
    }


def main() -> int:
    positives: list[dict[str, Any]] = []
    for name, problem in POSITIVE_CASES.items():
        positives.append(_positive_record(name, "base", problem))
        positives.append(_positive_record(name, "permutation", permuted(problem)))
        positives.append(_positive_record(name, "affine-target", affine_target(problem)))

    negatives: list[dict[str, Any]] = []
    for name, (problem, expected) in NEGATIVE_CASES.items():
        start = time.perf_counter_ns()
        actual = "unexpected-certificate"
        try:
            certify(problem)
        except CertificationFailure as failure:
            actual = failure.reason
        negatives.append(
            {
                "family": name,
                "expected_reason": expected,
                "actual_reason": actual,
                "fail_closed": actual == expected,
                "elapsed_ms": round((time.perf_counter_ns() - start) / 1_000_000, 3),
            }
        )

    mutation_problem = POSITIVE_CASES["regular-zero-dimensional-degree2"]
    base_certificate = certify(mutation_problem)
    mutations: list[dict[str, Any]] = []
    mutation_values = []
    changed_digest = copy.deepcopy(base_certificate)
    changed_digest["problem_sha256"] = "0" * 64
    mutation_values.append(("problem-digest", changed_digest))
    changed_matrix = copy.deepcopy(base_certificate)
    changed_matrix["quotient"]["multiplication_matrices"]["x"][0][0] = "1"
    mutation_values.append(("multiplication-matrix", changed_matrix))
    changed_hermite = copy.deepcopy(base_certificate)
    changed_hermite["tarski_queries"][0]["hermite"][0][0] = "999"
    mutation_values.append(("hermite-matrix", changed_hermite))
    for name, mutation in mutation_values:
        rejected = False
        reason = "accepted"
        try:
            verify(mutation_problem, mutation)
        except VerificationFailure as failure:
            rejected = True
            reason = str(failure)
        mutations.append({"mutation": name, "rejected": rejected, "reason": reason})

    artifact = {
        "schema": "target-constrained-hermite-generated-gate/v1",
        "authority": "GENERATED_ONLY_NO_FORMAL_DATA",
        "environment": {
            "python": platform.python_version(),
            "sympy": sp.__version__,
            "cpu_affinity": sorted(os.sched_getaffinity(0)),
        },
        "source_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (ROOT / "candidate.py", ROOT / "verifier.py", ROOT / "generated_cases.py")
        },
        "positive_records": positives,
        "negative_records": negatives,
        "mutation_records": mutations,
        "aggregate": {
            "positive_family_count": len(POSITIVE_CASES),
            "positive_variant_count": len(positives),
            "certified_and_verified_count": sum(
                record["certified"] and record["independently_verified"] for record in positives
            ),
            "negative_family_count": len(NEGATIVE_CASES),
            "fail_closed_count": sum(record["fail_closed"] for record in negatives),
            "mutation_count": len(mutations),
            "mutation_rejected_count": sum(record["rejected"] for record in mutations),
            "activated_target_degrees": sorted({record["target_polynomial_degree"] for record in positives}),
            "activated_nonradical_signal": any(record["max_hermite_nullity"] > 0 for record in positives),
            "all_without_coordinate_exactification": all(
                record["coordinate_exactification"] is False for record in positives
            ),
        },
    }
    print(json.dumps(artifact, indent=2, sort_keys=True))
    return int(
        artifact["aggregate"]["certified_and_verified_count"] != len(positives)
        or artifact["aggregate"]["fail_closed_count"] != len(negatives)
        or artifact["aggregate"]["mutation_rejected_count"] != len(mutations)
        or not artifact["aggregate"]["activated_nonradical_signal"]
    )


if __name__ == "__main__":
    raise SystemExit(main())
