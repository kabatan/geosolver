"""Freeze jobs using the repository's pre-existing train/dev variant split."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TRAIN_SOURCE = Path("benchmarks/humpty_configurations_v2/training_variants.jsonl")
EVAL_SOURCE = Path("benchmarks/humpty_configurations_v2/eval_variants.jsonl")
PROOF_SOURCE = Path("benchmarks/humpty_proof_evaluation_v2/evaluation_prompts.jsonl")
INSTRUCTION = (
    "以下の求値問題を解いてください。問題文には解法を示していません。"
    "まず、この作図に固有で、未知量や計算を実際に減らす一般的な関係を一つ自分で見つけてください。"
    "必要なら補助点・補助円・補助線を自分で導入してよく、座標・ベクトルも使えます。"
    "回答には(1)関係と成立条件、(2)作図の定義から核心を省略しない一般証明、"
    "(3)その関係を与えられた数値に使う計算と最終値を含めてください。"
    "相似・共円・恒等式を『明らか』『計算で分かる』だけで済ませないでください。"
    "解けない部分は推測で埋めず、未証明・未解決と明記してください。"
    "可能なら簡潔に書いてください。\n\n"
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def make_job(row, phase, repetition=0):
    key = f"diverse-v2-{phase}-{row['id']}-{row['variant']}-{repetition}"
    seed = int.from_bytes(hashlib.sha256(key.encode()).digest()[:4], "big") % (2**31)
    return {
        "id": f"{row['id']}-{row['variant']}-{phase}-{repetition}",
        "source_id": row["id"], "variant": row["variant"],
        "augmentation": row["augmentation"], "seed": seed,
        "messages": [{"role": "user", "content": INSTRUCTION + row["problem"]}],
    }


def save(name, rows):
    path = ROOT / name
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
    return sha(path)


def main():
    train = load_jsonl(TRAIN_SOURCE)
    evaluation = load_jsonl(EVAL_SOURCE)
    proof = load_jsonl(PROOF_SOURCE)
    assert len(train) == 148 and len(evaluation) == 37 and len(proof) == 6
    assert {row["id"] for row in train} == {row["id"] for row in evaluation}
    assert all(row["split"] == "train" for row in train)
    assert all(row["split"] == "dev" for row in evaluation)
    assert len({(row["id"], row["variant"]) for row in train}) == 148
    originals = [row for row in train if row["augmentation"] == "original"]
    shapes = [row for row in train if row["augmentation"] == "shape"]
    assert len(originals) == 37 and len(shapes) == 27
    jobs_hashes = {
        "material_original": save("material-original-jobs-v2.json", [make_job(row, "material", 0) for row in originals]),
        "material_original_repeat": save("material-repeat-jobs-v2.json", [make_job(row, "material", 1) for row in originals]),
        "material_shape": save("material-shape-jobs-v2.json", [make_job(row, "material", 0) for row in shapes]),
        "numeric_dev": save("eval-numeric-jobs-v2.json", [make_job(row, "eval", 0) for row in evaluation]),
    }
    protocol = {
        "status": "frozen_before_v2_material_generation_or_weight_update",
        "replaces": "protocol.json: its ad hoc ten-configuration evaluation was stopped before any SFT and is excluded from the primary comparison",
        "model_id": "Qwen/Qwen3.5-9B",
        "model_revision": "c202236235762e1c871ad0ccb60c8ee5ba337b9a",
        "train_source": str(TRAIN_SOURCE), "train_source_sha256": sha(TRAIN_SOURCE),
        "numeric_dev_source": str(EVAL_SOURCE), "numeric_dev_source_sha256": sha(EVAL_SOURCE),
        "proof_source": str(PROOF_SOURCE), "proof_source_sha256": sha(PROOF_SOURCE),
        "jobs_sha256": jobs_hashes,
        "first_material_pass": "All 37 v0 training configurations, one self-generation each. Further frozen passes are 37 new seeds and 27 shape variants; similarity-only variants are excluded from material diversity counts.",
        "numeric_dev": "The existing one-per-configuration dev variants, 37 questions, each sampled twice. Nine are shape variants and 28 similarity variants; score these strata separately. Same configuration as training, new numerical parameters; not a new-structure test.",
        "proof_eval": "The existing six proof prompts; retain three transfer and three same-configuration groups. Prior base outputs are available, but the after-SFT arm must use the same frozen prompts and generation settings.",
        "material_sampling": {"thinking": True, "temperature": 0.7, "top_p": 0.95,
                              "top_k": 20, "presence_penalty": 0.2, "max_tokens": 12288},
        "numeric_eval_sampling": {"thinking": False, "temperature": 1.0, "top_p": 0.95,
                                  "top_k": 20, "presence_penalty": 1.5,
                                  "max_tokens": 8192, "samples_per_configuration": 2},
        "primary_measure": "Per-answer complete on numeric dev: exact answer, true nontrivial useful relation, self-contained proof, and application of that relation. Also report per-configuration success and truncation.",
        "secondary_measure": "Complete proof on the existing six-problem proof evaluation, transfer and same-configuration separately; auxiliary hint prompts excluded.",
        "material_admission": "Only own visible final self-contained relation/proof/use with exact numeric value verified against the separate label. No human or stronger-model repair, no reference solution or target relation in prompt. Record all generation attempts and admit reasons.",
        "training_gate": "Aim for at least 12 distinct admitted configurations and 24 complete examples before broad SFT. If short after the frozen passes, report the observed yield and do not label an inadequate corpus as a broad test.",
        "interpretation": "Pre-existing numeric dev uses the same 37 configurations and is a variant-generalization measure. Existing proof transfer group is the configuration-transfer measure. Existing problems may be known from earlier research or pretraining.",
    }
    (ROOT / "protocol-v2.json").write_text(json.dumps(protocol, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"original": len(originals), "shape": len(shapes),
                      "numeric_dev": len(evaluation), "proof": len(proof)}, indent=2))


if __name__ == "__main__":
    main()
