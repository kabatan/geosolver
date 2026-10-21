"""Freeze the single main LoRA run after the audited dataset is built."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((HERE / "manifest.json").read_text())
    data = json.loads((HERE / "train.json").read_text())
    ids = [x["source"] for x in data]
    assert len(ids) == len(set(ids)) and set(ids) <= set(manifest["train_configuration_ids"])
    eval_jobs = ROOT / manifest["files"]["proof_eval_jobs"]["path"]
    protocol = {
        "seed": 2026092427,
        "lr": 5e-5,
        "grad_clip": 1.0,
        "lora_rank": 8,
        "lora_alpha": 16,
        "modules": ["q_proj", "k_proj", "v_proj", "o_proj", "in_proj_qkv",
                    "in_proj_z", "out_proj", "gate_proj", "up_proj", "down_proj"],
        "max_sequence_tokens": 8192,
        "micro_batch": 1,
        "optimizer": "AdamW, weight decay zero, constant learning rate",
        "loss": "English visible assistant answer including EOS only; non-thinking chat template",
        "checkpoint": "One frozen two-epoch final adapter; no eval-based selection",
        "dataset": str((HERE / "train.json").resolve()),
        "dataset_sha256": sha(HERE / "train.json"),
        "eval_jobs": str(eval_jobs.resolve()),
        "eval_jobs_sha256": sha(eval_jobs),
        "model_revision": manifest["model_revision"],
        "n_examples": len(data),
        "n_configurations": len(ids),
        "broad_gate_passed": len(ids) == 37,
        "epochs": 2,
        "study_arm": "external_teacher_positive_control" if len(ids) == 37 else "external_teacher_partial_coverage",
        "planned_updates": len(ids) * 2,
    }
    path = HERE / "train-protocol.json"
    assert not path.exists(), "Never overwrite a frozen training protocol"
    path.write_text(json.dumps(protocol, ensure_ascii=False, indent=2) + "\n")
    print(path, sha(path), len(data), "examples")


if __name__ == "__main__":
    main()
