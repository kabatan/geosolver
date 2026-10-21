"""Create a condition-blind packet for the frozen near-transfer comparison."""

import argparse
import hashlib
import json
import random
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", required=True)
    parser.add_argument("--input", action="append", required=True, metavar="CONDITION=DIR")
    parser.add_argument("--out", required=True)
    parser.add_argument("--seed", type=int, default=20260925)
    args = parser.parse_args()

    jobs_path = Path(args.jobs)
    jobs = json.loads(jobs_path.read_text())
    expected = {job["id"]: job for job in jobs}
    assert len(expected) == len(jobs)
    entries = []
    conditions = []
    for item in args.input:
        condition, sep, directory = item.partition("=")
        assert sep and condition and directory
        assert condition not in conditions
        conditions.append(condition)
        folder = Path(directory)
        receipt = json.loads((folder / "receipt.json").read_text())
        assert receipt["status"] == "complete", folder
        assert receipt["jobs_sha256"] == digest(jobs_path), folder
        assert receipt["samples"] == 1, folder
        found = {}
        for path in folder.glob("*.json"):
            if path.name == "receipt.json":
                continue
            result = json.loads(path.read_text())
            job_id = result["id"]
            assert job_id in expected and job_id not in found, path
            assert result["sample"] == 0 and result["messages"] == expected[job_id]["messages"]
            found[job_id] = (path, result)
        assert set(found) == set(expected), (condition, sorted(set(expected) - set(found)))
        for job_id in expected:
            path, result = found[job_id]
            entries.append({"condition": condition, "path": str(path.resolve()), "result": result})

    random.Random(args.seed).shuffle(entries)
    packet = []
    mapping = []
    for number, entry in enumerate(entries, start=1):
        result = entry["result"]
        blind_id = f"B{number:03d}"
        packet.append({
            "blind_id": blind_id,
            "source_id": result["source_id"],
            "problem": result["english_problem"],
            "final_text": result["final_text"],
            "finish_reason": result["finish_reason"],
        })
        mapping.append({"blind_id": blind_id, "condition": entry["condition"],
                        "job_id": result["id"], "file": entry["path"]})
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    write(out / "packet.json", packet)
    write(out / "mapping.json", mapping)
    write(out / "receipt.json", {"jobs_sha256": digest(jobs_path),
                                  "conditions": conditions, "n_jobs": len(jobs),
                                  "n_answers": len(entries), "shuffle_seed": args.seed,
                                  "packet_sha256": digest(out / "packet.json")})
    print(json.dumps({"packet": str(out / "packet.json"), "n_answers": len(entries)}))


if __name__ == "__main__":
    main()
