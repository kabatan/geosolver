#!/usr/bin/env python3
"""Aggregate-only intersection with the existing source polynomial seam.

This executes compiler eligibility only. It never invokes HomotopyContinuation,
root solving, source replay, target evaluation, scorer or result artifacts.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
from typing import Any

import static_source_census as source_census


def _load_backend(path: Path) -> Any:
    specification = importlib.util.spec_from_file_location(
        "trig_d0_audited_existing_polynomial_backend", path
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("existing backend module is unavailable")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(dataset: Path, backend_path: Path) -> dict[str, object]:
    backend = _load_backend(backend_path)
    counts = Counter(
        {
            "existing_backend_static_eligible": 0,
            "eligible_and_any_exact_affine_trig": 0,
            "eligible_and_d0_compatible_trig": 0,
            "eligible_and_safe_distance_square": 0,
            "eligible_and_d0_trig_safe_distance": 0,
        }
    )
    reasons = Counter()
    row_count = 0
    started = time.monotonic()
    with dataset.open("rb") as source:
        for raw_row in source:
            if not raw_row.strip():
                continue
            encoded = source_census.formulation_bytes(raw_row.rstrip(b"\r\n"))
            document = json.loads(encoded)
            surface = source_census.analyze_formulation(document)
            try:
                compiled = backend.compile_source(
                    document, source_sha256=hashlib.sha256(encoded).hexdigest()
                )
            except backend.Ineligible as error:
                reasons[str(error).split(":", 1)[0]] += 1
                row_count += 1
                continue
            report = compiled.report
            if (
                report.get("source_target_evaluated") is not False
                or report.get("source_target_graph_added") is not False
            ):
                raise RuntimeError("existing compiler crossed the target-free boundary")
            counts["existing_backend_static_eligible"] += 1
            counts["eligible_and_any_exact_affine_trig"] += int(
                bool(surface["any_exact_affine_trig"])
            )
            counts["eligible_and_d0_compatible_trig"] += int(
                bool(surface["d0_compatible_trig"])
            )
            counts["eligible_and_safe_distance_square"] += int(
                bool(surface["safe_distance_square"])
            )
            counts["eligible_and_d0_trig_safe_distance"] += int(
                bool(surface["d0_compatible_trig"] and surface["safe_distance_square"])
            )
            row_count += 1
    if row_count != source_census.EXPECTED_FORMULATION_COUNT:
        raise source_census.SourceBoundaryError("development row count mismatch")
    if _sha256(dataset) != source_census.EXPECTED_DEVELOPMENT_SHA256:
        raise source_census.SourceBoundaryError("development source digest mismatch")
    compiler_path = backend.COMPILER_ROOT / "compiler.py"
    reducer_path = backend.REDUCER_ROOT / "reducer.py"
    return {
        "schema_version": "geotarget.exp-trig-lift-d0-backend-seam-audit/v1",
        "authority": "TRUTH_BLIND_STATIC_COMPILER_INTERSECTION_ONLY",
        "counts": dict(sorted(counts.items())),
        "ineligible_reason_counts": dict(sorted(reasons.items())),
        "custody": {
            "development_container_sha256": source_census.EXPECTED_DEVELOPMENT_SHA256,
            "formulation_count": row_count,
            "row_objects_deserialized": False,
            "sibling_values_deserialized": False,
            "problem_ids_retained_or_reported": False,
            "source_target_evaluated": False,
            "source_target_graph_added": False,
            "root_backend_invoked": False,
            "source_replay_invoked": False,
            "truth_scorer_result_loaded": False,
            "validation_or_sealed_access": False,
        },
        "existing_bytes": {
            "source_backend_sha256": _sha256(backend_path),
            "semantic_compiler_sha256": _sha256(compiler_path),
            "bounded_reducer_sha256": _sha256(reducer_path),
        },
        "elapsed_seconds": time.monotonic() - started,
        "interpretation_limit": (
            "Static compiler eligibility is not root enumeration, a completeness proof, source replay, "
            "or solved-target evidence."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("backend", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    result = audit(arguments.dataset, arguments.backend)
    arguments.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
