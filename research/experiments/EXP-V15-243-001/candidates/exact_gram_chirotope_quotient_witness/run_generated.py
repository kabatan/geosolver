#!/usr/bin/env python3
"""Generated S0 evidence for exact Gram/chirotope quotient authority."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile

from candidate import attempt_source
from generated_cases import NEGATIVES, POSITIVES, permuted, reflected, rotated
from verifier import verify_source


HERE = Path(__file__).resolve().parent
CORE = (HERE / "candidate.py", HERE / "verifier.py", HERE / "or_connector.py")


def _run(root: Path, ordinal: int, document: dict):
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    source = root / f"anonymous-{ordinal}.json"
    source.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    result = attempt_source(source=source, source_sha256=digest)
    verified = False
    if result.get("authority_pass") is True:
        verified = verify_source(source=source, source_sha256=digest, certificate=result).get("verified") is True
    return result, verified


def main() -> None:
    if tuple(os.sched_getaffinity(0)) != (15,):
        raise SystemExit("generated evidence must run only on CPU15")
    positives = []
    metamorphics = []
    negatives = []
    with tempfile.TemporaryDirectory(prefix="geotarget-gram-d0-") as temporary:
        root = Path(temporary)
        ordinal = 0
        for document in POSITIVES.values():
            positives.append(_run(root, ordinal, document)); ordinal += 1
        for name in POSITIVES:
            for transformed in (permuted(name), rotated(name), reflected(name)):
                metamorphics.append(_run(root, ordinal, transformed)); ordinal += 1
        for document in NEGATIVES.values():
            negatives.append(_run(root, ordinal, document)); ordinal += 1
    evidence = {
        "schema": "geotarget.exact-gram-chirotope-generated-evidence/v1",
        "authority": "GENERATED_SOURCE_ONLY_S0_NO_FORMAL_SCORER_TRUTH",
        "cpu_affinity": [15],
        "positive": {
            "families": len(positives),
            "authority_pass": sum(result.get("authority_pass") is True for result, _ in positives),
            "independent_verify_pass": sum(verified for _, verified in positives),
        },
        "metamorphic": {
            "families": len(POSITIVES),
            "variants": len(metamorphics),
            "point_permutation_rotation_reflection_each_family": True,
            "authority_pass": sum(result.get("authority_pass") is True for result, _ in metamorphics),
            "independent_verify_pass": sum(verified for _, verified in metamorphics),
        },
        "negative": {
            "families": len(negatives),
            "false_authority": sum(result.get("authority_pass") is True for result, _ in negatives),
            "reason_histogram": {
                reason: sum(result.get("failure_reason") == reason for result, _ in negatives)
                for reason in sorted({result.get("failure_reason") for result, _ in negatives})
            },
        },
        "same_edm_mirror_chirotope_and_selector_flip_tested": True,
        "exact_qqbar_realization_tested": True,
        "exact_symmetry_hollow_psd_rank_minors_tested": True,
        "untouched_source_guard_branch_raw_target_replay_tested": True,
        "core_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in CORE},
        "formal_execute_used": False,
        "scorer_or_truth_used": False,
        "validation_or_sealed_used": False,
    }
    (HERE / "GENERATED_EVIDENCE.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
