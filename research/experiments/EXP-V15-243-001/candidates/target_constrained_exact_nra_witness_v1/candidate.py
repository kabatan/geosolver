"""Exact target-constrained QF_NRA witness microprototype.

This disposable D0 candidate asks whether the untouched polynomial source has
one real witness whose raw target lies in a proposed exact descriptor cell.
The preferred Z3 complete-NRA backend is unavailable in the frozen runtime.
The fallback is complete only for the explicitly admitted subset: a
zero-dimensional QQ polynomial equality variety, plus declared coordinates
that occur nowhere in equations, guards, definedness, or the raw target.

Every backend model is serialized as rational/real-algebraic descriptors and
then reconstructed for a fresh exact replay.  Backend SAT alone is never an
authority.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import signal
import sys
import time
from typing import Mapping, Sequence

import sympy as sp
from sympy.core.relational import (
    Equality,
    GreaterThan,
    LessThan,
    Relational,
    StrictGreaterThan,
    StrictLessThan,
    Unequality,
)


SCHEMA = "geotarget.target-constrained-exact-nra-witness/v1"
BACKEND = "SYMPY_COMPLETE_ZERO_DIMENSIONAL_QQ_WITH_IRRELEVANT_FREE_COORDS"
MAX_VARIABLES = 8
MAX_EQUATIONS = 16
MAX_TOTAL_DEGREE = 12
MAX_TERMS = 256
RUNTIME_ROOT = Path(
    os.environ.get(
        "GEOTARGET_EXPERIMENT_RUNTIME",
        "/home/kabatan/work/solver-experiment-runtime/solver",
    )
).resolve()
SEMANTIC_ROOT = (
    RUNTIME_ROOT
    / "research/experiments/EXP-V15-243-001/candidates/semantic_algebraic_lift"
)
SEMANTIC_LIFT = SEMANTIC_ROOT / "semantic_lift.py"
SEMANTIC_REPLAY = SEMANTIC_ROOT / "exact_replay.py"
EXPECTED_SEMANTIC_SHA256 = {
    SEMANTIC_LIFT: "4ab15c79605156b25d7aa3fbbf7b37a02be89a8a42bb642a09a4addcecb99836",
    SEMANTIC_REPLAY: "8c1c18e4d46ce4910ca630589fda3424198dfcfc2c3537ff39f31d3b9f89d23a",
}


class NotProved(ValueError):
    """The source/proposal is outside the proved subset or has no witness."""


class BackendTimeout(TimeoutError):
    """The bounded exact backend did not finish."""


@dataclass(frozen=True)
class PolynomialSource:
    variables: tuple[str, ...]
    equations: tuple[sp.Expr, ...]
    guard: sp.Expr
    raw_target: sp.Expr
    definedness: tuple[sp.Expr, ...] = ()
    label: str = "anonymous"


@dataclass(frozen=True)
class TargetProposal:
    polynomial_high_to_low: tuple[int, ...]
    real_root_ordinal: int
    lower: Fraction
    upper: Fraction


@dataclass(frozen=True)
class CompiledFormula:
    variables: tuple[sp.Symbol, ...]
    target: sp.Symbol
    equations: tuple[sp.Expr, ...]
    guard: sp.Expr
    definedness: tuple[sp.Expr, ...]
    raw_target: sp.Expr
    qf_nra: sp.Expr
    irrelevant_free_variables: tuple[sp.Symbol, ...]


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("ascii")
    ).hexdigest()


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _semantic_modules():
    for path, expected in EXPECTED_SEMANTIC_SHA256.items():
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise NotProved("FROZEN_SEMANTIC_LIFT_HASH_MISMATCH")
    semantic = sys.modules.get("semantic_lift")
    if semantic is None:
        semantic = _load("semantic_lift", SEMANTIC_LIFT)
    replay = sys.modules.get("geotarget_target_constrained_semantic_replay")
    if replay is None:
        replay = _load(
            "geotarget_target_constrained_semantic_replay", SEMANTIC_REPLAY
        )
    return semantic, replay


def _qq(value: object) -> sp.Rational:
    if isinstance(value, Fraction):
        return sp.Rational(value.numerator, value.denominator)
    return sp.Rational(value)


def _poly(expr: sp.Expr, symbols: Sequence[sp.Symbol]) -> sp.Poly:
    try:
        polynomial = sp.Poly(sp.expand(expr), *symbols, domain=sp.QQ)
    except (sp.PolynomialError, TypeError, ValueError) as error:
        raise NotProved("UNSUPPORTED_NONPOLYNOMIAL") from error
    if polynomial.total_degree() > MAX_TOTAL_DEGREE:
        raise NotProved("RESOURCE_DEGREE_CAP")
    if len(polynomial.terms()) > MAX_TERMS:
        raise NotProved("RESOURCE_TERM_CAP")
    return polynomial


def _rational_parts(expr: sp.Expr) -> tuple[sp.Expr, sp.Expr]:
    expression = sp.sympify(expr)
    if expression.has(sp.sin, sp.cos, sp.tan, sp.exp, sp.log, sp.Abs):
        raise NotProved("UNSUPPORTED_TRANSCENDENTAL_OR_BRANCH")
    numerator, denominator = sp.fraction(sp.together(expression))
    return sp.expand(numerator), sp.expand(denominator)


def _compile_relation(
    relation: Relational,
    symbols: Sequence[sp.Symbol],
) -> tuple[sp.Expr, tuple[sp.Expr, ...]]:
    numerator, denominator = _rational_parts(relation.lhs - relation.rhs)
    _poly(numerator, symbols)
    _poly(denominator, symbols)
    definedness = () if denominator == 1 else (denominator,)
    if isinstance(relation, Equality):
        result = sp.Eq(numerator, 0)
    elif isinstance(relation, Unequality):
        result = sp.Ne(numerator, 0)
    elif isinstance(relation, StrictGreaterThan):
        result = sp.StrictGreaterThan(sp.expand(numerator * denominator), 0)
    elif isinstance(relation, GreaterThan):
        result = sp.GreaterThan(sp.expand(numerator * denominator), 0)
    elif isinstance(relation, StrictLessThan):
        result = sp.StrictLessThan(sp.expand(numerator * denominator), 0)
    elif isinstance(relation, LessThan):
        result = sp.LessThan(sp.expand(numerator * denominator), 0)
    else:
        raise NotProved("UNSUPPORTED_RELATION")
    _poly(result.lhs, symbols)
    return result, definedness


def _compile_boolean(
    expression: sp.Expr,
    symbols: Sequence[sp.Symbol],
) -> tuple[sp.Expr, tuple[sp.Expr, ...]]:
    if expression in (sp.true, True):
        return sp.true, ()
    if expression in (sp.false, False):
        return sp.false, ()
    if isinstance(expression, Relational):
        return _compile_relation(expression, symbols)
    if isinstance(expression, sp.And):
        children = [_compile_boolean(item, symbols) for item in expression.args]
        return sp.And(*(item[0] for item in children)), tuple(
            denominator for item in children for denominator in item[1]
        )
    if isinstance(expression, sp.Or):
        children = [_compile_boolean(item, symbols) for item in expression.args]
        return sp.Or(*(item[0] for item in children)), tuple(
            denominator for item in children for denominator in item[1]
        )
    if isinstance(expression, sp.Not):
        child, denominators = _compile_boolean(expression.args[0], symbols)
        return sp.Not(child), denominators
    raise NotProved("UNSUPPORTED_BOOLEAN")


def _proposal_poly(proposal: TargetProposal, target: sp.Symbol) -> sp.Poly:
    coefficients = tuple(proposal.polynomial_high_to_low)
    if len(coefficients) < 2 or coefficients[0] == 0:
        raise NotProved("MALFORMED_PROPOSAL_POLYNOMIAL")
    polynomial = sp.Poly.from_list(coefficients, gens=target, domain=sp.ZZ)
    _, primitive = polynomial.primitive()
    if primitive.LC() < 0:
        primitive = -primitive
    if primitive != polynomial:
        raise NotProved("PROPOSAL_NOT_PRIMITIVE_POSITIVE")
    if sp.gcd(polynomial, polynomial.diff()).degree() != 0:
        raise NotProved("PROPOSAL_NOT_SQUARE_FREE")
    return polynomial


def _truth(value: object) -> bool:
    simplified = sp.simplify(value)
    if simplified in (sp.true, True):
        return True
    if simplified in (sp.false, False):
        return False
    raise NotProved("EXACT_SIGN_UNDECIDED")


def _proposal_root(
    polynomial: sp.Poly,
    proposal: TargetProposal,
) -> sp.Expr:
    roots = polynomial.real_roots(multiple=True)
    ordinal = proposal.real_root_ordinal
    if ordinal < 0 or ordinal >= len(roots):
        raise NotProved("ROOT_ORDINAL_OUT_OF_RANGE")
    lower, upper = _qq(proposal.lower), _qq(proposal.upper)
    if lower >= upper:
        raise NotProved("MALFORMED_ISOLATOR")
    selected = roots[ordinal]
    contained = [root for root in roots if _truth(sp.And(root > lower, root < upper))]
    if contained != [selected]:
        raise NotProved("ISOLATOR_OR_ORDINAL_MISMATCH")
    return selected


def compile_qf_nra(
    source: PolynomialSource,
    proposal: TargetProposal,
) -> CompiledFormula:
    if len(source.variables) != len(set(source.variables)):
        raise NotProved("DUPLICATE_VARIABLE")
    if not source.variables or len(source.variables) > MAX_VARIABLES:
        raise NotProved("VARIABLE_CAP_OR_EMPTY")
    variables = tuple(sp.Symbol(name, real=True) for name in source.variables)
    symbol_by_name = dict(zip(source.variables, variables, strict=True))
    substitutions = {
        symbol: symbol_by_name[symbol.name]
        for expression in (*source.equations, source.guard, source.raw_target, *source.definedness)
        for symbol in sp.sympify(expression).free_symbols
        if symbol.name in symbol_by_name
    }
    equations: list[sp.Expr] = []
    definedness: list[sp.Expr] = []
    for raw in source.equations:
        numerator, denominator = _rational_parts(sp.sympify(raw).xreplace(substitutions))
        _poly(numerator, variables)
        _poly(denominator, variables)
        equations.append(numerator)
        if denominator != 1:
            definedness.append(denominator)
    if len(equations) > MAX_EQUATIONS:
        raise NotProved("EQUATION_CAP")
    guard, guard_denominators = _compile_boolean(
        sp.sympify(source.guard).xreplace(substitutions), variables
    )
    definedness.extend(guard_denominators)
    for raw in source.definedness:
        numerator, denominator = _rational_parts(sp.sympify(raw).xreplace(substitutions))
        _poly(numerator, variables)
        _poly(denominator, variables)
        definedness.extend((numerator,))
        if denominator != 1:
            definedness.append(denominator)

    raw_target = sp.sympify(source.raw_target).xreplace(substitutions)
    target_numerator, target_denominator = _rational_parts(raw_target)
    target = sp.Symbol("__nra_raw_target", real=True)
    all_symbols = (*variables, target)
    _poly(target_numerator, variables)
    _poly(target_denominator, variables)
    target_link = sp.expand(target * target_denominator - target_numerator)
    _poly(target_link, all_symbols)
    if target_denominator != 1:
        definedness.append(target_denominator)

    proposal_poly = _proposal_poly(proposal, target)
    _proposal_root(proposal_poly, proposal)
    equations.extend((target_link, proposal_poly.as_expr()))
    for item in definedness:
        _poly(item, variables)
    qf = sp.And(
        *(sp.Eq(item, 0) for item in equations),
        guard,
        *(sp.Ne(item, 0) for item in definedness),
        target > _qq(proposal.lower),
        target < _qq(proposal.upper),
    )
    semantic_symbols = set().union(
        *(item.free_symbols for item in equations),
        guard.free_symbols,
        *(item.free_symbols for item in definedness),
    )
    irrelevant = tuple(symbol for symbol in variables if symbol not in semantic_symbols)
    return CompiledFormula(
        variables,
        target,
        tuple(equations),
        guard,
        tuple(dict.fromkeys(definedness)),
        raw_target,
        qf,
        irrelevant,
    )


@contextmanager
def _deadline(seconds: float):
    if not math.isfinite(seconds) or seconds <= 0:
        raise NotProved("INVALID_TIMEOUT")
    if not hasattr(signal, "SIGALRM"):
        yield
        return
    previous = signal.getsignal(signal.SIGALRM)

    def expired(_signum, _frame):
        raise BackendTimeout("exact backend timeout")

    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def _integer_primitive(poly: sp.Poly) -> tuple[int, ...]:
    denominator_lcm = sp.ilcm(*[term.q for term in poly.all_coeffs()])
    values = [int(term * denominator_lcm) for term in poly.all_coeffs()]
    common = 0
    for value in values:
        common = math.gcd(common, abs(value))
    values = [value // max(1, common) for value in values]
    if values[0] < 0:
        values = [-value for value in values]
    return tuple(values)


def _descriptor(value: sp.Expr) -> dict[str, object]:
    value = sp.simplify(value)
    if value.is_Rational is True:
        rational = sp.Rational(value)
        return {
            "kind": "Rational",
            "numerator": int(rational.p),
            "denominator": int(rational.q),
        }
    symbol = sp.Symbol("__descriptor_z")
    polynomial = sp.Poly(sp.minpoly(value, symbol), symbol, domain=sp.QQ)
    coefficients = _integer_primitive(polynomial)
    integer_poly = sp.Poly.from_list(coefficients, gens=symbol, domain=sp.ZZ)
    roots = integer_poly.real_roots(multiple=True)
    matches = [index for index, root in enumerate(roots) if sp.simplify(root - value) == 0]
    if len(matches) != 1:
        approximated = sp.N(value, 100)
        distances = [abs(sp.N(root, 100) - approximated) for root in roots]
        best = min(range(len(roots)), key=lambda index: distances[index])
        if sum(distances[index] == distances[best] for index in range(len(roots))) != 1:
            raise NotProved("ALGEBRAIC_ROOT_IDENTITY_AMBIGUOUS")
        matches = [best]
    ordinal = matches[0]
    intervals = integer_poly.intervals(eps=sp.Rational(1, 2**80))
    if len(intervals) != len(roots):
        raise NotProved("ALGEBRAIC_ISOLATOR_UNAVAILABLE")
    (lower, upper), multiplicity = intervals[ordinal]
    if multiplicity != 1:
        raise NotProved("MINPOLY_NOT_SQUARE_FREE")
    return {
        "kind": "AlgebraicNumRef",
        "minimal_polynomial_high_to_low": list(coefficients),
        "selected_real_root_index": ordinal,
        "isolating_interval": {
            "lower": [int(lower.p), int(lower.q)],
            "upper": [int(upper.p), int(upper.q)],
        },
    }


def _from_descriptor(descriptor: Mapping[str, object]) -> sp.Expr:
    if descriptor.get("kind") == "Rational":
        return sp.Rational(int(descriptor["numerator"]), int(descriptor["denominator"]))
    if descriptor.get("kind") != "AlgebraicNumRef":
        raise NotProved("MALFORMED_MODEL_DESCRIPTOR")
    symbol = sp.Symbol("__replay_z")
    coefficients = descriptor.get("minimal_polynomial_high_to_low")
    ordinal = descriptor.get("selected_real_root_index")
    interval = descriptor.get("isolating_interval")
    if not isinstance(coefficients, list) or not isinstance(ordinal, int) or not isinstance(interval, Mapping):
        raise NotProved("MALFORMED_MODEL_DESCRIPTOR")
    polynomial = sp.Poly.from_list(coefficients, gens=symbol, domain=sp.ZZ)
    roots = polynomial.real_roots(multiple=True)
    if ordinal < 0 or ordinal >= len(roots):
        raise NotProved("MALFORMED_MODEL_ORDINAL")
    root = roots[ordinal]
    lower_raw, upper_raw = interval.get("lower"), interval.get("upper")
    if not (
        isinstance(lower_raw, list)
        and isinstance(upper_raw, list)
        and len(lower_raw) == len(upper_raw) == 2
    ):
        raise NotProved("MALFORMED_MODEL_ISOLATOR")
    lower = sp.Rational(*map(int, lower_raw))
    upper = sp.Rational(*map(int, upper_raw))
    if not _truth(sp.And(root > lower, root < upper)):
        raise NotProved("MODEL_ISOLATOR_MISMATCH")
    return root


def _exact_zero(value: sp.Expr) -> bool:
    return sp.simplify(value) == 0


def independent_replay(
    source: PolynomialSource,
    proposal: TargetProposal,
    formula: CompiledFormula,
    descriptors: Mapping[str, Mapping[str, object]],
) -> tuple[bool, str]:
    try:
        values = {name: _from_descriptor(descriptor) for name, descriptor in descriptors.items()}
        substitutions = {
            symbol: values[symbol.name] for symbol in formula.variables
        }
        target = values[formula.target.name]
        for raw in source.equations:
            numerator, denominator = _rational_parts(sp.sympify(raw).subs(substitutions))
            if not _exact_zero(numerator) or _exact_zero(denominator):
                return False, "untouched-source-equation-or-definedness"
        for raw in source.definedness:
            numerator, denominator = _rational_parts(sp.sympify(raw).subs(substitutions))
            if _exact_zero(numerator) or _exact_zero(denominator):
                return False, "untouched-explicit-definedness"
        if not _truth(sp.sympify(source.guard).subs(substitutions)):
            return False, "untouched-typed-guard"
        raw_target = sp.sympify(source.raw_target).subs(substitutions)
        target_numerator, target_denominator = _rational_parts(raw_target)
        if _exact_zero(target_denominator) or not _exact_zero(target - raw_target):
            return False, "untouched-raw-target-link"
        target_symbol = formula.target
        polynomial = _proposal_poly(proposal, target_symbol)
        if not _exact_zero(polynomial.as_expr().subs({target_symbol: target})):
            return False, "proposal-polynomial"
        selected = _proposal_root(polynomial, proposal)
        if not _exact_zero(target - selected):
            return False, "proposal-root-ordinal"
        if not _truth(sp.And(target > _qq(proposal.lower), target < _qq(proposal.upper))):
            return False, "proposal-isolator"
        return True, "verified"
    except (NotProved, TypeError, ValueError, sp.PolynomialError) as error:
        return False, f"replay-error:{error}"


def prove(
    source: PolynomialSource,
    proposal: TargetProposal,
    *,
    timeout_seconds: float = 3.0,
) -> dict[str, object]:
    started = time.monotonic()
    common: dict[str, object] = {
        "schema_version": SCHEMA,
        "backend": BACKEND,
        "preferred_z3_backend_available": False,
        "truth_case_family_expected_target_inputs": False,
        "source_label_used_for_routing": False,
        "status": "NOT_PROVED",
        "authority_pass": False,
    }
    try:
        formula = compile_qf_nra(source, proposal)
        solve_symbols = tuple(
            symbol
            for symbol in (*formula.variables, formula.target)
            if symbol not in formula.irrelevant_free_variables
        )
        with _deadline(timeout_seconds):
            basis = sp.groebner(formula.equations, *solve_symbols, order="lex", domain=sp.QQ)
            if not basis.is_zero_dimensional:
                raise NotProved("UNSUPPORTED_POSITIVE_DIMENSIONAL_RELEVANT_FIBER")
            solutions = sp.solve_poly_system(list(formula.equations), *solve_symbols)
        if solutions is None:
            raise NotProved("BACKEND_DID_NOT_RETURN_COMPLETE_SOLUTION_LIST")
        checked = 0
        for solution in solutions:
            if len(solution) != len(solve_symbols):
                continue
            model = dict(zip(solve_symbols, map(sp.simplify, solution), strict=True))
            model.update({symbol: sp.Integer(0) for symbol in formula.irrelevant_free_variables})
            if any(value.free_symbols for value in model.values()):
                continue
            if any(value.is_real is not True for value in model.values()):
                continue
            checked += 1
            if not _truth(formula.guard.subs(model)):
                continue
            if any(_exact_zero(item.subs(model)) for item in formula.definedness):
                continue
            if any(not _exact_zero(item.subs(model)) for item in formula.equations):
                continue
            descriptors = {
                symbol.name: _descriptor(model[symbol])
                for symbol in (*formula.variables, formula.target)
            }
            replay_ok, replay_reason = independent_replay(
                source, proposal, formula, descriptors
            )
            if not replay_ok:
                continue
            result = {
                **common,
                "status": "TARGET_CONSTRAINED_EXACT_WITNESS_READY",
                "authority_pass": True,
                "qf_nra_formula": str(formula.qf_nra),
                "complete_backend_scope": (
                    "zero-dimensional QQ equality variety plus semantically "
                    "irrelevant free coordinates"
                ),
                "irrelevant_free_variables": [item.name for item in formula.irrelevant_free_variables],
                "backend_solution_count": len(solutions),
                "real_models_checked": checked,
                "model_descriptors": descriptors,
                "independent_replay": {
                    "pass": True,
                    "reason": replay_reason,
                    "untouched_source_equations": True,
                    "typed_boolean_guard": True,
                    "division_definedness": True,
                    "raw_target_link": True,
                    "proposal_polynomial_isolator_ordinal": True,
                },
            }
            result["witness_sha256"] = _canonical_sha256(descriptors)
            result["elapsed_seconds"] = time.monotonic() - started
            return result
        raise NotProved("QF_NRA_UNSAT_IN_PROPOSAL_CELL")
    except BackendTimeout:
        common["reason"] = "TIMEOUT"
    except NotProved as error:
        common["reason"] = str(error)
    except Exception as error:  # fail closed for disposable backend defects
        common["reason"] = f"BACKEND_ERROR:{type(error).__name__}:{error}"
    common["elapsed_seconds"] = time.monotonic() - started
    return common


def _artifact_source(artifact) -> PolynomialSource:
    symbols = {name: sp.Symbol(name, real=True) for name in artifact.variables}
    if artifact.proof_ready is not True:
        raise NotProved("SEMANTIC_LIFT_COVER_ONLY")
    equations = tuple(sp.sympify(text, locals=symbols) for text in artifact.equations)
    relations = {
        "eq": lambda expression: sp.Eq(expression, 0),
        "ne": lambda expression: sp.Ne(expression, 0),
        "gt": lambda expression: expression > 0,
        "ge": lambda expression: expression >= 0,
        "lt": lambda expression: expression < 0,
        "le": lambda expression: expression <= 0,
    }
    guard_rows = []
    for predicate in artifact.predicates:
        relation = predicate["relation"]
        if relation not in relations:
            raise NotProved("SEMANTIC_LIFT_UNKNOWN_PREDICATE")
        expression = sp.sympify(predicate["expression"], locals=symbols)
        guard_rows.append(relations[relation](expression))
    return PolynomialSource(
        tuple(artifact.variables),
        equations,
        sp.And(*guard_rows),
        symbols[artifact.target_variable],
        label="frozen-semantic-algebraic-lift",
    )


def prove_semantic_document(
    document: Mapping[str, object],
    proposal: TargetProposal,
    *,
    timeout_seconds: float = 3.0,
) -> dict[str, object]:
    """Thinly reuse the frozen frontend; keep backend/certificate private."""

    started = time.monotonic()
    try:
        semantic, replay = _semantic_modules()
        artifact = semantic.compile_document(document)
        result = prove(
            _artifact_source(artifact), proposal, timeout_seconds=timeout_seconds
        )
        result["semantic_frontend"] = {
            "reused_frozen_lift": True,
            "semantic_source_sha256": artifact.semantic_source_sha256,
            "lift_sha256": EXPECTED_SEMANTIC_SHA256[SEMANTIC_LIFT],
            "replay_sha256": EXPECTED_SEMANTIC_SHA256[SEMANTIC_REPLAY],
            "proof_ready": artifact.proof_ready,
        }
        if result.get("authority_pass") is not True:
            return result
        descriptors = result["model_descriptors"]
        lifted_values = {
            name: _from_descriptor(descriptors[name]) for name in artifact.variables
        }
        lift_ok, lift_reason = semantic.verify_polynomial_witness(
            artifact, lifted_values
        )
        raw_names = tuple(document.get("variables", {}).get("names", ()))
        raw_values = {name: lifted_values[name] for name in raw_names}
        untouched = replay.ExactSourceRuntime(document, raw_values).verify()
        source_link_ok, source_link_reason = replay.verify_source_and_target_replay(
            document, artifact, raw_values, lifted_values
        )
        if not (lift_ok and untouched.accepted and source_link_ok):
            return {
                **result,
                "status": "NOT_PROVED",
                "authority_pass": False,
                "reason": (
                    f"SEMANTIC_REPLAY_REJECTED:{lift_reason}:"
                    f"{untouched.reason}:{source_link_reason}"
                ),
            }
        result["independent_replay"].update(
            {
                "frozen_lift_polynomial_replay": True,
                "untouched_source_dsl_replay": True,
                "semantic_phase_selector_branch_ledger_replay": True,
                "semantic_replay_reason": source_link_reason,
            }
        )
        result["elapsed_seconds"] = time.monotonic() - started
        return result
    except Exception as error:
        return {
            "schema_version": SCHEMA,
            "backend": BACKEND,
            "status": "NOT_PROVED",
            "authority_pass": False,
            "reason": f"SEMANTIC_FRONTEND_ERROR:{type(error).__name__}:{error}",
            "elapsed_seconds": time.monotonic() - started,
        }


__all__ = [
    "BACKEND",
    "PolynomialSource",
    "TargetProposal",
    "compile_qf_nra",
    "independent_replay",
    "prove",
    "prove_semantic_document",
]
