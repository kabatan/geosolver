#!/usr/bin/env python3
"""CPU14-only independent adversary audit for the partial-ideal/root join."""

from __future__ import annotations

import copy
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Mapping


CANDIDATE_ROOT = Path(
    os.environ.get(
        "PARTIAL_IDEAL_CANDIDATE_ROOT",
        "/home/kabatan/work/solver-wt/guided-target-ideal-membership-v1/"
        "research/experiments/EXP-V15-243-001/candidates/"
        "guided_target_ideal_membership_v1",
    )
).resolve()
RUNTIME_ROOT = Path(
    os.environ.get(
        "GEOTARGET_CURRENT_RUNTIME_ROOT",
        "/home/kabatan/work/solver-experiment-runtime/solver",
    )
).resolve()
JULIA = Path("/home/kabatan/.juliaup/bin/julia")
WORKER = (
    RUNTIME_ROOT
    / "research/experiments/EXP-REAL61-004/local_validated_witness/worker.jl"
)
PROJECT = (
    RUNTIME_ROOT
    / "research/experiments/EXP-REAL61-002/interval_completeness"
)
HERE = Path(__file__).resolve().parent


def canonical_sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    ).hexdigest()


def descriptor(value: int) -> dict[str, object]:
    return {
        "minimal_polynomial_high_to_low": [1, -value],
        "selected_real_root_index": 0,
        "isolating_interval": {
            "left": str(value),
            "right": str(value),
            "multiplicity": 1,
            "real_root_index": 0,
        },
    }


def ordinary(value: int, *, custom_descriptor: object | None = None) -> dict[str, object]:
    return {
        "status": "TARGET_AUTHORITY_READY",
        "authority_pass": True,
        "descriptor": descriptor(value) if custom_descriptor is None else custom_descriptor,
        "case_family_truth_target_count_routing": False,
    }


def affine() -> dict[str, object]:
    return {
        "task": "solve",
        "variables": {"names": ["x", "y"]},
        "construction": [],
        "constraints": [
            {"def": "x+y", "value": "5"},
            {"def": "x-y", "value": "1"},
        ],
        "guards": ["AssumeGt(x,0)", "AssumeGt(y,0)"],
        "bounds": [[-10, 10], [-10, 10]],
        "answer": "x",
        "post_process": None,
    }


def one_variable(constraints: list[dict[str, str]], answer: str) -> dict[str, object]:
    return {
        "task": "solve",
        "variables": {"names": ["x"]},
        "construction": [],
        "constraints": constraints,
        "guards": [],
        "bounds": [[-10, 10]],
        "answer": answer,
        "post_process": None,
    }


def write_source(root: Path, name: str, document: object) -> Path:
    path = root / f"{name}.json"
    path.write_text(
        json.dumps(document, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def run_worker(job: object, root: Path) -> tuple[int, dict[str, object], str]:
    job_path = root / "typed-job.json"
    result_path = root / "typed-certificate.json"
    job_path.write_text(json.dumps(job, separators=(",", ":")), encoding="utf-8")
    environment = os.environ.copy()
    environment.update(
        {
            "JULIA_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
        }
    )
    completed = subprocess.run(
        [
            "taskset",
            "-c",
            "14",
            str(JULIA),
            f"--project={PROJECT}",
            str(WORKER),
            str(job_path),
            str(result_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
        env=environment,
    )
    result = json.loads(result_path.read_text()) if result_path.is_file() else {}
    return completed.returncode, result, completed.stderr[-1000:]


def is_rejected(proof: Mapping[str, object]) -> bool:
    return proof.get("status") == "SUBSET_IDENTITY_NOT_PROVED"


def main() -> int:
    if os.sched_getaffinity(0) != {14}:
        raise RuntimeError("independent audit must run with taskset -c 14")
    if not CANDIDATE_ROOT.is_dir():
        raise RuntimeError(f"candidate root missing: {CANDIDATE_ROOT}")
    sys.path.insert(0, str(CANDIDATE_ROOT))
    ideal = importlib.import_module("ideal_membership")
    joiner = importlib.import_module("typed_join")

    checks: dict[str, bool] = {}
    observations: dict[str, object] = {}
    with tempfile.TemporaryDirectory(prefix="partial-ideal-adversary-") as name:
        root = Path(name)
        affine_path = write_source(root, "affine", affine())
        ordinary3 = ordinary(3)
        proof3 = ideal.prove_subset_identity(
            affine_path, ordinary_proposal=ordinary3, timeout_seconds=3.0
        )
        checks["positive_affine_universal_identity"] = (
            proof3.get("status") == "SUBSET_IDENTITY_PROVED_HOLD"
            and proof3.get("cofactor_witness_complete") is True
            and proof3.get("authority_pass") is False
            and proof3.get("target_release") is False
        )

        inconsistent_path = write_source(
            root,
            "inconsistent",
            one_variable(
                [{"def": "x", "value": "0"}, {"def": "x", "value": "1"}],
                "x",
            ),
        )
        checks["inconsistent_unit_ideal_rejected"] = is_rejected(
            ideal.prove_subset_identity(
                inconsistent_path, ordinary_proposal=ordinary(0), timeout_seconds=3.0
            )
        )

        component_path = write_source(
            root,
            "two-components",
            one_variable([{"def": "x*x", "value": "1"}], "x"),
        )
        checks["wrong_component_or_missing_target_rejected"] = is_rejected(
            ideal.prove_subset_identity(
                component_path, ordinary_proposal=ordinary(1), timeout_seconds=3.0
            )
        )
        same_target_path = write_source(
            root,
            "two-configurations-one-target",
            one_variable([{"def": "x*x", "value": "1"}], "x*x"),
        )
        same_target_proof = ideal.prove_subset_identity(
            same_target_path, ordinary_proposal=ordinary(1), timeout_seconds=3.0
        )
        checks["multiple_configurations_same_target_accepted"] = (
            same_target_proof.get("status") == "SUBSET_IDENTITY_PROVED_HOLD"
        )

        denominator_document = {
            "task": "solve",
            "variables": {"names": ["x", "y"]},
            "construction": [],
            "constraints": [
                {"def": "x", "value": "1"},
                {"def": "y", "value": "0"},
            ],
            "guards": [],
            "bounds": [[-10, 10], [-10, 10]],
            "answer": "x/y",
            "post_process": None,
        }
        denominator_path = write_source(root, "zero-denominator", denominator_document)
        checks["symbolic_or_zero_denominator_rejected"] = is_rejected(
            ideal.prove_subset_identity(
                denominator_path, ordinary_proposal=ordinary(1), timeout_seconds=3.0
            )
        )

        square = descriptor(1)
        square["minimal_polynomial_high_to_low"] = [1, 0, -1]
        sign = descriptor(3)
        sign["minimal_polynomial_high_to_low"] = [-1, 3]
        scaled = descriptor(3)
        scaled["minimal_polynomial_high_to_low"] = [2, -6]
        bad_ordinal = descriptor(3)
        bad_ordinal["selected_real_root_index"] = 1
        bad_ordinal["isolating_interval"]["real_root_index"] = 1
        bad_multiplicity = descriptor(3)
        bad_multiplicity["isolating_interval"]["multiplicity"] = 2
        descriptor_near_misses = {
            "square": square,
            "negative-leading-sign": sign,
            "nonprimitive-scale": scaled,
            "wrong-root-ordinal": bad_ordinal,
            "wrong-multiplicity": bad_multiplicity,
        }
        descriptor_results = {}
        for label, value in descriptor_near_misses.items():
            trial = ideal.prove_subset_identity(
                affine_path,
                ordinary_proposal=ordinary(3, custom_descriptor=value),
                timeout_seconds=3.0,
            )
            descriptor_results[label] = trial.get("status")
        checks["degree_one_descriptor_is_canonical_and_ordinal_zero"] = all(
            status == "SUBSET_IDENTITY_NOT_PROVED"
            for status in descriptor_results.values()
        )
        observations["descriptor_near_misses"] = descriptor_results

        branch_document = affine()
        branch_document["answer"] = "abs(x)"
        branch_path = write_source(root, "branch-target", branch_document)
        checks["branch_selector_target_rejected"] = is_rejected(
            ideal.prove_subset_identity(
                branch_path, ordinary_proposal=ordinary(3), timeout_seconds=3.0
            )
        )

        source_branch_document = affine()
        source_branch_document["construction"] = [
            {"name": "A", "expr": "Point(-2,0)"},
            {"name": "B", "expr": "Point(2,0)"},
            {"name": "L", "expr": "Line(A,B)"},
            {"name": "C", "expr": "Circle(Point(0,0),1)"},
            {
                "name": "P",
                "expr": "Intersect(L,C,exclude=Point(1,0))",
            },
        ]
        source_branch_path = write_source(root, "source-branch", source_branch_document)
        source_branch_proof = ideal.prove_subset_identity(
            source_branch_path, ordinary_proposal=ordinary3, timeout_seconds=3.0
        )
        source_branch_root_rejected = False
        try:
            joiner.prepare_typed_regular_job(source_branch_path, [3.0, 2.0])
        except Exception:
            source_branch_root_rejected = True
        checks["branch_selector_cannot_bypass_R_scope"] = (
            source_branch_proof.get("status") == "SUBSET_IDENTITY_PROVED_HOLD"
            and source_branch_root_rejected
        )

        altered = copy.deepcopy(affine())
        altered["constraints"][0]["value"] = "7"
        altered_path = write_source(root, "altered-source", altered)
        checks["proof_is_bound_to_raw_source_bytes"] = False
        try:
            ideal.verify_subset_proof(
                altered_path,
                ordinary_proposal=ordinary3,
                artifact=proof3,
                timeout_seconds=3.0,
            )
        except Exception:
            checks["proof_is_bound_to_raw_source_bytes"] = True

        tampered_statement = copy.deepcopy(proof3)
        tampered_statement["statement"]["target_minus_q"] = "0"
        checks["tampered_statement_rejected"] = False
        try:
            ideal.verify_subset_proof(
                affine_path,
                ordinary_proposal=ordinary3,
                artifact=tampered_statement,
                timeout_seconds=3.0,
            )
        except Exception:
            checks["tampered_statement_rejected"] = True

        tampered_cofactor = copy.deepcopy(proof3)
        tampered_cofactor["statement"]["source_equation_cofactors"] = []
        tampered_cofactor["statement_sha256"] = canonical_sha(tampered_cofactor["statement"])
        checks["tampered_cofactor_rejected_even_with_rehashed_statement"] = False
        try:
            ideal.verify_subset_proof(
                affine_path,
                ordinary_proposal=ordinary3,
                artifact=tampered_cofactor,
                timeout_seconds=3.0,
            )
        except Exception:
            checks["tampered_cofactor_rejected_even_with_rehashed_statement"] = True

        checks["proposal_q_binding_rejects_wrong_q"] = False
        try:
            ideal.verify_subset_proof(
                affine_path,
                ordinary_proposal=ordinary(4),
                artifact=proof3,
                timeout_seconds=3.0,
            )
        except Exception:
            checks["proposal_q_binding_rejects_wrong_q"] = True

        duplicate = ideal.prove_subset_identity(
            affine_path, ordinary_proposal=ordinary3, timeout_seconds=3.0
        )
        checks["duplicate_proofs_have_stable_identity_key"] = (
            duplicate.get("statement_sha256") == proof3.get("statement_sha256")
            and duplicate.get("ordinary_proposal_sha256")
            == proof3.get("ordinary_proposal_sha256")
            and duplicate.get("source_sha256") == proof3.get("source_sha256")
        )

        job = joiner.prepare_typed_regular_job(affine_path, [3.0, 2.0])
        worker_returncode, certificate, worker_stderr = run_worker(job, root)
        observations["typed_worker_returncode"] = worker_returncode
        observations["typed_worker_stderr_tail"] = worker_stderr
        result = joiner.verify_three_way_join(
            source_path=affine_path,
            job=job,
            certificate=certificate,
            subset_proof=proof3,
            ordinary_proposal=ordinary3,
        )
        checks["three_way_join_reaches_experimental_ready"] = (
            worker_returncode == 0
            and result.get("status") == "THREE_WAY_JOIN_READY_EXPERIMENTAL"
        )
        checks["local_witness_never_directly_emits_collector_authority"] = (
            result.get("authority_pass") is False
            and result.get("target_release") is False
            and result.get("all_target_authority_conjuncts_present") is False
            and result.get("common_worker_integration") == "HOLD"
        )

        forged = copy.deepcopy(proof3)
        forged["statement"]["source_equation_cofactors"] = []
        forged["statement_sha256"] = canonical_sha(forged["statement"])
        forged_join = joiner.verify_three_way_join(
            source_path=affine_path,
            job=job,
            certificate=certificate,
            subset_proof=forged,
            ordinary_proposal=ordinary3,
        )
        checks["join_replays_subset_identity_not_status_boolean"] = (
            forged_join.get("status") == "THREE_WAY_JOIN_HOLD"
        )

        certificate_tamper = copy.deepcopy(certificate)
        certificate_tamper["all_source_predicates_interval_valid"] = False
        certificate_tamper_join = joiner.verify_three_way_join(
            source_path=affine_path,
            job=job,
            certificate=certificate_tamper,
            subset_proof=proof3,
            ordinary_proposal=ordinary3,
        )
        checks["guard_certificate_tamper_rejected"] = (
            certificate_tamper_join.get("status") == "THREE_WAY_JOIN_HOLD"
        )

    candidate_hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(CANDIDATE_ROOT.glob("*.py"))
    }
    result = {
        "schema_version": "geotarget.partial-ideal-regular-root-join-adversary/v1",
        "candidate_root": str(CANDIDATE_ROOT),
        "candidate_hashes": candidate_hashes,
        "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "checks": checks,
        "observations": observations,
        "pass_count": sum(checks.values()),
        "check_count": len(checks),
        "truth_used": False,
        "formal_scorer_used": False,
    }
    result["passed"] = all(checks.values())
    output = HERE / "AUDIT_RESULT.json"
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result, separators=(",", ":"), ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
