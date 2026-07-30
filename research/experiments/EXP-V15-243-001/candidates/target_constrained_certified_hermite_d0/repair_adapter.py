"""Repair A: pinned semantic-lift -> typed Hermite witness adapter.

The source compiler is loaded read-only from the frozen experiment archive and
digest checked.  This module adds no geometry primitives.  It only maps the
compiler's already-typed polynomial artifact and an ordinary target descriptor
to the D0 certificate contract.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Mapping, Sequence

import sympy as sp

from candidate import CertificationFailure, certify, parse_problem
from verifier import VerificationFailure, verify


ARCHIVE_ROOT = Path(
    os.environ.get("GEOTARGET_ARCHIVE_RUNTIME_ROOT", "/home/kabatan/work/solver-experiment-runtime/solver")
).resolve()
SEMANTIC_LIFT = (
    ARCHIVE_ROOT
    / "research/experiments/EXP-V15-243-001/candidates/semantic_algebraic_lift/semantic_lift.py"
)
EXPECTED_SEMANTIC_LIFT_SHA256 = "4ab15c79605156b25d7aa3fbbf7b37a02be89a8a42bb642a09a4addcecb99836"
ALGEBRAIC_COMPILER = (
    ARCHIVE_ROOT / "research/experiments/EXP-REAL61-002/algebraic_lane/compiler.py"
)
EXPECTED_ALGEBRAIC_COMPILER_SHA256 = "f127f7f1e2f93161e1353f07222e93ffacfa1c2dbd4e68e5b1fd23a8a3b10318"

MAX_ADAPTER_TERMS_PER_POLYNOMIAL = 256
MAX_ADAPTER_TOTAL_TERMS = 1_024
SUPPORTED_RELATIONS = frozenset({"eq", "ne", "gt", "ge", "lt", "le"})


class AdapterFailure(ValueError):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _fail(reason: str) -> None:
    raise AdapterFailure(reason)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_sha(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_pinned_semantic_lift(*, fresh_name: str = "geotarget_repair_a_semantic_lift"):
    if not SEMANTIC_LIFT.is_file() or _sha256(SEMANTIC_LIFT) != EXPECTED_SEMANTIC_LIFT_SHA256:
        _fail("semantic-lift-digest-mismatch")
    specification = importlib.util.spec_from_file_location(fresh_name, SEMANTIC_LIFT)
    if specification is None or specification.loader is None:
        _fail("semantic-lift-load-failed")
    module = importlib.util.module_from_spec(specification)
    sys.modules[fresh_name] = module
    specification.loader.exec_module(module)
    return module


def load_pinned_algebraic_compiler(*, fresh_name: str = "geotarget_repair_a_algebraic_compiler"):
    if (
        not ALGEBRAIC_COMPILER.is_file()
        or _sha256(ALGEBRAIC_COMPILER) != EXPECTED_ALGEBRAIC_COMPILER_SHA256
    ):
        _fail("algebraic-compiler-digest-mismatch")
    specification = importlib.util.spec_from_file_location(fresh_name, ALGEBRAIC_COMPILER)
    if specification is None or specification.loader is None:
        _fail("algebraic-compiler-load-failed")
    module = importlib.util.module_from_spec(specification)
    sys.modules[fresh_name] = module
    specification.loader.exec_module(module)
    return module


def _parse_descriptor(descriptor: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(descriptor, Mapping):
        _fail("descriptor-not-object")
    coefficients = descriptor.get("minimal_polynomial_high_to_low")
    root_index = descriptor.get("selected_real_root_index")
    isolator = descriptor.get("isolating_interval")
    if (
        not isinstance(coefficients, list)
        or not (2 <= len(coefficients) <= 11)
        or any(not isinstance(value, int) or isinstance(value, bool) for value in coefficients)
        or coefficients[0] == 0
        or not isinstance(root_index, int)
        or isinstance(root_index, bool)
        or root_index < 0
        or not isinstance(isolator, Mapping)
        or descriptor.get("proposal_relation_low_to_high") != list(reversed(coefficients))
        or descriptor.get("confirmation_relation_low_to_high") != list(reversed(coefficients))
        or not isinstance(descriptor.get("target_768"), str)
        or not isinstance(descriptor.get("target_1024"), str)
    ):
        _fail("malformed-target-descriptor")
    left_raw, right_raw = isolator.get("left"), isolator.get("right")
    if not isinstance(left_raw, str) or not isinstance(right_raw, str):
        _fail("malformed-target-isolator")
    if isolator.get("multiplicity") != 1 or isolator.get("real_root_index") != root_index:
        _fail("descriptor-root-metadata-mismatch")
    try:
        left, right = sp.Rational(left_raw), sp.Rational(right_raw)
    except (TypeError, ValueError, ZeroDivisionError):
        _fail("nonrational-target-isolator")
    if not left < right:
        _fail("target-isolator-not-open")
    variable = sp.Symbol("__descriptor_target")
    expression = sum(
        coefficient * variable ** (len(coefficients) - index - 1)
        for index, coefficient in enumerate(coefficients)
    )
    polynomial = sp.Poly(expression, variable, domain=sp.QQ)
    if sp.gcd(polynomial, polynomial.diff()).degree() != 0:
        _fail("descriptor-polynomial-not-square-free")
    if polynomial.eval(left) == 0 or polynomial.eval(right) == 0:
        _fail("target-isolator-endpoint-root")
    if int(polynomial.count_roots(left, right)) != 1:
        _fail("target-isolator-not-single-root")
    if int(polynomial.count_roots(-sp.oo, left)) != root_index:
        _fail("target-root-ordinal-mismatch")
    return {
        "coefficients": tuple(coefficients),
        "degree": polynomial.degree(),
        "left": left,
        "right": right,
        "root_index": root_index,
        "identity": [list(coefficients), root_index],
    }


def _qq_expr(text: str, symbols: Sequence[sp.Symbol], locals_: Mapping[str, sp.Symbol], label: str) -> sp.Expr:
    try:
        expression = sp.sympify(text, locals=dict(locals_))
    except (sp.SympifyError, TypeError, ValueError):
        _fail(f"invalid-{label}")
    if expression.atoms(sp.Float) or not expression.free_symbols.issubset(set(symbols)):
        _fail(f"nonexact-{label}")
    try:
        return sp.Poly(sp.expand(expression), *symbols, domain=sp.QQ).as_expr()
    except (sp.PolynomialError, sp.CoercionFailed):
        _fail(f"non-qq-{label}")


def _artifact_gate(algebraic: Any, semantic: Any) -> None:
    if semantic.schema_version != "geotarget.semantic-algebraic-lift/v1":
        _fail("semantic-lift-schema-mismatch")
    if semantic.phase_groups:
        _fail("phase-sheet-replay-not-supported")
    if semantic.selector_ledger:
        _fail("boolean-selector-replay-not-supported")
    if semantic.proof_ready is not True or semantic.cover_only_reasons:
        _fail("semantic-lift-not-proof-ready")
    # Repair A does not invent a correspondence between the two compilers'
    # auxiliary names.  Definedness-bearing sources therefore fail closed.
    if semantic.definedness_ledger:
        _fail("definedness-replay-not-supported-by-thin-seam")
    replay_kinds = [item.get("kind") for item in semantic.replay_ledger]
    if replay_kinds != ["raw-source-target-link"]:
        _fail("unmapped-replay-obligation")
    raw_link = semantic.replay_ledger[0]
    if (
        raw_link.get("source") != "target"
        or raw_link.get("target_variable") != semantic.target_variable
        or not isinstance(raw_link.get("expression"), str)
    ):
        _fail("raw-target-ledger-mismatch")
    if any(predicate.get("relation") not in SUPPORTED_RELATIONS for predicate in algebraic.predicates):
        _fail("unsupported-typed-predicate")
    if (
        algebraic.classification != "EXACT_SEMIALGEBRAIC"
        or algebraic.unsupported
        or algebraic.reconstruction
        or any(item.get("kind") != "canonical-guard" for item in algebraic.replay_obligations)
    ):
        _fail("algebraic-cover-replay-not-thin-authority")


def _polynomial_key(expression: sp.Expr, symbols: Sequence[sp.Symbol]) -> tuple[tuple[tuple[int, ...], str], ...]:
    polynomial = sp.Poly(sp.expand(expression), *symbols, domain=sp.QQ)
    return tuple((tuple(monomial), str(coefficient)) for monomial, coefficient in polynomial.terms())


def build_problem(
    algebraic: Any,
    semantic: Any,
    descriptor: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Map every typed predicate; return D0 problem plus a losslessness ledger."""

    _artifact_gate(algebraic, semantic)
    target_descriptor = _parse_descriptor(descriptor)
    source_names = tuple(algebraic.variables)
    if len(set(source_names)) != len(source_names) or semantic.target_variable in source_names:
        _fail("invalid-lifted-variable-ledger")
    original_names = (*source_names, semantic.target_variable)
    original_symbols = tuple(sp.Symbol(name) for name in original_names)
    source_symbols = original_symbols[:-1]
    original_locals = dict(zip(original_names, original_symbols, strict=True))
    target_symbol = original_locals[semantic.target_variable]
    target_expression = _qq_expr(
        semantic.target_expression, original_symbols, original_locals, "raw-target-expression"
    )
    source_equations = [
        _qq_expr(text, original_symbols, original_locals, f"algebraic-equation-{index}")
        for index, text in enumerate(algebraic.equations)
    ]
    semantic_names = tuple(semantic.variables)
    semantic_symbols = tuple(sp.Symbol(name) for name in semantic_names)
    semantic_locals = dict(zip(semantic_names, semantic_symbols, strict=True))
    semantic_target = semantic_locals[semantic.target_variable]
    semantic_target_expression = _qq_expr(
        semantic.target_expression, semantic_symbols, semantic_locals, "semantic-target-expression"
    )
    semantic_equations = [
        _qq_expr(text, semantic_symbols, semantic_locals, f"semantic-equation-{index}")
        for index, text in enumerate(semantic.equations)
    ]
    semantic_link = sp.expand(semantic_target - semantic_target_expression)
    semantic_source_equations = [
        equation for equation in semantic_equations if sp.expand(equation - semantic_link) != 0
    ]
    if len(semantic_equations) - len(semantic_source_equations) != 1:
        _fail("raw-target-equation-not-unique")
    if set(source_names) != set(name for name in semantic_names if name != semantic.target_variable):
        _fail("compiler-variable-ring-mismatch")
    semantic_source_symbols_in_order = tuple(semantic_locals[name] for name in source_names)
    algebraic_keys = sorted(_polynomial_key(item, source_symbols) for item in source_equations)
    semantic_keys = sorted(_polynomial_key(item, semantic_source_symbols_in_order) for item in semantic_source_equations)
    if algebraic_keys != semantic_keys:
        _fail("compiler-equation-ledger-mismatch")

    algebraic_predicate_keys = []
    for index, predicate in enumerate(algebraic.predicates):
        expression = _qq_expr(
            predicate["expression"], original_symbols, original_locals, f"algebraic-predicate-{index}"
        )
        algebraic_predicate_keys.append((predicate["relation"], _polynomial_key(expression, source_symbols)))
    semantic_predicate_keys = []
    for index, predicate in enumerate(semantic.predicates):
        expression = _qq_expr(
            predicate["expression"], semantic_symbols, semantic_locals, f"semantic-predicate-{index}"
        )
        semantic_predicate_keys.append(
            (predicate["relation"], _polynomial_key(expression, semantic_source_symbols_in_order))
        )
    if sorted(algebraic_predicate_keys) != sorted(semantic_predicate_keys):
        _fail("compiler-predicate-ledger-mismatch")

    names = list(original_names)
    transformed_equations = list(source_equations)
    strict_guards: list[sp.Expr] = []
    predicate_mapping: list[dict[str, Any]] = []
    for index, predicate in enumerate(algebraic.predicates):
        relation = predicate["relation"]
        expression = _qq_expr(
            predicate["expression"], original_symbols, original_locals, f"predicate-{index}"
        )
        record: dict[str, Any] = {
            "index": index,
            "relation": relation,
            "expression": str(expression),
            "source": predicate["source"],
        }
        if relation == "eq":
            transformed_equations.append(expression)
            record["encoding"] = "equation"
        elif relation == "gt":
            strict_guards.append(expression)
            record["encoding"] = "strict-positive"
        elif relation == "lt":
            strict_guards.append(-expression)
            record["encoding"] = "strict-negative"
        elif relation in {"ge", "le"}:
            name = f"__hermite_predicate_{index}_slack"
            if name in names:
                _fail("adapter-variable-collision")
            names.append(name)
            slack = sp.Symbol(name)
            transformed_equations.append((expression if relation == "ge" else -expression) - slack**2)
            record.update({"encoding": "nonnegative-square-slack", "auxiliary": name})
        elif relation == "ne":
            name = f"__hermite_predicate_{index}_inverse"
            if name in names:
                _fail("adapter-variable-collision")
            names.append(name)
            inverse = sp.Symbol(name)
            transformed_equations.append(expression * inverse - 1)
            record.update({"encoding": "nonzero-inverse", "auxiliary": name})
        else:  # guarded by _artifact_gate; retained as fail-closed defense.
            _fail("unsupported-typed-predicate")
        predicate_mapping.append(record)

    all_symbols = tuple(sp.Symbol(name) for name in names)
    target_polynomial = sum(
        coefficient * target_symbol ** (len(target_descriptor["coefficients"]) - index - 1)
        for index, coefficient in enumerate(target_descriptor["coefficients"])
    )
    # Reparse every polynomial consumed by D0, including the raw target link,
    # target proposal, and open interval legs.  This is a measured child cap,
    # not the frontend's much looser syntax-only proxy.
    capped_expressions = (
        *transformed_equations,
        target_symbol - target_expression,
        target_polynomial,
        *strict_guards,
        target_symbol - target_descriptor["left"],
        target_descriptor["right"] - target_symbol,
    )
    total_terms = 0
    maximum_terms = 0
    maximum_degree = 0
    for index, expression in enumerate(capped_expressions):
        try:
            polynomial = sp.Poly(expression, *all_symbols, domain=sp.QQ)
        except (sp.PolynomialError, sp.CoercionFailed):
            _fail(f"augmented-polynomial-not-qq-{index}")
        terms = len(polynomial.terms())
        total_terms += terms
        maximum_terms = max(maximum_terms, terms)
        maximum_degree = max(maximum_degree, polynomial.total_degree())
    if maximum_terms > MAX_ADAPTER_TERMS_PER_POLYNOMIAL or total_terms > MAX_ADAPTER_TOTAL_TERMS:
        _fail("adapter-polynomial-term-cap")

    problem = {
        "variables": names,
        "target_variable": semantic.target_variable,
        "equations": [str(sp.expand(expression)) for expression in transformed_equations],
        "target": str(target_expression),
        "polynomial": str(sp.expand(target_polynomial)),
        "interval": [str(target_descriptor["left"]), str(target_descriptor["right"])],
        "guards": [str(sp.expand(expression)) for expression in strict_guards],
    }
    # Exercise the D0 parser before emitting a binding.
    parsed = parse_problem(problem)
    algebraic_data = algebraic.to_data()
    semantic_data = semantic.to_data()
    binding = {
        "semantic_lift_sha256": EXPECTED_SEMANTIC_LIFT_SHA256,
        "algebraic_compiler_sha256": EXPECTED_ALGEBRAIC_COMPILER_SHA256,
        "semantic_source_sha256": semantic.semantic_source_sha256,
        "semantic_artifact_sha256": _canonical_sha(semantic_data),
        "algebraic_artifact_sha256": _canonical_sha(algebraic_data),
        "target_descriptor_identity": target_descriptor["identity"],
        "target_degree": target_descriptor["degree"],
        "predicate_count": len(algebraic.predicates),
        "predicate_mapping": predicate_mapping,
        "definedness_count": len(semantic.definedness_ledger),
        "definedness_ledger_sha256": _canonical_sha(list(semantic.definedness_ledger)),
        "raw_target_link_sha256": _canonical_sha(semantic.replay_ledger[0]),
        "d0_problem_sha256": parsed.problem_sha256,
        "actual_terms": {
            "maximum_per_polynomial": maximum_terms,
            "total_all_d0_polynomials": total_terms,
            "polynomial_count": len(capped_expressions),
            "maximum_total_degree": maximum_degree,
        },
        "caps": {
            "maximum_terms_per_polynomial": MAX_ADAPTER_TERMS_PER_POLYNOMIAL,
            "maximum_total_terms": MAX_ADAPTER_TOTAL_TERMS,
        },
        "phase_sheet_obligations_dropped": 0,
        "selector_obligations_dropped": 0,
        "typed_predicates_dropped": 0,
        "definedness_entries_dropped": 0,
    }
    return problem, binding


def _endpoint_seed(endpoint: Sequence[Any]) -> dict[str, Any]:
    try:
        payload = json.dumps(list(endpoint), separators=(",", ":"), allow_nan=False).encode("ascii")
    except (TypeError, ValueError, UnicodeEncodeError):
        _fail("invalid-endpoint-seed")
    return {
        "endpoint_sha256": hashlib.sha256(payload).hexdigest(),
        "coordinate_count": len(endpoint),
        "used_for_routing": False,
        "used_as_witness_cell_seed_only": True,
    }


def attempt_repair(
    *,
    source: Path,
    source_sha256: str,
    descriptor: Mapping[str, Any],
    endpoint: Sequence[Any],
    deadline_monotonic: float | None = None,
) -> dict[str, Any]:
    """Generated/dry source route. Every failure returns no descriptor."""

    def check_deadline(stage: str) -> None:
        if deadline_monotonic is not None and time.monotonic() >= deadline_monotonic:
            _fail(f"deadline-exceeded:{stage}")

    try:
        check_deadline("entry")
        raw = source.read_bytes()
        if hashlib.sha256(raw).hexdigest() != source_sha256:
            _fail("untouched-source-digest-mismatch")
        document = json.loads(raw)
        if not isinstance(document, Mapping):
            _fail("source-not-object")
        semantic = load_pinned_semantic_lift()
        algebraic_module = load_pinned_algebraic_compiler()
        check_deadline("before-compile")
        semantic_artifact = semantic.compile_document(document)
        algebraic_artifact = algebraic_module.compile_document(document)
        problem, binding = build_problem(algebraic_artifact, semantic_artifact, descriptor)
        check_deadline("before-certificate")
        certificate = certify(problem)
        check_deadline("before-independent-verifier")
        independent = verify(problem, certificate)
        if not independent.get("verified"):
            _fail("independent-d0-verifier-rejected")

        # Import late to keep the direction explicit: certificate, independent
        # verifier, then fresh untouched-source replay.
        from untouched_replay import verify_untouched_replay

        replay = verify_untouched_replay(
            source=source,
            source_sha256=source_sha256,
            descriptor=descriptor,
            expected_binding=binding,
            certificate=certificate,
        )
        if replay.get("verified") is not True:
            _fail("untouched-source-replay-rejected")
        check_deadline("after-untouched-replay")
        return {
            "schema": "geotarget.target-hermite-repair-a/v1",
            "status": "TARGET_AUTHORITY_READY",
            "authority_pass": True,
            "descriptor": dict(descriptor),
            "source_sha256": source_sha256,
            "source_or_problem_modified": False,
            "truth_used": False,
            "case_family_target_or_outcome_routing": False,
            "coordinate_exactification": False,
            "witness_cell_seed": _endpoint_seed(endpoint),
            "binding": binding,
            "certificate": certificate,
            "independent_verification": independent,
            "untouched_source_replay": replay,
            "deadline_contract": {
                "kind": "cooperative-dry-only",
                "hard_child_kill": False,
                "partial_certificate_can_authorize": False,
            },
        }
    except Exception as error:  # noqa: BLE001 - authority boundary must fail closed
        reason = getattr(error, "reason", None)
        if not isinstance(reason, str) or not reason:
            reason = (
                str(error)
                if isinstance(error, (CertificationFailure, VerificationFailure, ValueError))
                and str(error)
                else f"unsupported-exception:{type(error).__name__}"
            )
        return {
            "schema": "geotarget.target-hermite-repair-a/v1",
            "status": "HERMITE_REPAIR_NOT_PROVED",
            "authority_pass": False,
            "descriptor": None,
            "source_sha256": source_sha256,
            "source_or_problem_modified": False,
            "truth_used": False,
            "case_family_target_or_outcome_routing": False,
            "coordinate_exactification": False,
            "failure_reason": reason,
            "partial_certificate_discarded": True,
        }


__all__ = [
    "AdapterFailure",
    "EXPECTED_ALGEBRAIC_COMPILER_SHA256",
    "EXPECTED_SEMANTIC_LIFT_SHA256",
    "SEMANTIC_LIFT",
    "attempt_repair",
    "build_problem",
    "load_pinned_algebraic_compiler",
    "load_pinned_semantic_lift",
]
