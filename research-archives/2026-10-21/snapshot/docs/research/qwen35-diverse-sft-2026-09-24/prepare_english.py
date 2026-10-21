"""Render checked English train/dev/proof jobs from the pre-existing split."""

import hashlib
import json
import re
import string
from pathlib import Path

from english_templates import NUMERIC_EN, PROOF_EN

ROOT = Path(__file__).resolve().parent
TEMPLATES = Path("benchmarks/humpty_configurations_v2/authoring/variant_templates.json")
TRAIN = Path("benchmarks/humpty_configurations_v2/training_variants.jsonl")
DEV = Path("benchmarks/humpty_configurations_v2/eval_variants.jsonl")
PROOF = Path("benchmarks/humpty_proof_evaluation_v2/evaluation_prompts.jsonl")
ENGLISH_INSTRUCTION = (
    "Solve the following geometry problem. No solution is supplied. First find a "
    "nontrivial general relation specific to this construction that actually reduces "
    "the unknowns or computation. You may introduce auxiliary points, lines, or "
    "circles, and you may use coordinates or vectors. Give (1) the relation and its "
    "conditions, (2) a self-contained proof from the construction without skipping "
    "the decisive step, and (3) its application to the given numerical data and "
    "the final exact value. Do not merely assert a similarity, concyclicity, or "
    "algebraic identity. If you cannot prove a claim or solve the problem, say so "
    "rather than guessing. Write the entire answer in English. Keep the answer "
    "concise, preferably within 1200 words.\n\n"
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def slots(template):
    return {name for _, name, _, _ in string.Formatter().parse(template) if name}


def save(name, rows):
    path = ROOT / name
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
    return sha(path)


def job(row, stage, repeat=0):
    ident = row["id"]
    rendered = NUMERIC_EN[ident].format(**row["givens"])
    assert not re.search(r"[ぁ-んァ-ン一-龥]", rendered)
    assert "{" not in rendered and "}" not in rendered
    key = f"diverse-en-{stage}-{ident}-{row['variant']}-{repeat}"
    seed = int.from_bytes(hashlib.sha256(key.encode()).digest()[:4], "big") % (2**31)
    return {"id": key, "source_id": ident, "variant": row["variant"],
            "augmentation": row["augmentation"], "seed": seed,
            "japanese_problem_sha256": hashlib.sha256(row["problem"].encode()).hexdigest(),
            "english_problem": rendered,
            "messages": [{"role": "user", "content": ENGLISH_INSTRUCTION + rendered}]}


def main():
    templates = json.loads(TEMPLATES.read_text())
    train = load_jsonl(TRAIN)
    dev = load_jsonl(DEV)
    proof = load_jsonl(PROOF)
    assert len(templates) == len(NUMERIC_EN) == 37
    assert len(train) == 148 and len(dev) == 37 and len(proof) == len(PROOF_EN) == 6
    for ident, entry in templates.items():
        assert slots(entry["template"]) == slots(NUMERIC_EN[ident]), (ident, slots(entry["template"]), slots(NUMERIC_EN[ident]))
    originals = [row for row in train if row["augmentation"] == "original"]
    shapes = [row for row in train if row["augmentation"] == "shape"]
    assert len(originals) == 37 and len(shapes) == 27
    assert {x["id"] for x in originals} == {x["id"] for x in dev}
    hashes = {
        "material_original": save("material-original-jobs-en.json", [job(row, "material", 0) for row in originals]),
        "material_repeat": save("material-repeat-jobs-en.json", [job(row, "material", 1) for row in originals]),
        "material_shape": save("material-shape-jobs-en.json", [job(row, "material", 0) for row in shapes]),
        "numeric_dev": save("eval-numeric-jobs-en.json", [job(row, "eval", 0) for row in dev]),
    }
    proof_jobs = []
    for row in proof:
        ident = row["id"]
        translated = PROOF_EN[ident]
        assert not re.search(r"[ぁ-んァ-ン一-龥]", translated)
        key = f"diverse-en-proof-{ident}"
        seed = int.from_bytes(hashlib.sha256(key.encode()).digest()[:4], "big") % (2**31)
        proof_jobs.append({"id": key, "source_id": ident, "variant": "proof",
                           "augmentation": "proof", "seed": seed,
                           "japanese_prompt_sha256": hashlib.sha256(row["prompt"].encode()).hexdigest(),
                           "messages": [{"role": "user", "content": translated + " Write the entire proof in English."}]})
    hashes["proof_eval"] = save("eval-proof-jobs-en.json", proof_jobs)
    protocol = {
        "status": "frozen_before_english_generation_or_training",
        "supersedes": ["protocol.json", "protocol-v2.json", "protocol-english.json", "protocol-english-v2.json"],
        "reason": "User requested English throughout and the original 32768-token generation allowance. Earlier Japanese, 6144-token English, and 16384-token English material runs were stopped and excluded; no SFT updates occurred.",
        "model_id": "Qwen/Qwen3.5-9B",
        "model_revision": "c202236235762e1c871ad0ccb60c8ee5ba337b9a",
        "source_sha256": {str(path): sha(path) for path in (TEMPLATES, TRAIN, DEV, PROOF, ROOT / "english_templates.py")},
        "job_sha256": hashes,
        "english_instruction": ENGLISH_INSTRUCTION,
        "translation_checks": "English templates were manually translated from all 37 approved Japanese configuration templates; each has the identical set of numeric placeholders. Each rendered job has no Japanese script. Point/order/tangency/branch semantics require separate bilingual audit before causal interpretation.",
        "split": "Original and shape train variants only as teacher sources, 37 dev variants as numeric evaluation (9 shape, 28 similarity), six existing proof tasks as separate evaluation (three transfer, three same configuration). Never train on dev or proof outputs.",
        "material_first_pass": {"thinking": False, "temperature": 0.7, "top_p": 0.95,
                                "top_k": 20, "presence_penalty": 0.2, "cap": 32768,
                                "samples_per_job": 1},
        "material_additional_passes": "Second original pass and 27 shape jobs are frozen; run if needed. A thinking-mode pass, if used, is an explicitly exploratory collection arm with its own receipt.",
        "eval_numeric": {"thinking": False, "temperature": 1.0, "top_p": 0.95,
                         "top_k": 20, "presence_penalty": 1.5, "cap": 32768,
                         "samples_per_job": 2},
        "eval_proof": {"thinking": False, "temperature": 1.0, "top_p": 0.95,
                       "top_k": 20, "presence_penalty": 1.5, "cap": 32768,
                       "samples_per_job": 2},
        "primary_measure": "Numeric dev: exact value plus true useful general relation plus self-contained proof plus actual use; report each part, shape/similarity strata, and configuration-level successes.",
        "secondary_measure": "Existing proof six: complete proof, transfer and same-configuration separately. Both suites are development sets and not final untouched holdouts.",
        "teacher_gate": "At least 24 admitted own-answer examples from at least 12 distinct configurations for broad SFT; no reference solution or target relation supplied to model. If unmet, report yield and do not call a small run a broad test.",
    }
    (ROOT / "protocol-english-32k.json").write_text(json.dumps(protocol, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"train_original": len(originals), "train_shape": len(shapes),
                      "numeric_dev": len(dev), "proof": len(proof)}, indent=2))


if __name__ == "__main__":
    main()
