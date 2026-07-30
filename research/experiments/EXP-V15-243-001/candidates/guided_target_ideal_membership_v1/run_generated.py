#!/usr/bin/env python3
"""CPU14 generated subset-identity and three-way join D0."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from ideal_membership import prove_subset_identity, verify_subset_proof
from typed_join import prepare_typed_regular_job, verify_three_way_join


HERE = Path(__file__).resolve().parent
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


def _descriptor(value: int):
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


def _ordinary_proposal(value: int):
    return {
        "status": "TARGET_AUTHORITY_READY",
        "authority_pass": True,
        "descriptor": _descriptor(value),
        "case_family_truth_target_count_routing": False,
    }


def _affine():
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


def _point_reflect():
    return {
        "task": "solve",
        "variables": {"names": ["x", "y"]},
        "construction": [
            {"name": "P", "expr": "Point(x,y)"},
            {"name": "C", "expr": "Point(2,3)"},
            {"name": "R", "expr": "Reflect(P,C)"},
        ],
        "constraints": [
            {"def": "R.x", "value": "3"},
            {"def": "R.y", "value": "4"},
        ],
        "guards": [],
        "bounds": [[-10, 10], [-10, 10]],
        "answer": "Dot(Vector(P,R),Point(1,0))",
        "post_process": None,
    }


def _line_incidence():
    return {
        "task": "solve",
        "variables": {"names": ["x", "y"]},
        "construction": [
            {"name": "P", "expr": "Point(x,y)"},
            {"name": "A", "expr": "Point(0,0)"},
            {"name": "B", "expr": "Point(1,0)"},
            {"name": "L", "expr": "Line(A,B)"},
            {"name": "M", "expr": "PerpendicularLine(L,Point(2,0))"},
        ],
        "constraints": [
            {"def": "OnLine(P,M)", "value": "0"},
            {"def": "y", "value": "1"},
        ],
        "guards": [],
        "bounds": [[-10, 10], [-10, 10]],
        "answer": "x",
        "post_process": None,
    }


def _metamorphic_affine():
    return {
        "task": "solve",
        "variables": {"names": ["v", "u"]},
        "construction": [],
        "constraints": [
            {"def": "3*(u-v)", "value": "3"},
            {"def": "2*(u+v)", "value": "10"},
        ],
        "guards": ["AssumeGt(u,0)", "AssumeGt(v,0)"],
        "bounds": [[-10, 10], [-10, 10]],
        "answer": "u",
        "post_process": None,
    }


def _recursive_guard():
    value = _affine()
    value["guards"] = ["Assume((x > 0 and y > 0) or (x < 0 and y < 0))"]
    return value


def _proof(source_path: Path, value: int):
    ordinary = _ordinary_proposal(value)
    return prove_subset_identity(
        source_path,
        ordinary_proposal=ordinary,
        timeout_seconds=3.0,
    )


def _write_source(root: Path, name: str, document):
    path = root / f"{name}.json"
    path.write_text(json.dumps(document, separators=(",", ":")), encoding="utf-8")
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def _run_typed_worker(job, root: Path):
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
    certificate = (
        json.loads(result_path.read_text(encoding="utf-8"))
        if result_path.is_file()
        else {}
    )
    return completed.returncode, certificate


def main() -> int:
    if os.sched_getaffinity(0) != {14}:
        raise RuntimeError("generated ideal-membership D0 must be pinned to CPU14")
    with tempfile.TemporaryDirectory(prefix="guided-target-ideal-generated-") as name:
        root = Path(name)
        fixtures = [
            ("affine", _affine(), 3),
            ("point-reflect-vector-dot", _point_reflect(), 2),
            ("line-incidence", _line_incidence(), 2),
            ("metamorphic-affine", _metamorphic_affine(), 3),
        ]
        proofs = []
        paths = {}
        for label, document, value in fixtures:
            path, _digest = _write_source(root, label, document)
            paths[label] = path
            proofs.append((label, _proof(path, value)))

        affine_path = paths["affine"]
        wrong_q = _proof(affine_path, 4)
        descriptor_near_misses = []
        for coefficients, multiplicity in (([2, -6], 1), ([-1, 3], 1), ([1, -3], 2)):
            malformed = _ordinary_proposal(3)
            malformed["descriptor"] = dict(malformed["descriptor"])
            malformed["descriptor"]["minimal_polynomial_high_to_low"] = coefficients
            malformed["descriptor"]["isolating_interval"] = dict(
                malformed["descriptor"]["isolating_interval"]
            )
            malformed["descriptor"]["isolating_interval"]["multiplicity"] = multiplicity
            descriptor_near_misses.append(
                prove_subset_identity(
                    affine_path,
                    ordinary_proposal=malformed,
                    timeout_seconds=3.0,
                )
            )
        unsupported = _affine()
        unsupported["constraints"] = [
            {"def": "Distance(Point(x,y),Point(0,0))", "value": "1"}
        ]
        unsupported_path, _unsupported_sha = _write_source(root, "unsupported", unsupported)
        unsupported_result = _proof(unsupported_path, 3)
        inconsistent = _affine()
        inconsistent["constraints"] = [
            {"def": "x", "value": "0"},
            {"def": "x", "value": "1"},
        ]
        inconsistent_path, _inconsistent_sha = _write_source(root, "inconsistent", inconsistent)
        inconsistent_result = _proof(inconsistent_path, 7)

        ordinary = _ordinary_proposal(3)
        affine_proof = dict(proofs[0][1])
        typed_job = prepare_typed_regular_job(affine_path, [3.0, 2.0])
        worker_returncode, typed_certificate = _run_typed_worker(typed_job, root)
        join = verify_three_way_join(
            source_path=affine_path,
            job=typed_job,
            certificate=typed_certificate,
            subset_proof=affine_proof,
            ordinary_proposal=ordinary,
        )

        tampered = dict(typed_certificate)
        tampered["source_sha256"] = "0" * 64
        tampered_join = verify_three_way_join(
            source_path=affine_path,
            job=typed_job,
            certificate=tampered,
            subset_proof=affine_proof,
            ordinary_proposal=ordinary,
        )
        forged_proof = dict(affine_proof)
        forged_statement = dict(forged_proof["statement"])
        forged_statement["source_equation_cofactors"] = ["0"]
        forged_proof["statement"] = forged_statement
        forged_join = verify_three_way_join(
            source_path=affine_path,
            job=typed_job,
            certificate=typed_certificate,
            subset_proof=forged_proof,
            ordinary_proposal=ordinary,
        )
        wrong_ordinary_join = verify_three_way_join(
            source_path=affine_path,
            job=typed_job,
            certificate=typed_certificate,
            subset_proof=affine_proof,
            ordinary_proposal=_ordinary_proposal(4),
        )
        mutation_path, _mutation_sha = _write_source(root, "mutation", _affine())
        mutation_proof = _proof(mutation_path, 3)
        mutated_document = _affine()
        mutated_document["answer"] = "y"
        mutation_path.write_text(
            json.dumps(mutated_document, separators=(",", ":")), encoding="utf-8"
        )
        source_mutation_rejected = False
        try:
            verify_subset_proof(
                mutation_path,
                ordinary_proposal=ordinary,
                artifact=mutation_proof,
            )
        except Exception:
            source_mutation_rejected = True
        recursive_path, _recursive_sha = _write_source(root, "recursive", _recursive_guard())
        recursive_rejected = False
        try:
            prepare_typed_regular_job(recursive_path, [3.0, 2.0])
        except Exception:
            recursive_rejected = True

    proof_passes = {
        label: bool(
            proof.get("status") == "SUBSET_IDENTITY_PROVED_HOLD"
            and proof.get("cofactor_witness_complete") is True
            and proof.get("exact_remainder") == "0"
            and proof.get("authority_pass") is False
            and proof.get("target_release") is False
        )
        for label, proof in proofs
    }
    aggregate = {
        "schema_version": "geotarget.guided-target-ideal-membership-generated/v1",
        "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "positive_family_passes": proof_passes,
        "positive_pass_count": sum(proof_passes.values()),
        "positive_total": len(proof_passes),
        "negative_wrong_q_rejected": wrong_q.get("status") == "SUBSET_IDENTITY_NOT_PROVED",
        "noncanonical_degree1_descriptors_rejected": all(
            item.get("status") == "SUBSET_IDENTITY_NOT_PROVED"
            for item in descriptor_near_misses
        ),
        "unsupported_constraint_not_promoted": unsupported_result.get("status") == "SUBSET_IDENTITY_NOT_PROVED",
        "inconsistent_unit_ideal_rejected": inconsistent_result.get("status") == "SUBSET_IDENTITY_NOT_PROVED",
        "typed_worker_returncode": worker_returncode,
        "three_way_join_ready_experimental": join.get("status") == "THREE_WAY_JOIN_READY_EXPERIMENTAL",
        "three_way_join_authority_emitted": join.get("authority_pass") is True,
        "tampered_binding_rejected": tampered_join.get("status") == "THREE_WAY_JOIN_HOLD",
        "forged_subset_artifact_rejected": forged_join.get("status") == "THREE_WAY_JOIN_HOLD",
        "wrong_ordinary_proposal_binding_rejected": wrong_ordinary_join.get("status") == "THREE_WAY_JOIN_HOLD",
        "source_mutation_rejected": source_mutation_rejected,
        "recursive_guard_rejected_before_worker": recursive_rejected,
        "truth_used": False,
        "formal_scorer_used": False,
    }
    aggregate["passed"] = bool(
        aggregate["positive_pass_count"] == aggregate["positive_total"]
        and aggregate["negative_wrong_q_rejected"]
        and aggregate["noncanonical_degree1_descriptors_rejected"]
        and aggregate["unsupported_constraint_not_promoted"]
        and aggregate["inconsistent_unit_ideal_rejected"]
        and aggregate["typed_worker_returncode"] == 0
        and aggregate["three_way_join_ready_experimental"]
        and not aggregate["three_way_join_authority_emitted"]
        and aggregate["tampered_binding_rejected"]
        and aggregate["forged_subset_artifact_rejected"]
        and aggregate["wrong_ordinary_proposal_binding_rejected"]
        and aggregate["source_mutation_rejected"]
        and aggregate["recursive_guard_rejected_before_worker"]
    )
    (HERE / "GENERATED_RESULT.json").write_text(
        json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(aggregate, ensure_ascii=False, separators=(",", ":")))
    return 0 if aggregate["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
