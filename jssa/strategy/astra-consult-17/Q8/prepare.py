"""Freeze the declared one-variable cohort; no solving or reference labels."""
import hashlib
import json
from pathlib import Path
import subprocess
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]


def h(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = ROOT / "benchmarks/cases.jsonl"
    rows = [json.loads(l) for l in source.read_text().splitlines()]
    selected = sorted((r for r in rows if len(r["dsl"]["variables"]) == 1), key=lambda c: c["id"])
    assert len(selected) == 43
    inputs = OUT / "inputs"
    inputs.mkdir(exist_ok=True)
    manifest = []
    for row in selected:
        path = inputs / (row["id"] + ".json")
        path.write_text(json.dumps({"id": row["id"], "dsl": row["dsl"]}, ensure_ascii=False, indent=2) + "\n")
        manifest.append({"id": row["id"], "input_file_sha256": h(path)})
    meta = {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "source_sha256": h(source), "selection": "len(dsl.variables)==1, sorted id", "n": 43,
            "preregistration_sha256": h(OUT / "preregistration.md"), "inputs": manifest}
    (OUT / "manifest.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in meta.items() if k != "inputs"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
