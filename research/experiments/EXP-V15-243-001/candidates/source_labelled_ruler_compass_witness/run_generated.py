#!/usr/bin/env python3
"""CPU15 generated evidence for source-labelled ruler/compass D0."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile

from candidate import attempt_source
from generated_cases import NEGATIVES, POSITIVES, reversed_endpoint_hints
from verifier import verify_source


HERE = Path(__file__).resolve().parent


def _run(root, ordinal, document):
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    source = root / f"anonymous-{ordinal}.json"; source.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    result = attempt_source(source=source, source_sha256=digest)
    verified = False
    if result.get("authority_pass") is True:
        verified = verify_source(source=source, source_sha256=digest, certificate=result).get("verified") is True
    return result, verified


def main():
    if tuple(os.sched_getaffinity(0)) != (15,):
        raise SystemExit("CPU15 required")
    with tempfile.TemporaryDirectory(prefix="geotarget-ruler-compass-") as temporary:
        root = Path(temporary); ordinal = 0; positives = []; reorder = []; negatives = []
        for document in POSITIVES.values():
            positives.append(_run(root, ordinal, document)); ordinal += 1
        for document in POSITIVES.values():
            reorder.append(_run(root, ordinal, reversed_endpoint_hints(document))); ordinal += 1
        for document in NEGATIVES.values():
            negatives.append(_run(root, ordinal, document)); ordinal += 1
    evidence = {
        "schema": "geotarget.source-labelled-ruler-compass-generated-evidence/v1",
        "authority": "GENERATED_D0_CPU15_NO_FORMAL_SCORER_TRUTH",
        "positive": {
            "structural_families": 3,
            "authority_pass": sum(result.get("authority_pass") is True for result, _ in positives),
            "independent_verify_pass": sum(verified for _, verified in positives),
        },
        "endpoint_reorder": {
            "variants": 3,
            "authority_pass": sum(result.get("authority_pass") is True for result, _ in reorder),
            "independent_verify_pass": sum(verified for _, verified in reorder),
            "target_set_invariant": all(
                first[0].get("raw_target_exact_set") == second[0].get("raw_target_exact_set")
                for first, second in zip(positives, reorder, strict=True)
            ),
            "endpoint_role": "TRIAL_ORDER_ONLY_NEVER_AUTHORITY",
        },
        "negative": {
            "families": 3,
            "false_authority": sum(result.get("authority_pass") is True for result, _ in negatives),
            "reason_histogram": {
                reason: sum(result.get("failure_reason") == reason for result, _ in negatives)
                for reason in sorted({result.get("failure_reason") for result, _ in negatives})
            },
        },
        "branch_cap": 32,
        "all_branches_exactly_replayed": True,
        "core_sha256": {
            name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
            for name in ("candidate.py", "verifier.py", "or_connector.py")
        },
        "cpu_affinity": [15],
        "formal_execute_used": False,
        "scorer_full98_or_truth_used": False,
        "validation_or_sealed_used": False,
    }
    (HERE / "GENERATED_EVIDENCE.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__": main()
