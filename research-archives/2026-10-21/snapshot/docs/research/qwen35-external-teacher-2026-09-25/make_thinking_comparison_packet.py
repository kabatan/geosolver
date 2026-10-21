"""Make a mode/adapter-blind packet from the paired fresh4 A/E outputs."""

import argparse
import hashlib
import json
import random
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", required=True)
    parser.add_argument("--arm", action="append", required=True, metavar="NAME:MODE:DIR")
    parser.add_argument("--packet-dir", required=True)
    parser.add_argument("--vault-dir", required=True)
    parser.add_argument("--seed", type=int, default=2026092502)
    args = parser.parse_args()

    jobs_path = Path(args.jobs)
    jobs = json.loads(jobs_path.read_text())
    expected = {job["id"]: job for job in jobs}
    assert len(expected) == len(jobs) == 6
    entries = []
    arms = []
    for arm_arg in args.arm:
        name, mode, folder_text = arm_arg.split(":", 2)
        assert mode in {"thinking", "nonthinking"}
        assert name not in arms
        arms.append(name)
        folder = Path(folder_text)
        receipt = json.loads((folder / "receipt.json").read_text())
        assert receipt["status"] == "complete"
        assert receipt["jobs_sha256"] == sha256(jobs_path)
        assert receipt["samples"] == 1
        assert receipt["thinking"] == (mode == "thinking")
        expected_cap, expected_context = ((81920, 90112)
                                          if mode == "thinking" else
                                          (32768, 45056))
        assert receipt["cap"] == expected_cap
        assert receipt["context"] == expected_context
        found = {}
        for path in folder.glob("*.json"):
            if path.name == "receipt.json":
                continue
            result = json.loads(path.read_text())
            job_id = result["id"]
            assert job_id in expected and job_id not in found
            assert result["sample"] == 0
            assert result["messages"] == expected[job_id]["messages"]
            found[job_id] = (path, result)
        assert set(found) == set(expected)
        for job_id in expected:
            path, result = found[job_id]
            raw = result["raw_text"]
            if mode == "thinking":
                has_close = "</think>" in raw
                answer = raw.split("</think>", 1)[1] if has_close else ""
            else:
                has_close = "</think>" in raw
                answer = raw
            entries.append({
                "name": name,
                "mode": mode,
                "path": str(path.resolve()),
                "result": result,
                "answer": answer,
                "has_close": has_close,
            })

    assert len(arms) == 4 and len(entries) == 24
    random.Random(args.seed).shuffle(entries)
    packet = []
    mapping = []
    for number, entry in enumerate(entries, start=1):
        result = entry["result"]
        blind_id = f"T{number:03d}"
        packet.append({
            "blind_id": blind_id,
            "source_id": result["source_id"],
            "problem": result["english_problem"],
            "answer_text": entry["answer"],
            "finish_reason": result["finish_reason"],
            "answer_present": bool(entry["answer"].replace("<|im_end|>", "").strip()),
        })
        mapping.append({
            "blind_id": blind_id,
            "arm": entry["name"],
            "mode": entry["mode"],
            "job_id": result["id"],
            "file": entry["path"],
            "has_generated_close": entry["has_close"],
            "completion_tokens": len(result["completion_ids"]),
        })

    packet_dir = Path(args.packet_dir)
    vault_dir = Path(args.vault_dir)
    packet_dir.mkdir(parents=True, exist_ok=False)
    vault_dir.mkdir(parents=True, exist_ok=False)
    write(packet_dir / "packet.json", packet)
    write(vault_dir / "mapping.json", mapping)
    write(vault_dir / "receipt.json", {
        "jobs_sha256": sha256(jobs_path),
        "arms": arms,
        "n_answers": len(packet),
        "shuffle_seed": args.seed,
        "packet_sha256": sha256(packet_dir / "packet.json"),
    })
    print(json.dumps({"packet": str(packet_dir / "packet.json"),
                      "n_answers": len(packet)}))


if __name__ == "__main__":
    main()
