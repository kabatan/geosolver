"""Q41: 段階1成果物のSHA-256/UTC封印。solverを起動する機能はない。"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOCK = HERE / "prediction.lock.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def payload_files():
    paths = []
    for path in sorted(HERE.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"symlink_not_allowed:{path}")
        if path.is_file() and path != LOCK:
            if "__pycache__" in path.parts:
                raise ValueError("unexpected_python_cache")
            paths.append(path)
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="読取専用で封印を照合")
    args = parser.parse_args()
    if args.check:
        locked = json.loads(LOCK.read_text())
        expected = locked["files"]
        actual = {p.relative_to(HERE).as_posix(): digest(p) for p in payload_files()}
        if expected != actual:
            raise SystemExit("封印と不一致。実行不可。")
        assert locked["sha256"] == digest(HERE / "prediction.md")
        assert locked["execution_authorized"] is False
        assert locked["solver_calls"] == locked["local_search_calls"] == 0
        assert locked["utc"].endswith("Z")
        print(json.dumps({"lock_verified": True, "files": len(expected), "utc": locked["utc"]}))
        return
    if LOCK.exists():
        raise SystemExit("既存の封印は上書きしない。照合には --check を使用。")
    checks = json.loads((HERE / "static-checks.json").read_text())
    rules = json.loads((HERE / "rules.json").read_text())
    ids = (HERE / "selected-problems.txt").read_text().splitlines()
    assert checks["solver_calls"] == checks["local_search_calls"] == 0
    assert checks["arm_status_counts"].get("static_invalid", 0) == 0
    assert len(ids) == len(set(ids)) == checks["selected"]
    paths = payload_files()
    assert all(p.stat().st_size < rules["per_file_max_bytes"] for p in paths)
    record = {
        "schema_version": 1,
        "task": "Q41-symmetry-break-stage1",
        "utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "file": "prediction.md",
        "sha256": digest(HERE / "prediction.md"),
        "frozen_commit": rules["frozen_commit"],
        "stage": 1,
        "execution_authorized": False,
        "solver_calls": 0,
        "local_search_calls": 0,
        "selected_problem_count": len(ids),
        "selected_problem_ids": ids,
        "selected_problem_list_sha256": digest(HERE / "selected-problems.txt"),
        "checks": checks,
        "files": {p.relative_to(HERE).as_posix(): digest(p) for p in paths},
        "release_gate": "Claudeのcommit・push確認後、別タスクの明示許可が必要。hash一致は実行許可ではない。",
    }
    with LOCK.open("x", encoding="utf-8") as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"sealed": True, "files": len(paths), "utc": record["utc"], "sha256": record["sha256"]}))


if __name__ == "__main__":
    main()
