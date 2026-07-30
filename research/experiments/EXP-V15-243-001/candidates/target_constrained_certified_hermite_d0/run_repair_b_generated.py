#!/usr/bin/env python3
"""Generated-only Repair B hard-child and containment evidence."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

from generated_repair_cases import POSITIVE
from hard_child_runner import EXPECTED_GUARD_SHA256, run_hard_child, verify_guard_pins


HERE = Path(__file__).resolve().parent
CORE_FILES = (
    HERE / "candidate.py",
    HERE / "verifier.py",
    HERE / "repair_adapter.py",
    HERE / "untouched_replay.py",
    HERE / "hermite_child.py",
    HERE / "hard_child_runner.py",
    HERE / "repair_b_connector.py",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source(root: Path, ordinal: int, document: dict) -> tuple[Path, str]:
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    path = root / f"SOURCE-{ordinal}.json"
    path.write_bytes(raw)
    return path, hashlib.sha256(raw).hexdigest()


def main() -> None:
    if tuple(os.sched_getaffinity(0)) != (15,):
        raise SystemExit("generated Repair B evidence must be pinned only to CPU15")
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="geotarget-repair-b-") as temporary:
        root = Path(temporary)
        positives = []
        first = None
        for ordinal, (document, descriptor, endpoint) in enumerate(POSITIVE.values()):
            source, source_sha256 = _source(root, ordinal, document)
            first = first or (source, source_sha256, descriptor, endpoint)
            result = run_hard_child(
                source=source,
                source_sha256=source_sha256,
                descriptor=descriptor,
                endpoint=endpoint,
                output_dir=root / f"positive-{ordinal}",
                cpu=15,
                side_seconds=5.0,
            )
            positives.append(result)
        assert first is not None
        source, source_sha256, descriptor, endpoint = first
        faults = {}
        late_marker = root / "late-marker"
        for fault, seconds in (
            ("partial-json", 2.0),
            ("sleep", 0.70),
            ("output", 2.0),
            ("rss", 2.0),
            ("leak-late-artifact", 2.0),
        ):
            result = run_hard_child(
                source=source,
                source_sha256=source_sha256,
                descriptor=descriptor,
                endpoint=endpoint,
                output_dir=root / f"fault-{fault}",
                cpu=15,
                side_seconds=seconds,
                fault=fault,
                late_marker=late_marker if fault == "leak-late-artifact" else None,
            )
            faults[fault] = {
                "authority": result["authority"] is not None,
                "failure_reason": result["failure_reason"],
                "classification": result["process"]["classification"],
                "descendant_leak": result["process"]["descendant_leak"],
            }
        time.sleep(1.25)

        evidence = {
            "schema": "geotarget.target-hermite-repair-b-generated-evidence/v1",
            "authority": "GENERATED_S0_ONLY_NO_FORMAL_SCORER_OR_TRUTH",
            "cpu_affinity": [15],
            "positive_real_child": {
                "accepted": sum(result["authority"] is not None for result in positives),
                "total": len(positives),
                "independent_verifier_pass": sum(
                    result["authority"] is not None
                    and result["authority"]["independent_verification"]["verified"] is True
                    for result in positives
                ),
                "untouched_replay_pass": sum(
                    result["authority"] is not None
                    and result["authority"]["untouched_source_replay"]["verified"] is True
                    for result in positives
                ),
                "process_classification_histogram": {
                    classification: sum(
                        result["process"]["classification"] == classification for result in positives
                    )
                    for classification in sorted({result["process"]["classification"] for result in positives})
                },
                "maximum_closure_rss_bytes": max(
                    result["process"]["peak_descendant_closure_rss_bytes"] for result in positives
                ),
                "artifact_sha256": [result.get("artifact_sha256") for result in positives],
            },
            "fault_probes": faults,
            "late_artifact_exists_after_1_25_seconds": late_marker.exists(),
            "partial_or_fault_authority_count": sum(item["authority"] for item in faults.values()),
            "guard_pins": verify_guard_pins(),
            "guard_expected_pins": {str(path): digest for path, digest in EXPECTED_GUARD_SHA256.items()},
            "core_sha256": {path.name: _sha256(path) for path in CORE_FILES},
            "formal_execute_used": False,
            "scorer_or_truth_used": False,
            "validation_or_sealed_used": False,
            "elapsed_seconds": time.monotonic() - started,
        }
        output = HERE / "REPAIR_B_GENERATED_EVIDENCE.json"
        output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
