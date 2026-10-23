"""Materialize the already locked bytes without changing the shared checkout."""
import ast
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess

BASE = Path(__file__).resolve().parent
WORKSPACE = BASE.parents[2]
DEST = BASE / "execution" / "frozen-runtime"
SOURCE_COMMIT = "60db4b679b04167175c51c479c87c22fa663fda0"
AUDIT_COMMIT = "59691a9215aaf017451ca1f1c892eecad9478920"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=WORKSPACE)


def digest(b):
    return hashlib.sha256(b).hexdigest()


def main():
    manifest = json.loads((BASE / "source-manifest.json").read_text())
    paths = git("ls-tree", "-r", "--name-only", SOURCE_COMMIT, "--", "src", "benchmarks/dsl",
                "benchmarks/cases.jsonl", "benchmarks/research_runner.py", "benchmarks/__init__.py",
                "pyproject.toml", "uv.lock").decode().splitlines()
    copied = {}
    for path in paths:
        payload = git("show", SOURCE_COMMIT + ":" + path)
        target = DEST / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        target.chmod(0o444)
        copied[path] = digest(payload)
    for path in manifest["read_inputs_sha256"]:
        if path not in copied:
            payload = git("show", AUDIT_COMMIT + ":" + path)
            target = DEST / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            target.chmod(0o444)
            copied[path] = digest(payload)
    expected = {**manifest["tracked_src_files_sha256"], **manifest["read_inputs_sha256"]}
    assert all(copied[path] == sha for path, sha in expected.items())
    selected = json.loads((BASE / "selection.json").read_text())["selected"]
    assert all(copied[row["dsl_path"]] == row["dsl_sha256"] for row in selected)
    live_changes = {p: {"expected": sha, "live": digest((WORKSPACE / p).read_bytes())}
                    for p, sha in expected.items() if digest((WORKSPACE / p).read_bytes()) != sha}
    def function(source, name):
        return ast.dump(next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)
                             and n.name == name), include_attributes=False)
    reference_parser_unchanged = function((WORKSPACE / "benchmarks/research_runner.py").read_text(),
                                         "reference_expressions") == function(
        (DEST / "benchmarks/research_runner.py").read_text(), "reference_expressions")
    receipt = {"utc": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
               "root": str(DEST), "source_commit": SOURCE_COMMIT, "audit_commit": AUDIT_COMMIT,
               "copied_file_count": len(copied), "copied_sha256": copied,
               "all_locked_source_and_input_hashes_match": True,
               "all_selected_DSL_hashes_match": True,
               "shared_checkout_changes_detected_before_first_rear": live_changes,
               "existing_numeric_reference_parser_AST_identical": reference_parser_unchanged,
               "shared_checkout_modified_by_isolation": False,
               "prediction_design_selection_changed": False,
               "reason": "Shared work changed scorer null-diagnostics handling and the task document. Run only the committed locked bytes; do not adopt or revert those unrelated changes."}
    (BASE / "runtime-isolation.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    (BASE / "runtime-location.json").write_text(json.dumps({"root": str(DEST),
             "isolation_receipt_sha256": digest((BASE / "runtime-isolation.json").read_bytes())}, indent=2) + "\n")
    print(json.dumps({"copied_files": len(copied), "all_locked_hashes_match": True,
                      "shared_changes": list(live_changes),
                      "reference_parser_identical": reference_parser_unchanged}))


if __name__ == "__main__":
    main()
