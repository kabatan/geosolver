"""Q42 stage1 only: field names and SHA-256, never numerical analysis.

Run without arguments once to create schema.json, input-manifest.json and
prediction.lock.json. --verify reads and checks the existing seal only.
No solver or analysis module is imported. No stage2 command is provided.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FROZEN = "60db4b679b04167175c51c479c87c22fa663fda0"
Q22 = "jssa/strategy/astra-consult-18/q22a-hidden-coincidence"
CSV_INPUTS = (
    "jssa/difficulty/minima/basins-323.csv",
    "jssa/difficulty/ghost-1023/human_feat.csv",
    f"{Q22}/features.csv",
)
COLLECTIONS = {
    "probe_seed0": "jssa/difficulty/minima/raw-323/*.json",
    "probe_seed1": "jssa/difficulty/minima/raw-323-seed1/*.json",
    "q22_figures": f"{Q22}/figures/*.json",
}
FIXED_INPUTS = (
    *CSV_INPUTS,
    "benchmarks/cases.jsonl",
    "jssa/difficulty/probe_basins.py",
    f"{Q22}/experiment.py",
    "jssa/strategy/codex-tasks-1023.md",
    "pyproject.toml",
    "uv.lock",
    ".python-version",
)
LOCAL_FIXED = ("prediction.md", "seal_prediction.py", "schema.json", "input-manifest.json")


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def inventory() -> tuple[dict[str, list[str]], list[str]]:
    collections = {
        name: [relative(p) for p in sorted(ROOT.glob(pattern)) if p.is_file()]
        for name, pattern in COLLECTIONS.items()
    }
    if any(not paths for paths in collections.values()):
        raise RuntimeError("An expected input collection is absent; do not silently omit it")
    src = git("ls-tree", "-r", "--name-only", FROZEN, "--", "src").splitlines()
    paths = sorted(set(FIXED_INPUTS).union(src, *(v for v in collections.values())))
    for name in paths:
        if not (ROOT / name).is_file():
            raise FileNotFoundError(name)
    return collections, paths


def frozen_source() -> str:
    expected = git("rev-parse", f"{FROZEN}:src")
    if git("rev-parse", "HEAD:src") != expected:
        raise RuntimeError("HEAD/src differs from the frozen solver")
    if git("diff", "--name-only", FROZEN, "--", "src"):
        raise RuntimeError("Working src differs from the frozen solver")
    if git("ls-files", "--others", "--exclude-standard", "--", "src"):
        raise RuntimeError("Untracked source under src; inspect before sealing")
    return expected


def fields(value: object, path: str = "") -> set[str]:
    """Union of field names only; never return scalar values or row counts."""
    found = set()
    if path:
        found.add(path)
    if isinstance(value, dict):
        dynamic = path in {"first_hit", "counts", "points", "circles", "depths"}
        for key, child in value.items():
            key = "*" if dynamic else str(key)
            found.update(fields(child, f"{path}.{key}" if path else key))
    elif isinstance(value, list):
        found.add(path + "[]")
        for child in value:
            found.update(fields(child, path + "[]"))
    return found


def schema(collections: dict[str, list[str]]) -> dict:
    headers = {}
    for name in CSV_INPUTS:
        with (ROOT / name).open(newline="", encoding="utf-8") as stream:
            headers[name] = next(csv.reader(stream))
    unions = {}
    for collection, names in collections.items():
        union = set()
        for name in names:
            union.update(fields(json.loads((ROOT / name).read_text(encoding="utf-8"))))
        unions[collection] = sorted(union)
    with (ROOT / "benchmarks/cases.jsonl").open(encoding="utf-8") as stream:
        case_fields = sorted(fields(json.loads(next(stream))))
    return {
        "scope": "Field names only; no values, distributions, missingness counts or associations",
        "csv_headers": headers,
        "json_union_field_paths": unions,
        "cases_first_row_field_paths": case_fields,
    }


def create_json(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def verify() -> None:
    lock = json.loads((HERE / "prediction.lock.json").read_text(encoding="utf-8"))
    if lock["stage"] != 1 or lock["analysis_authorized"] is not False:
        raise RuntimeError("This is not an unexecuted stage1 lock")
    if lock["solver_commit"] != FROZEN or lock["solver_src_tree"] != frozen_source():
        raise RuntimeError("Frozen solver mismatch")
    expected_local = {relative(HERE / name) for name in LOCAL_FIXED}
    if set(lock["files"]) != expected_local:
        raise RuntimeError("Unexpected fixed-file set")
    for name, sha in lock["files"].items():
        if digest(ROOT / name) != sha:
            raise RuntimeError(f"Changed fixed file: {name}")
    if digest(HERE / "prediction.md") != lock["prediction_sha256"]:
        raise RuntimeError("Prediction digest mismatch")
    manifest = json.loads((HERE / "input-manifest.json").read_text(encoding="utf-8"))
    collections, paths = inventory()
    if collections != manifest["collections"] or paths != sorted(manifest["files"]):
        raise RuntimeError("Input file membership changed")
    for name, entry in manifest["files"].items():
        if digest(ROOT / name) != entry["sha256"]:
            raise RuntimeError(f"Changed input: {name}")
        if (ROOT / name).stat().st_size != entry["bytes"]:
            raise RuntimeError(f"Input size changed: {name}")
    print("stage1 lock verified; no analysis executed")


def seal() -> None:
    for name in ("schema.json", "input-manifest.json", "prediction.lock.json"):
        if (HERE / name).exists():
            raise FileExistsError(f"Refusing to replace existing stage1 artifact: {name}")
    src_tree = frozen_source()
    collections, paths = inventory()
    # Schemas inspect keys only. Hashes treat inputs as uninterpreted bytes.
    observed_schema = schema(collections)
    manifest = {
        "path_base": "repository root",
        "collections": collections,
        "fixed_inputs": list(FIXED_INPUTS),
        "solver_commit": FROZEN,
        "solver_src_tree": src_tree,
        "files": {
            name: {"sha256": digest(ROOT / name), "bytes": (ROOT / name).stat().st_size}
            for name in paths
        },
    }
    create_json(HERE / "schema.json", observed_schema)
    create_json(HERE / "input-manifest.json", manifest)
    lock = {
        "stage": 1,
        "utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "prediction_sha256": digest(HERE / "prediction.md"),
        "repository_head_at_lock": git("rev-parse", "HEAD"),
        "solver_commit": FROZEN,
        "solver_src_tree": src_tree,
        "files": {relative(HERE / name): digest(HERE / name) for name in LOCAL_FIXED},
        "input_hashes": relative(HERE / "input-manifest.json"),
        "schema_inspection_only": True,
        "analysis_authorized": False,
        "analysis_executed": False,
        "solver_runs_executed": 0,
        "commit_push_performed_by_this_task": False,
        "stage2_gate": "Claude commit/push confirmation AND analysis authorization in a separate task",
    }
    create_json(HERE / "prediction.lock.json", lock)
    verify()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="Verify SHA-256 and membership only")
    args = parser.parse_args()
    if args.verify:
        verify()
    else:
        seal()


if __name__ == "__main__":
    main()
