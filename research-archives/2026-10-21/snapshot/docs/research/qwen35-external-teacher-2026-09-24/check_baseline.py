"""Check whether existing base generations can be reused without changing conditions."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
manifest = json.loads((HERE / "manifest.json").read_text())
expected = {
    "numeric": ("numeric_eval_jobs", 37, 74, "eval-numeric-base-en-32k"),
    "proof": ("proof_eval_jobs", 6, 12, "eval-proof-base-en-32k"),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    for kind, (job_key, n_jobs, n_answers, directory) in expected.items():
        source = manifest["files"][job_key]
        assert sha(ROOT / source["path"]) == source["sha256"]
        out = ROOT / "qwen/.runtime/qwen35_diverse_sft_20260924" / directory
        receipt = json.loads((out / "receipt.json").read_text())
        assert receipt["status"] == "complete"
        assert receipt["jobs_sha256"] == source["sha256"]
        assert receipt["adapter"] is None and not receipt["thinking"]
        assert receipt["samples"] == 2 and receipt["cap"] == 32768 and receipt["context"] == 45056
        assert receipt["temperature"] == 1 and receipt["top_p"] == .95
        assert receipt["top_k"] == 20 and receipt["presence_penalty"] == 1.5
        assert len(json.loads((ROOT / source["path"]).read_text())) == n_jobs
        outputs = [p for p in out.glob("*.json") if p.name != "receipt.json" and p.name != "manual-grades.json"]
        assert len(outputs) == n_answers, (kind, len(outputs), n_answers)
        assert all(json.loads(p.read_text())["finish_reason"] == "stop" for p in outputs)
        print(kind, "base reusable", len(outputs), "outputs", source["sha256"])


if __name__ == "__main__":
    main()
