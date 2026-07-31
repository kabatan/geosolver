#!/usr/bin/env python3.12
"""Aggregate-only msolve exact-witness applicability census.

The input panel is anonymous but contains source paths, Float64 endpoints, and
degree-one ordinary proposals.  Individual paths, source hashes, targets,
signatures, and records never cross the output boundary.  This worker compiles
and classifies only; it never executes msolve or reads an outcome.
"""

from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

from mpmath import mp
import sympy as sp


RUNTIME_ROOT = Path("/home/kabatan/work/solver-experiment-runtime/solver")
PANEL_ROOT = Path(
    "/home/kabatan/work/solver-experiment-results/partial-ideal-root-readiness-v1"
).resolve()
PANEL_SOURCE_ROOT = (PANEL_ROOT / "degree1-inputs").resolve()
SOURCE_COMPILER_PATH = (
    RUNTIME_ROOT
    / "research/experiments/EXP-REAL61-004/msolve_all_real_proposal/source_compile.py"
)
LEGACY_RUNTIME_PATH = (
    RUNTIME_ROOT / "research/experiments/EXP-REAL61-001/legacy61_runtime.py"
)
SOURCE_COMPILER_SHA256 = "24d6cee020256043f6ad4657ffa84a8b4e9188ab9ff18bf3e9339672a3229349"
SEMANTIC_COMPILER_SHA256 = "f127f7f1e2f93161e1353f07222e93ffacfa1c2dbd4e68e5b1fd23a8a3b10318"
LEGACY_RUNTIME_SHA256 = "3261a6289f4a43681e698937c158d4a4f1740e54b70b88559c399e3b6395ec2b"
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
    }
)

# Frozen before the panel census.  These are deliberately small-route caps,
# not estimates derived from the 85 records.
MAX_COVER_VARIABLES = 12
MAX_NONZERO_EQUATIONS = 24
MAX_PREDICATES = 64
MAX_POLYNOMIAL_TOTAL_DEGREE = 4
MAX_TOTAL_MONOMIALS = 400
MAX_COEFFICIENT_BITS = 256
MAX_EXPRESSION_OPERATIONS = 5_000
MAX_MSOLVE_INPUT_BYTES = 64 * 1024
MAX_MINIMUM_MATCHING_DEGREE_PRODUCT = 4_096
MAX_ENDPOINT_DIMENSION = 12
TARGET_BOX_RELATIVE_RADIUS = mp.mpf(2) ** -20
TARGET_BOX_ABSOLUTE_RADIUS = mp.mpf(2) ** -40


class ApplicabilityError(ValueError):
    """One record failed closed before the next cumulative stage."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"cannot load frozen dependency: {name}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _load_dependencies():
    semantic_path = (
        RUNTIME_ROOT
        / "research/experiments/EXP-REAL61-002/algebraic_lane/compiler.py"
    )
    expected = {
        SOURCE_COMPILER_PATH: SOURCE_COMPILER_SHA256,
        semantic_path: SEMANTIC_COMPILER_SHA256,
        LEGACY_RUNTIME_PATH: LEGACY_RUNTIME_SHA256,
    }
    for path, digest in expected.items():
        if _sha256(path) != digest:
            raise RuntimeError("frozen applicability dependency changed")
    source_compiler = _load(
        "msolve_bigint_reopen_frozen_source_compiler", SOURCE_COMPILER_PATH
    )
    if str(LEGACY_RUNTIME_PATH.parent) not in sys.path:
        sys.path.insert(0, str(LEGACY_RUNTIME_PATH.parent))
    legacy = _load("msolve_bigint_reopen_frozen_legacy_runtime", LEGACY_RUNTIME_PATH)
    load_problem_bundle, build_ir_evaluator, _infer, _penalty = (
        legacy.load_legacy_runtime()
    )
    return source_compiler, load_problem_bundle, build_ir_evaluator


def _bounded_source_path(value: object) -> Path:
    if not isinstance(value, str):
        raise ApplicabilityError("source path is not a string")
    path = Path(value).resolve()
    if path.parent != PANEL_SOURCE_ROOT or path.suffix != ".json" or not path.is_file():
        raise ApplicabilityError("source path is outside the frozen anonymous panel")
    return path


def _endpoint(value: object) -> tuple[float, ...]:
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_ENDPOINT_DIMENSION:
        raise ApplicabilityError("endpoint dimension is outside cap")
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in value):
        raise ApplicabilityError("endpoint contains a non-number")
    endpoint = tuple(float(item) for item in value)
    if any(not math.isfinite(item) for item in endpoint):
        raise ApplicabilityError("endpoint is non-finite")
    return endpoint


def _degree_one_root(value: object) -> tuple[Fraction, tuple[int, int]]:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(not isinstance(item, int) or isinstance(item, bool) for item in value)
    ):
        raise ApplicabilityError("proposal is not an integer degree-one relation")
    leading, constant = int(value[0]), int(value[1])
    if leading <= 0 or math.gcd(leading, constant) != 1:
        raise ApplicabilityError("proposal is not primitive leading-positive degree one")
    return Fraction(-constant, leading), (leading, constant)


def _compile_polynomials(
    compiled: Mapping[str, Any],
) -> tuple[tuple[sp.Symbol, ...], tuple[sp.Poly, ...]]:
    names = compiled.get("cover_variable_names")
    equations = compiled.get("equations")
    if (
        not isinstance(names, list)
        or not names
        or not isinstance(equations, list)
        or not equations
    ):
        raise ApplicabilityError("compiled cover shape is malformed")
    symbols = tuple(sp.Symbol(str(name)) for name in names)
    locals_map = {symbol.name: symbol for symbol in symbols}
    try:
        polynomials = tuple(
            sp.Poly(sp.sympify(text, locals=locals_map), *symbols, domain=sp.ZZ)
            for text in equations
        )
    except (sp.PolynomialError, sp.CoercionFailed, TypeError, ValueError) as error:
        raise ApplicabilityError("compiled cover is not ZZ polynomial") from error
    if any(polynomial.is_zero or polynomial.total_degree() < 1 for polynomial in polynomials):
        raise ApplicabilityError("compiled cover contains a zero/constant equation")
    return symbols, polynomials


def _minimum_matching_degree_product(
    symbols: Sequence[sp.Symbol], polynomials: Sequence[sp.Poly]
) -> int | None:
    """Minimum degree product among structural equation-variable matchings."""

    full = (1 << len(symbols)) - 1
    best: dict[int, int] = {0: 1}
    for polynomial in polynomials:
        support = [
            index for index, symbol in enumerate(symbols) if symbol in polynomial.free_symbols
        ]
        degree = int(polynomial.total_degree())
        updated = dict(best)
        for mask, cost in best.items():
            for variable_index in support:
                bit = 1 << variable_index
                if mask & bit:
                    continue
                new_mask = mask | bit
                new_cost = cost * degree
                if new_cost < updated.get(new_mask, new_cost + 1):
                    updated[new_mask] = new_cost
        best = updated
    return best.get(full)


def _answer_is_proposal_compatible(
    document: Mapping[str, Any],
    endpoint: Sequence[float],
    root: Fraction,
    *,
    load_problem_bundle: Any,
    build_ir_evaluator: Any,
) -> bool:
    from geosolver._internal.solver.precision.type_guards.boundary_float_to_mpf import (
        BoundaryOrigin,
        boundary_float_to_mpf,
    )
    from geosolver._internal.solver.precision.type_guards.high_precision_mode import (
        high_precision_mode,
    )

    bundle = load_problem_bundle(dict(document), prefer_fast=False)
    evaluator = build_ir_evaluator(bundle)
    values = [
        boundary_float_to_mpf(value, origin=BoundaryOrigin.SCIPY_OPTIMIZE)
        for value in endpoint
    ]
    with mp.workdps(80), high_precision_mode():
        answer = evaluator.evaluate_answer_hp(
            values, precision=80
        ).answer_hp
        if answer is None or not mp.isfinite(answer):
            return False
        target = mp.mpf(root.numerator) / mp.mpf(root.denominator)
        radius = max(
            TARGET_BOX_ABSOLUTE_RADIUS,
            TARGET_BOX_RELATIVE_RADIUS * max(mp.mpf(1), abs(answer), abs(target)),
        )
        return bool(abs(answer - target) <= radius)


def _cost_caps_pass(
    compiled: Mapping[str, Any],
    polynomials: Sequence[sp.Poly],
    relation: tuple[int, int],
    matching_product: int,
) -> bool:
    variable_count = int(compiled.get("cover_variable_count", -1))
    equation_count = int(compiled.get("nonzero_equation_count", -1))
    predicate_count = len(compiled.get("predicates", []))
    maximum_degree = max(int(polynomial.total_degree()) for polynomial in polynomials)
    total_monomials = sum(len(polynomial.terms()) for polynomial in polynomials)
    maximum_coefficient_bits = max(
        [abs(int(coefficient)).bit_length() for polynomial in polynomials for coefficient in polynomial.coeffs()]
        + [abs(value).bit_length() for value in relation]
    )
    return bool(
        variable_count <= MAX_COVER_VARIABLES
        and equation_count <= MAX_NONZERO_EQUATIONS
        and predicate_count <= MAX_PREDICATES
        and maximum_degree <= MAX_POLYNOMIAL_TOTAL_DEGREE
        and total_monomials <= MAX_TOTAL_MONOMIALS
        and maximum_coefficient_bits <= MAX_COEFFICIENT_BITS
        and int(compiled.get("expression_operations", -1)) <= MAX_EXPRESSION_OPERATIONS
        and int(compiled.get("msolve_input_bytes", -1)) <= MAX_MSOLVE_INPUT_BYTES
        and matching_product <= MAX_MINIMUM_MATCHING_DEGREE_PRODUCT
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--requests-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-cpu", type=int, default=14)
    arguments = parser.parse_args()
    if os.sched_getaffinity(0) != {arguments.expected_cpu}:
        raise SystemExit("applicability census must be pinned to exactly the expected CPU")

    panel_bytes = arguments.requests.read_bytes()
    panel_sha256 = hashlib.sha256(panel_bytes).hexdigest()
    if panel_sha256 != arguments.requests_sha256.lower():
        raise SystemExit("request panel SHA-256 mismatch")
    requests = json.loads(panel_bytes)
    if not isinstance(requests, list):
        raise SystemExit("request panel must be an array")
    source_compiler, load_problem_bundle, build_ir_evaluator = _load_dependencies()

    stage_counts = {
        "request_contract_ready": 0,
        "reversible_qq_exact_cover": 0,
        "equations_ge_variables": 0,
        "endpoint_target_proposal_compatible": 0,
        "dimension0_selected_factor_possible": 0,
        "fixed_degree_cost_caps": 0,
        "eligible": 0,
    }
    eligible_source_hashes: set[str] = set()
    signatures: set[str] = set()

    for request in requests:
        try:
            if (
                not isinstance(request, Mapping)
                or set(request) != REQUEST_KEYS
                or FORBIDDEN_REQUEST_KEYS & set(request)
            ):
                raise ApplicabilityError("request contract rejected")
            source_path = _bounded_source_path(request["source_path"])
            source_bytes = source_path.read_bytes()
            document = json.loads(source_bytes)
            if not isinstance(document, dict) or "id" in document:
                raise ApplicabilityError("anonymous source projection rejected")
            endpoint = _endpoint(request["endpoint"])
            root, relation = _degree_one_root(
                request["candidate_relation_high_to_low"]
            )
            stage_counts["request_contract_ready"] += 1

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
                and set(compiled.get("source_variable_names", [])).issubset(
                    compiled.get("cover_variable_names", [])
                )
                and len(endpoint) == len(compiled.get("source_variable_names", []))
            ):
                raise ApplicabilityError("reversible QQ cover rejected")
            symbols, polynomials = _compile_polynomials(compiled)
            stage_counts["reversible_qq_exact_cover"] += 1

            if len(polynomials) < len(symbols):
                raise ApplicabilityError("height lower bound excludes dimension zero")
            stage_counts["equations_ge_variables"] += 1

            if not _answer_is_proposal_compatible(
                document,
                endpoint,
                root,
                load_problem_bundle=load_problem_bundle,
                build_ir_evaluator=build_ir_evaluator,
            ):
                raise ApplicabilityError("endpoint target box misses proposal")
            stage_counts["endpoint_target_proposal_compatible"] += 1

            matching_product = _minimum_matching_degree_product(symbols, polynomials)
            if matching_product is None:
                raise ApplicabilityError("no structural square subsystem")
            stage_counts["dimension0_selected_factor_possible"] += 1

            if not _cost_caps_pass(compiled, polynomials, relation, matching_product):
                raise ApplicabilityError("fixed cost cap exceeded")
            stage_counts["fixed_degree_cost_caps"] += 1
            stage_counts["eligible"] += 1
            eligible_source_hashes.add(hashlib.sha256(source_bytes).hexdigest())
            signatures.add(
                _canonical_sha256(
                    {
                        "cover_shape": compiled.get("cover_shape"),
                        "variable_count": len(symbols),
                        "equation_count": len(polynomials),
                        "predicate_count": len(compiled.get("predicates", [])),
                        "maximum_degree": max(
                            int(polynomial.total_degree()) for polynomial in polynomials
                        ),
                        "total_monomial_bucket": sum(
                            len(polynomial.terms()) for polynomial in polynomials
                        )
                        // 16,
                        "minimum_matching_degree_product": matching_product,
                        "endpoint_dimension": len(endpoint),
                    }
                )
            )
        except Exception:
            continue

    gate_pass = len(eligible_source_hashes) >= 4 and len(signatures) >= 2
    aggregate = {
        "schema_version": "geotarget.msolve-exact-witness-static-applicability/v1",
        "candidate_id": "MSOLVE_EXACT_WITNESS_BIGINT_TRANSPORT_REOPEN_V1",
        "request_panel_sha256": panel_sha256,
        "request_count": len(requests),
        "stage_counts_cumulative": stage_counts,
        "eligible_anonymous_hash_count": len(eligible_source_hashes),
        "anonymous_signature_count": len(signatures),
        "gate_minimum_eligible_hashes": 4,
        "gate_minimum_signatures": 2,
        "applicability_gate_pass": gate_pass,
        "fixed_caps": {
            "cover_variables": MAX_COVER_VARIABLES,
            "nonzero_equations": MAX_NONZERO_EQUATIONS,
            "predicates": MAX_PREDICATES,
            "polynomial_total_degree": MAX_POLYNOMIAL_TOTAL_DEGREE,
            "total_monomials": MAX_TOTAL_MONOMIALS,
            "coefficient_bits": MAX_COEFFICIENT_BITS,
            "expression_operations": MAX_EXPRESSION_OPERATIONS,
            "msolve_input_bytes": MAX_MSOLVE_INPUT_BYTES,
            "minimum_matching_degree_product": MAX_MINIMUM_MATCHING_DEGREE_PRODUCT,
            "endpoint_dimension": MAX_ENDPOINT_DIMENSION,
            "target_box_relative_radius": "2^-20",
            "target_box_absolute_radius": "2^-40"
        },
        "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "workers_enabled": False,
        "msolve_runs": 0,
        "authority_pass": False,
        "target_release": False,
        "completeness_claim": "NOT_MADE",
        "truth_used": False,
        "formal_scorer_used": False,
        "full98_used": False,
        "individual_paths_emitted": False,
        "individual_hashes_emitted": False,
        "individual_targets_emitted": False,
        "individual_records_emitted": False,
        "structural_signatures_emitted": False
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(aggregate, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(aggregate, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
