#!/usr/bin/env python3.12
"""Aggregate-only census from raw anonymous degree-one requests.

This is a candidate-local adapter, not a reusable campaign facility.  Paths,
endpoints, proposal coefficients, target values, and per-record dispositions
remain process-local.  The only persisted result is the counts-only output of
``static_census.summarize``.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import signal
import sys
from typing import Any, Mapping, Sequence

import sympy as sp

from static_census import (
    BOOLEAN_FIELDS,
    CAPS,
    INTEGER_FIELDS,
    RECORD_FIELDS,
    SCHEMA,
    summarize,
)


RUNTIME_ROOT = Path("/home/kabatan/work/solver-experiment-runtime/solver")
PANEL_SOURCE_ROOT = Path(
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
REQUEST_KEYS = frozenset(
    {"source_path", "endpoint", "candidate_relation_high_to_low"}
)
FORBIDDEN_REQUEST_KEYS = frozenset(
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
FORBIDDEN_SOURCE_KEYS = frozenset(
    {"truth", "outcome", "result", "score", "known_count", "expected", "solution"}
)
MAX_ENDPOINT_DIMENSION = 64
MAX_REQUESTS = 10_000
MAX_REQUEST_BYTES = 16 * 1024 * 1024
RECORD_SECONDS = 3.0


class DegreeOneCensusError(ValueError):
    """The raw panel or one request violates the frozen blind contract."""


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
    return _load_module(
        "thom_hermite_degree1_frozen_source_compiler", SOURCE_COMPILER_PATH
    )


@contextlib.contextmanager
def _record_deadline():
    previous = signal.getsignal(signal.SIGALRM)

    def timeout(_signum, _frame):
        raise TimeoutError("record census deadline")

    signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, RECORD_SECONDS)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def _validated_request(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise DegreeOneCensusError("request is not an object")
    keys = set(value)
    if keys != REQUEST_KEYS or keys & FORBIDDEN_REQUEST_KEYS:
        raise DegreeOneCensusError("request fields violate the frozen whitelist")
    return dict(value)


def _bounded_source_path(value: object, source_root: Path) -> Path:
    if not isinstance(value, str):
        raise DegreeOneCensusError("source path is malformed")
    path = Path(value).resolve()
    try:
        relative = path.relative_to(source_root)
    except ValueError as error:
        raise DegreeOneCensusError("source path escapes the anonymous panel") from error
    if len(relative.parts) != 1 or path.suffix != ".json" or not path.is_file():
        raise DegreeOneCensusError("source path is not a panel JSON file")
    return path


def _endpoint(value: object) -> tuple[float, ...]:
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_ENDPOINT_DIMENSION:
        raise DegreeOneCensusError("endpoint dimension is malformed")
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in value):
        raise DegreeOneCensusError("endpoint contains a non-number")
    endpoint = tuple(float(item) for item in value)
    if any(not math.isfinite(item) for item in endpoint):
        raise DegreeOneCensusError("endpoint contains a non-finite value")
    return endpoint


def _degree_one_relation(value: object) -> tuple[int, int]:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(isinstance(item, bool) or not isinstance(item, int) for item in value)
    ):
        raise DegreeOneCensusError("proposal is not an integer degree-one relation")
    leading, constant = map(int, value)
    if leading <= 0 or math.gcd(leading, constant) != 1:
        raise DegreeOneCensusError("proposal relation is not primitive leading-positive")
    return leading, constant


def _empty_feature() -> dict[str, bool | int]:
    result: dict[str, bool | int] = {field: False for field in BOOLEAN_FIELDS}
    result.update({field: 0 for field in INTEGER_FIELDS})
    assert set(result) == RECORD_FIELDS
    return result


def _compile_polynomials(
    compiled: Mapping[str, Any],
) -> tuple[tuple[sp.Symbol, ...], tuple[sp.Poly, ...], tuple[sp.Poly, ...]]:
    names = compiled.get("cover_variable_names")
    equations = compiled.get("equations")
    predicates = compiled.get("predicates")
    if (
        not isinstance(names, list)
        or not names
        or not isinstance(equations, list)
        or not equations
        or not isinstance(predicates, list)
    ):
        raise DegreeOneCensusError("compiled QQ cover is malformed")
    symbols = tuple(sp.Symbol(str(name)) for name in names)
    local_names = {symbol.name: symbol for symbol in symbols}
    try:
        equalities = tuple(
            sp.Poly(sp.sympify(text, locals=local_names), *symbols, domain=sp.QQ)
            for text in equations
        )
        ordered = tuple(
            sp.Poly(
                sp.sympify(item["expression"], locals=local_names),
                *symbols,
                domain=sp.QQ,
            )
            for item in predicates
        )
    except (KeyError, sp.PolynomialError, sp.CoercionFailed, TypeError, ValueError) as error:
        raise DegreeOneCensusError("compiled cover is not QQ polynomial") from error
    if any(polynomial.is_zero for polynomial in equalities):
        raise DegreeOneCensusError("compiled equality list contains zero")
    if any(
        not isinstance(item, Mapping) or item.get("relation") not in {"gt", "ge", "ne"}
        for item in predicates
    ):
        raise DegreeOneCensusError("compiled predicate ledger is malformed")
    return symbols, equalities, ordered


def _compile_exact_answer(
    source_compiler: Any,
    document: Mapping[str, Any],
    compiled: Mapping[str, Any],
    symbols: Sequence[sp.Symbol],
) -> sp.Poly:
    answer_text = document.get("answer")
    if not isinstance(answer_text, (str, int, float)) or isinstance(answer_text, bool):
        raise DegreeOneCensusError("raw answer AST is malformed")
    semantic = source_compiler.SEMANTIC.Compiler(dict(document))
    semantic_result = semantic.compile()
    if (
        semantic_result.unsupported
        or semantic_result.variables != compiled.get("cover_variable_names")
        or semantic_result.reconstruction
        or semantic_result.replay_obligations != compiled.get("replay_obligations")
    ):
        raise DegreeOneCensusError("semantic target compiler disagrees with cover")
    before = (
        len(semantic.unknowns),
        len(semantic.equations),
        len(semantic.predicates),
        len(semantic.replay),
    )
    try:
        value = semantic.eval(
            ast.parse(str(answer_text), mode="eval").body,
            "raw-answer-census",
        )
    except Exception as error:
        raise DegreeOneCensusError("raw answer AST is not exactly algebraic") from error
    after = (
        len(semantic.unknowns),
        len(semantic.equations),
        len(semantic.predicates),
        len(semantic.replay),
    )
    if before != after or not isinstance(value, (sp.Basic, int, float)):
        raise DegreeOneCensusError("raw answer requires an enlarged cover")
    expression = sp.cancel(sp.together(sp.sympify(value)))
    _numerator, denominator = sp.fraction(expression)
    if denominator.free_symbols:
        raise DegreeOneCensusError("raw answer is rational rather than polynomial")
    try:
        return sp.Poly(expression, *symbols, domain=sp.QQ)
    except (sp.PolynomialError, sp.CoercionFailed, TypeError, ValueError) as error:
        raise DegreeOneCensusError("raw answer is not an exact QQ polynomial") from error


def _coefficient_bits(polynomials: Sequence[sp.Poly], relation: Sequence[int]) -> int:
    values = [abs(int(value)).bit_length() for value in relation]
    for polynomial in polynomials:
        for coefficient in polynomial.coeffs():
            rational = sp.Rational(coefficient)
            values.extend(
                (abs(int(rational.p)).bit_length(), abs(int(rational.q)).bit_length())
            )
    return max(values, default=0)


def _standard_monomial_count(
    basis: Sequence[sp.Poly], variable_count: int, cap: int
) -> int:
    leading = [tuple(map(int, polynomial.monoms()[0])) for polynomial in basis]

    def divisible(monomial: tuple[int, ...]) -> bool:
        return any(
            all(left <= right for left, right in zip(generator, monomial, strict=True))
            for generator in leading
        )

    origin = (0,) * variable_count
    if divisible(origin):
        return 0
    seen = {origin}
    queue = [origin]
    while queue:
        current = queue.pop(0)
        for axis in range(variable_count):
            candidate = list(current)
            candidate[axis] += 1
            item = tuple(candidate)
            if item in seen or divisible(item):
                continue
            seen.add(item)
            queue.append(item)
            if len(seen) > cap:
                raise DegreeOneCensusError("quotient dimension exceeds frozen cap")
    return len(seen)


def _feature(
    request: Mapping[str, Any], source_root: Path, source_compiler: Any
) -> dict[str, bool | int]:
    feature = _empty_feature()
    source_path = _bounded_source_path(request["source_path"], source_root)
    endpoint = _endpoint(request["endpoint"])
    relation = _degree_one_relation(request["candidate_relation_high_to_low"])
    feature["global_upper_proof_producer_available"] = True
    feature["global_upper_degree"] = 1
    feature["target_root_count"] = 1
    feature["max_target_factor_degree"] = 1

    source_bytes = source_path.read_bytes()
    document = json.loads(source_bytes)
    if (
        not isinstance(document, dict)
        or "id" in document
        or FORBIDDEN_SOURCE_KEYS & set(document)
    ):
        raise DegreeOneCensusError("source is not an anonymous problem projection")
    compiled, _msolve_input = source_compiler.compile_source_document(
        document, source_bytes=source_bytes
    )
    if not (
        compiled.get("status") == "ELIGIBLE_MSOLVE_DIMENSION_PROBE"
        and compiled.get("truth_used") is False
        and compiled.get("known_target_count_used") is False
        and compiled.get("case_identity_routing") is False
        and compiled.get("canonical_validation_required") is True
        and compiled.get("dimension_status") == "MUST_BE_CLASSIFIED_BY_MSOLVE"
        and compiled.get("source_variable_names")
        == document.get("variables", {}).get("names")
        and set(compiled.get("source_variable_names", ())).issubset(
            compiled.get("cover_variable_names", ())
        )
        and len(endpoint) == len(compiled.get("source_variable_names", ()))
    ):
        raise DegreeOneCensusError("source compiler rejected the exact QQ cover")
    feature["complete_semantic_cover"] = True
    feature["source_variable_count"] = len(compiled["source_variable_names"])
    feature["cover_variable_count"] = len(compiled["cover_variable_names"])
    feature["equation_count"] = int(compiled["nonzero_equation_count"])
    feature["predicate_count"] = len(compiled["predicates"])

    symbols, equalities, predicates = _compile_polynomials(compiled)
    feature["qq_coefficients"] = True
    feature["ordered_field_sign_available"] = True
    replay = compiled.get("replay_obligations")
    feature["complete_predicate_ledger"] = isinstance(replay, list) and not replay
    feature["reversible_semantic_cover"] = bool(
        feature["complete_predicate_ledger"]
        and not compiled.get("branch_replay_obligation_count")
    )

    answer = _compile_exact_answer(
        source_compiler, document, compiled, symbols
    )
    feature["exact_raw_target_ast"] = True
    all_polynomials = (*equalities, *predicates, answer)
    feature["max_total_degree"] = max(
        (int(polynomial.total_degree()) for polynomial in all_polynomials),
        default=0,
    )
    feature["total_term_count"] = sum(
        len(polynomial.terms()) for polynomial in all_polynomials
    )
    feature["max_coefficient_bits"] = _coefficient_bits(all_polynomials, relation)

    # Avoid spending a Groebner attempt on records that the frozen consumer
    # will reject by static cost caps anyway.
    if any(int(feature[field]) > cap for field, cap in CAPS.items() if field in feature):
        return feature
    basis = sp.groebner(
        [polynomial.as_expr() for polynomial in equalities],
        *symbols,
        order="lex",
        domain=sp.QQ,
    )
    target_relation = sp.expand(relation[0] * answer.as_expr() + relation[1])
    remainder = basis.reduce(target_relation)[1]
    feature["global_upper_identity_provable"] = bool(
        sp.Poly(remainder, *symbols, domain=sp.QQ).is_zero
    )
    if basis.is_zero_dimensional:
        quotient_dimension = _standard_monomial_count(
            tuple(sp.Poly(item, *symbols, domain=sp.QQ) for item in basis.polys),
            len(symbols),
            CAPS["max_specialized_quotient_dimension"],
        )
        feature["max_specialized_quotient_dimension"] = quotient_dimension
        feature["all_specialized_fibres_finite"] = quotient_dimension > 0
    return feature


def build_panel(
    requests: object, source_root: Path, source_compiler: Any
) -> dict[str, Any]:
    if not isinstance(requests, list) or len(requests) > MAX_REQUESTS:
        raise DegreeOneCensusError("request panel is not a bounded array")
    validated = [_validated_request(value) for value in requests]
    features: list[dict[str, bool | int]] = []
    for request in validated:
        try:
            with _record_deadline():
                features.append(_feature(request, source_root, source_compiler))
        except Exception:
            features.append(_empty_feature())
    return {"schema_version": SCHEMA, "records": features}


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
    parser.add_argument("--source-root", type=Path, default=PANEL_SOURCE_ROOT)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-cpu", type=int, default=14)
    arguments = parser.parse_args()
    if os.sched_getaffinity(0) != {arguments.expected_cpu}:
        raise SystemExit("degree-one census must be pinned to exactly the expected CPU")
    if arguments.requests.stat().st_size > MAX_REQUEST_BYTES:
        raise SystemExit("request panel exceeds frozen byte cap")
    payload = arguments.requests.read_bytes()
    if hashlib.sha256(payload).hexdigest() != arguments.requests_sha256.lower():
        raise SystemExit("request panel SHA-256 mismatch")
    try:
        requests = json.loads(payload)
        source_root = arguments.source_root.resolve()
        source_compiler = _load_source_compiler()
        result = summarize(build_panel(requests, source_root, source_compiler))
        _write(arguments.output, result)
    except (DegreeOneCensusError, OSError, json.JSONDecodeError, RuntimeError):
        print(json.dumps({"status": "FAIL_CLOSED"}))
        return 2
    print(json.dumps({"status": "COUNTS_WRITTEN", "gate_pass": result["gate"]["pass"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
