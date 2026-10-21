"""Build SFT data only from individually admitted external-teacher solutions."""

import hashlib
import json
import re
from pathlib import Path

from transformers import AutoTokenizer

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
MODEL = ROOT / "docs/research/qwen35-self-materials-2026-09-23/model.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((HERE / "manifest.json").read_text())
    for row in manifest["files"].values():
        assert sha(ROOT / row["path"]) == row["sha256"], row["path"]
    candidates_path = HERE / "candidates.json"
    audits_path = HERE / "audits.json"
    candidates = json.loads(candidates_path.read_text())
    audits = json.loads(audits_path.read_text())
    assert isinstance(candidates, list) and isinstance(audits, list)
    by_id = {x["id"]: x for x in candidates}
    by_audit = {x["id"]: x for x in audits}
    assert len(by_id) == len(candidates) and len(by_audit) == len(audits)
    assert set(by_id) <= set(manifest["train_configuration_ids"])
    assert set(by_audit) == set(by_id)
    jobs = json.loads((ROOT / manifest["files"]["teacher_jobs"]["path"]).read_text())
    job_by_id = {x["source_id"]: x for x in jobs}
    model = json.loads(MODEL.read_text())
    assert model["revision"] == manifest["model_revision"]
    tokenizer = AutoTokenizer.from_pretrained(model["snapshot"], local_files_only=True)
    selected, provenance = [], []
    for config in manifest["train_configuration_ids"]:
        if config not in by_id:
            continue
        candidate, audit = by_id[config], by_audit[config]
        if audit["status"] != "accept":
            continue
        assert candidate["status"] == "complete", config
        assert all(audit[k] is True for k in ("numeric", "true_relation", "proof", "use", "branches_checked")), config
        assert audit["reviewer_reason"].strip(), config
        answer = candidate["answer"].strip()
        assert answer and not re.search(r"[ぁ-んァ-ン一-龥]", answer), config
        assert all(token not in answer for token in ("<|im_", "<think>", "</think>")), config
        prompt = job_by_id[config]["messages"][0]["content"]
        prompt_text = tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}], tokenize=False,
            add_generation_prompt=True, enable_thinking=False)
        full = tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}, {"role": "assistant", "content": answer}],
            tokenize=False, enable_thinking=False)
        assert full.startswith(prompt_text)
        prompt_tokens = len(tokenizer.encode(prompt_text, add_special_tokens=False))
        answer_tokens = len(tokenizer.encode(full[len(prompt_text):].rstrip(), add_special_tokens=False))
        assert prompt_tokens + answer_tokens <= 8192, (config, prompt_tokens + answer_tokens)
        selected.append({"id": "external-" + config + "-v0", "source": config,
                         "prompt": prompt, "answer": answer})
        provenance.append({"id": config, "candidate_source": candidate["source"],
                           "method": candidate["method"], "audit_reason": audit["reviewer_reason"],
                           "prompt_tokens": prompt_tokens, "answer_tokens": answer_tokens,
                           "candidate_sha256": hashlib.sha256(answer.encode()).hexdigest()})
    assert selected, "No audited answers admitted"
    (HERE / "train.json").write_text(json.dumps(selected, ensure_ascii=False, indent=2) + "\n")
    (HERE / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"admitted": len(selected), "target": 37,
                      "missing": sorted(set(manifest["train_configuration_ids"]) - {x["source"] for x in selected}),
                      "answer_tokens_per_epoch": sum(x["answer_tokens"] for x in provenance),
                      "dataset_sha256": sha(HERE / "train.json")}))


if __name__ == "__main__":
    main()
