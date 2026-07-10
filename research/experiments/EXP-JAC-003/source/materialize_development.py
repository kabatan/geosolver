"""One-shot EXP-JAC-003 development input materializer.

Run only at the clean commit that introduced ``preimplementation-lock.json``.
There is deliberately no force, overwrite, resume or output-path option.
"""

from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = EXPERIMENT_ROOT.parents[2]
SOURCE_ROOT = EXPERIMENT_ROOT / "source"
LOCK_PATH = EXPERIMENT_ROOT / "preimplementation-lock.json"
BASELINE_CONTRACT_PATH = EXPERIMENT_ROOT / "baseline-contract.json"
BASELINE_SNAPSHOT_PATH = EXPERIMENT_ROOT / "public-baseline-snapshot.json"
SEED_DENYLIST_PATH = EXPERIMENT_ROOT / "seed-denylist.json"
OUTPUT_PATH = EXPERIMENT_ROOT / "development-inputs"
COMPLETION_NAME = "ONE_SHOT_COMPLETE.json"

FORBIDDEN_CANDIDATE_KEYS = {
    "family",
    "family_id",
    "factors",
    "seed",
    "instance_seed",
    "start_seed",
    "gold",
    "gold_configuration",
    "gold_target",
    "truth",
    "expected",
    "analytic",
    "analytic_jacobian",
    "jacobian",
    "target",
    "branch_label",
    "root",
}
FORBIDDEN_MECHANISM_PATH_TOKENS = (
    "candidate",
    "provider",
    "prepared_coloring",
    "cached_coloring",
    "mechanism",
)


class MaterializationError(RuntimeError):
    """Fail-closed precondition or artifact validation error."""


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_path(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical_bytes(document: Any) -> bytes:
    return (
        json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise MaterializationError(f"{path} is not a JSON object")
    return raw


def _run_git(*arguments: str, capture: bool = True) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=REPOSITORY_ROOT,
        check=False,
        text=True,
        capture_output=capture,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() if capture else ""
        raise MaterializationError(f"git {' '.join(arguments)} failed: {detail}")
    return completed.stdout.strip() if capture else ""


def _import_frozen(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise MaterializationError(f"cannot load frozen source {path}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _verify_clean_lock_head(lock: dict[str, Any]) -> None:
    if OUTPUT_PATH.exists():
        raise MaterializationError("development output already exists; one-shot rerun refused")
    if _run_git("status", "--porcelain=v1", "--untracked-files=all"):
        raise MaterializationError("one-shot materialization requires a completely clean worktree")
    head = _run_git("rev-parse", "HEAD")
    lock_commit = _run_git("log", "-1", "--format=%H", "--", str(LOCK_PATH.relative_to(REPOSITORY_ROOT)))
    if not lock_commit or lock_commit != head:
        raise MaterializationError(
            "HEAD must be exactly the commit that introduced the preimplementation lock"
        )
    if lock.get("status") != "frozen-before-one-shot-materialization":
        raise MaterializationError("preimplementation lock is not in the frozen state")


def _verify_source_lock(lock: dict[str, Any]) -> None:
    declared = lock.get("files")
    if not isinstance(declared, dict) or not declared:
        raise MaterializationError("preimplementation lock has no file hashes")
    for relative, expected in declared.items():
        path = REPOSITORY_ROOT / relative
        if not path.is_file() or _sha256_path(path) != expected:
            raise MaterializationError(f"preimplementation source hash drift: {relative}")
    experiment_prefix = EXPERIMENT_ROOT.relative_to(REPOSITORY_ROOT).as_posix() + "/"
    allowed_sources = {
        (REPOSITORY_ROOT / relative).resolve()
        for relative in declared
        if relative.endswith((".py", ".jl")) and relative.startswith(experiment_prefix)
    }
    actual_sources = {
        path.resolve()
        for path in EXPERIMENT_ROOT.rglob("*")
        if path.is_file() and path.suffix in {".py", ".jl"}
    }
    if actual_sources != allowed_sources:
        extras = sorted(str(path) for path in actual_sources - allowed_sources)
        missing = sorted(str(path) for path in allowed_sources - actual_sources)
        raise MaterializationError(
            f"experiment source allowlist drift; extras={extras}, missing={missing}"
        )
    for path in actual_sources:
        lowered = "/".join(path.relative_to(EXPERIMENT_ROOT).parts).lower()
        if any(token in lowered for token in FORBIDDEN_MECHANISM_PATH_TOKENS):
            raise MaterializationError(f"mechanism-like source exists before input freeze: {path}")


def _verify_product_baseline() -> dict[str, Any]:
    contract = _load_json(BASELINE_CONTRACT_PATH)
    if contract.get("schema_version") != "exp-jac-003-public-baseline-contract/v1":
        raise MaterializationError("wrong baseline contract schema")
    product_sources = contract.get("product_sources")
    if not isinstance(product_sources, dict):
        raise MaterializationError("baseline product source map missing")
    actual_paths = {
        path.relative_to(REPOSITORY_ROOT).as_posix()
        for path in (REPOSITORY_ROOT / "julia" / "GeoTargetCore" / "src").glob("*.jl")
    }
    if actual_paths != set(product_sources):
        raise MaterializationError("GeoTargetCore product source set drift")
    for relative, expected in product_sources.items():
        if _sha256_path(REPOSITORY_ROOT / relative) != expected:
            raise MaterializationError(f"product source differs from public baseline: {relative}")
    baseline = str(contract["baseline_commit"])
    _run_git("merge-base", "--is-ancestor", baseline, "HEAD")
    completed = subprocess.run(
        ["git", "diff", "--quiet", baseline, "--", "julia/GeoTargetCore/src"],
        cwd=REPOSITORY_ROOT,
        check=False,
    )
    if completed.returncode != 0:
        raise MaterializationError("GeoTargetCore tree differs from the pre-EXP-JAC002 baseline commit")
    return contract


def _walk_forbidden_keys(value: Any, path: str = "candidate") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            if normalized in FORBIDDEN_CANDIDATE_KEYS:
                raise MaterializationError(f"forbidden candidate-visible key at {path}.{key}")
            _walk_forbidden_keys(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk_forbidden_keys(child, f"{path}[{index}]")
    elif isinstance(value, str):
        lowered = value.lower()
        if "jac3-trig-tree" in lowered or "jac3-rational-hypergraph" in lowered or \
                "jac3-hex-ring-stencil" in lowered or "jac3-dense-branch-control" in lowered:
            raise MaterializationError(f"family identity leaked into candidate value at {path}")


def _program_supports(program: dict[str, Any]) -> list[list[int]]:
    kind = program["kind"]
    size = len(program["offsets"])
    if kind == "sin-cos-tree-v1":
        return [sorted({row, *children}) for row, children in enumerate(program["children"])]
    if kind == "safe-rational-hypergraph-v1":
        return [sorted({row, *edge}) for row, edge in enumerate(program["edges"])]
    if kind == "hex-ring-atan-v1":
        return [sorted({row, *values}) for row, values in enumerate(program["neighbours"])]
    if kind == "dense-chart-v1":
        matrix = program["matrix"]
        alternate = program["alternate_matrix"]
        return [
            sorted({
                row,
                *(column for column, value in enumerate(matrix[row]) if value != 0.0),
                *(column for column, value in enumerate(alternate[row]) if value != 0.0),
            })
            for row in range(size)
        ]
    raise MaterializationError(f"unknown oracle program {kind!r}")


def _validate_candidate(candidate: dict[str, Any]) -> None:
    if candidate.get("schema_version") != "exp-jac-003-candidate-inputs/v1":
        raise MaterializationError("wrong candidate schema")
    cases = candidate.get("cases")
    if not isinstance(cases, list) or len(cases) != 64:
        raise MaterializationError("candidate partition must contain exactly 64 cases")
    ids = [case.get("opaque_case_id") for case in cases]
    if len(set(ids)) != 64 or ids != sorted(ids):
        raise MaterializationError("candidate IDs must be unique and canonically ordered")
    _walk_forbidden_keys(candidate)
    for case in cases:
        size = case["variable_count"]
        if case["residual_count"] != size or len(case["starts"]) != 32:
            raise MaterializationError("candidate dimension/start allocation drift")
        graph = case["typed_graph"]
        nodes = graph["nodes"]
        node_ids = [node["node_id"] for node in nodes]
        if len(node_ids) != len(set(node_ids)):
            raise MaterializationError("typed graph node IDs are not unique")
        by_id = {node["node_id"]: node for node in nodes}
        expected = _program_supports(case["oracle_program"])
        actual = []
        for relation in graph["relations"]:
            node = by_id[relation]
            actual.append(sorted(int(argument[1:]) for argument in node["arguments"]))
        if actual != expected:
            raise MaterializationError("typed graph supports disagree with black-box program")
        for start in case["starts"]:
            if len(start) != size or any(
                not lower <= value <= upper
                for value, lower, upper in zip(start, case["lower"], case["upper"], strict=True)
            ):
                raise MaterializationError("candidate start is outside its declared box")


def _validate_seeds(assessor: dict[str, Any]) -> None:
    denylist = _load_json(SEED_DENYLIST_PATH)
    allowed = denylist["allowed_development_blocks"]
    expected_instance = {
        value for lower, upper in allowed["instance"] for value in range(lower, upper + 1)
    }
    expected_start = {
        value for lower, upper in allowed["start"] for value in range(lower, upper + 1)
    }
    actual_instance = {item["instance_seed"] for item in assessor["assessments"]}
    actual_start = {item["start_seed"] for item in assessor["assessments"]}
    if actual_instance != expected_instance or actual_start != expected_start:
        raise MaterializationError("development seed allocation differs from frozen blocks")
    for seed in actual_instance | actual_start:
        if any(item["lower"] <= seed <= item["upper"] for item in denylist["retired_or_reserved_ranges"]):
            raise MaterializationError("development seed intersects a retired/reserved range")


def _validate_joins(candidate: dict[str, Any], assessor: dict[str, Any], control: dict[str, Any]) -> None:
    candidate_ids = [case["opaque_case_id"] for case in candidate["cases"]]
    assessor_ids = [item["opaque_case_id"] for item in assessor["assessments"]]
    control_ids = [item["opaque_case_id"] for item in control["cases"]]
    if candidate_ids != assessor_ids or candidate_ids != control_ids:
        raise MaterializationError("candidate/assessor/K0 join order mismatch")
    if any(len(item["attempts"]) != 32 for item in control["cases"]):
        raise MaterializationError("K0 trace start-count mismatch")


def _write_canonical(path: Path, document: Any) -> None:
    path.write_bytes(_canonical_bytes(document))


def _gzip_canonical(source: Path, destination: Path) -> dict[str, Any]:
    raw = source.read_bytes()
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    destination.write_bytes(compressed)
    return {
        "path": destination.name,
        "uncompressed_sha256": _sha256_bytes(raw),
        "compressed_sha256": _sha256_bytes(compressed),
        "uncompressed_bytes": len(raw),
        "compressed_bytes": len(compressed),
        "compression": "gzip-level-9-mtime-0",
    }


def _julia_executable() -> str:
    configured = os.environ.get("JULIA")
    executable = configured or shutil.which("julia")
    if not executable:
        raise MaterializationError("Julia executable not found; set JULIA explicitly")
    return executable


def materialize() -> Path:
    if not LOCK_PATH.is_file() or not BASELINE_SNAPSHOT_PATH.is_file():
        raise MaterializationError("source lock and committed public baseline snapshot are required")
    lock = _load_json(LOCK_PATH)
    _verify_clean_lock_head(lock)
    _verify_source_lock(lock)
    baseline_contract = _verify_product_baseline()
    baseline_snapshot = _load_json(BASELINE_SNAPSHOT_PATH)
    if baseline_snapshot.get("schema_version") != "exp-jac-003-public-baseline-snapshot/v1":
        raise MaterializationError("wrong committed public baseline snapshot schema")
    if baseline_snapshot.get("contract_sha256") != _sha256_path(BASELINE_CONTRACT_PATH):
        raise MaterializationError("public baseline snapshot does not belong to the frozen contract")

    generator = _import_frozen("jac3_frozen_generator", SOURCE_ROOT / "generator.py")
    assessor_module = _import_frozen("jac3_frozen_assessor", SOURCE_ROOT / "assessor.py")
    candidate = generator.build_candidate_document()
    _validate_candidate(candidate)
    assessor = assessor_module.build_assessor_document(candidate)
    _validate_seeds(assessor)

    staging_parent = Path(tempfile.mkdtemp(prefix=".jac3-materialize-", dir=EXPERIMENT_ROOT))
    try:
        raw_candidate = staging_parent / "candidate.json"
        raw_assessor = staging_parent / "assessor.json"
        raw_control = staging_parent / "control.json"
        _write_canonical(raw_candidate, candidate)
        _write_canonical(raw_assessor, assessor)
        project = str(EXPERIMENT_ROOT)
        subprocess.run(
            [
                _julia_executable(),
                "--startup-file=no",
                f"--project={project}",
                str(SOURCE_ROOT / "capture_k0_control.jl"),
                str(raw_candidate),
                str(raw_control),
            ],
            cwd=REPOSITORY_ROOT,
            check=True,
        )
        control = _load_json(raw_control)
        _validate_joins(candidate, assessor, control)

        publication = staging_parent / "publication"
        publication.mkdir()
        artifacts = {
            "candidate": _gzip_canonical(
                raw_candidate, publication / "development-candidate-inputs.json.gz"
            ),
            "assessor": _gzip_canonical(
                raw_assessor, publication / "development-assessor-truth.json.gz"
            ),
            "k0_control": _gzip_canonical(
                raw_control, publication / "development-k0-control-traces.json.gz"
            ),
        }
        shutil.copyfile(BASELINE_SNAPSHOT_PATH, publication / BASELINE_SNAPSHOT_PATH.name)
        manifest = {
            "schema_version": "exp-jac-003-development-manifest/v1",
            "experiment_id": "EXP-JAC-003",
            "partition": "development",
            "case_count": 64,
            "starts_per_case": 32,
            "candidate_route_visibility": [
                "variable_count",
                "residual_count",
                "structural_nonzeros",
                "color_count",
            ],
            "candidate_provider_visibility": [
                "compiler-derived row supports",
                "compiler-derived color partition",
            ],
            "assessor_join_key": "opaque_case_id plus start_index",
            "preimplementation_lock_sha256": _sha256_path(LOCK_PATH),
            "baseline_contract_sha256": _sha256_path(BASELINE_CONTRACT_PATH),
            "public_baseline_snapshot_sha256": _sha256_path(BASELINE_SNAPSHOT_PATH),
            "baseline_commit": baseline_contract["baseline_commit"],
            "artifacts": artifacts,
            "locked_inputs_materialized": False,
        }
        _write_canonical(publication / "manifest.json", manifest)
        if OUTPUT_PATH.exists():
            raise MaterializationError("development output appeared during staging")
        publication.rename(OUTPUT_PATH)
        completion = {
            "schema_version": "exp-jac-003-one-shot-completion/v1",
            "manifest_sha256": _sha256_path(OUTPUT_PATH / "manifest.json"),
            "source_lock_commit": _run_git("rev-parse", "HEAD"),
            "rerun_permitted": False,
        }
        _write_canonical(OUTPUT_PATH / COMPLETION_NAME, completion)
        return OUTPUT_PATH
    except Exception:
        if not OUTPUT_PATH.exists():
            shutil.rmtree(staging_parent, ignore_errors=True)
        raise
    finally:
        if staging_parent.exists():
            shutil.rmtree(staging_parent, ignore_errors=True)


def main() -> int:
    if len(sys.argv) != 1:
        raise MaterializationError("materializer accepts no options; it is one-shot")
    output = materialize()
    print(f"materialized frozen JAC003 development inputs at {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
