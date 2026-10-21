#!/usr/bin/env python3
"""Freeze relation-given proof prompts paired to the six fresh4 jobs.

CPU-only derivative. It preserves each numerical problem and seed exactly,
adds one common orthocenter-projection lemma plus generic proof requirements,
and keeps all exact answers and target branch audits in grader-only files.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
FRESH4 = HERE.parent / "followup-fresh4"

SUPPLIED_LEMMA = (
    "General lemma (you may use this without proof): In any nondegenerate "
    "triangle ABC, let H be its orthocenter and M the midpoint of BC. If P "
    "is the orthogonal projection of H onto line AM, then the directed-vector "
    "identity (vector MP) dot (vector MA) = (BC/2)^2 holds. Equivalently, "
    "vector MP = ((BC/2)^2 / AM^2) vector MA. Here AM and BC in the formula "
    "are lengths; the arrows in the identity denote directed vectors. This "
    "lemma does not identify any point defined elsewhere in a problem."
)

PROOF_REQUIREMENT = (
    "Before substituting numerical values, identify any problem-defined point "
    "to which you apply the lemma and prove from the stated construction that "
    "its projection hypothesis holds; do not infer that mapping from the "
    "lemma or from a point merely lying on a named line or circle. If the "
    "foot is explicitly given, say so and still derive the remaining "
    "construction relation. Establish the selected intersection, order, "
    "sign, and every nonzero-factor condition before using it or canceling. "
    "Then derive the relation needed for the requested quantity and compute "
    "the exact value. The supplied lemma alone does not determine that value."
)


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def write_json(name: str, value) -> str:
    path = HERE / name
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    return sha_file(path)


def main():
    source_jobs_path = FRESH4 / "eval_jobs.json"
    source_keys_path = FRESH4 / "answer_key.json"
    source_checks_path = FRESH4 / "construction_checks.json"
    source_jobs = json.loads(source_jobs_path.read_text())
    answer_key = json.loads(source_keys_path.read_text())
    source_checks = json.loads(source_checks_path.read_text())
    assert len(source_jobs) == len(answer_key) == 6
    assert source_checks["status"] == "passed"
    checks_by_job = {row["job_id"]: row for row in source_checks["checks_by_job"]}
    assert set(checks_by_job) == {row["id"] for row in source_jobs}

    jobs = []
    original_prompts = {}
    for source in source_jobs:
        job = copy.deepcopy(source)
        original_message = job["messages"][0]["content"]
        original_prompts[job["id"]] = original_message
        job["messages"][0]["content"] = (
            original_message
            + "\n\nRelation-given proof diagnostic:\n"
            + SUPPLIED_LEMMA
            + "\n\n"
            + PROOF_REQUIREMENT
        )
        assert job["english_problem"] == source["english_problem"]
        assert job["seed"] == source["seed"]
        assert job["messages"][0]["content"].startswith(original_message)
        assert "answer_exact" not in json.dumps(job, ensure_ascii=False)
        assert all(word not in job["messages"][0]["content"] for word in (
            "26/3", "28/3", "sqrt(2198)/11", "sqrt(305)/4", "507/200", "289/39"
        ))
        assert job["id"] in checks_by_job
        assert checks_by_job[job["id"]]["exact_answer_matches_independent_formula"] is True
        jobs.append(job)

    # The complete answer key is copied to a separate file unchanged. Branch
    # audits likewise stay outside every model message.
    assert {row["job_id"] for row in answer_key} == {row["id"] for row in jobs}
    serialized_messages = json.dumps([j["messages"] for j in jobs], ensure_ascii=False)
    assert "branch_conditions" not in serialized_messages
    assert all(j["seed"] == s["seed"] for j, s in zip(jobs, source_jobs, strict=True))
    assert all(j["english_problem"] == s["english_problem"] for j, s in zip(jobs, source_jobs, strict=True))

    s, x, y = __import__("sympy").symbols("s x y", nonzero=True, real=True)
    sp = __import__("sympy")
    orthocenter = sp.Matrix([x, (s**2 - x**2) / y])
    vertex = sp.Matrix([x, y])
    symbolic_residual = sp.simplify(orthocenter.dot(vertex) - s**2)
    assert symbolic_residual == 0

    math_audit = {
        "status": "passed",
        "scope": "audit the supplied general lemma and its separation from target-specific construction mappings",
        "supplied_lemma": SUPPLIED_LEMMA,
        "assumptions": [
            "ABC is nondegenerate, so in coordinates with BC horizontal the altitude height y is nonzero",
            "A != M, so AM^2 is nonzero",
            "P is defined as the orthogonal projection of H onto line AM; no target construction point is presumed to be P",
        ],
        "coordinate_proof": [
            "Set M=(0,0), B=(-s,0), C=(s,0), A=(x,y), where s=BC/2.",
            "The altitude from A is vertical. Intersecting it with the altitude from B gives H=(x,(s^2-x^2)/y).",
            "Then (vector MH) dot (vector MA) = x^2 + y*(s^2-x^2)/y = s^2.",
            "Since vector MH - vector MP is perpendicular to MA, (vector MP) dot (vector MA) equals (vector MH) dot (vector MA), hence s^2.",
            "Because MP is parallel to MA, the equivalent vector formula follows by dividing by AM^2.",
        ],
        "symbolic_residual_after_simplification": str(symbolic_residual),
        "target_specific_construction_maps": "not supplied in model messages; each prompt explicitly requires the model to establish its own mapping and branch",
        "instances": [
            {
                "job_id": job["id"],
                "source_id": job["source_id"],
                "instance_index": job["fresh4_instance"],
                "construction_and_branch_verification_reused": checks_by_job[job["id"]]["branch_conditions"],
                "grader_only_answer_key_separate": True,
                "prompt_contains_target_answer": False,
            }
            for job in jobs
        ],
        "source_fresh4_sha256": {
            "eval_jobs.json": sha_file(source_jobs_path),
            "answer_key.json": sha_file(source_keys_path),
            "construction_checks.json": sha_file(source_checks_path),
            "hashes.json": sha_file(FRESH4 / "hashes.json"),
        },
        "gpu_used": False,
        "model_outputs_opened": False,
        "scores_inspected": False,
    }

    jobs_hash = write_json("eval_jobs.json", jobs)
    keys_hash = write_json("answer_key.json", answer_key)
    math_hash = write_json("math_audit.json", math_audit)
    source_paths = [
        source_jobs_path,
        source_keys_path,
        source_checks_path,
        FRESH4 / "PROTOCOL.md",
        FRESH4 / "freeze_fresh4.py",
        FRESH4 / "hashes.json",
    ]
    sources = {str(path.relative_to(ROOT)): sha_file(path) for path in source_paths}
    created = {
        "eval_jobs.json": jobs_hash,
        "answer_key.json": keys_hash,
        "math_audit.json": math_hash,
        "PROTOCOL.md": sha_file(HERE / "PROTOCOL.md"),
        "freeze_relation_given_fresh4.py": sha_file(Path(__file__)),
    }
    manifest = {
        "label": "relation-given fresh4; six theorem-execution diagnostic jobs; no evaluation performed",
        "created_artifacts_sha256": created,
        "source_artifacts_sha256": sources,
        "supplied_lemma_sha256": sha_bytes(SUPPLIED_LEMMA.encode()),
        "preserved_fresh4_fields": ["id", "source_id", "seed", "english_problem"],
        "runtime": {"python": sys.version.split()[0], "sympy": sp.__version__},
        "reproduction": ".venv/bin/python3.12 docs/research/qwen35-external-teacher-2026-09-25/heldout-near-transfer/followup-relation-given-fresh4/freeze_relation_given_fresh4.py",
    }
    hashes_hash = write_json("hashes.json", manifest)
    print(json.dumps({
        "status": "passed",
        "job_count": len(jobs),
        "eval_jobs_sha256": jobs_hash,
        "answer_key_sha256": keys_hash,
        "math_audit_sha256": math_hash,
        "hashes_json_sha256": hashes_hash,
        "seeds_and_numerical_prompts_preserved": True,
        "target_answers_and_branch_checks_absent_from_model_messages": True,
        "gpu_used": False,
        "model_outputs_opened": False,
        "scores_inspected": False,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
