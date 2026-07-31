#!/usr/bin/env python3.12
"""Aggregate-only source applicability scan for derivative-energy transport."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys
from typing import Any, Mapping, Sequence

import sympy as sp

from prototype import (
    CapabilityError,
    derivative_energy_certificate,
    standardized_residuals,
)


RUNTIME_ROOT = Path("/home/kabatan/work/solver-experiment-runtime/solver")
DEFAULT_SOURCE_ROOT = Path(
    "/home/kabatan/work/solver-experiment-results/partial-ideal-root-readiness-v1/degree1-inputs"
).resolve()
SOURCE_COMPILER_PATH = (
    RUNTIME_ROOT
    / "research/experiments/EXP-REAL61-004/msolve_all_real_proposal/source_compile.py"
)
SEMANTIC_COMPILER_PATH = (
    RUNTIME_ROOT
    / "research/experiments/EXP-REAL61-002/algebraic_lane/compiler.py"
)
SOURCE_COMPILER_SHA256 = "24d6cee020256043f6ad4657ffa84a8b4e9188ab9ff18bf3e9339672a3229349"
SEMANTIC_COMPILER_SHA256 = "f127f7f1e2f93161e1353f07222e93ffacfa1c2dbd4e68e5b1fd23a8a3b10318"
REQUEST_KEYS = frozenset({"source_path"})
FORBIDDEN_KEYS = frozenset(
    {
        "id",
        "case_id",
        "family",
        "truth",
        "answer",
        "target",
        "outcome",
        "result",
        "score",
        "known_count",
        "expected",
        "solution",
    }
)
FORBIDDEN_SOURCE_KEYS = FORBIDDEN_KEYS - {"answer"}
MAX_REQUESTS = 10_000
MAX_REQUEST_BYTES = 4 * 1024 * 1024
MAX_SOURCE_VARIABLES = 8
MAX_EQUATIONS = 16
MAX_TOTAL_DEGREE = 6
MAX_TOTAL_TERMS = 512
MAX_COEFFICIENT_BITS = 2_048
RECORD_SECONDS = 3.0


class ScanError(ValueError):
    """The source-only scan contract or capability failed closed."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_module(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError("frozen source compiler is unavailable")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _load_source_compiler():
    if (
        _sha256(SOURCE_COMPILER_PATH) != SOURCE_COMPILER_SHA256
        or _sha256(SEMANTIC_COMPILER_PATH) != SEMANTIC_COMPILER_SHA256
    ):
        raise RuntimeError("frozen source compiler dependency changed")
    return _load_module("source_energy_frozen_compiler", SOURCE_COMPILER_PATH)


@contextlib.contextmanager
def _record_deadline():
    previous = signal.getsignal(signal.SIGALRM)

    def timeout(_signum, _frame):
        raise TimeoutError("source energy scan deadline")

    signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, RECORD_SECONDS)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def _request(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ScanError("source request is not an object")
    keys = set(value)
    if keys != REQUEST_KEYS or keys & FORBIDDEN_KEYS:
        raise ScanError("source request violates the frozen whitelist")
    return dict(value)


def _source_path(value: object, source_root: Path) -> Path:
    if not isinstance(value, str):
        raise ScanError("source path is malformed")
    path = Path(value).resolve()
    try:
        relative = path.relative_to(source_root)
    except ValueError as error:
        raise ScanError("source path escapes source-only panel") from error
    if len(relative.parts) != 1 or path.suffix != ".json" or not path.is_file():
        raise ScanError("source path is not a panel JSON file")
    return path


def _bounds(document: Mapping[str, Any], dimension: int) -> tuple[tuple[sp.Rational, sp.Rational], ...]:
    raw = document.get("bounds")
    if not isinstance(raw, list) or len(raw) != dimension:
        raise ScanError("finite source bounds are unavailable")
    result: list[tuple[sp.Rational, sp.Rational]] = []
    for pair in raw:
        if not isinstance(pair, list) or len(pair) != 2:
            raise ScanError("source bound is malformed")
        try:
            lower, upper = (sp.Rational(str(value)) for value in pair)
        except (TypeError, ValueError) as error:
            raise ScanError("source bound is not rational") from error
        if not lower.is_finite or not upper.is_finite or not lower < upper:
            raise ScanError("source bound is not a finite interval")
        result.append((lower, upper))
    return tuple(result)


def _polynomials(
    compiled: Mapping[str, Any],
) -> tuple[tuple[sp.Symbol, ...], tuple[sp.Poly, ...]]:
    names = compiled.get("cover_variable_names")
    equations = compiled.get("equations")
    if not isinstance(names, list) or not names or not isinstance(equations, list) or not equations:
        raise ScanError("compiled source cover is malformed")
    variables = tuple(sp.Symbol(str(name)) for name in names)
    local_names = {variable.name: variable for variable in variables}
    try:
        residuals = tuple(
            sp.Poly(sp.sympify(text, locals=local_names), *variables, domain=sp.QQ)
            for text in equations
        )
    except (sp.PolynomialError, sp.CoercionFailed, TypeError, ValueError) as error:
        raise ScanError("compiled residual is not QQ polynomial") from error
    if any(item.is_zero for item in residuals):
        raise ScanError("compiled residual contains zero")
    return variables, residuals


def _coefficient_bits(polynomials: Sequence[sp.Poly]) -> int:
    values: list[int] = []
    for polynomial in polynomials:
        for coefficient in polynomial.coeffs():
            rational = sp.Rational(coefficient)
            values.extend(
                (abs(int(rational.p)).bit_length(), abs(int(rational.q)).bit_length())
            )
    return max(values, default=0)


def _signature(
    dimension: int,
    residuals: Sequence[sp.Poly],
    matrix: sp.MatrixBase,
) -> tuple[object, ...]:
    maximum_degree = max(int(item.total_degree()) for item in residuals)
    total_terms = sum(len(item.terms()) for item in residuals)
    off_diagonal = any(
        matrix[row, column] != 0
        for row in range(dimension)
        for column in range(row)
    )
    identity_scaled = bool(matrix == sp.eye(dimension) * matrix[0, 0])
    return (
        dimension,
        len(residuals) - dimension,
        maximum_degree,
        total_terms // 16,
        int(matrix.rank()),
        off_diagonal,
        identity_scaled,
    )


def _classify(
    path: Path, source_compiler: Any
) -> tuple[bool, bool, tuple[object, ...] | None]:
    source_bytes = path.read_bytes()
    document = json.loads(source_bytes)
    if (
        not isinstance(document, dict)
        or "id" in document
        or FORBIDDEN_SOURCE_KEYS & set(document)
    ):
        raise ScanError("source is not an anonymous problem projection")
    compiled, _msolve_input = source_compiler.compile_source_document(
        document, source_bytes=source_bytes
    )
    if not (
        compiled.get("status") == "ELIGIBLE_MSOLVE_DIMENSION_PROBE"
        and compiled.get("truth_used") is False
        and compiled.get("known_target_count_used") is False
        and compiled.get("case_identity_routing") is False
        and compiled.get("source_variable_names")
        == document.get("variables", {}).get("names")
    ):
        return False, False, None
    if compiled.get("cover_variable_names") != compiled.get("source_variable_names"):
        return True, False, None
    variables, residuals = _polynomials(compiled)
    if not (
        1 <= len(variables) <= MAX_SOURCE_VARIABLES
        and len(residuals) <= MAX_EQUATIONS
        and max(int(item.total_degree()) for item in residuals) <= MAX_TOTAL_DEGREE
        and sum(len(item.terms()) for item in residuals) <= MAX_TOTAL_TERMS
        and _coefficient_bits(residuals) <= MAX_COEFFICIENT_BITS
    ):
        return True, True, None
    bounds = _bounds(document, len(variables))
    standardized_variables, standardized = standardized_residuals(
        residuals, variables, bounds
    )
    certificate = derivative_energy_certificate(standardized, standardized_variables)
    if not certificate.verify():
        raise ScanError("exact derivative-energy certificate failed")
    return True, True, _signature(len(variables), standardized, certificate.matrix)


def scan(requests: object, source_root: Path, source_compiler: Any) -> dict[str, Any]:
    if not isinstance(requests, list) or len(requests) > MAX_REQUESTS:
        raise ScanError("source panel is not a bounded array")
    validated = [_request(value) for value in requests]
    compiler_eligible = 0
    source_polynomial_eligible = 0
    metric_eligible = 0
    signatures: set[tuple[object, ...]] = set()
    for request in validated:
        try:
            with _record_deadline():
                compiler_ready, source_polynomial_ready, signature = _classify(
                    _source_path(request["source_path"], source_root), source_compiler
                )
                compiler_eligible += int(compiler_ready)
                source_polynomial_eligible += int(source_polynomial_ready)
                if signature is not None:
                    metric_eligible += 1
                    signatures.add(signature)
        except Exception:
            continue
    gate_pass = metric_eligible >= 8 and len(signatures) >= 3
    return {
        "schema_version": "geotarget.source-analytic-derivative-energy-static-scan/v1",
        "candidate": "SOURCE_ANALYTIC_DERIVATIVE_ENERGY_TRANSPORT_START_V1",
        "counts": {
            "input_count": len(validated),
            "compiler_eligible_count": compiler_eligible,
            "source_polynomial_eligible_count": source_polynomial_eligible,
            "metric_eligible_count": metric_eligible,
            "ineligible_count": len(validated) - metric_eligible,
            "signature_count": len(signatures),
        },
        "gate": {
            "minimum_metric_eligible_count": 8,
            "minimum_signature_count": 3,
            "pass": gate_pass,
        },
        "mechanism": {
            "baseline_quota": "3/4",
            "transport_quota": "1/4",
            "radius_preserving": True,
            "target_used": False,
            "score_used": False,
        },
        "authority": False,
        "release": False,
        "individual_records_emitted": False,
        "identifiers_hashes_paths_polynomials_emitted": False,
    }


def _write(path: Path, result: Mapping[str, Any]) -> None:
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", required=True, type=Path)
    parser.add_argument("--requests-sha256", required=True)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-cpu", type=int, default=14)
    arguments = parser.parse_args()
    if os.sched_getaffinity(0) != {arguments.expected_cpu}:
        raise SystemExit("source scan must be pinned to exactly the expected CPU")
    if arguments.requests.stat().st_size > MAX_REQUEST_BYTES:
        raise SystemExit("source request panel exceeds byte cap")
    payload = arguments.requests.read_bytes()
    if hashlib.sha256(payload).hexdigest() != arguments.requests_sha256.lower():
        raise SystemExit("source request panel SHA-256 mismatch")
    try:
        requests = json.loads(payload)
        result = scan(requests, arguments.source_root.resolve(), _load_source_compiler())
        _write(arguments.output, result)
    except (json.JSONDecodeError, OSError, RuntimeError, ScanError, CapabilityError):
        print(json.dumps({"status": "FAIL_CLOSED"}))
        return 2
    print(json.dumps({"status": "COUNTS_WRITTEN", "gate_pass": result["gate"]["pass"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
