#!/usr/bin/env python3
"""Run the frozen generated-only D0 gate and write aggregate evidence."""

from __future__ import annotations

import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import time

import candidate
import canonical_replay
import generated_cases
import sympy as sp


HERE = Path(__file__).resolve().parent


def _linux_peak_rss_bytes():
    for line in Path("/proc/self/status").read_text(encoding="utf-8").splitlines():
        if line.startswith("VmHWM:"):
            fields = line.split()
            if len(fields) == 3 and fields[2] == "kB":
                return int(fields[1]) * 1024
    raise RuntimeError("Linux VmHWM telemetry unavailable")


def _failure_reason(function, *args):
    try:
        function(*args)
    except candidate.LiftFailure as error:
        return str(error)
    return "NOT_REJECTED"


def run():
    started = time.monotonic()
    affinity = tuple(sorted(os.sched_getaffinity(0)))
    if len(affinity) != 1:
        raise RuntimeError("generated D0 must run on exactly one pinned CPU")
    triangle, triangle_assignment = generated_cases.triangle_sum()
    reflected, reflected_assignment = generated_cases.triangle_sum(reflected=True)
    rational, rational_assignment, near_miss_assignment = generated_cases.rational_sum_difference()

    triangle_proposal = candidate.compile_relation(triangle)
    reflected_proposal = candidate.compile_relation(reflected)
    rational_proposal = candidate.compile_relation(rational)
    positive = []
    for name, relation, assignment, proposal in (
        ("triangle_angle_sum", triangle, triangle_assignment, triangle_proposal),
        ("multi_angle_rational_sum_difference", rational, rational_assignment, rational_proposal),
        ("reflection", reflected, reflected_assignment, reflected_proposal),
    ):
        check = candidate.check_exact_proposal(proposal, assignment)
        replay = canonical_replay.replay_original_relation(relation, assignment)
        positive.append(
            {
                "name": name,
                "proposal_pass": check.passed,
                "canonical_replay_pass": replay.generated_replay_pass,
                "authority_pass": proposal.authority_pass or check.authority_pass or replay.formal_authority_pass,
                "target_release": proposal.target_release or check.target_release or replay.target_release,
            }
        )

    permutation_digests = set()
    permutation_passes = []
    for terms in itertools.permutations(triangle.terms):
        permuted = candidate.AngleRelation(terms, triangle.pi_coefficient)
        proposal = candidate.compile_relation(permuted)
        permutation_digests.add(proposal.cover.source_relation_sha256)
        permutation_passes.append(
            candidate.check_exact_proposal(proposal, triangle_assignment).passed
            and canonical_replay.replay_original_relation(permuted, triangle_assignment).generated_replay_pass
        )

    collinear, collinear_assignment = generated_cases.undefined_collinear()
    collinear_proposal = candidate.compile_relation(collinear)
    collinear_check = candidate.check_exact_proposal(collinear_proposal, collinear_assignment)
    collinear_replay = canonical_replay.replay_original_relation(collinear, collinear_assignment)

    alias, alias_assignment = generated_cases.two_pi_alias()
    alias_cover = candidate.build_phase_cover(alias)
    alias_cover_check = candidate.ProposalCheck(
        passed=(
            candidate._zero(alias_cover.imaginary_polynomial)
            and candidate._sign(alias_cover.sign_polynomial) > 0
        ),
        reason="MODULO_COVER_ONLY",
    )
    alias_reason = _failure_reason(candidate.compile_relation, alias)

    ambiguous, _ambiguous_assignment = generated_cases.winding_ambiguity()
    ambiguity_reason = _failure_reason(candidate.compile_relation, ambiguous)

    legacy = generated_cases.legacy_sector3_shape()
    legacy_detected = candidate.is_legacy_sector3_shape(legacy)
    legacy_reason = _failure_reason(candidate.compile_relation, legacy)

    near_miss_check = candidate.check_exact_proposal(rational_proposal, near_miss_assignment)
    near_miss_replay = canonical_replay.replay_original_relation(rational, near_miss_assignment)

    result = {
        "schema_version": "geotarget.trace-closed-angle-lift-generated/v1",
        "positive_total": len(positive),
        "positive_pass": sum(
            row["proposal_pass"] and row["canonical_replay_pass"] for row in positive
        ),
        "permutation_total": len(permutation_passes),
        "permutation_pass": sum(permutation_passes),
        "permutation_digest_count": len(permutation_digests),
        "reflection_cover_invariant": (
            triangle_proposal.cover.algebraic_cover_sha256
            == reflected_proposal.cover.algebraic_cover_sha256
        ),
        "undefined_collinear_rejected": (
            not collinear_check.passed and not collinear_replay.generated_replay_pass
        ),
        "two_pi_alias_cover_pass": alias_cover_check.passed,
        "two_pi_alias_compile_reason": alias_reason,
        "winding_ambiguity_compile_reason": ambiguity_reason,
        "near_miss_rejected": (
            not near_miss_check.passed and not near_miss_replay.generated_replay_pass
        ),
        "legacy_sector3_shape_detected": legacy_detected,
        "legacy_sector3_compile_reason": legacy_reason,
        "legacy_sector3_activation_count": 0,
        "legacy_sector3_positive_count": 0,
        "authority_pass_count": sum(row["authority_pass"] for row in positive),
        "target_release_count": sum(row["target_release"] for row in positive),
        "truth_score_outcome_used": False,
        "formal_or_real_corpus_run": False,
        "telemetry": {
            "elapsed_seconds": time.monotonic() - started,
            "max_rss_bytes": _linux_peak_rss_bytes(),
            "cpu_affinity": list(affinity),
            "python": platform.python_version(),
            "sympy": sp.__version__,
            "native_thread_environment": {
                name: os.environ.get(name)
                for name in (
                    "OPENBLAS_NUM_THREADS",
                    "OMP_NUM_THREADS",
                    "MKL_NUM_THREADS",
                    "NUMEXPR_NUM_THREADS",
                )
            },
        },
        "records": positive,
        "hashes": {
            name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
            for name in (
                "candidate.py",
                "canonical_replay.py",
                "generated_cases.py",
                "run_generated.py",
                "test_candidate.py",
            )
        },
    }
    result["decision"] = (
        "GO_STATIC_AUDIT"
        if (
            result["positive_pass"] == result["positive_total"] == 3
            and result["permutation_pass"] == result["permutation_total"] == 6
            and result["permutation_digest_count"] == 1
            and result["reflection_cover_invariant"]
            and result["undefined_collinear_rejected"]
            and result["two_pi_alias_cover_pass"]
            and result["two_pi_alias_compile_reason"].startswith("NONZERO_OR_AMBIGUOUS_WINDING")
            and result["winding_ambiguity_compile_reason"].startswith("NONZERO_OR_AMBIGUOUS_WINDING")
            and result["near_miss_rejected"]
            and result["legacy_sector3_shape_detected"]
            and result["legacy_sector3_compile_reason"] == "LEGACY_SECTOR3_SHAPE_EXCLUDED"
            and result["authority_pass_count"] == 0
            and result["target_release_count"] == 0
            and result["telemetry"]["cpu_affinity"] == [14]
            and all(
                value == "1"
                for value in result["telemetry"]["native_thread_environment"].values()
            )
        )
        else "STOP_GENERATED_D0"
    )
    return result


def main():
    result = run()
    (HERE / "GENERATED_RESULT.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({key: value for key, value in result.items() if key != "records"}, indent=2))
    if result["decision"] != "GO_STATIC_AUDIT":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
