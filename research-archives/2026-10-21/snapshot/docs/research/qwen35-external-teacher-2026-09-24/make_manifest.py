"""Record the effective files for the external-teacher diagnostic."""

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
FILES = {
    "train_original": "benchmarks/humpty_configurations_v2/training_problems.jsonl",
    "train_variants": "benchmarks/humpty_configurations_v2/training_variants.jsonl",
    "numeric_dev": "benchmarks/humpty_configurations_v2/eval_variants.jsonl",
    "proof_dev": "benchmarks/humpty_proof_evaluation_v2/evaluation_prompts.jsonl",
    "researcher_solutions": "benchmarks/humpty_configurations_v2/revisions.json",
    "english_templates": "docs/research/qwen35-diverse-sft-2026-09-24/english_templates.py",
    "teacher_jobs": "docs/research/qwen35-diverse-sft-2026-09-24/material-original-jobs-en.json",
    "numeric_eval_jobs": "docs/research/qwen35-diverse-sft-2026-09-24/eval-numeric-jobs-en.json",
    "proof_eval_jobs": "docs/research/qwen35-diverse-sft-2026-09-24/eval-proof-jobs-en.json",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main():
    paths = {key: ROOT / relative for key, relative in FILES.items()}
    train = read_jsonl(paths["train_original"])
    variants = read_jsonl(paths["train_variants"])
    dev = read_jsonl(paths["numeric_dev"])
    proof = read_jsonl(paths["proof_dev"])
    teacher_jobs = json.loads(paths["teacher_jobs"].read_text())
    numeric_jobs = json.loads(paths["numeric_eval_jobs"].read_text())
    proof_jobs = json.loads(paths["proof_eval_jobs"].read_text())
    ids = [x["id"] for x in train]
    assert len(ids) == len(set(ids)) == 37
    assert {x["id"] for x in variants} == set(ids)
    assert {x["id"] for x in dev} == set(ids)
    assert {x["source_id"] for x in teacher_jobs} == set(ids)
    assert {x["source_id"] for x in numeric_jobs} == set(ids)
    assert len(proof) == len(proof_jobs) == 6
    assert {x["id"] for x in proof} == {x["source_id"] for x in proof_jobs}
    assert all(x["augmentation"] == "original" and x["variant"] == "v0" for x in teacher_jobs)
    assert all(x["split"] == "dev" for x in dev)
    assert all(not re.search(r"[ぁ-んァ-ン一-龥]", x["messages"][0]["content"])
               for x in teacher_jobs + numeric_jobs + proof_jobs)
    historical = json.loads((ROOT / "benchmarks/humpty_proof_evaluation_v2/manifest.json").read_text())
    result = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "effective_sources_frozen_before_training",
        "study": "external_teacher_positive_control",
        "model_id": "Qwen/Qwen3.5-9B",
        "model_revision": "c202236235762e1c871ad0ccb60c8ee5ba337b9a",
        "files": {key: {"path": FILES[key], "sha256": sha(path)} for key, path in paths.items()},
        "train_configuration_ids": ids,
        "numeric_dev_configuration_ids": [x["id"] for x in dev],
        "proof_dev_ids": [x["id"] for x in proof],
        "proof_transfer_ids": ["EV02", "DU01", "OB01"],
        "proof_same_configuration_ids": ["AP01", "N01", "N02"],
        "historical_proof_manifest_training_sha256": historical["training_sha256"],
        "historical_training_hash_matches_current": historical["training_sha256"] == sha(paths["train_original"]),
        "prior_base_numeric_receipt": "qwen/.runtime/qwen35_diverse_sft_20260924/eval-numeric-base-en-32k/receipt.json",
        "prior_base_proof_receipt": "qwen/.runtime/qwen35_diverse_sft_20260924/eval-proof-base-en-32k/receipt.json",
        "evaluation_boundary": "37 numeric dev configurations overlap all 37 training IDs; six existing proof development tasks are near/compositional or same-configuration probes.",
    }
    assert not result["historical_training_hash_matches_current"]
    destination = HERE / "manifest.json"
    assert not destination.exists(), "Never overwrite a frozen manifest"
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(destination, sha(destination))


if __name__ == "__main__":
    main()
