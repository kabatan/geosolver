"""Build assistant-only SFT data from individually audited visible answer spans."""

import hashlib
import json
import re
from pathlib import Path

from transformers import AutoTokenizer

HERE = Path(__file__).resolve().parent
MODEL = Path("docs/research/qwen35-self-materials-2026-09-23/model.json")
AUDITS = [HERE / "candidate-audit.json", HERE / "candidate-audit-additional.json"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    meta = json.loads(MODEL.read_text())
    tokenizer = AutoTokenizer.from_pretrained(meta["snapshot"], local_files_only=True)
    data, provenance = [], []
    for audit_path in AUDITS:
        if not audit_path.exists():
            continue
        for entry in json.loads(audit_path.read_text())["entries"]:
            if entry["status"] != "accept":
                continue
            source = Path(entry["source"])
            assert sha(source) == entry["sha256"], source
            obj = json.loads(source.read_text())
            start, end = entry["visible_span"]
            answer = obj["final_text"][start:end].strip()
            assert answer and "<|im_" not in answer and "<think>" not in answer and "</think>" not in answer
            assert not re.search(r"[ぁ-んァ-ン一-龥]", answer)
            prompt = obj["messages"][0]["content"]
            assert not re.search(r"[ぁ-んァ-ン一-龥]", prompt)
            ident = obj["id"]
            n_tokens = len(tokenizer.encode(answer, add_special_tokens=False))
            assert n_tokens > 20 and n_tokens < 7900, (ident, n_tokens)
            data.append({"id": ident, "source": obj["source_id"], "prompt": prompt, "answer": answer})
            provenance.append({"id": ident, "source": obj["source_id"],
                               "source_path": str(source), "source_sha256": entry["sha256"],
                               "visible_span": [start, end], "answer_tokens": n_tokens,
                               "audit_path": str(audit_path), "audit_reason": entry["reason"]})
    assert len({x["id"] for x in data}) == len(data)
    counts = {config: sum(row["source"] == config for row in data) for config in {x["source"] for x in data}}
    assert all(n <= 2 for n in counts.values())
    dataset = HERE / "train-multiconfig-en.json"
    dataset.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    (HERE / "train-provenance-en.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"examples": len(data), "configurations": len(counts),
                      "dataset_sha256": sha(dataset), "answer_tokens": sum(x["answer_tokens"] for x in provenance)}))


if __name__ == "__main__":
    main()
