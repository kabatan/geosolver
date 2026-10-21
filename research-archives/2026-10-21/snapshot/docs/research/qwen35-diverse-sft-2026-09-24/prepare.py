"""Freeze disjoint configuration pools before collecting new model answers."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = Path("benchmarks/humpty_configurations_v2/training_problems.jsonl")
EVAL_IDS = (
    "H04", "H08", "H15", "DA08", "DA09", "DA18", "DB02", "DB03",
    "DB06", "DB15",
)
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


def main():
    rows = [json.loads(line) for line in SOURCE.read_text().splitlines() if line]
    assert len(rows) == 37 and len({row["id"] for row in rows}) == 37
    train_ids = [row["id"] for row in rows if row["id"] not in EVAL_IDS]
    assert len(train_ids) == 27
    def job(row, stage, index):
        ident = row["id"]
        digest = hashlib.sha256(f"20260924-diverse-{stage}-{ident}-{index}".encode()).digest()
        return {
            "id": f"{ident}-{stage}-{index}", "source_id": ident,
            "seed": int.from_bytes(digest[:4], "big") % (2**31),
            "messages": [{"role": "user", "content": INSTRUCTION + row["problem"]}],
        }
    material = [job(row, "material", 0) for row in rows if row["id"] in train_ids]
    evaluation = [job(row, "eval", 0) for row in rows if row["id"] in EVAL_IDS]
    (ROOT / "material-jobs.json").write_text(json.dumps(material, ensure_ascii=False, indent=2) + "\n")
    (ROOT / "eval-jobs.json").write_text(json.dumps(evaluation, ensure_ascii=False, indent=2) + "\n")
    protocol = {
        "status": "frozen_before_new_generation_and_training",
        "model_id": "Qwen/Qwen3.5-9B",
        "model_revision": "c202236235762e1c871ad0ccb60c8ee5ba337b9a",
        "source": str(SOURCE), "source_sha256": sha(SOURCE),
        "train_configuration_ids": train_ids,
        "eval_configuration_ids": list(EVAL_IDS),
        "prior_pilot_exposed_eval_ids": ["H04", "H15", "DA08", "DB06"],
        "material_jobs_sha256": sha(ROOT / "material-jobs.json"),
        "eval_jobs_sha256": sha(ROOT / "eval-jobs.json"),
        "material_sampling": {"thinking": True, "temperature": 0.7, "top_p": 0.95,
                              "top_k": 20, "presence_penalty": 0.2, "max_tokens": 12288},
        "eval_sampling": {"thinking": False, "temperature": 1.0, "top_p": 0.95,
                          "top_k": 20, "presence_penalty": 1.5, "max_tokens": 8192,
                          "samples_per_configuration": 2},
        "primary_measure": "Per-answer complete: correct final numeric answer, a true nontrivial general relation, a self-contained proof from the construction, and actual use of that relation for the numeric answer. Report per-configuration too.",
        "other_measures": ["numeric correctness", "true useful relation", "proof validity", "truncation", "novel auxiliary construction"],
        "training_admission": "Only the model's own visible answer with correct numeric value and audited, self-contained relation/proof/use. No human- or stronger-model-repaired teacher; no target theorem or answer is supplied in prompts. Record candidate yield by configuration.",
        "decision": "A broad SFT comparison requires at least 12 distinct admitted configurations and 24 complete answers. If the first material pass falls short, run a separately logged second self-generation pass rather than filling with unverified or duplicated examples.",
        "interpretation": "Existing 37 problems are researcher-authored and some configurations were used in prior development. The split is disjoint for this SFT, not a claim of never-seen pretraining data.",
    }
    (ROOT / "protocol.json").write_text(json.dumps(protocol, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"train": len(train_ids), "eval": len(EVAL_IDS),
                      "material_jobs": len(material), "eval_jobs": len(evaluation)}, indent=2))


if __name__ == "__main__":
    main()
