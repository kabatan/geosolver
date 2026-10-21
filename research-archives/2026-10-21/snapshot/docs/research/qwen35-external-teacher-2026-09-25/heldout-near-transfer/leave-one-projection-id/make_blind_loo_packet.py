"""Blind the three separately evaluated leave-one-projection-ID arms."""

import argparse
import hashlib
import json
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CONTROL_IDS = {"H01", "H02", "H07", "H13"}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", action="append", required=True, metavar="H03=OUTPUT_DIR")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    entries = []
    seen = set()
    for spec in args.input:
        target, sep, name = spec.partition("=")
        assert sep and target in {"H03", "H04", "H14"} and target not in seen
        seen.add(target)
        folder = Path(name)
        jobs_path = ROOT / f"eval-minus-{target}.json"
        jobs = json.loads(jobs_path.read_text())
        expected = {x["id"]: x for x in jobs}
        assert len(jobs) == len(expected) == 5
        assert {x["source_id"] for x in jobs} == CONTROL_IDS | {target}
        receipt = json.loads((folder / "receipt.json").read_text())
        assert receipt["status"] == "complete" and receipt["jobs_sha256"] == sha256(jobs_path)
        assert receipt["samples"] == 1
        found = {}
        for path in folder.glob("*.json"):
            if path.name == "receipt.json":
                continue
            row = json.loads(path.read_text())
            assert row["id"] in expected and row["id"] not in found
            assert row["sample"] == 0 and row["messages"] == expected[row["id"]]["messages"]
            found[row["id"]] = (path, row)
        assert found.keys() == expected.keys()
        for job in jobs:
            path, row = found[job["id"]]
            entries.append((target, path, row))
    assert seen == {"H03", "H04", "H14"} and len(entries) == 15
    random.Random(20260928).shuffle(entries)
    packet, mapping = [], []
    for number, (target, path, row) in enumerate(entries, start=1):
        bid = f"L{number:03d}"
        packet.append({"blind_id": bid, "source_id": row["source_id"],
                       "problem": row["english_problem"], "final_text": row["final_text"],
                       "finish_reason": row["finish_reason"]})
        mapping.append({"blind_id": bid, "condition": f"minus-{target}",
                        "job_id": row["id"], "file": str(path.resolve())})
    args.out.mkdir(parents=True, exist_ok=False)
    write(args.out / "packet.json", packet)
    write(args.out / "mapping.json", mapping)
    write(args.out / "receipt.json", {"n_answers": 15, "shuffle_seed": 20260928,
                                      "packet_sha256": sha256(args.out / "packet.json"),
                                      "inputs": sorted(seen)})


if __name__ == "__main__":
    main()
