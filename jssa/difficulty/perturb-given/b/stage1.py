"""Q40b stage 1 only: copy Q40a's inputs, statically check, and seal.

No solver import, geometry evaluation, numerical search, or execution command.
The reviewed Q40a input generator only reads JSON/AST and uses read-only git.
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SIBLING = HERE.parent / "a"
SHARED = HERE / "shared"
LOCK = HERE / "prediction.lock.json"
FROZEN = "60db4b679b04167175c51c479c87c22fa663fda0"
SEEDS = (404001, 404002, 404003)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def packed(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + "\n").encode("utf-8")


def read_generator(directory):
    path = directory / "plan_stage1.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    allowed = {"__future__", "argparse", "ast", "copy", "csv", "hashlib", "io", "json",
               "math", "re", "subprocess", "collections", "datetime", "pathlib"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            require(all(x.name in allowed for x in node.names), "unexpected generator import")
        elif isinstance(node, ast.ImportFrom):
            require(node.module in allowed, "unexpected generator import")
    spec = importlib.util.spec_from_file_location("q40_static_inputs", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # The copy is one directory deeper than a; only the repository path differs.
    module.ROOT = ROOT
    module.HERE = directory
    require(module.FROZEN == FROZEN and module.SEED == 4040, "unexpected shared contract")
    return module


def shared_expected(directory):
    source_names = ("plan_stage1.py", "interventions.json")
    before = {name: (directory / name).read_bytes() for name in source_names}
    generator = read_generator(directory)
    generated = generator.build_expected()  # Static JSON/AST generation only.
    for name, data in generated.items():
        require((directory / name).read_bytes() == data, f"Q40a regeneration differs: {name}")
    require(all((directory / n).read_bytes() == d for n, d in before.items()),
            "Q40a generator changed while reading; retry static preparation")
    return generated | before


def audit_shared(files):
    selected = json.loads(files["selected.json"])
    variants = [json.loads(line) for line in files["variants.jsonl"].splitlines()]
    require(len(selected) == 40 and len(variants) == 240, "wrong input count")
    require(len({r["canonical_id"] for r in selected}) == 40, "duplicate selected ID")
    require(all(r["n_vars"] >= 2 and r["given_count"] >= 1 for r in selected), "ineligible case")
    originals = {r["canonical_id"]: json.loads(files[r["path"]])
                 for r in variants if r["variant"] == "original"}
    for row in variants:
        data = files[row["path"]]
        require(sha(data) == row["sha256"], "DSL byte hash mismatch")
        dsl = json.loads(data)
        restored = copy.deepcopy(dsl)
        for edit in row["edits"]:
            section, index, field = edit["path"]
            require(restored[section][index][field] == edit["after"], "edit receipt mismatch")
            restored[section][index][field] = edit["before"]
        require(restored == originals[row["canonical_id"]], "unrecorded DSL change")
    return selected, variants


def b_artifacts(files):
    selected, variants = audit_shared(files)
    by_case = {}
    for row in variants:
        by_case.setdefault(row["canonical_id"], []).append(row)
    blocks = sorted(((r, s) for r in selected for s in SEEDS),
                    key=lambda pair: sha(f"Q40b|4040|block|{pair[0]['canonical_id']}|{pair[1]}".encode()))
    runs = []
    for block, (row, seed) in enumerate(blocks):
        order = sorted(by_case[row["canonical_id"]], key=lambda v: sha(
            f"Q40b|4040|order|{row['canonical_id']}|{seed}|{v['variant']}".encode()))
        for position, variant in enumerate(order):
            runs.append({"block": block, "position": position, "id": row["id"],
                         "canonical_id": row["canonical_id"], "cohort": row["cohort"],
                         "seed": seed, "variant": variant["variant"],
                         "epsilon": variant["epsilon"], "dsl_path": "shared/" + variant["path"],
                         "dsl_sha256": variant["sha256"],
                         "cpu_limit_seconds": 180, "wall_limit_seconds": 180})
    require(len({(r["canonical_id"], r["seed"], r["variant"]) for r in runs}) == 720,
            "run schedule duplicates")
    return {
        "execution-plan.json": packed({
            "stage": 1, "execution_authorized": False,
            "frozen_commit": FROZEN, "run_count": 720, "seeds": SEEDS,
            "requires": ["Claude confirms commit and push", "explicit permission in a separate task",
                         "lock and frozen src check", "all shared files equal locked Q40a"],
            "maximum_concurrency": 4, "cores_per_run": 1, "thread_count": 1,
            "runs": runs,
        }),
        "static-validation.json": packed({
            "stage": 1, "solver_calls": 0, "local_search_calls": 0, "geometry_evaluations": 0,
            "cohort_counts": json.loads(files["selection-contract.json"])["cohort_counts"],
            "dsl_count": 240, "planned_runs": 720,
            "checks": ["regeneration by Q40a's exact static generator",
                       "40 selected problems, n_vars>=2, direct numeric givens",
                       "240 DSL byte hashes identical to Q40a",
                       "reversing recorded edits exactly restores each original",
                       "720 distinct scheduled runs", "src bytes match frozen git blobs"],
            "public_geosolver_validate_called": False,
            "not_checked": ["geometric feasibility", "solver runtime or dependencies",
                            "Jacobian rank or branch proximity", "outcomes"],
            "shared_sha256": {name: sha(data) for name, data in sorted(files.items())},
        }),
    }


def verify_b(files):
    for name, data in b_artifacts(files).items():
        require((HERE / name).read_bytes() == data, f"b artifact differs: {name}")


def verify_sibling(files):
    sibling_lock = SIBLING / "prediction.lock.json"
    require(sibling_lock.is_file(), "Q40a has not sealed its prediction yet")
    lock = json.loads(sibling_lock.read_bytes())
    require(lock["execution_authorized"] is False, "unexpected Q40a permission")
    for name, record in lock["files"].items():
        data = (SIBLING / name).read_bytes()
        require(sha(data) == record["sha256"] and len(data) == record["bytes"],
                f"Q40a lock mismatch: {name}")
    for name, data in files.items():
        require((SIBLING / name).read_bytes() == data, f"Q40a/b differ: {name}")
        require(lock["files"].get(name, {}).get("sha256") == sha(data),
                f"shared file is not sealed by Q40a: {name}")
    return sibling_lock.read_bytes()


def verify_lock():
    lock = json.loads(LOCK.read_bytes())
    require(lock["execution_authorized"] is False, "unexpected permission in lock")
    for path, expected in lock["files_sha256"].items():
        require(sha((ROOT / path).read_bytes()) == expected, f"lock mismatch: {path}")


def write(path, data):
    require(len(data) < 5_000_000, f"file too large: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("sync", "check", "seal", "check-sibling"))
    args = parser.parse_args()
    if LOCK.exists():
        verify_lock()
    if args.command == "sync":
        require(not LOCK.exists(), "already sealed; syncing is disabled")
        files = shared_expected(SIBLING)
        for name, data in files.items():
            write(SHARED / name, data)
        for name, data in b_artifacts(files).items():
            write(HERE / name, data)
    else:
        files = shared_expected(SHARED)
        verify_b(files)
    sibling_matched = False
    if args.command in ("seal", "check-sibling") or LOCK.exists():
        sibling_lock = verify_sibling(files)
        sibling_matched = True
    if args.command == "seal":
        require(not LOCK.exists(), "refuse to overwrite prediction lock")
        require((HERE / "prediction.md").is_file(), "prediction.md missing")
        write(HERE / "sibling-prediction.lock.json", sibling_lock)
        paths = [p for p in HERE.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
        manifest = json.loads(files["source-manifest.json"])
        paths += [ROOT / name for name in manifest["files"]]
        paths += [ROOT / name for name in manifest["input_files"]]
        paths += [ROOT / manifest["instruction_file"]["path"], ROOT / "pyproject.toml", ROOT / "uv.lock",
                  SIBLING / "prediction.lock.json"]
        lock = {
            "schema": "q40b-prediction-lock-v1", "stage": 1,
            "sealed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "frozen_commit": FROZEN, "execution_authorized": False,
            "commit_push_confirmed": False, "separate_task_permission_received": False,
            "solver_calls_in_stage1": 0, "local_search_calls_in_stage1": 0,
            "q40a_agreement": "all shared files match sealed Q40a byte for byte",
            "static_python_version": sys.version.split()[0], "self_hash_excluded": True,
            "files_sha256": {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in sorted(set(paths))},
        }
        write(LOCK, packed(lock))
        verify_lock()
    print(json.dumps({"status": "static_checks_passed", "stage": 1, "selected": 40,
                      "dsl_count": 240, "planned_runs": 720, "solver_calls": 0,
                      "local_search_calls": 0, "sealed": LOCK.exists(),
                      "sibling_lock_matched": sibling_matched}, ensure_ascii=False))


if __name__ == "__main__":
    main()
