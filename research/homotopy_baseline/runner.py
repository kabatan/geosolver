"""Python orchestration for the HC + exact-certification baseline."""

from __future__ import annotations

import hashlib
import json
import math
import os
import resource
import shutil
import signal
import subprocess
import tempfile
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .compiler import UnsupportedFormulation, admission_report, compile_problem
from .exact import (
    ExactEliminationError,
    descriptors_from_candidates,
    exact_degree,
    polynomial_expression,
)

PACKAGE_ROOT = Path(__file__).resolve().parent
JULIA_PROJECT = PACKAGE_ROOT / "julia"
JULIA_WORKER = JULIA_PROJECT / "worker.jl"
DATASET_SHA256 = "c150bb352fc905dc4eead8a56ec50125d6dd2409d2de14ccd91a502836ea8511"


class _DeadlineExceeded(TimeoutError):
    """Raised when a solve phase consumes the complete wall budget."""


def _raise_deadline(_signum: int, _frame: Any) -> None:
    raise _DeadlineExceeded("solve deadline exceeded")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def translator_hash() -> str:
    digest = hashlib.sha256()
    for path in (PACKAGE_ROOT / "compiler.py", PACKAGE_ROOT / "ir.py", PACKAGE_ROOT / "exact.py"):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def environment_hash() -> str:
    files = [JULIA_PROJECT / "Project.toml", JULIA_PROJECT / "Manifest.toml", JULIA_WORKER]
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _git_revision() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=PACKAGE_ROOT.parents[1], text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _engine_identity() -> dict[str, str | None]:
    try:
        from geotarget.engine import OPTIMIZED_ENGINE_ID, optimized_engine_hash

        return {
            "engine_id": str(OPTIMIZED_ENGINE_ID),
            "engine_hash": str(optimized_engine_hash()),
        }
    except Exception:
        return {"engine_id": None, "engine_hash": None}


def admission_manifest(problem: Mapping[str, Any], *, mode: str) -> dict[str, Any]:
    report = admission_report(problem, mode=mode)
    payload = report.json()
    payload.update(
        {
            "schema_version": "geotarget.homotopy-admission/v1",
            "source_sha256": hashlib.sha256(
                json.dumps(
                    problem, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest(),
            "translator_hash": translator_hash(),
            "environment_hash": environment_hash(),
            "source_revision": _git_revision(),
            "dataset_sha256": DATASET_SHA256,
            **_engine_identity(),
        }
    )
    return payload


def _candidate_satisfies_guards(compilation, candidate: Mapping[str, Any]) -> bool:
    coordinates = candidate.get("coordinates")
    if not isinstance(coordinates, list):
        return False
    values: list[complex] = []
    try:
        for value in coordinates:
            if isinstance(value, Mapping):
                values.append(complex(float(value.get("re", 0)), float(value.get("im", 0))))
            elif isinstance(value, list):
                values.append(complex(float(value[0]), float(value[1])))
            else:
                values.append(complex(value))
    except (TypeError, ValueError, IndexError):
        return False
    import sympy as sp

    symbols = [sp.Symbol(name) for name in compilation.variables]
    substitutions = dict(zip(symbols, values, strict=False))
    tolerance = 1e-8
    for condition in compilation.inequalities:
        expression = polynomial_expression(condition.polynomial, symbols)
        try:
            evaluated = complex(sp.N(expression.subs(substitutions), 30))
        except Exception:
            return False
        if abs(evaluated.imag) > 1e-6:
            return False
        real_value = evaluated.real
        relation = condition.relation
        if relation == "eq" and abs(real_value) > tolerance:
            return False
        if relation == "ne" and abs(real_value) <= tolerance:
            return False
        if relation == ">" and not real_value > tolerance:
            return False
        if relation == ">=" and not real_value >= -tolerance:
            return False
        if relation == "<" and not real_value < -tolerance:
            return False
        if relation == "<=" and not real_value <= tolerance:
            return False
    return True


def _candidate_duplicate_count(candidates: list[Mapping[str, Any]]) -> int:
    representatives: list[list[complex]] = []
    duplicates = 0
    for candidate in candidates:
        coordinates = candidate.get("coordinates") or []
        try:
            values = [
                complex(float(value.get("re", 0)), float(value.get("im", 0)))
                for value in coordinates
            ]
        except (AttributeError, TypeError, ValueError):
            continue
        if any(
            len(values) == len(previous)
            and all(abs(left - right) <= 1e-8 for left, right in zip(values, previous, strict=True))
            for previous in representatives
        ):
            duplicates += 1
        else:
            representatives.append(values)
    return duplicates


def _run_julia(compilation_payload: dict[str, Any], *, seconds: float, seed: int) -> dict[str, Any]:
    julia = (
        os.environ.get("JULIA_BIN") or shutil.which("julia") or "/home/kabatan/.juliaup/bin/julia"
    )
    if not Path(julia).exists():
        raise RuntimeError("julia executable was not found")
    with tempfile.TemporaryDirectory(prefix="geotarget-hc-") as directory:
        root = Path(directory)
        input_path, output_path = root / "compilation.json", root / "worker.json"
        compilation_payload = {**compilation_payload, "seed": int(seed)}
        input_path.write_text(json.dumps(compilation_payload, ensure_ascii=False), encoding="utf-8")
        environment = os.environ.copy()
        environment.update(
            {
                "JULIA_NUM_THREADS": "1",
                "OPENBLAS_NUM_THREADS": "1",
                "MKL_NUM_THREADS": "1",
                "OMP_NUM_THREADS": "1",
                "JULIA_PROJECT": str(JULIA_PROJECT),
            }
        )
        command = [
            julia,
            "--project=" + str(JULIA_PROJECT),
            str(JULIA_WORKER),
            str(input_path),
            str(output_path),
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=PACKAGE_ROOT.parents[1],
                env=environment,
                capture_output=True,
                text=True,
                timeout=max(0.1, float(seconds)),
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            return {
                "status": "timeout",
                "stderr": str(error),
                "paths": 0,
                "failed_paths": 0,
                "candidates": [],
            }
        if completed.returncode != 0 or not output_path.exists():
            return {
                "status": "engine_error",
                "stderr": completed.stderr[-4000:],
                "stdout": completed.stdout[-1000:],
                "paths": 0,
                "failed_paths": 0,
                "candidates": [],
            }
        try:
            result = json.loads(output_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            return {
                "status": "engine_error",
                "stderr": f"invalid worker JSON: {error}",
                "candidates": [],
            }
        if completed.stderr:
            result["worker_stderr"] = completed.stderr[-4000:]
        return result


def solve_problem(
    problem: Mapping[str, Any],
    *,
    mode: str = "core",
    seconds: float = 180.0,
    seed: int = 0,
    completeness: str = "complete",
) -> dict[str, Any]:
    """Compile, certify target witnesses, and emit v1 result JSON.

    ``complete`` is the proof-oriented arm: it additionally checks that every
    path was certified and that the certified path count agrees with the exact
    quotient-space degree.  ``target`` deliberately omits that global claim;
    it still requires a Krawczyk-certified witness and exact elimination/root
    isolation, but reports the result as ``answers_found_completeness_unknown``.
    """

    if completeness not in {"complete", "target"}:
        raise ValueError("completeness must be 'complete' or 'target'")

    started = time.monotonic()
    base: dict[str, Any] = {
        "schema_version": "geotarget.homotopy-result/v1",
        "mode": mode,
        "completeness_policy": completeness,
        "completeness_claim": completeness == "complete",
        "source_sha256": "",
        "translator_hash": translator_hash(),
        "environment_hash": environment_hash(),
        "source_revision": _git_revision(),
        "dataset_sha256": DATASET_SHA256,
        "seed": int(seed),
        "requested_seconds": float(seconds),
        "answers": [],
        "distinct_exact_targets": [],
        "timings": {},
        "metrics": {},
        "warnings": [],
    }
    compile_budget = float(seconds)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    timer_enabled = math.isfinite(compile_budget) and compile_budget > 0.0
    if timer_enabled:
        signal.signal(signal.SIGALRM, _raise_deadline)
        signal.setitimer(signal.ITIMER_REAL, compile_budget)
    try:
        compilation = compile_problem(problem, mode=mode)
    except _DeadlineExceeded as error:
        base.update(
            {
                "status": "timeout",
                "admission": {
                    "mode": mode,
                    "supported": False,
                    "stage": "compile_timeout",
                    "reasons": ["compile_deadline_exceeded"],
                    "calls": [],
                    "variable_count": 0,
                    "equation_count": 0,
                    "branch_count": 1,
                },
                "detail": str(error),
                "timeout_phase": "compile",
                "timings": {"compile_seconds": time.monotonic() - started},
            }
        )
        return base
    except UnsupportedFormulation as error:
        base.update(
            {
                "status": "unsupported",
                "admission": admission_manifest(problem, mode=mode),
                "detail": str(error),
                "timings": {"total_seconds": time.monotonic() - started},
            }
        )
        return base
    finally:
        if timer_enabled:
            signal.setitimer(signal.ITIMER_REAL, 0.0)
            if previous_timer != (0.0, 0.0):
                signal.setitimer(signal.ITIMER_REAL, *previous_timer)
    base["source_sha256"] = compilation.source_sha256
    base["admission"] = compilation.admission.json()
    base["system"] = compilation.json()
    compile_elapsed = time.monotonic() - started
    remaining = max(0.1, float(seconds) - compile_elapsed)
    worker = _run_julia(compilation.json(), seconds=remaining, seed=seed)
    worker_elapsed = time.monotonic() - started - compile_elapsed
    base["worker"] = worker
    base["metrics"].update(
        {
            "paths": int(worker.get("paths", 0)),
            "failed_paths": int(worker.get("failed_paths", 0)),
            "singular_paths": int(worker.get("singular_paths", 0)),
            "duplicate_paths": _candidate_duplicate_count(worker.get("candidates", [])),
            "certified_count": int(worker.get("certified_count", 0)),
            "real_certified_count": int(worker.get("real_certified_count", 0)),
            "certification_precision_bits": worker.get("certification_precision_bits"),
            "certificate_min_precision_bits": worker.get("certificate_min_precision_bits"),
            "certificate_max_precision_bits": worker.get("certificate_max_precision_bits"),
        }
    )
    if time.monotonic() - started >= float(seconds):
        base.update(
            {
                "status": "timeout",
                "timeout_phase": "homotopy_or_certification",
                "timings": {
                    "compile_seconds": compile_elapsed,
                    "homotopy_seconds": float(
                        worker.get("timings", {}).get("homotopy_seconds", worker_elapsed)
                    ),
                    "certification_seconds": float(
                        worker.get("timings", {}).get("certification_seconds", 0.0)
                    ),
                    "total_seconds": time.monotonic() - started,
                },
            }
        )
        return base
    candidates = [
        item
        for item in worker.get("candidates", [])
        if item.get("certified")
        and item.get("real")
        and _candidate_satisfies_guards(compilation, item)
    ]
    descriptors: list[dict[str, Any]] = []
    elimination = None
    elimination_budget = float(seconds) - (time.monotonic() - started)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    timer_enabled = math.isfinite(elimination_budget) and elimination_budget > 0.0
    if timer_enabled:
        signal.signal(signal.SIGALRM, _raise_deadline)
        signal.setitimer(signal.ITIMER_REAL, elimination_budget)
    try:
        descriptors, elimination = descriptors_from_candidates(compilation, candidates)
        base["metrics"]["elimination_degree"] = int(elimination.degree())
        # The target arm still constructs an exact target certificate, but it
        # does not pay for (or claim) the independent quotient-degree proof.
        base["metrics"]["ideal_degree"] = (
            exact_degree(compilation) if completeness == "complete" else None
        )
        base["answers"] = descriptors
        base["distinct_exact_targets"] = descriptors
    except _DeadlineExceeded as error:
        base.update(
            {
                "status": "timeout",
                "timeout_phase": "elimination",
                "detail": str(error),
                "timings": {
                    "compile_seconds": compile_elapsed,
                    "homotopy_seconds": float(
                        worker.get("timings", {}).get("homotopy_seconds", worker_elapsed)
                    ),
                    "certification_seconds": float(
                        worker.get("timings", {}).get("certification_seconds", 0.0)
                    ),
                    "elimination_seconds": time.monotonic() - started
                    - compile_elapsed
                    - worker_elapsed,
                    "total_seconds": time.monotonic() - started,
                },
            }
        )
        return base
    except ExactEliminationError as error:
        base["warnings"].append(str(error))
    finally:
        if timer_enabled:
            signal.setitimer(signal.ITIMER_REAL, 0.0)
            if previous_timer != (0.0, 0.0):
                signal.setitimer(signal.ITIMER_REAL, *previous_timer)
    status = str(worker.get("status", "engine_error"))
    degree = base["metrics"].get("ideal_degree")
    complete = (
        completeness == "complete"
        and status == "certified"
        and not worker.get("failed_paths", 0)
        and not worker.get("singular_paths", 0)
        and not base["metrics"].get("duplicate_paths", 0)
        and int(worker.get("certified_count", 0)) == int(worker.get("paths", 0))
        and degree is not None
        and int(degree) == int(worker.get("paths", 0))
        and len(descriptors) >= 0
    )
    if complete:
        base["status"] = "exact_complete"
    elif descriptors:
        base["status"] = "answers_found_completeness_unknown"
    elif status == "timeout":
        base["status"] = "timeout"
    elif status == "certification_failed":
        base["status"] = "certification_failed"
    elif status == "certified":
        base["status"] = "no_answer_found"
    else:
        base["status"] = status
    base["timings"] = {
        "compile_seconds": compile_elapsed,
        "homotopy_seconds": float(
            worker.get("timings", {}).get("homotopy_seconds", worker_elapsed)
        ),
        "certification_seconds": float(worker.get("timings", {}).get("certification_seconds", 0.0)),
        "elimination_seconds": max(
            0.0, time.monotonic() - started - compile_elapsed - worker_elapsed
        ),
        "total_seconds": time.monotonic() - started,
    }
    if base["timings"]["total_seconds"] > float(seconds):
        base["status"] = "timeout"
        base["timeout_phase"] = "elimination"
    base["peak_rss_kib"] = int(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
    return base


__all__ = [
    "DATASET_SHA256",
    "admission_manifest",
    "environment_hash",
    "solve_problem",
    "translator_hash",
]
