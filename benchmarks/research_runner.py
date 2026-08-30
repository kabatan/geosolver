"""Repository-only campaign runner for reproducible GeoSolver experiments.

The runner deliberately separates solver execution from reference assessment:
``run`` never serializes the benchmark answer into a worker request or raw run.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from queue import Queue
from statistics import median
from typing import Any

import psutil

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "benchmarks" / "cases.jsonl"
CANONICAL_TIME_LIMIT_SECONDS = 180
CANONICAL_CORES = 1
THREAD_ENVIRONMENT = {
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
}


class CampaignError(RuntimeError):
    """Raised when corpus or campaign artifacts violate the research contract."""


@dataclass(frozen=True)
class CaseRecord:
    identifier: str
    dsl_path: Path | None
    dsl: dict[str, Any] | None
    source: str
    references: tuple[str, ...]
    authoring_status: str
    truth_status: str
    dedupe_key: str

    @property
    def runnable(self) -> bool:
        return (
            self.authoring_status == "runnable"
            and self.dsl_path is not None
            and self.dsl is not None
        )


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_hash() -> str:
    from geosolver.runtime.integrity import source_tree_hash

    return source_tree_hash()


def runtime_fingerprint():
    """Check the imported product and active-platform runtime dependency closure."""
    from importlib.metadata import PackageNotFoundError, distribution

    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name

    import geosolver

    lock = json.loads((ROOT / "src/geosolver/dependency-lock.json").read_text())["packages"]
    pending, actual, issues = ["geosolver"], {}, []
    while pending:
        name = canonicalize_name(pending.pop())
        if name in actual:
            continue
        try:
            package = distribution(name)
        except PackageNotFoundError:
            actual[name] = "missing"
            issues.append(f"missing runtime dependency: {name}")
            continue
        actual[name] = package.version
        if name != "geosolver" and lock.get(name) != package.version:
            issues.append(f"runtime dependency mismatch: {name}")
        for text in package.requires or []:
            requirement = Requirement(text)
            if requirement.marker is None or requirement.marker.evaluate({"extra": ""}):
                pending.append(requirement.name)
    imported = Path(geosolver.__file__).resolve().parent
    if imported != (ROOT / "src/geosolver").resolve():
        issues.append(f"unexpected import root: {imported}")
    return {
        "import_root": str(imported),
        "source_hash": _source_hash(),
        "runtime_dependencies": actual,
        "platform": sys.platform,
        "issues": issues,
    }


def _atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as stream:
        temporary = Path(stream.name)
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _load_cases(path: Path = DEFAULT_CASES) -> list[CaseRecord]:
    base = path.parent
    records: list[CaseRecord] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise CampaignError(f"{path}:{line_number}: invalid JSON: {error}") from error
        identifier = str(row.get("id", ""))
        raw_path = row.get("dsl_path")
        dsl_path = (base / str(raw_path)).resolve() if raw_path else None
        raw_dsl = row.get("dsl")
        raw_references = row.get("answer", [])
        if not isinstance(raw_references, list):
            raw_references = [raw_references]
        records.append(
            CaseRecord(
                identifier=identifier,
                dsl_path=dsl_path,
                dsl=dict(raw_dsl) if isinstance(raw_dsl, dict) else None,
                source=str(row.get("source", "")),
                references=tuple(str(item) for item in raw_references),
                authoring_status=str(row.get("authoring_status", "runnable")),
                truth_status=str(row.get("truth_status", "verified")),
                dedupe_key=str(row.get("dedupe_key", identifier)),
            )
        )
    return records


def validate_corpus(path: Path = DEFAULT_CASES) -> dict[str, Any]:
    records = _load_cases(path)
    issues: list[dict[str, str]] = []
    seen: set[str] = set()
    declared_paths: set[Path] = set()
    for record in records:
        if not record.identifier:
            issues.append({"code": "empty_id", "case": ""})
        elif record.identifier in seen:
            issues.append({"code": "duplicate_id", "case": record.identifier})
        seen.add(record.identifier)
        if not record.runnable:
            if record.dsl_path is not None or record.dsl is not None:
                issues.append({"code": "nonrunnable_has_dsl", "case": record.identifier})
            continue
        assert record.dsl_path is not None
        assert record.dsl is not None
        declared_paths.add(record.dsl_path)
        if not record.dsl_path.is_file():
            issues.append({"code": "missing_dsl", "case": record.identifier})
            continue
        try:
            file_dsl = json.loads(record.dsl_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            issues.append(
                {"code": "invalid_dsl_json", "case": record.identifier, "message": str(error)}
            )
            continue
        if file_dsl != record.dsl:
            issues.append({"code": "embedded_dsl_mismatch", "case": record.identifier})
        if file_dsl.get("id") != record.identifier:
            issues.append({"code": "dsl_id_mismatch", "case": record.identifier})
        try:
            from geosolver.problem.models import GeometryProblem
            from geosolver.problem.validation import validate

            problem = GeometryProblem.model_validate(file_dsl)
            report = validate(problem)
            for issue in report.issues:
                issues.append(
                    {
                        "code": f"dsl_{issue.code}",
                        "case": record.identifier,
                        "message": f"{issue.path}: {issue.message}",
                    }
                )
        except Exception as error:
            issues.append(
                {"code": "invalid_public_dsl", "case": record.identifier, "message": str(error)}
            )

    dsl_directory = path.parent / "dsl"
    actual_paths = {entry.resolve() for entry in dsl_directory.glob("*.json")}
    for orphan in sorted(actual_paths - declared_paths):
        issues.append({"code": "orphan_dsl", "case": orphan.stem})
    for missing in sorted(declared_paths - actual_paths):
        issues.append({"code": "undeclared_or_missing_dsl", "case": missing.stem})

    return {
        "valid": not issues,
        "inventory_count": len(records),
        "runnable_count": sum(record.runnable for record in records),
        "reference_only_count": sum(
            record.authoring_status == "reference_only" for record in records
        ),
        "migration_blocked_count": sum(
            record.authoring_status == "migration_blocked" for record in records
        ),
        "truth_verified_count": sum(record.truth_status == "verified" for record in records),
        "unique_natural_problem_count": len({record.dedupe_key for record in records}),
        "dsl_file_count": len(actual_paths),
        "issues": issues,
    }


def _git_value(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _dependency_hash() -> str:
    lock = ROOT / "uv.lock"
    return _sha256_file(lock) if lock.is_file() else "missing"


def _manifest(records: Iterable[CaseRecord], seeds: list[int]) -> dict[str, Any]:
    config = {
        "time_limit_seconds": CANONICAL_TIME_LIMIT_SECONDS,
        "cores": CANONICAL_CORES,
        "seeds": seeds,
        "completeness": "unknown",
        "thread_environment": THREAD_ENVIRONMENT,
    }
    cases = [
        {
            "id": record.identifier,
            "source": record.source,
            "authoring_status": record.authoring_status,
            "truth_status": record.truth_status,
            "reference_hash": _sha256_bytes(
                _canonical_json(list(record.references)).encode("utf-8")
            ),
            "dedupe_key": record.dedupe_key,
            "problem_hash": (
                _sha256_bytes(_canonical_json(record.dsl).encode("utf-8"))
                if record.dsl is not None
                else None
            ),
            "dsl_file_hash": (
                _sha256_file(record.dsl_path) if record.dsl_path is not None else None
            ),
        }
        for record in records
    ]
    return {
        "schema_version": 2,
        "created_at_unix": time.time(),
        "git_commit": _git_value("rev-parse", "HEAD"),
        "git_dirty": bool(_git_value("status", "--porcelain")),
        "source_hash": _source_hash(),
        "runtime_identity": runtime_fingerprint(),
        "dependency_lock_hash": _dependency_hash(),
        "config": config,
        "config_hash": _sha256_bytes(_canonical_json(config).encode("utf-8")),
        "corpus_hash": _sha256_bytes(_canonical_json(cases).encode("utf-8")),
        "cases": cases,
    }


def _independent_cpus() -> list[int | None]:
    if sys.platform == "darwin":
        return [None] * (psutil.cpu_count(logical=False) or 1)
    eligible = psutil.Process().cpu_affinity()
    selected = []
    seen = set()
    for cpu in eligible:
        topology = Path(f"/sys/devices/system/cpu/cpu{cpu}/topology")
        try:
            key = (
                (topology / "physical_package_id").read_text().strip(),
                (topology / "core_id").read_text().strip(),
            )
        except OSError:
            key = ("logical", cpu)
        if key not in seen:
            seen.add(key)
            selected.append(cpu)
    return selected[: psutil.cpu_count(logical=False) or 1] or [None]


def _pin_process(process: subprocess.Popen[str], cpu: int | None = None):
    if sys.platform == "darwin":
        return
    try:
        target = psutil.Process(process.pid)
        eligible = target.cpu_affinity()
        if eligible:
            requested = [cpu] if cpu is not None else eligible[:1]
            target.cpu_affinity(requested)
            actual = target.cpu_affinity()
            if actual != requested:
                raise CampaignError(
                    f"CPU affinity mismatch: requested {requested}, actual {actual}"
                )
            return actual
    except (AttributeError, OSError, psutil.Error) as error:
        raise CampaignError(f"cannot establish CPU affinity: {error}") from error


def _run_one(record: CaseRecord, seed: int, campaign: Path, cpu: int | None = None) -> Path:
    from geosolver.platform.processes import spawn_process, terminate_process_tree

    if not record.runnable or record.dsl_path is None or record.dsl is None:
        raise CampaignError(f"case {record.identifier} is not runnable")
    output = campaign / "runs" / record.identifier / f"{seed}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_solver_output = output.with_suffix(".solver.tmp.json")
    command = [
        sys.executable,
        "-m",
        "geosolver.application.cli",
        "solve",
        str(record.dsl_path),
        "--time-limit-seconds",
        str(CANONICAL_TIME_LIMIT_SECONDS),
        "--cores",
        str(CANONICAL_CORES),
        "--seed",
        str(seed),
        "--output",
        str(temporary_solver_output),
    ]
    environment = os.environ.copy()
    environment.update(THREAD_ENVIRONMENT)
    started = time.monotonic()
    process = spawn_process(
        command,
        cwd=ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    affinity = _pin_process(process, cpu)
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=CANONICAL_TIME_LIMIT_SECONDS + 8)
    except subprocess.TimeoutExpired:
        timed_out = True
        terminate_process_tree(process)
        stdout, stderr = process.communicate()
    finally:
        if getattr(process, "_geosolver_owned_group", False):
            terminate_process_tree(process, grace_seconds=0.1)
    elapsed = time.monotonic() - started
    solver_result: dict[str, Any] | None = None
    if temporary_solver_output.is_file():
        try:
            solver_result = json.loads(temporary_solver_output.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            solver_result = None
        temporary_solver_output.unlink(missing_ok=True)
    contract_issues = []
    if solver_result and solver_result.get("status") in {"solved", "no_answer_found"}:
        identity = solver_result.get("engine", {})
        info = solver_result.get("diagnostics", {}).get("process_info", {})
        if identity.get("source_hash") != _source_hash():
            contract_issues.append("executed_product_hash_mismatch")
        if info.get("import_root") != str((ROOT / "src/geosolver").resolve()):
            contract_issues.append("executed_import_root_mismatch")
        if cpu is not None and info.get("cpu_affinity") != [cpu]:
            contract_issues.append("executed_affinity_mismatch")
        expected = runtime_fingerprint()["runtime_dependencies"]
        for name, version in expected.items():
            if name != "geosolver" and info.get("installed_dependencies", {}).get(name) != version:
                contract_issues.append(f"executed_dependency_mismatch:{name}")
    raw = {
        "schema_version": 2,
        "execution_contract_issues": contract_issues,
        "case_id": record.identifier,
        "seed": seed,
        "problem_hash": _sha256_bytes(_canonical_json(record.dsl).encode("utf-8")),
        "source_hash": _source_hash(),
        "dependency_lock_hash": _dependency_hash(),
        "config": {
            "time_limit_seconds": CANONICAL_TIME_LIMIT_SECONDS,
            "cores": CANONICAL_CORES,
            "thread_environment": THREAD_ENVIRONMENT,
        },
        "process": {
            "assigned_cpu": cpu,
            "actual_affinity": affinity,
            "returncode": process.returncode,
            "timed_out": timed_out,
            "elapsed_seconds": elapsed,
            "stdout": stdout,
            "stderr": stderr,
        },
        "solver_result": solver_result,
    }
    _atomic_json(output, raw)
    if contract_issues:
        raise CampaignError(f"execution contract failed for {record.identifier}: {contract_issues}")
    return output


def run_campaign(
    destination: Path,
    *,
    cases_path: Path = DEFAULT_CASES,
    seeds: list[int],
    jobs: int,
    case_ids: set[str] | None = None,
    allow_dirty: bool = False,
) -> None:
    if not seeds or len(seeds) != len(set(seeds)):
        raise CampaignError("seeds must be nonempty and unique")
    if jobs < 1:
        raise CampaignError("jobs must be positive")
    if destination.exists() and any(destination.iterdir()):
        raise CampaignError("destination must be empty; existing campaigns are immutable")
    validation = validate_corpus(cases_path)
    if not validation["valid"]:
        raise CampaignError(f"corpus validation failed: {validation['issues']}")
    records = _load_cases(cases_path)
    if case_ids:
        known = {record.identifier for record in records}
        unknown = sorted(case_ids - known)
        if unknown:
            raise CampaignError(f"unknown case ids: {unknown}")
        records = [record for record in records if record.identifier in case_ids]
    runnable_records = [record for record in records if record.runnable]
    if not runnable_records:
        raise CampaignError("campaign selection contains no runnable cases")
    fingerprint = runtime_fingerprint()
    if fingerprint["issues"]:
        raise CampaignError(f"runtime environment mismatch: {fingerprint['issues']}")
    if not allow_dirty:
        from geosolver.runtime.integrity import verify_engine_lock

        valid, detail = verify_engine_lock()
        if not valid:
            raise CampaignError(f"engine lock mismatch: {detail}")
        if _git_value("status", "--porcelain"):
            raise CampaignError(
                "canonical campaigns require a clean tree; use --allow-dirty for development"
            )
    manifest = _manifest(records, seeds)
    manifest["development_allow_dirty"] = allow_dirty
    destination.mkdir(parents=True, exist_ok=True)
    _atomic_json(destination / "campaign-manifest.json", manifest)
    cpus = _independent_cpus()
    worker_count = min(int(jobs), len(cpus))
    available = Queue()
    for cpu in cpus[:worker_count]:
        available.put(cpu)

    def run_pinned(record, seed):
        cpu = available.get()
        try:
            return _run_one(record, seed, destination, cpu)
        finally:
            available.put(cpu)

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(run_pinned, record, seed): (record.identifier, seed)
            for record in runnable_records
            for seed in seeds
        }
        for future in as_completed(futures):
            identifier, seed = futures[future]
            try:
                future.result()
            except Exception as error:
                raise CampaignError(f"run failed for {identifier} seed {seed}: {error}") from error
    write_checksums(destination)


def _answer_keys(result: dict[str, Any] | None) -> list[str]:
    from pydantic import TypeAdapter

    from geosolver.problem.models import ExactAnswer

    if not result:
        return []
    answers = result.get("answers", [])
    adapter = TypeAdapter(ExactAnswer)
    return sorted(
        {
            _canonical_json(adapter.validate_python(answer).canonical_key())
            for answer in answers
            if isinstance(answer, dict)
        }
    )


def read_run_outcome(raw):
    """Read v1/v2 raw artifacts without rewriting historical files."""
    result = raw.get("solver_result") or {}
    process = raw.get("process", {})
    status = result.get("status", "artifact_missing")
    if process.get("timed_out"):
        status = "external_timeout"
    elif process.get("returncode") not in (None, 0) and status == "artifact_missing":
        status = "process_crash"
    diagnostics = result.get("diagnostics", {})
    info = diagnostics.get("process_info", {})
    summary = diagnostics.get("pipeline_summary", {})
    assembly = summary.get("exact_assembly", {})
    normal = status in {"solved", "no_answer_found"} and not raw.get("execution_contract_issues")
    stage = None
    if not normal:
        stage = "execution_contract" if raw.get("execution_contract_issues") else "runtime"
    elif status == "no_answer_found":
        if assembly.get("numeric_feasible_count", 0):
            stage = "exactification"
        elif summary.get("verification_records"):
            stage = "final_verification"
        else:
            stage = "search_or_refinement"
    return {
        "status": status,
        "normal_completion": normal,
        "failure_stage": stage,
        "termination_reason": result.get("termination_reason"),
        "rejection_tags": diagnostics.get("rejection_tags", assembly.get("rejection_tags", [])),
        "wall_seconds": result.get("elapsed_seconds", process.get("elapsed_seconds")),
        "cpu_seconds": info.get("cpu_seconds"),
        "peak_rss_bytes": info.get("peak_rss_bytes"),
        "phase_timings": diagnostics.get("phase_timings", {}),
        "counters": diagnostics.get("counters", {}),
    }


def reference_expressions(value: str) -> list[str]:
    """Normalize the corpus's explicit display notation, not its mathematical values.

    Keep original strings/hashes in the manifest. Reject unspecified notation
    through the existing exact parser rather than guessing its meaning.
    """
    counted = re.fullmatch(r"(.+)\s*\((\d+)個\)", value.strip())
    expression = (counted.group(1) if counted else value).strip()
    expression = re.sub(r"\\+sqrt\{(\d+)\}", r"sqrt(\1)", expression)
    expression = re.sub(r"√(\d+)", r"sqrt(\1)", expression).replace("π", "pi")
    expression = re.sub(r"∛(\d+)", r"root(\1,3)", expression)
    expression = re.sub(r"(?<=\d)(?=sqrt\(|root\(|pi\b|\()", "*", expression)
    try:
        node = ast.parse(expression, mode="eval").body
    except SyntaxError as exc:
        raise CampaignError("invalid reference expression") from exc
    # A comma-separated answer set is distinct from commas inside RootOf(...).
    # Source segments preserve long decimal literals without float round-tripping.
    result = (
        [ast.get_source_segment(expression, item) for item in node.elts]
        if isinstance(node, ast.Tuple)
        else [expression]
    )
    if counted and len(result) != int(counted.group(2)):
        raise CampaignError("reference answer count does not match its explicit list")
    return result


def assess_campaign(destination: Path, *, cases_path: Path = DEFAULT_CASES) -> None:
    from geosolver.exact import describe_exact

    records = _load_cases(cases_path)
    manifest = json.loads((destination / "campaign-manifest.json").read_text(encoding="utf-8"))
    selected = {row["id"]: row for row in manifest["cases"]}
    current = {record.identifier: record for record in records}
    for identifier, row in selected.items():
        record = current[identifier]
        expected_hash = _sha256_bytes(_canonical_json(list(record.references)).encode("utf-8"))
        if row.get("reference_hash") != expected_hash or row["truth_status"] != record.truth_status:
            raise CampaignError(
                f"reference changed for {identifier}; do not reassess a historical run"
            )
    references = {record.identifier: (record.truth_status, record.references) for record in records}
    rows: list[dict[str, Any]] = []
    expected_runs = {
        (row["id"], seed)
        for row in manifest["cases"]
        if row["authoring_status"] == "runnable"
        for seed in manifest["config"]["seeds"]
    }
    seen_runs = set()
    for raw_path in sorted((destination / "runs").glob("*/*.json")):
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        identifier = str(raw["case_id"])
        if identifier not in selected or raw["seed"] not in manifest["config"]["seeds"]:
            raise CampaignError(f"unexpected run artifact: {raw_path}")
        if raw["problem_hash"] != selected[identifier]["problem_hash"]:
            raise CampaignError(f"problem hash mismatch: {raw_path}")
        key = (identifier, raw["seed"])
        if key in seen_runs or key not in expected_runs:
            raise CampaignError(f"duplicate or unplanned run: {raw_path}")
        seen_runs.add(key)
        for field in ("source_hash", "dependency_lock_hash"):
            if raw.get(field) != manifest[field]:
                raise CampaignError(f"{field} mismatch: {raw_path}")
        for field in ("time_limit_seconds", "cores", "thread_environment"):
            if raw.get("config", {}).get(field) != manifest["config"][field]:
                raise CampaignError(f"config mismatch: {raw_path}")
        truth_status, reference_values = references[identifier]
        actual_keys = _answer_keys(raw.get("solver_result"))
        expected_keys = (
            sorted(
                {
                    _canonical_json(describe_exact(value).canonical_key())
                    for reference in reference_values
                    for value in reference_expressions(reference)
                }
            )
            if truth_status == "verified"
            else []
        )
        outcome = read_run_outcome(raw)
        extra = sorted(set(actual_keys) - set(expected_keys)) if truth_status == "verified" else []
        missing = (
            sorted(set(expected_keys) - set(actual_keys)) if truth_status == "verified" else []
        )
        relation = (
            "extra_and_missing"
            if extra and missing
            else ("extra" if extra else ("missing" if missing else "equal"))
        )
        rows.append(
            {
                "case_id": identifier,
                "seed": raw["seed"],
                "truth_status": truth_status,
                "reference": list(reference_values),
                "expected": [json.loads(value) for value in expected_keys],
                "matched": bool(outcome["normal_completion"] and actual_keys == expected_keys)
                if truth_status == "verified"
                else None,
                "actual": [json.loads(value) for value in actual_keys],
                "set_relation": relation if truth_status == "verified" else None,
                "extra": [json.loads(value) for value in extra],
                "missing": [json.loads(value) for value in missing],
                **outcome,
            }
        )
    if seen_runs != expected_runs:
        raise CampaignError(f"missing run artifacts: {sorted(expected_runs - seen_runs)}")
    path = destination / "assessment.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(_canonical_json(row) + "\n" for row in rows)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(payload, encoding="utf-8", newline="\n")
    os.replace(temporary, path)
    write_checksums(destination)


def summarize_campaign(destination: Path) -> None:
    assessment_path = destination / "assessment.jsonl"
    rows = [
        json.loads(line)
        for line in assessment_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    total = len(rows)
    assessed = sum(row["matched"] is not None for row in rows)
    matched = sum(row["matched"] is True for row in rows)
    summary = {
        "schema_version": 2,
        "run_count": total,
        "assessed_count": assessed,
        "unassessed_count": total - assessed,
        "matched_count": matched,
        "match_rate": matched / assessed if assessed else None,
        "completeness": "unknown",
        "status_counts": dict(
            sorted(Counter(row.get("status", "legacy_unrecorded") for row in rows).items())
        ),
        "set_relation_counts": dict(
            sorted(Counter(row.get("set_relation") or "unassessed" for row in rows).items())
        ),
        "failure_stage_counts": dict(
            sorted(Counter(row.get("failure_stage") or "none" for row in rows).items())
        ),
    }
    for metric in ("wall_seconds", "cpu_seconds", "peak_rss_bytes"):
        values = [row[metric] for row in rows if isinstance(row.get(metric), int | float)]
        summary[metric] = {
            "observed_count": len(values),
            "median": median(values) if values else None,
            "total": sum(values) if values else None,
        }
    for metric in ("phase_timings", "counters"):
        keys = sorted({key for row in rows for key in row.get(metric, {})})
        summary[metric] = {
            key: {
                "total": sum(row.get(metric, {}).get(key, 0) for row in rows),
                "median": median([row.get(metric, {}).get(key, 0) for row in rows]),
            }
            for key in keys
        }
    _atomic_json(destination / "summary.json", summary)
    write_checksums(destination)


def write_checksums(destination: Path) -> None:
    entries: list[str] = []
    for path in sorted(destination.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            entries.append(f"{_sha256_file(path)}  {path.relative_to(destination).as_posix()}")
    target = destination / "SHA256SUMS"
    temporary = destination / ".SHA256SUMS.tmp"
    temporary.write_text("\n".join(entries) + "\n", encoding="utf-8", newline="\n")
    os.replace(temporary, target)


def _parse_seeds(value: str) -> list[int]:
    seeds = [int(item.strip()) for item in value.split(",") if item.strip()]
    if not seeds:
        raise argparse.ArgumentTypeError("at least one seed is required")
    if len(seeds) != len(set(seeds)):
        raise argparse.ArgumentTypeError("duplicate seeds are not allowed")
    return seeds


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("destination", type=Path)
    run_parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    run_parser.add_argument("--seeds", type=_parse_seeds, default=[0])
    run_parser.add_argument("--jobs", type=int, default=1)
    run_parser.add_argument("--case-id", action="append", dest="case_ids")
    run_parser.add_argument(
        "--allow-dirty", action="store_true", help="explicit development-only execution"
    )
    assess_parser = subparsers.add_parser("assess")
    assess_parser.add_argument("destination", type=Path)
    assess_parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    summarize_parser = subparsers.add_parser("summarize")
    summarize_parser.add_argument("destination", type=Path)
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "validate":
            report = validate_corpus(arguments.cases)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if report["valid"] else 2
        if arguments.command == "run":
            run_campaign(
                arguments.destination,
                cases_path=arguments.cases,
                seeds=arguments.seeds,
                jobs=arguments.jobs,
                case_ids=set(arguments.case_ids) if arguments.case_ids else None,
                allow_dirty=arguments.allow_dirty,
            )
        elif arguments.command == "assess":
            assess_campaign(arguments.destination, cases_path=arguments.cases)
        elif arguments.command == "summarize":
            summarize_campaign(arguments.destination)
    except CampaignError as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
