"""Freeze exploratory dose protocols after the teacher audit, before evaluation."""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan = json.loads((HERE / "train-plan-v2.json").read_text())
    dataset = HERE / "train-multiconfig-en.json"
    rows = json.loads(dataset.read_text())
    n = len(rows)
    configs = len({row["source"] for row in rows})
    broad_gate = n >= 24 and configs >= 12
    if broad_gate:
        arms = {"broad_2ep": 2}
    else:
        # This is an exploratory fallback and is never labelled broad SFT.
        arms = {"exploratory_2ep": 2, "exploratory_repeat": max(3, math.ceil(40 / n))}
    common = {
        "seed": plan["seed"], "lr": plan["learning_rate"], "grad_clip": 1.0,
        "lora_rank": plan["lora_rank"], "lora_alpha": plan["lora_alpha"],
        "modules": ["q_proj", "k_proj", "v_proj", "o_proj", "in_proj_qkv",
                    "in_proj_z", "out_proj", "gate_proj", "up_proj", "down_proj"],
        "max_sequence_tokens": plan["max_sequence_tokens"],
        "micro_batch": 1,
        "optimizer": "AdamW, weight decay zero, constant learning rate",
        "loss": "Visible assistant answer including EOS only; non-thinking chat template",
        "checkpoint": "Single final adapter; no selection using evaluation outputs",
        "dataset": str(dataset.resolve()), "dataset_sha256": sha(dataset),
        "eval_jobs": str((HERE / "eval-proof-jobs-en.json").resolve()),
        "eval_jobs_sha256": sha(HERE / "eval-proof-jobs-en.json"),
        "model_revision": plan["model_revision"], "n_examples": n,
        "n_configurations": configs, "broad_gate_passed": broad_gate,
        "protocol_status": "frozen_before_any_english_evaluation",
    }
    for arm, epochs in arms.items():
        spec = common | {"epochs": epochs, "study_arm": arm,
                         "planned_updates": epochs * n}
        path = HERE / f"train-{arm}-protocol-en.json"
        path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n")
    decision = {"broad_gate_passed": broad_gate, "examples": n,
                "configurations": configs, "required_examples": 24,
                "required_configurations": 12,
                "arms": arms,
                "fallback_rationale": "Quantify whether repeating the small audited corpus changes performance, without claiming the planned broad-diversity comparison was run."}
    (HERE / "training-entry-decision-en.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(decision))


if __name__ == "__main__":
    main()
