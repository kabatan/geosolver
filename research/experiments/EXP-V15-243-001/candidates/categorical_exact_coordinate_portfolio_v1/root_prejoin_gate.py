#!/usr/bin/env python3
"""Root-owned five-source canonical prejoin gate; aggregate output only."""

from __future__ import annotations

import argparse
from collections import Counter
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent
WORKER = HERE / "categorical_fallback_worker.py"
WORKER_SHA256 = "73c5a8be044f37d7815df08572318cf7294cb5b4008d57983e8367a8ae58bee6"
SCHEMA = "geotarget.categorical-exact-coordinate-prejoin/v1"
EXPECTED_SOURCE_COUNT = 5
MAX_MANIFEST_BYTES = 1024 * 1024
PER_SOURCE_SECONDS = 18.0
MAX_RESULT_BYTES = 2 * 1024 * 1024
PYTHON = Path("/home/kabatan/work/solver-experiment-runtime/solver/python/.venv/bin/python")
SAFE_SUBPROCESS = Path(
    "/home/kabatan/work/solver-experiment-runtime/solver/research/"
    "infrastructure/memory_safety/safe_subprocess.py"
)
SAFE_LIMIT_EXEC = SAFE_SUBPROCESS.with_name("_limit_exec.py")
GATE_DEPENDENCIES = {
    PYTHON: "ccc93c55c24bb92866cc2f9eff61b124abf5d1ee6c8da0ef9b5eed4d78a21f07",
    SAFE_SUBPROCESS: "76aa547f235bd0ae11c8b567461384b22537a9b98c990db2ed126db0a19b55c5",
    SAFE_LIMIT_EXEC: "2173e83e6bcdc96bff5de5957f96b85a1281f7070e9e21deea047f81a16af8fb",
}


class GateError(RuntimeError):
    pass


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _load_worker():
    if _sha256(WORKER.read_bytes()) != WORKER_SHA256:
        raise GateError("categorical worker hash drift")
    name = "geotarget_categorical_exact_prejoin_worker"
    specification = importlib.util.spec_from_file_location(name, WORKER)
    if specification is None or specification.loader is None:
        raise GateError("categorical worker cannot be loaded")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    module.verify_frozen_dependencies()
    return module


def _load_guard():
    observed = {
        path: _sha256(path.read_bytes()) if path.is_file() else "MISSING"
        for path in GATE_DEPENDENCIES
    }
    if observed != GATE_DEPENDENCIES:
        raise GateError("prejoin process-guard closure changed")
    name = "geotarget_categorical_prejoin_safe_subprocess"
    specification = importlib.util.spec_from_file_location(name, SAFE_SUBPROCESS)
    if specification is None or specification.loader is None:
        raise GateError("prejoin process guard cannot be loaded")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _guarded_terminal(worker: Any, guard: Any, row: Mapping[str, Any], output: Path):
    output.unlink(missing_ok=True)
    command = [
        str(PYTHON),
        str(WORKER),
        "--source",
        str(row["source"].resolve()),
        "--source-sha256",
        row["source_sha256"],
        "--endpoint",
        json.dumps(row["endpoint"], separators=(",", ":")),
        "--endpoint-sha256",
        row["endpoint_sha256"],
        "--timeout-seconds",
        str(PER_SOURCE_SECONDS),
        "--output",
        str(output.resolve()),
    ]
    environment = os.environ.copy()
    environment.update(worker.THREAD_ENVIRONMENT)
    guarded = guard.run_guarded(
        command,
        limits=guard.Limits(
            timeout_seconds=PER_SOURCE_SECONDS + 0.50,
            rss_bytes=768 * 1024**2,
            address_space_bytes=3072 * 1024**2,
            data_bytes=2048 * 1024**2,
            output_bytes=1024**2,
            tail_bytes=16 * 1024,
        ),
        environment=environment,
        cwd=HERE,
    )
    result = None
    try:
        if not output.is_file() or not 0 < output.stat().st_size <= MAX_RESULT_BYTES:
            raise OSError("result artifact size invalid")
        loaded = json.loads(output.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            result = loaded
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        pass
    process_ok = bool(
        guarded.accepted_output is True
        and guarded.classification == "SUCCESS"
        and guarded.timeout is False
        and guarded.rss_cap_exceeded is False
        and guarded.rss_monitor_failed is False
        and guarded.output_cap_exceeded is False
        and guarded.descendant_leak is False
        and isinstance(result, dict)
    )
    return result, process_ok


def _manifest(path: Path) -> list[dict[str, Any]]:
    payload = path.read_bytes()
    if not payload or len(payload) > MAX_MANIFEST_BYTES:
        raise GateError("private request manifest size invalid")
    try:
        document = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GateError("private request manifest is not JSON") from error
    rows = document.get("requests") if isinstance(document, Mapping) else None
    if not isinstance(rows, list) or len(rows) != EXPECTED_SOURCE_COUNT:
        raise GateError("gate requires exactly five private requests")
    allowed = {"source", "source_sha256", "endpoint", "endpoint_sha256"}
    result: list[dict[str, Any]] = []
    sources: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != allowed:
            raise GateError("private request row schema invalid")
        source = row.get("source")
        source_sha = row.get("source_sha256")
        endpoint = row.get("endpoint")
        endpoint_sha = row.get("endpoint_sha256")
        if (
            not isinstance(source, str)
            or not isinstance(source_sha, str)
            or len(source_sha) != 64
            or not isinstance(endpoint, list)
            or not endpoint
            or not isinstance(endpoint_sha, str)
            or len(endpoint_sha) != 64
        ):
            raise GateError("private request binding malformed")
        sources.add(source_sha)
        result.append(
            {
                "source": Path(source),
                "source_sha256": source_sha,
                "endpoint": endpoint,
                "endpoint_sha256": endpoint_sha,
            }
        )
    if len(sources) != EXPECTED_SOURCE_COUNT:
        raise GateError("gate requests must bind five distinct anonymous sources")
    return result


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--global-lock", required=True, type=Path)
    arguments = parser.parse_args()
    if sorted(os.sched_getaffinity(0)) != [14]:
        raise GateError("canonical prejoin gate requires exclusive CPU14")
    rows = _manifest(arguments.requests)
    worker = _load_worker()
    guard = _load_guard()
    status_counts: Counter[str] = Counter()
    route_activation_counts: Counter[str] = Counter()
    guarded_process_failure_count = 0
    ready_sources = 0
    descriptor_identities: set[tuple[tuple[int, ...], int]] = set()
    with arguments.global_lock.open("a+b") as lock, tempfile.TemporaryDirectory(
        prefix="categorical-union-prejoin-"
    ) as temporary_name:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        temporary_root = Path(temporary_name)
        for ordinal, row in enumerate(rows):
            source_payload, source_document = worker._source_document(
                row["source"], row["source_sha256"]
            )
            if _sha256(source_payload) != row["source_sha256"]:
                raise GateError("private source binding changed")
            result, process_ok = _guarded_terminal(
                worker,
                guard,
                row,
                temporary_root / f"terminal-{ordinal}.json",
            )
            if not process_ok:
                guarded_process_failure_count += 1
            if not isinstance(result, Mapping):
                status_counts["GUARDED_PROCESS_REJECTED"] += 1
                continue
            status_counts[str(result.get("status"))] += 1
            portfolio = result.get("categorical_exact_coordinate_portfolio")
            if isinstance(portfolio, Mapping):
                activated_routes = portfolio.get("activated_routes")
                if (
                    portfolio.get("schema_version") != worker.PORTFOLIO_SCHEMA
                    or portfolio.get("categorical_route_activated") is not True
                    or portfolio.get("actual_exact_dispatch_activation") is not True
                    or portfolio.get("target_set_completeness_claim") is not False
                    or portfolio.get("truth_used") is not False
                    or not isinstance(activated_routes, list)
                    or not activated_routes
                    or not all(isinstance(route, str) for route in activated_routes)
                    or len(activated_routes) != len(set(activated_routes))
                    or not set(activated_routes) <= {"qreflect", "sector_angle"}
                ):
                    raise GateError("portfolio emitted without actual activation")
                for route in activated_routes:
                    route_activation_counts[route] += 1
            if not worker._authority_ready(
                result,
                source_document=source_document,
                source_sha256=row["source_sha256"],
                endpoint_sha256=row["endpoint_sha256"],
            ):
                continue
            identity = worker._descriptor_identity(result.get("descriptor"))
            if identity is None:
                raise GateError("canonical boundary accepted no descriptor identity")
            ready_sources += 1
            descriptor_identities.add(identity)
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    qreflect_activated = route_activation_counts["qreflect"] >= 1
    sector_activated = route_activation_counts["sector_angle"] >= 1
    go = bool(
        ready_sources == EXPECTED_SOURCE_COUNT
        and qreflect_activated
        and sector_activated
        and guarded_process_failure_count == 0
    )
    aggregate = {
        "schema_version": SCHEMA,
        "status": (
            "GO_CANONICAL_PREJOIN"
            if go
            else "STOP_CANONICAL_PREJOIN_INCOMPLETE"
        ),
        "request_count": len(rows),
        "anonymous_source_count": EXPECTED_SOURCE_COUNT,
        "canonical_ready_source_count": ready_sources,
        "distinct_descriptor_identity_count": len(descriptor_identities),
        "status_counts": dict(sorted(status_counts.items())),
        "route_activation_counts": dict(sorted(route_activation_counts.items())),
        "qreflect_actual_activation_observed": qreflect_activated,
        "sector_angle_actual_activation_observed": sector_activated,
        "guarded_process_failure_count": guarded_process_failure_count,
        "single_refinement_union_worker": True,
        "worker_sha256": WORKER_SHA256,
        "existing_exact_outer_authority_boundary_used": True,
        "canonical_scorer_executed": False,
        "formal_score_claim": False,
        "target_set_completeness_claim": False,
        "truth_used": False,
        "case_ids_retained": False,
        "targets_endpoints_descriptors_retained": False,
        "per_row_output_emitted": False,
        "cpu": 14,
        "global_lock_held": True,
    }
    aggregate["aggregate_sha256"] = _sha256(
        json.dumps(aggregate, sort_keys=True, separators=(",", ":")).encode()
    )
    _atomic_json(arguments.output.resolve(), aggregate)
    print(json.dumps(aggregate, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
