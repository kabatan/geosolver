"""Generated/source-only Repair A gate; prints aggregate JSON."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import tempfile
import time
from typing import Any

import sympy as sp

from exact_outer_or_route import verify_outer_pins
from generated_repair_cases import NEGATIVE, POSITIVE, affine_target, renamed
from repair_adapter import attempt_repair


HERE = Path(__file__).resolve().parent


def _source(root: Path, name: str, document: dict[str, Any]) -> tuple[Path, str]:
    path = root / f"{name}.json"
    path.write_text(json.dumps(document, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def _certificate_sha(result: dict[str, Any]) -> str | None:
    certificate = result.get("certificate")
    if not isinstance(certificate, dict):
        return None
    return hashlib.sha256(
        json.dumps(certificate, sort_keys=True, separators=(",", ":")).encode("ascii")
    ).hexdigest()


def main() -> int:
    verify_outer_pins()
    positives: list[dict[str, Any]] = []
    negatives: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for name, (document, descriptor, endpoint) in POSITIVE.items():
            affine_document, affine_descriptor = affine_target(document, descriptor)
            variants = (
                ("base", document, descriptor),
                ("variable-rename", renamed(document), descriptor),
                ("affine-target", affine_document, affine_descriptor),
            )
            for variant, variant_document, variant_descriptor in variants:
                source, digest = _source(root, f"{name}-{variant}", variant_document)
                started = time.perf_counter_ns()
                result = attempt_repair(
                    source=source,
                    source_sha256=digest,
                    descriptor=variant_descriptor,
                    endpoint=endpoint,
                )
                elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
                certificate = result.get("certificate", {})
                quotient = certificate.get("quotient", {}) if isinstance(certificate, dict) else {}
                positives.append(
                    {
                        "stratum": name,
                        "variant": variant,
                        "accepted": result.get("authority_pass") is True,
                        "degree": result.get("binding", {}).get("target_degree"),
                        "quotient_dimension": quotient.get("dimension"),
                        "typed_predicate_relations": sorted(
                            {
                                item["relation"]
                                for item in result.get("binding", {}).get("predicate_mapping", [])
                            }
                        ),
                        "actual_terms": result.get("binding", {}).get("actual_terms"),
                        "coordinate_exactification": result.get("coordinate_exactification"),
                        "independent_verifier": result.get("independent_verification", {}).get("verified"),
                        "untouched_replay": result.get("untouched_source_replay", {}).get("verified"),
                        "certificate_sha256": _certificate_sha(result),
                        "elapsed_ms": round(elapsed_ms, 3),
                    }
                )
        for name, (document, descriptor, endpoint, expected) in NEGATIVE.items():
            source, digest = _source(root, name, document)
            result = attempt_repair(
                source=source,
                source_sha256=digest,
                descriptor=descriptor,
                endpoint=endpoint,
            )
            negatives.append(
                {
                    "stratum": name,
                    "accepted": result.get("authority_pass") is True,
                    "expected_reason": expected,
                    "actual_reason": result.get("failure_reason"),
                    "failed_as_expected": result.get("failure_reason") == expected,
                }
            )

    accepted = [record for record in positives if record["accepted"]]
    source_hashes = {
        name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
        for name in (
            "repair_adapter.py",
            "untouched_replay.py",
            "exact_outer_or_route.py",
            "generated_repair_cases.py",
        )
    }
    artifact = {
        "schema": "geotarget.target-hermite-repair-a-generated/v1",
        "authority": "GENERATED_AND_STATIC_SOURCE_ONLY",
        "environment": {
            "python": platform.python_version(),
            "sympy": sp.__version__,
            "cpu_affinity": sorted(os.sched_getaffinity(0)),
        },
        "positive_records": positives,
        "negative_records": negatives,
        "aggregate": {
            "anonymous_strata": len(POSITIVE),
            "positive_variants": len(positives),
            "accepted_positive_variants": len(accepted),
            "activated_degrees": sorted({record["degree"] for record in accepted}),
            "false_accepts": sum(record["accepted"] for record in negatives),
            "negative_controls": len(negatives),
            "expected_failures": sum(record["failed_as_expected"] for record in negatives),
            "maximum_quotient_dimension": max(record["quotient_dimension"] for record in accepted),
            "maximum_terms_per_polynomial": max(
                record["actual_terms"]["maximum_per_polynomial"] for record in accepted
            ),
            "maximum_total_augmented_terms": max(
                record["actual_terms"]["total_all_d0_polynomials"]
                for record in accepted
            ),
            "all_independently_verified": all(record["independent_verifier"] for record in accepted),
            "all_untouched_replayed": all(record["untouched_replay"] for record in accepted),
            "all_without_coordinate_exactification": all(
                record["coordinate_exactification"] is False for record in accepted
            ),
        },
        "source_sha256": source_hashes,
        "formal_boundary": (
            "No formal execute, scorer, truth, corpus case result, validation, sealed data, or CPU0-6."
        ),
    }
    print(json.dumps(artifact, indent=2, sort_keys=True))
    aggregate = artifact["aggregate"]
    return int(
        aggregate["accepted_positive_variants"] != len(positives)
        or aggregate["false_accepts"] != 0
        or aggregate["expected_failures"] != len(negatives)
        or aggregate["activated_degrees"] != [1, 2, 4]
        or not aggregate["all_independently_verified"]
        or not aggregate["all_untouched_replayed"]
    )


if __name__ == "__main__":
    raise SystemExit(main())
