#!/usr/bin/env python3
"""Run one disposable solver arm on frozen development-only partitions.

The worker receives only a canonical formulation and its SHA-256.  The outer
answer field remains in a temporary dataset consumed by the offline scorer
after all worker processes have exited.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Mapping, Sequence


HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[2]
DEFAULT_FROZEN_ROOT = Path("/home/kabatan/work/solver-experiment-runtime/solver")
DEFAULT_DATASET = Path(
    "/home/kabatan/work/solver-artifacts/experiment-freeze-20260727/"
    "product-145-20260727-v4/development145.jsonl"
)
DEFAULT_PYTHON = Path("/home/kabatan/work/solver/.venv/bin/python")
BENCHMARK_LOCK = Path("/tmp/geotarget-exp-global-benchmark-v1.lock")
ARM_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{2,79}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
THREAD_ENVIRONMENT = {
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONHASHSEED": "0",
    "OMP_NUM_THREADS": "1",
    "OMP_THREAD_LIMIT": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "BLIS_NUM_THREADS": "1",
    "GOTO_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "JULIA_NUM_THREADS": "1",
    "RAYON_NUM_THREADS": "1",
    "MALLOC_ARENA_MAX": "2",
    "GEOTARGET_GLOBAL_RSS_RESERVATION_BYTES": str(8 * 1024**3),
}
TELEMETRY_TOKENS = (
    "elapsed",
    "wall",
    "callback",
    "start",
    "rank",
    "guard",
    "reservoir",
    "restoration",
    "precision",
    "pslq",
    "rss",
    "endpoint_count",
    "candidate_count",
    "attempt_count",
    "completed",
    "termination",
    "deadline",
)
SECRET_TOKENS = ("answer", "descriptor", "polynomial", "selected_real_root", "target_value")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, payload: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def resolve_entrypoint(raw: str, arm_path: Path, frozen_root: Path) -> Path:
    if raw.startswith("frozen://"):
        candidate = frozen_root / raw.removeprefix("frozen://")
    else:
        source = Path(raw).expanduser()
        candidate = source if source.is_absolute() else arm_path.parent / source
    return candidate.resolve()


def load_arm(path: Path, frozen_root: Path) -> tuple[dict[str, str], Path]:
    raw = load_json(path)
    if not isinstance(raw, Mapping) or set(raw) != {
        "id",
        "base_commit",
        "entrypoint",
        "mechanism_hash",
    }:
        raise ValueError("arm.json must contain exactly the four contract fields")
    arm = {key: value for key, value in raw.items() if isinstance(value, str)}
    if len(arm) != 4:
        raise ValueError("all arm fields must be strings")
    if not ARM_ID.fullmatch(arm["id"]):
        raise ValueError("invalid arm id")
    if not HEX40.fullmatch(arm["base_commit"]):
        raise ValueError("invalid base_commit")
    if not HEX64.fullmatch(arm["mechanism_hash"]):
        raise ValueError("invalid mechanism_hash")
    entrypoint = resolve_entrypoint(arm["entrypoint"], path, frozen_root)
    if not entrypoint.is_file():
        raise ValueError(f"arm entrypoint is unavailable: {entrypoint}")
    actual_hash = sha256_file(entrypoint)
    if actual_hash != arm["mechanism_hash"]:
        raise ValueError(
            f"mechanism hash mismatch: expected {arm['mechanism_hash']}, got {actual_hash}"
        )
    return arm, entrypoint


def canonical_formulation_bytes(formulation: Mapping[str, object]) -> bytes:
    return (
        json.dumps(
            formulation,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


def load_rows(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"dataset row {line_number} is not an object")
        problem_id = row.get("problem_id")
        formulation = row.get("formulation")
        if (
            not isinstance(problem_id, str)
            or not isinstance(formulation, Mapping)
            or formulation.get("id") != problem_id
            or formulation.get("task") != "solve"
        ):
            raise ValueError(f"dataset row {line_number} violates the source contract")
        rows.append(row)
    if len(rows) != 145 or len({str(row["problem_id"]) for row in rows}) != 145:
        raise ValueError("development dataset must contain exactly 145 unique cases")
    return rows


def validate_development_rows(
    rows: Sequence[dict[str, object]], input_manifest: Path
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    manifest = load_json(input_manifest)
    expected = manifest.get("rows") if isinstance(manifest, Mapping) else None
    if not isinstance(expected, list) or len(expected) != 145:
        raise ValueError("archived INPUT_MANIFEST.json is malformed")
    by_id = {str(row["problem_id"]): row for row in rows}
    ordered: list[dict[str, object]] = []
    normalized_expected: list[dict[str, object]] = []
    for ordinal, item in enumerate(expected, 1):
        if not isinstance(item, Mapping):
            raise ValueError("archived input manifest contains a non-object row")
        problem_id = item.get("problem_id")
        expected_sha = item.get("source_sha256")
        if not isinstance(problem_id, str) or not isinstance(expected_sha, str):
            raise ValueError("archived input manifest row is incomplete")
        row = by_id.get(problem_id)
        if row is None:
            raise ValueError(f"development case is absent: ordinal {ordinal}")
        formulation = row["formulation"]
        assert isinstance(formulation, Mapping)
        actual_sha = sha256_bytes(canonical_formulation_bytes(formulation))
        if actual_sha != expected_sha:
            raise ValueError(f"canonical formulation mismatch at ordinal {ordinal}")
        ordered.append(row)
        normalized_expected.append(
            {"ordinal": ordinal, "problem_id": problem_id, "source_sha256": expected_sha}
        )
    if set(by_id) != {str(item["problem_id"]) for item in normalized_expected}:
        raise ValueError("development dataset case identities differ from the archive")
    return ordered, normalized_expected


def select_partition(
    ordered_rows: Sequence[dict[str, object]], partition: str, screen_manifest: Path
) -> list[dict[str, object]]:
    if partition == "development":
        return list(ordered_rows)
    document = load_json(screen_manifest)
    screens = document.get("screens") if isinstance(document, Mapping) else None
    selected = screens.get(partition) if isinstance(screens, Mapping) else None
    case_ids = selected.get("case_ids") if isinstance(selected, Mapping) else None
    if not isinstance(case_ids, list) or not all(isinstance(value, str) for value in case_ids):
        raise ValueError("frozen screen manifest is malformed")
    by_id = {str(row["problem_id"]): row for row in ordered_rows}
    if any(problem_id not in by_id for problem_id in case_ids):
        raise ValueError("screen manifest refers to an unknown development case")
    return [by_id[problem_id] for problem_id in case_ids]


def subset_payload(rows: Sequence[dict[str, object]]) -> bytes:
    return b"".join(
        (
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
        ).encode("utf-8")
        for row in rows
    )


def runtime_versions(python: Path) -> dict[str, str]:
    if not python.is_file() or not os.access(python, os.X_OK):
        raise ValueError(f"Python interpreter is unavailable: {python}")
    code = (
        "import json,numpy,scipy,mpmath,sympy,sys;"
        "print(json.dumps({'python':sys.version.split()[0],'numpy':numpy.__version__,"
        "'scipy':scipy.__version__,'mpmath':mpmath.__version__,"
        "'sympy':sympy.__version__},sort_keys=True))"
    )
    completed = subprocess.run(
        [str(python), "-c", code],
        check=True,
        text=True,
        capture_output=True,
        env={**os.environ, **THREAD_ENVIRONMENT},
    )
    return json.loads(completed.stdout)


def load_module(path: Path, name: str):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def invoke(module, arguments: Sequence[str]) -> None:
    previous = sys.argv
    try:
        sys.argv = [str(module.__file__), *arguments]
        module.main()
    finally:
        sys.argv = previous


def scalar_telemetry(document: Mapping[str, object]) -> dict[str, object]:
    telemetry: dict[str, object] = {}

    def visit(prefix: str, value: object) -> None:
        lowered = prefix.lower()
        if any(token in lowered for token in SECRET_TOKENS):
            return
        if isinstance(value, Mapping):
            for key, child in value.items():
                visit(f"{prefix}.{key}" if prefix else str(key), child)
            return
        if isinstance(value, list):
            if any(token in lowered for token in TELEMETRY_TOKENS):
                telemetry[prefix + ".length"] = len(value)
            return
        if isinstance(value, (str, int, float, bool)) or value is None:
            if any(token in lowered for token in TELEMETRY_TOKENS):
                telemetry[prefix] = value

    visit("", document)
    return telemetry


def write_truth_free_telemetry(output: Path) -> None:
    run = load_json(output / "RESULT.json")
    rows = run.get("rows") if isinstance(run, Mapping) else None
    if not isinstance(rows, list):
        raise ValueError("run RESULT.json has no rows")
    input_manifest = load_json(output / "INPUT_MANIFEST.json")
    input_rows = input_manifest.get("rows") if isinstance(input_manifest, Mapping) else None
    if not isinstance(input_rows, list):
        raise ValueError("run INPUT_MANIFEST.json has no rows")
    source_sha_by_slug = {
        str(item["slug"]): str(item["source_sha256"])
        for item in input_rows
        if isinstance(item, Mapping) and "slug" in item and "source_sha256" in item
    }
    emitted = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        slug = str(row.get("slug", ""))
        result_path = output / "artifacts" / slug / "RESULT.json"
        search_path = output / "artifacts" / slug / "search.json"
        worker = load_json(result_path) if result_path.is_file() else {}
        search = load_json(search_path) if search_path.is_file() else {}
        worker = worker if isinstance(worker, Mapping) else {}
        search = search if isinstance(search, Mapping) else {}
        emitted.append(
            {
                "ordinal": row.get("index"),
                "source_sha256": source_sha_by_slug.get(slug),
                "accepted": row.get("accepted"),
                "outer_elapsed_seconds": row.get("outer_elapsed_seconds"),
                "worker_elapsed_seconds": row.get("elapsed_wall_seconds"),
                "returned_exact_target_count": row.get("exact_target_count"),
                "worker": scalar_telemetry(worker),
                "search": scalar_telemetry(search),
            }
        )
    atomic_json(
        output / "TELEMETRY.json",
        {
            "schema_version": "geotarget.exp-global-001-telemetry/v1",
            "truth_included": False,
            "case_count": len(emitted),
            "rows": emitted,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", required=True, type=Path)
    parser.add_argument(
        "--partition", choices=("screen24", "screen60", "development"), default="screen24"
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--frozen-root", type=Path, default=DEFAULT_FROZEN_ROOT)
    parser.add_argument("--python", type=Path, default=DEFAULT_PYTHON)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--cpus", default="0")
    parser.add_argument("--total-seconds", type=float, default=30.0)
    parser.add_argument("--search-seconds", type=float, default=20.0)
    parser.add_argument("--starts", type=int, default=256)
    parser.add_argument("--callbacks-per-start", type=int, default=600)
    parser.add_argument("--aggregate-callback-cap", type=int, default=153600)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--execute", action="store_true")
    arguments = parser.parse_args()

    try:
        arm_path = arguments.arm.expanduser().resolve()
        frozen_root = arguments.frozen_root.expanduser().resolve()
        dataset = arguments.dataset.expanduser().resolve()
        python = arguments.python.expanduser().absolute()
        output = arguments.output.expanduser().resolve()
        if output.exists():
            raise ValueError(f"refusing existing output path: {output}")
        if is_within(output, REPOSITORY):
            raise ValueError("raw run output must be outside the repository")
        runner_path = frozen_root / (
            "research/experiments/EXP-OMC-G-PART01-V15-EVAL-001/run_dataset.py"
        )
        scorer_path = frozen_root / (
            "research/experiments/EXP-OMC-G-PART01-V15-EVAL-001/score_dataset.py"
        )
        input_manifest = frozen_root / (
            "research/experiments/EXP-V15-243-001/results/"
            "repro-20260722-champion-v2-poc-preloaded-development145-180s-jobs7-v1/"
            "INPUT_MANIFEST.json"
        )
        screen_manifest = frozen_root / (
            "research/experiments/EXP-V15-243-001/benchmark/SCREEN_MANIFEST.json"
        )
        for required in (runner_path, scorer_path, input_manifest, screen_manifest):
            if not required.is_file():
                raise ValueError(f"frozen dependency is unavailable: {required}")
        arm, entrypoint = load_arm(arm_path, frozen_root)
        rows = load_rows(dataset)
        ordered, expected = validate_development_rows(rows, input_manifest)
        selected = select_partition(ordered, arguments.partition, screen_manifest)
        payload = subset_payload(selected)
        versions = runtime_versions(python)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error)) from error

    plan = {
        "schema_version": "geotarget.exp-global-001-arm-plan/v1",
        "execute": arguments.execute,
        "arm": arm,
        "entrypoint": str(entrypoint),
        "entrypoint_sha256": sha256_file(entrypoint),
        "partition": arguments.partition,
        "case_count": len(selected),
        "development_dataset_sha256": sha256_file(dataset),
        "selected_dataset_sha256": sha256_bytes(payload),
        "archived_input_manifest_sha256": sha256_file(input_manifest),
        "canonical_formulations_verified": len(expected),
        "runner_sha256": sha256_file(runner_path),
        "scorer_sha256": sha256_file(scorer_path),
        "python": str(python),
        "runtime_versions": versions,
        "truth_passed_to_worker": False,
        "validation_or_sealed_supported": False,
        "jobs": arguments.jobs,
        "cpus": arguments.cpus,
        "total_seconds": arguments.total_seconds,
        "search_seconds": arguments.search_seconds,
        "starts": arguments.starts,
        "callbacks_per_start": arguments.callbacks_per_start,
        "aggregate_callback_cap": arguments.aggregate_callback_cap,
        "seed": arguments.seed,
    }
    if not arguments.execute:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    environment = {**os.environ, **THREAD_ENVIRONMENT}
    with BENCHMARK_LOCK.open("a+", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise SystemExit("another EXP-GLOBAL-001 benchmark is active") from error
        with tempfile.TemporaryDirectory(
            prefix=f".{output.name}.dataset-", dir=output.parent
        ) as temporary:
            subset = Path(temporary) / f"{arguments.partition}.jsonl"
            subset.write_bytes(payload)
            os.chmod(subset, 0o600)
            if str(frozen_root) not in sys.path:
                sys.path.insert(0, str(frozen_root))
            runner = load_module(
                runner_path, f"geotarget_exp_global_runner_{arm['id'].replace('-', '_')}"
            )
            runner.PYTHON = python
            runner.WORKER = entrypoint
            runner.THREAD_ENVIRONMENT = {
                **runner.THREAD_ENVIRONMENT,
                **THREAD_ENVIRONMENT,
            }
            invoke(
                runner,
                [
                    "--execute",
                    "--dataset",
                    str(subset),
                    "--jobs",
                    str(arguments.jobs),
                    "--cpus",
                    arguments.cpus,
                    "--total-seconds",
                    str(arguments.total_seconds),
                    "--search-seconds",
                    str(arguments.search_seconds),
                    "--starts",
                    str(arguments.starts),
                    "--callbacks-per-start",
                    str(arguments.callbacks_per_start),
                    "--aggregate-callback-cap",
                    str(arguments.aggregate_callback_cap),
                    "--seed",
                    str(arguments.seed),
                    "--output",
                    str(output),
                ],
            )
            subprocess.run(
                [str(python), str(scorer_path), "--dataset", str(subset), "--run", str(output)],
                cwd=frozen_root,
                env=environment,
                check=True,
            )
        atomic_json(output / "CAMPAIGN_PLAN.json", plan)
        write_truth_free_telemetry(output)
    print(output / "OFFLINE_SCORE.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
