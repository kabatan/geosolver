"""One-shot C1 materializer for EXP-LOCAL-003 development inputs.

This module is C0 source. Importing it does not generate an input. The CLI is
enabled only by a future immutable ``preimplementation-lock.json`` at the exact
clean HEAD that introduced that lock. There is no force, resume, overwrite, or
output-path option.
"""

from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import math
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from types import ModuleType
from typing import Any


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = EXPERIMENT_ROOT.parents[2]
PYTHON_SOURCE = REPOSITORY_ROOT / "python" / "src"
if str(PYTHON_SOURCE) not in sys.path:
    sys.path.insert(0, str(PYTHON_SOURCE))

from geotarget.canonical import canonical_bytes, canonical_hash  # noqa: E402
from geotarget.validation import validate_document  # noqa: E402


SOURCE_ROOT = EXPERIMENT_ROOT / "source"
CARD_PATH = EXPERIMENT_ROOT.parent / "EXP-LOCAL-003.json"
LOCK_PATH = EXPERIMENT_ROOT / "preimplementation-lock.json"
VISIBILITY_PATH = EXPERIMENT_ROOT / "visibility-contract.json"
NUMERIC_DOMAIN_PATH = EXPERIMENT_ROOT / "numeric-json-domain.json"
OUTPUT_PATH = EXPERIMENT_ROOT / "development-inputs"
COMPLETION_NAME = "ONE_SHOT_COMPLETE.json"
CARD_SHA256 = "0caae294a032f6d920c718219836e60e57f20c76fe5d790a615e554a95c6ee3c"

FAMILY_IDS = (
    "SCALE-LADDER",
    "CURVED-CHAIN",
    "NEAR-RANK-DEFICIENT",
    "REDUNDANT-OVERDETERMINED",
    "TANGENT-CIRCLE-LINE",
    "MULTIROOT-WARPED",
    "STRICT-GUARD-BOUNDARY",
    "OPAQUE-TRANSCENDENTAL-C0",
)
PRIMARY_REPRESENTATIONS = (
    "base",
    "signed-permutation",
    "semantic-row-rescaling",
)
SAFETY_REPRESENTATION = "orthogonal-safety"

CANDIDATE_CASE_KEYS = {
    "opaque_case_key",
    "problem_document",
    "problem_sha256",
    "calibration_points",
    "calibration_points_sha256",
    "starts",
    "starts_sha256",
    "public_numeric_metadata",
    "budget",
}
FORBIDDEN_CANDIDATE_KEYS = {
    "family",
    "family_id",
    "family_ordinal",
    "factors",
    "latent_group",
    "latent_group_id",
    "representation",
    "expected_invariant",
    "primary",
    "calibration_key",
    "calibration_key_hex",
    "start_key",
    "start_key_hex",
    "gold",
    "gold_configurations",
    "gold_targets",
    "analytic_truth",
    "expected_decision",
    "configuration_tolerance",
    "target_tolerance",
    "tolerances",
}
FORBIDDEN_CANDIDATE_MARKERS = tuple(value.lower() for value in FAMILY_IDS) + (
    "signed-permutation",
    "semantic-row-rescaling",
    "orthogonal-safety",
)


class MaterializationError(RuntimeError):
    """A frozen precondition or projection invariant failed closed."""


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_path(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MaterializationError(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise MaterializationError(f"{path} is not a JSON object")
    return value


def _run_git(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise MaterializationError(
            f"git {' '.join(arguments)} failed: {completed.stderr.strip()}"
        )
    return completed.stdout.strip()


def _import_frozen(name: str, path: Path) -> ModuleType:
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise MaterializationError(f"cannot import frozen source {path}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    try:
        specification.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return module


def _verify_clean_lock_head(lock: dict[str, Any]) -> str:
    if OUTPUT_PATH.exists():
        raise MaterializationError("development inputs already exist; one-shot rerun refused")
    if _run_git("status", "--porcelain=v1", "--untracked-files=all"):
        raise MaterializationError("one-shot materialization requires a completely clean worktree")
    head = _run_git("rev-parse", "HEAD")
    lock_commit = _run_git(
        "log", "-1", "--format=%H", "--", str(LOCK_PATH.relative_to(REPOSITORY_ROOT))
    )
    if not lock_commit or lock_commit != head:
        raise MaterializationError("HEAD must be exactly the commit that introduced the C0 lock")
    if lock.get("status") != "frozen-before-one-shot-development-materialization":
        raise MaterializationError("preimplementation lock is not frozen for C1")
    if lock.get("card_sha256") != CARD_SHA256 or _sha256_path(CARD_PATH) != CARD_SHA256:
        raise MaterializationError("EXP-LOCAL-003 card identity drift")
    return head


def _verify_file_lock(lock: dict[str, Any]) -> None:
    declared = lock.get("files")
    if not isinstance(declared, dict) or not declared:
        raise MaterializationError("preimplementation lock has no file hashes")
    for relative, expected in declared.items():
        if not isinstance(relative, str) or not isinstance(expected, str):
            raise MaterializationError("preimplementation file map is not string-to-string")
        path = REPOSITORY_ROOT / relative
        if not path.is_file() or _sha256_path(path) != expected:
            raise MaterializationError(f"preimplementation hash drift: {relative}")

    declared_sources = lock.get("experiment_source_files")
    if not isinstance(declared_sources, list) or not declared_sources:
        raise MaterializationError("experiment source allowlist is missing")
    expected_sources = {str(value) for value in declared_sources}
    actual_sources = {
        path.relative_to(REPOSITORY_ROOT).as_posix()
        for path in SOURCE_ROOT.rglob("*")
        if path.is_file() and path.suffix in {".py", ".jl", ".json"}
    }
    if actual_sources != expected_sources:
        raise MaterializationError(
            "experiment source allowlist drift: "
            f"extra={sorted(actual_sources - expected_sources)}, "
            f"missing={sorted(expected_sources - actual_sources)}"
        )
    forbidden_paths = lock.get("forbidden_mechanism_paths")
    if not isinstance(forbidden_paths, list) or not forbidden_paths:
        raise MaterializationError("mechanism-absence list is missing")
    for relative in forbidden_paths:
        if (REPOSITORY_ROOT / str(relative)).exists():
            raise MaterializationError(f"candidate mechanism exists before C1: {relative}")


def _walk_candidate_boundary(value: Any, path: str = "candidate") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower()
            if normalized in FORBIDDEN_CANDIDATE_KEYS:
                raise MaterializationError(f"forbidden candidate key at {path}.{key}")
            _walk_candidate_boundary(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk_candidate_boundary(child, f"{path}[{index}]")
    elif isinstance(value, str):
        lowered = value.lower()
        if any(marker in lowered for marker in FORBIDDEN_CANDIDATE_MARKERS):
            raise MaterializationError(f"family/representation marker leaked at {path}")


def _finite_number(value: Any, *, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MaterializationError(f"{path} must be a JSON number, not {type(value).__name__}")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise MaterializationError(f"{path} must be finite")
    return numeric


def _validate_points(
    points: Any,
    *,
    count: int,
    lower: list[float],
    upper: list[float],
    path: str,
) -> None:
    if not isinstance(points, list) or len(points) != count:
        raise MaterializationError(f"{path} must contain exactly {count} points")
    for row_index, row in enumerate(points):
        if not isinstance(row, list) or len(row) != len(lower):
            raise MaterializationError(f"{path}[{row_index}] has wrong dimension")
        for column, value in enumerate(row):
            numeric = _finite_number(value, path=f"{path}[{row_index}][{column}]")
            if not lower[column] <= numeric <= upper[column]:
                raise MaterializationError(f"{path}[{row_index}] is outside public bounds")


def _validate_candidate(candidate: dict[str, Any]) -> list[str]:
    if candidate.get("schema_version") != "exp-local-003-candidate-inputs/v1":
        raise MaterializationError("wrong candidate projection schema")
    if candidate.get("card_sha256") != CARD_SHA256:
        raise MaterializationError("candidate projection card mismatch")
    cases = candidate.get("cases")
    if not isinstance(cases, list) or len(cases) != 64:
        raise MaterializationError("candidate projection must contain 64 cases")
    keys: list[str] = []
    _walk_candidate_boundary(candidate)
    for index, case in enumerate(cases):
        if not isinstance(case, dict) or set(case) != CANDIDATE_CASE_KEYS:
            raise MaterializationError(f"candidate case {index} has unexpected fields")
        key = case["opaque_case_key"]
        if not isinstance(key, str) or not key:
            raise MaterializationError(f"candidate case {index} has invalid opaque key")
        keys.append(key)
        problem = case["problem_document"]
        validate_document(problem, schema="problem", schemas=REPOSITORY_ROOT / "schemas")
        if case["problem_sha256"] != canonical_hash(problem):
            raise MaterializationError(f"candidate case {index} problem hash mismatch")
        if not isinstance(problem, dict):
            raise MaterializationError(f"candidate case {index} problem is not an object")
        variables = problem.get("variables")
        if not isinstance(variables, list) or not variables:
            raise MaterializationError(f"candidate case {index} has no variables")
        lower: list[float] = []
        upper: list[float] = []
        for variable_index, variable in enumerate(variables):
            if not isinstance(variable, dict):
                raise MaterializationError("problem variable is not an object")
            lo = _finite_number(
                variable.get("lower"), path=f"candidate[{index}].lower[{variable_index}]"
            )
            hi = _finite_number(
                variable.get("upper"), path=f"candidate[{index}].upper[{variable_index}]"
            )
            if not lo < hi:
                raise MaterializationError("candidate variable bounds are not strict")
            lower.append(lo)
            upper.append(hi)
        _validate_points(
            case["calibration_points"],
            count=64,
            lower=lower,
            upper=upper,
            path=f"candidate[{index}].calibration_points",
        )
        _validate_points(
            case["starts"],
            count=32,
            lower=lower,
            upper=upper,
            path=f"candidate[{index}].starts",
        )
        if case["calibration_points_sha256"] != canonical_hash(case["calibration_points"]):
            raise MaterializationError(f"candidate case {index} calibration hash mismatch")
        if case["starts_sha256"] != canonical_hash(case["starts"]):
            raise MaterializationError(f"candidate case {index} start hash mismatch")
        budget = case["budget"]
        expected_budget = {
            "local_max_iterations": 250,
            "local_max_evaluations": 2000,
            "launch_prefixes": [8, 16, 32],
        }
        if budget != expected_budget:
            raise MaterializationError(f"candidate case {index} budget drift")
        canonical_bytes(case["public_numeric_metadata"])
    if keys != sorted(keys) or len(keys) != len(set(keys)):
        raise MaterializationError("candidate opaque keys must be unique and sorted")
    canonical_bytes(candidate)
    return keys


def _validate_assessor(assessor: dict[str, Any]) -> list[str]:
    if assessor.get("schema_version") != "exp-local-003-assessor-truth/v1":
        raise MaterializationError("wrong assessor projection schema")
    if assessor.get("card_sha256") != CARD_SHA256:
        raise MaterializationError("assessor projection card mismatch")
    cases = assessor.get("cases")
    if not isinstance(cases, list) or len(cases) != 64:
        raise MaterializationError("assessor projection must contain 64 cases")
    keys: list[str] = []
    allocation: Counter[tuple[str, int, str]] = Counter()
    primary_count = 0
    safety_count = 0
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise MaterializationError(f"assessor case {index} is not an object")
        key = case.get("opaque_case_key")
        family = case.get("family_id")
        family_ordinal = case.get("family_ordinal")
        group = case.get("latent_group")
        representation = case.get("representation")
        invariant = case.get("expected_invariant")
        if not isinstance(key, str) or not key:
            raise MaterializationError(f"assessor case {index} has invalid key")
        if family not in FAMILY_IDS or family_ordinal != FAMILY_IDS.index(family):
            raise MaterializationError(f"assessor case {index} family mapping drift")
        if isinstance(group, bool) or group not in (0, 1):
            raise MaterializationError(f"assessor case {index} latent group drift")
        if representation in PRIMARY_REPRESENTATIONS:
            if invariant is not True:
                raise MaterializationError("primary representation must be invariant")
            primary_count += 1
        elif representation == SAFETY_REPRESENTATION:
            if invariant is not False:
                raise MaterializationError("Safety16 must have expected_invariant=false")
            safety_count += 1
        else:
            raise MaterializationError(f"assessor case {index} representation drift")
        if not isinstance(case.get("gold"), dict) or not isinstance(case.get("tolerances"), dict):
            raise MaterializationError(f"assessor case {index} lacks Gold/tolerances")
        keys.append(key)
        allocation[(family, group, representation)] += 1
    expected_allocation = {
        (family, group, representation)
        for family in FAMILY_IDS
        for group in (0, 1)
        for representation in (*PRIMARY_REPRESENTATIONS, SAFETY_REPRESENTATION)
    }
    if set(allocation) != expected_allocation or any(value != 1 for value in allocation.values()):
        raise MaterializationError("assessor 8x2x4 allocation drift")
    if primary_count != 48 or safety_count != 16:
        raise MaterializationError("assessor primary/Safety16 counts drift")
    if keys != sorted(keys) or len(keys) != len(set(keys)):
        raise MaterializationError("assessor opaque keys must be unique and sorted")
    canonical_bytes(assessor)
    return keys


def _validate_private(private: dict[str, Any]) -> list[str]:
    if private.get("schema_version") != "exp-local-003-generator-private/v1":
        raise MaterializationError("wrong generator-private schema")
    if private.get("card_sha256") != CARD_SHA256:
        raise MaterializationError("generator-private card mismatch")
    cases = private.get("cases")
    if not isinstance(cases, list) or len(cases) != 64:
        raise MaterializationError("generator-private projection must contain 64 cases")
    keys: list[str] = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise MaterializationError(f"generator-private case {index} is not an object")
        key = case.get("opaque_case_key")
        calibration_key = case.get("calibration_key_hex")
        if not isinstance(key, str) or not key:
            raise MaterializationError(f"generator-private case {index} has invalid join key")
        if not isinstance(calibration_key, str) or len(calibration_key) != 64:
            raise MaterializationError(f"generator-private case {index} lacks calibration key")
        keys.append(key)
    if keys != sorted(keys) or len(keys) != len(set(keys)):
        raise MaterializationError("generator-private opaque keys must be unique and sorted")
    canonical_bytes(private)
    return keys


def validate_documents(documents: dict[str, dict[str, Any]]) -> None:
    if set(documents) != {"candidate", "assessor", "generator_private"}:
        raise MaterializationError("generator returned the wrong projection set")
    candidate_keys = _validate_candidate(documents["candidate"])
    assessor_keys = _validate_assessor(documents["assessor"])
    private_keys = _validate_private(documents["generator_private"])
    if candidate_keys != assessor_keys or candidate_keys != private_keys:
        raise MaterializationError("candidate/assessor/private joins differ")


def _gzip_document(path: Path, document: Any) -> dict[str, Any]:
    raw = canonical_bytes(document)
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    path.write_bytes(compressed)
    return {
        "path": path.name,
        "jcs_sha256": _sha256_bytes(raw),
        "gzip_sha256": _sha256_bytes(compressed),
        "jcs_bytes": len(raw),
        "gzip_bytes": len(compressed),
        "compression": "gzip-level-9-mtime-0",
    }


def _write_json(path: Path, document: Any) -> None:
    path.write_bytes(canonical_bytes(document))


def _publish_documents(
    publication: Path,
    documents: dict[str, dict[str, Any]],
    bootstrap: bytes,
    *,
    lock_sha256: str,
    lock_commit: str,
) -> None:
    candidate_root = publication / "candidate"
    assessor_root = publication / "assessor"
    private_root = publication / "generator-private"
    candidate_root.mkdir(parents=True)
    assessor_root.mkdir()
    private_root.mkdir()

    candidate_artifact = _gzip_document(
        candidate_root / "development-candidate-inputs.json.gz", documents["candidate"]
    )
    assessor_artifact = _gzip_document(
        assessor_root / "development-assessor-truth.json.gz", documents["assessor"]
    )
    private_artifact = _gzip_document(
        private_root / "development-generator-private.json.gz",
        documents["generator_private"],
    )
    bootstrap_path = assessor_root / "development-bootstrap-indices.bin"
    bootstrap_path.write_bytes(bootstrap)
    bootstrap_artifact = {
        "path": bootstrap_path.name,
        "sha256": _sha256_bytes(bootstrap),
        "bytes": len(bootstrap),
        "format": "GTLOCAL3BOOT1-development",
    }

    candidate_manifest = {
        "schema_version": "exp-local-003-candidate-manifest/v1",
        "experiment_id": "EXP-LOCAL-003",
        "partition": "development",
        "case_count": 64,
        "starts_per_case": 32,
        "calibration_points_per_case": 64,
        "card_sha256": CARD_SHA256,
        "preimplementation_lock_sha256": lock_sha256,
        "artifact": candidate_artifact,
        "visible_tree": "candidate-only",
    }
    assessor_manifest = {
        "schema_version": "exp-local-003-assessor-manifest/v1",
        "experiment_id": "EXP-LOCAL-003",
        "partition": "development",
        "primary_case_count": 48,
        "safety_case_count": 16,
        "card_sha256": CARD_SHA256,
        "preimplementation_lock_sha256": lock_sha256,
        "truth_artifact": assessor_artifact,
        "bootstrap_artifact": bootstrap_artifact,
        "visible_tree": "assessor-only-after-candidate-seal",
    }
    private_manifest = {
        "schema_version": "exp-local-003-generator-private-manifest/v1",
        "experiment_id": "EXP-LOCAL-003",
        "partition": "development",
        "card_sha256": CARD_SHA256,
        "preimplementation_lock_sha256": lock_sha256,
        "artifact": private_artifact,
        "visible_tree": "materializer-and-audit-only",
    }
    _write_json(candidate_root / "manifest.json", candidate_manifest)
    _write_json(assessor_root / "manifest.json", assessor_manifest)
    _write_json(private_root / "manifest.json", private_manifest)

    root_manifest = {
        "schema_version": "exp-local-003-development-input-manifest/v1",
        "experiment_id": "EXP-LOCAL-003",
        "partition": "development",
        "card_sha256": CARD_SHA256,
        "preimplementation_lock_sha256": lock_sha256,
        "source_lock_commit": lock_commit,
        "candidate_manifest_sha256": _sha256_path(candidate_root / "manifest.json"),
        "assessor_manifest_sha256": _sha256_path(assessor_root / "manifest.json"),
        "generator_private_manifest_sha256": _sha256_path(private_root / "manifest.json"),
        "candidate_process_argument": "candidate/ only",
        "assessor_open_order": "after sealed candidate raw output and process exit",
        "rerun_permitted": False,
        "locked_inputs_materialized": False,
    }
    _write_json(publication / "manifest.json", root_manifest)
    completion = {
        "schema_version": "exp-local-003-one-shot-completion/v1",
        "manifest_sha256": _sha256_path(publication / "manifest.json"),
        "source_lock_commit": lock_commit,
        "rerun_permitted": False,
    }
    _write_json(publication / COMPLETION_NAME, completion)


def _materialize_from_modules(
    generator: ModuleType,
    bootstrap_module: ModuleType,
    publication: Path,
    *,
    lock_sha256: str,
    lock_commit: str,
) -> None:
    build = getattr(generator, "build_development_documents", None)
    if not callable(build):
        raise MaterializationError("frozen generator lacks build_development_documents")
    documents = build()
    if not isinstance(documents, dict):
        raise MaterializationError("frozen generator did not return a projection object")
    validate_documents(documents)
    make_bootstrap = getattr(bootstrap_module, "bootstrap_index_bytes", None)
    parse_bootstrap = getattr(bootstrap_module, "parse_bootstrap_index_bytes", None)
    if not callable(make_bootstrap) or not callable(parse_bootstrap):
        raise MaterializationError("frozen bootstrap module lacks required functions")
    bootstrap = make_bootstrap("development")
    if not isinstance(bootstrap, bytes):
        raise MaterializationError("bootstrap authority is not bytes")
    parse_bootstrap(
        bootstrap,
        expected_stage="development",
        expected_sha256=_sha256_bytes(bootstrap),
    )
    _publish_documents(
        publication,
        documents,
        bootstrap,
        lock_sha256=lock_sha256,
        lock_commit=lock_commit,
    )


def materialize() -> Path:
    if not LOCK_PATH.is_file() or not VISIBILITY_PATH.is_file() or not NUMERIC_DOMAIN_PATH.is_file():
        raise MaterializationError("C0 lock, visibility and numeric-domain artifacts are required")
    lock = _load_object(LOCK_PATH)
    lock_commit = _verify_clean_lock_head(lock)
    _verify_file_lock(lock)
    lock_sha256 = _sha256_path(LOCK_PATH)
    generator = _import_frozen("local3_frozen_generator", SOURCE_ROOT / "generator.py")
    bootstrap = _import_frozen(
        "local3_frozen_bootstrap", SOURCE_ROOT / "bootstrap_indices.py"
    )

    staging_parent = Path(tempfile.mkdtemp(prefix=".local3-materialize-", dir=EXPERIMENT_ROOT))
    publication = staging_parent / "publication"
    try:
        publication.mkdir()
        _materialize_from_modules(
            generator,
            bootstrap,
            publication,
            lock_sha256=lock_sha256,
            lock_commit=lock_commit,
        )
        if OUTPUT_PATH.exists():
            raise MaterializationError("development output appeared during staging")
        publication.rename(OUTPUT_PATH)
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
    print(f"materialized frozen LOCAL003 development inputs at {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
