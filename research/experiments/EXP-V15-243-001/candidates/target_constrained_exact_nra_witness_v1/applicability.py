"""Candidate-private applicability and dry OR-authority seam.

This is deliberately not a worker or a general compiler.  It asks whether a
frozen semantic-lift artifact fits the exact backend's *actual* complete
subset, estimates its finite quotient/cost when possible, and otherwise fails
closed.  A source-only result is never authority because the solver proposal
polynomial, ordinal and isolator are still absent.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
import hashlib
import importlib.util
import math
from pathlib import Path
import sys
import time
from typing import Any

import sympy as sp

import candidate as backend


SCHEMA = "geotarget.target-constrained-nra-applicability/v1"
STATIC_GROEBNER_SECONDS = 0.35
DESCRIPTOR_GROEBNER_SECONDS = 0.75
MAX_QUOTIENT_ENUMERATION = 100_000
LEGACY_COMPILER = Path(
    "/home/kabatan/work/solver-experiment-runtime/solver/research/experiments/"
    "EXP-REAL61-002/algebraic_lane/compiler.py"
)
EXPECTED_LEGACY_COMPILER_SHA256 = (
    "f127f7f1e2f93161e1353f07222e93ffacfa1c2dbd4e68e5b1fd23a8a3b10318"
)


def _quantile(values: list[int | float], fraction: float) -> int | float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * fraction)]


def _quotient_dimension(basis: sp.GroebnerBasis) -> int:
    """Count standard monomials of a zero-dimensional leading ideal."""

    leading = [tuple(poly.LM(order=basis.order).exponents) for poly in basis.polys]
    variable_count = len(basis.gens)
    pure_bounds: list[int] = []
    for index in range(variable_count):
        powers = [
            exponents[index]
            for exponents in leading
            if exponents[index] > 0
            and all(power == 0 for j, power in enumerate(exponents) if j != index)
        ]
        if not powers:
            raise backend.NotProved("ZERO_DIMENSIONAL_BASIS_WITHOUT_PURE_BOUND")
        pure_bounds.append(min(powers))
    if math.prod(pure_bounds) > MAX_QUOTIENT_ENUMERATION:
        raise backend.NotProved("RESOURCE_QUOTIENT_ENUMERATION_CAP")
    quotient = 0
    for flat in range(math.prod(pure_bounds)):
        cursor = flat
        exponents = []
        for bound in reversed(pure_bounds):
            exponents.append(cursor % bound)
            cursor //= bound
        monomial = tuple(reversed(exponents))
        if not any(
            all(value >= divisor for value, divisor in zip(monomial, leader, strict=True))
            for leader in leading
        ):
            quotient += 1
    return quotient


def _stratum(artifact: object) -> str:
    if artifact.phase_groups:
        return "periodic-ledger"
    if artifact.selector_ledger:
        return "selector-ledger"
    kinds = {
        str(item.get("kind"))
        for item in artifact.auxiliary_definitions
        if item.get("kind") != "target"
    }
    if kinds:
        return "algebraic-auxiliary"
    return "direct-polynomial"


def _seams(artifact: object) -> dict[str, bool]:
    target_definitions = [
        item
        for item in artifact.auxiliary_definitions
        if item.get("kind") == "target"
        and item.get("variable") == artifact.target_variable
    ]
    target_replays = [
        item
        for item in artifact.replay_ledger
        if item.get("kind") == "raw-source-target-link"
        and item.get("target_variable") == artifact.target_variable
    ]
    return {
        "semantic_source_digest": bool(artifact.semantic_source_sha256),
        "target_definition": len(target_definitions) == 1,
        "exact_target_link": bool(artifact.exact_target_link),
        "untouched_source_replay": len(target_replays) == 1,
        "typed_predicate_replay": isinstance(artifact.predicates, tuple),
        "selector_phase_replay": isinstance(artifact.replay_ledger, tuple),
    }


def _source_state_from_source(source: backend.PolynomialSource) -> dict[str, Any]:
    symbols = tuple(sp.Symbol(name, real=True) for name in source.variables)
    by_name = {symbol.name: symbol for symbol in symbols}
    substitutions = {
        symbol: by_name[symbol.name]
        for expression in (*source.equations, source.guard, source.raw_target)
        for symbol in sp.sympify(expression).free_symbols
        if symbol.name in by_name
    }
    if len(source.variables) > backend.MAX_VARIABLES:
        raise backend.NotProved("RESOURCE_VARIABLE_CAP")
    # The proposal adds one target-link equation and one polynomial equation.
    if len(source.equations) + 2 > backend.MAX_EQUATIONS:
        raise backend.NotProved("RESOURCE_EQUATION_CAP_WITH_DESCRIPTOR")

    equations: list[sp.Expr] = []
    degrees: list[int] = []
    terms: list[int] = []
    for raw in source.equations:
        numerator, denominator = backend._rational_parts(
            sp.sympify(raw).xreplace(substitutions)
        )
        if denominator != 1:
            raise backend.NotProved("UNEXPECTED_LIFT_EQUATION_DENOMINATOR")
        polynomial = backend._poly(numerator, symbols)
        equations.append(polynomial.as_expr())
        degrees.append(polynomial.total_degree())
        terms.append(len(polynomial.terms()))
    guard, guard_denominators = backend._compile_boolean(
        sp.sympify(source.guard).xreplace(substitutions), symbols
    )
    target = sp.sympify(source.raw_target).xreplace(substitutions)
    target_numerator, target_denominator = backend._rational_parts(target)
    backend._poly(target_numerator, symbols)
    backend._poly(target_denominator, symbols)
    expressions = [*equations, guard, target_numerator, target_denominator, *guard_denominators]
    relevant = tuple(
        symbol
        for symbol in symbols
        if any(symbol in sp.sympify(expression).free_symbols for expression in expressions)
    )
    if not relevant:
        raise backend.NotProved("NO_RELEVANT_SOURCE_VARIABLE")
    active_equations = [
        expression for expression in equations if sp.sympify(expression) != 0
    ]
    height_dimension_lower_bound = max(0, len(relevant) - len(active_equations))
    sparse_cost_proxy = sum(
        max(1, degree) ** 2 * max(1, term)
        for degree, term in zip(degrees, terms, strict=True)
    ) * max(1, len(relevant))
    bezout_log2_proxy = sum(math.log2(max(1, degree)) for degree in degrees)
    return {
        "source": source,
        "symbols": symbols,
        "relevant": relevant,
        "equations": equations,
        "guard": guard,
        "height_dimension_lower_bound": height_dimension_lower_bound,
        "max_total_degree": max(degrees, default=0),
        "max_term_count": max(terms, default=0),
        "sparse_cost_proxy": sparse_cost_proxy,
        "bezout_log2_proxy": bezout_log2_proxy,
    }


def _source_state(artifact: object) -> dict[str, Any]:
    return _source_state_from_source(backend._artifact_source(artifact))


def _legacy_module():
    if (
        not LEGACY_COMPILER.is_file()
        or hashlib.sha256(LEGACY_COMPILER.read_bytes()).hexdigest()
        != EXPECTED_LEGACY_COMPILER_SHA256
    ):
        raise backend.NotProved("LEGACY_PRIMITIVE_COMPILER_HASH_MISMATCH")
    name = "geotarget_target_constrained_legacy_primitive_compiler"
    loaded = sys.modules.get(name)
    if loaded is not None:
        return loaded
    specification = importlib.util.spec_from_file_location(name, LEGACY_COMPILER)
    if specification is None or specification.loader is None:
        raise backend.NotProved("LEGACY_PRIMITIVE_COMPILER_LOAD_FAILED")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _legacy_target_link_source(
    document: Mapping[str, object],
    *,
    include_private_bridge_ledger: bool = False,
) -> tuple[backend.PolynomialSource, dict[str, object]]:
    """Thinly add a target graph to the existing primitive cover compiler."""

    legacy = _legacy_module()
    compiler = legacy.Compiler(dict(document))
    compiled = compiler.compile()
    if compiled.classification == "UNSUPPORTED":
        reason = compiled.unsupported[0] if compiled.unsupported else "unknown"
        raise backend.NotProved(f"LEGACY_PRIMITIVE_COVER_UNSUPPORTED:{reason}")
    try:
        target = compiler.eval(
            ast.parse(str(document["answer"]), mode="eval").body,
            "candidate-private-target-link",
        )
    except Exception as error:
        raise backend.NotProved(
            f"LEGACY_TARGET_GRAPH_UNSUPPORTED:{type(error).__name__}:{error}"
        ) from error
    if not isinstance(target, sp.Expr):
        raise backend.NotProved("LEGACY_TARGET_GRAPH_NOT_SCALAR")
    target_variable = compiler.new_aux("candidate_target")
    compiler.add_equation(
        target_variable - target, "candidate-private-exact-target-link"
    )
    compiler.replay.append(
        {
            "kind": "raw-source-target-link",
            "source": "answer",
            "detail": str(document["answer"]),
        }
    )
    final_unknowns = tuple(
        symbol
        for symbol in compiler.unknowns
        if symbol.name not in compiler._eliminated_parameters
    )
    equations = tuple(
        compiler.polynomialize(expression, source)
        for expression, source in compiler.equations
    )
    relation = {
        "eq": lambda expression: sp.Eq(expression, 0),
        "ne": lambda expression: sp.Ne(expression, 0),
        "gt": lambda expression: expression > 0,
        "ge": lambda expression: expression >= 0,
        "lt": lambda expression: expression < 0,
        "le": lambda expression: expression <= 0,
    }
    predicates = []
    for predicate in compiler.predicates:
        if predicate.relation not in relation:
            raise backend.NotProved("LEGACY_UNKNOWN_TYPED_PREDICATE")
        predicates.append(
            relation[predicate.relation](
                compiler.polynomialize(predicate.expression, predicate.source)
            )
        )
    source = backend.PolynomialSource(
        tuple(symbol.name for symbol in final_unknowns),
        equations,
        sp.And(*predicates),
        target_variable,
        label="digest-pinned-legacy-primitive-cover-with-target-link",
    )
    reconstruction_kinds = {
        str(item.get("kind")) for item in compiler.reconstruction
    }
    replay_kinds = {str(item.get("kind")) for item in compiler.replay}
    if any("trig" in kind or "periodic" in kind for kind in replay_kinds):
        stratum = "periodic-ledger"
    elif reconstruction_kinds:
        stratum = "algebraic-cover-reconstruction"
    elif replay_kinds - {"canonical-guard", "raw-source-target-link"}:
        stratum = "selector-or-branch-ledger"
    else:
        stratum = "direct-polynomial"
    metadata = {
        "structural_stratum": stratum,
        "primitive_compiler_sha256": EXPECTED_LEGACY_COMPILER_SHA256,
        "semantic_classification": compiled.classification,
        "canonical_source_replay_obligation_present": bool(compiler.replay),
        "candidate_private_exact_target_link_present": True,
        "source_replay_authority_bridge_wired": False,
        "cover_is_source_authority": False,
    }
    if include_private_bridge_ledger:
        bridge = {
            "source_document_sha256": backend._canonical_sha256(document),
            "cover_variables": list(source.variables),
            "cover_target_variable": target_variable.name,
            "reconstruction": [dict(item) for item in compiler.reconstruction],
            "replay_obligations": [dict(item) for item in compiler.replay],
        }
        bridge["bridge_ledger_sha256"] = backend._canonical_sha256(bridge)
        metadata["private_bridge_ledger"] = bridge
    return source, metadata


def _basis_measure(
    equations: list[sp.Expr] | tuple[sp.Expr, ...],
    symbols: tuple[sp.Symbol, ...],
    timeout_seconds: float,
) -> dict[str, Any]:
    started = time.monotonic()
    with backend._deadline(timeout_seconds):
        basis = sp.groebner(equations, *symbols, order="lex", domain=sp.QQ)
        unit_ideal = any(poly.as_expr() == 1 for poly in basis.polys)
        zero_dimensional = bool(basis.is_zero_dimensional)
        quotient = _quotient_dimension(basis) if zero_dimensional else None
    elapsed = time.monotonic() - started
    return {
        "unit_ideal": unit_ideal,
        "zero_dimensional": zero_dimensional,
        "quotient_dimension": quotient,
        "groebner_basis_size": len(basis.polys),
        "groebner_elapsed_seconds": elapsed,
    }


def assess_artifact(
    artifact: object,
    proposal: backend.TargetProposal | None = None,
) -> dict[str, Any]:
    """Return truth-free applicability; never solve or emit an authority."""

    result: dict[str, Any] = {
        "schema_version": SCHEMA,
        "authority_pass": False,
        "truth_case_family_outcome_expected_target_inputs": False,
        "structural_stratum": _stratum(artifact),
        "proposal_descriptor_present": proposal is not None,
        "resource_caps": {
            "source_variables": backend.MAX_VARIABLES,
            "equations_including_target_link_and_proposal": backend.MAX_EQUATIONS,
            "total_degree": backend.MAX_TOTAL_DEGREE,
            "terms_per_polynomial": backend.MAX_TERMS,
            "static_groebner_seconds": STATIC_GROEBNER_SECONDS,
            "descriptor_groebner_seconds": DESCRIPTOR_GROEBNER_SECONDS,
            "quotient_enumeration": MAX_QUOTIENT_ENUMERATION,
        },
        "replay_target_seams": _seams(artifact),
    }
    if artifact.proof_ready is not True:
        result.update(status="INELIGIBLE_SEMANTIC_REPLAY", reason="SEMANTIC_LIFT_COVER_ONLY")
        return result
    if not all(result["replay_target_seams"].values()):
        result.update(status="INELIGIBLE_SEAM", reason="SOURCE_REPLAY_OR_TARGET_LINK_SEAM_MISSING")
        return result
    try:
        state = _source_state(artifact)
        result["source_cost"] = {
            "declared_variable_count": len(state["source"].variables),
            "relevant_variable_count": len(state["relevant"]),
            "equation_count_before_descriptor": len(state["equations"]),
            "height_dimension_lower_bound": state["height_dimension_lower_bound"],
            "max_total_degree": state["max_total_degree"],
            "max_term_count": state["max_term_count"],
            "sparse_cost_proxy": state["sparse_cost_proxy"],
            "bezout_log2_proxy": state["bezout_log2_proxy"],
        }
        source_basis = _basis_measure(
            state["equations"], state["relevant"], STATIC_GROEBNER_SECONDS
        )
        result["source_quotient"] = source_basis
        result["statically_admissible_if_descriptor_compatible"] = bool(
            source_basis["zero_dimensional"] and not source_basis["unit_ideal"]
        )
        if proposal is None:
            result.update(
                status="HOLD_DESCRIPTOR_SEAM",
                reason="PROPOSED_POLYNOMIAL_ORDINAL_ISOLATOR_NOT_AVAILABLE_SOURCE_ONLY",
            )
            return result

        formula = backend.compile_qf_nra(state["source"], proposal)
        solve_symbols = tuple(
            symbol
            for symbol in (*formula.variables, formula.target)
            if symbol not in formula.irrelevant_free_variables
        )
        descriptor_basis = _basis_measure(
            formula.equations, solve_symbols, DESCRIPTOR_GROEBNER_SECONDS
        )
        result["descriptor_conditioned_quotient"] = descriptor_basis
        result["descriptor_cost"] = {
            "degree": len(proposal.polynomial_high_to_low) - 1,
            "coefficient_height_bits": max(
                abs(int(value)).bit_length() for value in proposal.polynomial_high_to_low
            ),
        }
        if descriptor_basis["zero_dimensional"]:
            result.update(
                status="ELIGIBLE_COMPLETE_SUBSET",
                reason="FINITE_QQ_EQUALITY_VARIETY_WITH_EXACT_DESCRIPTOR_CELL",
            )
        elif descriptor_basis["unit_ideal"]:
            result.update(
                status="ELIGIBLE_EQUATIONAL_UNSAT",
                reason="DESCRIPTOR_CELL_DISJOINT_FROM_SOURCE_EQUALITIES",
            )
        else:
            result.update(
                status="INELIGIBLE_POSITIVE_DIMENSIONAL_RELEVANT_FIBER",
                reason="DESCRIPTOR_DID_NOT_CLOSE_RELEVANT_FIBER",
            )
        return result
    except backend.BackendTimeout:
        result.update(status="INELIGIBLE_RESOURCE_TIMEOUT", reason="STATIC_GROEBNER_TIMEOUT")
    except backend.NotProved as error:
        result.update(status="INELIGIBLE_BACKEND_SUBSET", reason=str(error))
    except Exception as error:
        result.update(
            status="INELIGIBLE_BACKEND_ERROR",
            reason=f"{type(error).__name__}:{error}",
        )
    return result


def assess_document(
    document: Mapping[str, object],
    proposal: backend.TargetProposal | None = None,
) -> dict[str, Any]:
    try:
        semantic, _replay = backend._semantic_modules()
        artifact = semantic.compile_document(document)
    except Exception as error:
        return {
            "schema_version": SCHEMA,
            "authority_pass": False,
            "proposal_descriptor_present": proposal is not None,
            "truth_case_family_outcome_expected_target_inputs": False,
            "status": "INELIGIBLE_SEMANTIC_FRONTEND",
            "reason": f"{type(error).__name__}:{error}",
        }
    return assess_artifact(artifact, proposal)


def assess_source_document(
    document: Mapping[str, object],
    proposal: backend.TargetProposal | None = None,
) -> dict[str, Any]:
    """Use the frozen lift first, then its pre-existing primitive cover seam.

    The fallback is a digest-pinned compiler already used by prior experiments;
    this adapter adds only the missing raw-target graph.  Its cover is never
    promoted to source authority because the canonical replay bridge is not
    wired in this candidate.
    """

    frozen = assess_document(document, proposal)
    if frozen.get("status") != "INELIGIBLE_SEMANTIC_FRONTEND":
        frozen["semantic_frontend_route"] = "frozen-semantic-algebraic-lift"
        frozen["source_replay_authority_bridge_wired"] = True
        return frozen
    result: dict[str, Any] = {
        "schema_version": SCHEMA,
        "authority_pass": False,
        "truth_case_family_outcome_expected_target_inputs": False,
        "proposal_descriptor_present": proposal is not None,
        "semantic_frontend_route": "digest-pinned-existing-primitive-cover",
        "frozen_frontend_failure": frozen.get("reason"),
        "resource_caps": {
            "source_variables": backend.MAX_VARIABLES,
            "equations_including_target_link_and_proposal": backend.MAX_EQUATIONS,
            "total_degree": backend.MAX_TOTAL_DEGREE,
            "terms_per_polynomial": backend.MAX_TERMS,
            "static_groebner_seconds": STATIC_GROEBNER_SECONDS,
            "descriptor_groebner_seconds": DESCRIPTOR_GROEBNER_SECONDS,
            "quotient_enumeration": MAX_QUOTIENT_ENUMERATION,
        },
    }
    try:
        source, metadata = _legacy_target_link_source(document)
        result.update(metadata)
        result["replay_target_seams"] = {
            "semantic_source_compiled": True,
            "candidate_private_exact_target_link": bool(
                metadata["candidate_private_exact_target_link_present"]
            ),
            "canonical_source_replay_obligation": bool(
                metadata["canonical_source_replay_obligation_present"]
            ),
            "descriptor_cell_replay_available_in_backend": True,
        }
        state = _source_state_from_source(source)
        result["source_cost"] = {
            "declared_variable_count": len(source.variables),
            "relevant_variable_count": len(state["relevant"]),
            "equation_count_before_descriptor": len(state["equations"]),
            "height_dimension_lower_bound": state["height_dimension_lower_bound"],
            "max_total_degree": state["max_total_degree"],
            "max_term_count": state["max_term_count"],
            "sparse_cost_proxy": state["sparse_cost_proxy"],
            "bezout_log2_proxy": state["bezout_log2_proxy"],
        }
        source_basis = _basis_measure(
            state["equations"], state["relevant"], STATIC_GROEBNER_SECONDS
        )
        result["source_quotient"] = source_basis
        result["statically_admissible_if_descriptor_compatible"] = bool(
            source_basis["zero_dimensional"] and not source_basis["unit_ideal"]
        )
        result["descriptor_may_close_one_dimensional_fiber"] = bool(
            not source_basis["zero_dimensional"]
            and state["height_dimension_lower_bound"] <= 1
        )
        if proposal is None:
            result.update(
                status="HOLD_DESCRIPTOR_SEAM",
                reason="PROPOSED_POLYNOMIAL_ORDINAL_ISOLATOR_NOT_AVAILABLE_SOURCE_ONLY",
            )
            return result
        formula = backend.compile_qf_nra(source, proposal)
        solve_symbols = tuple(
            symbol
            for symbol in (*formula.variables, formula.target)
            if symbol not in formula.irrelevant_free_variables
        )
        descriptor_basis = _basis_measure(
            formula.equations, solve_symbols, DESCRIPTOR_GROEBNER_SECONDS
        )
        result["descriptor_conditioned_quotient"] = descriptor_basis
        result["descriptor_cost"] = {
            "degree": len(proposal.polynomial_high_to_low) - 1,
            "coefficient_height_bits": max(
                abs(int(value)).bit_length() for value in proposal.polynomial_high_to_low
            ),
        }
        if descriptor_basis["zero_dimensional"]:
            result.update(
                status="BACKEND_ELIGIBLE_HOLD_SOURCE_REPLAY_BRIDGE",
                reason="COMPLETE_BACKEND_SUBSET_BUT_LEGACY_COVER_REPLAY_NOT_WIRED",
            )
        elif descriptor_basis["unit_ideal"]:
            result.update(
                status="ELIGIBLE_EQUATIONAL_UNSAT",
                reason="DESCRIPTOR_CELL_DISJOINT_FROM_SOURCE_EQUALITIES",
            )
        else:
            result.update(
                status="INELIGIBLE_POSITIVE_DIMENSIONAL_RELEVANT_FIBER",
                reason="DESCRIPTOR_DID_NOT_CLOSE_RELEVANT_FIBER",
            )
    except backend.BackendTimeout:
        result.update(status="INELIGIBLE_RESOURCE_TIMEOUT", reason="STATIC_GROEBNER_TIMEOUT")
    except backend.NotProved as error:
        result.update(status="INELIGIBLE_BACKEND_SUBSET", reason=str(error))
    except Exception as error:
        result.update(
            status="INELIGIBLE_BACKEND_ERROR",
            reason=f"{type(error).__name__}:{error}",
        )
    return result


def dry_or_authority(
    baseline: Mapping[str, object],
    document: Mapping[str, object],
    proposal: backend.TargetProposal,
) -> dict[str, object]:
    """Generated-only OR seam; baseline/zero-dimensional authorities are immutable."""

    baseline_copy = dict(baseline)
    if baseline.get("authority_pass") is True:
        return baseline_copy
    if baseline.get("archive_reopen_execution_route") == (
        "existing_source_exact_zero_dimensional_authority"
    ):
        return baseline_copy
    applicability = assess_document(document, proposal)
    if applicability.get("status") != "ELIGIBLE_COMPLETE_SUBSET":
        return baseline_copy
    candidate = backend.prove_semantic_document(document, proposal)
    replay = candidate.get("independent_replay")
    if not (
        candidate.get("authority_pass") is True
        and isinstance(replay, Mapping)
        and replay.get("pass") is True
        and replay.get("untouched_source_dsl_replay") is True
        and replay.get("raw_target_link") is True
        and replay.get("proposal_polynomial_isolator_ordinal") is True
    ):
        return baseline_copy
    return {
        "status": "TARGET_AUTHORITY_READY",
        "authority_pass": True,
        "authority_route": "TARGET_CONSTRAINED_EXACT_NRA_WITNESS",
        "descriptor": {
            "polynomial_high_to_low": list(proposal.polynomial_high_to_low),
            "real_root_ordinal": proposal.real_root_ordinal,
            "isolator": [str(proposal.lower), str(proposal.upper)],
        },
        "target_constrained_exact_witness": candidate,
        "all_emissions_require_independent_replay": True,
        "baseline_and_existing_zero_dimensional_routes_modified": False,
        "truth_case_family_outcome_expected_target_routing": False,
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate anonymous applicability rows without retaining case records."""

    from collections import Counter

    def reason_class(row: Mapping[str, object]) -> str:
        status, reason = str(row.get("status")), str(row.get("reason"))
        if status == "HOLD_DESCRIPTOR_SEAM":
            return "descriptor-seam"
        if "RESOURCE_" in reason or "TIMEOUT" in status:
            return "backend-resource-cap-or-timeout"
        if "LEGACY_PRIMITIVE_COVER_UNSUPPORTED" in reason:
            return "existing-primitive-cover-unsupported"
        if "LEGACY_TARGET_GRAPH_UNSUPPORTED" in reason:
            return "existing-target-graph-unsupported"
        if "SEMANTIC" in reason or status == "INELIGIBLE_SEMANTIC_FRONTEND":
            return "semantic-frontend-or-replay"
        if status == "INELIGIBLE_BACKEND_ERROR" or "NONPOLYNOMIAL" in reason:
            return "non-QQ-polynomial-or-backend-error"
        return status.lower()

    statuses = Counter(str(row.get("status")) for row in rows)
    reasons = Counter(reason_class(row) for row in rows)
    frontends = Counter(str(row.get("semantic_frontend_route", "none")) for row in rows)
    strata = Counter(str(row.get("structural_stratum", "frontend-rejected")) for row in rows)
    eligible_strata = Counter(
        str(row.get("structural_stratum"))
        for row in rows
        if row.get("statically_admissible_if_descriptor_compatible") is True
    )
    quotient = [
        int(row["source_quotient"]["quotient_dimension"])
        for row in rows
        if isinstance(row.get("source_quotient"), Mapping)
        and row["source_quotient"].get("quotient_dimension") is not None
    ]
    costs = [
        int(row["source_cost"]["sparse_cost_proxy"])
        for row in rows
        if isinstance(row.get("source_cost"), Mapping)
    ]
    seam_complete = sum(
        isinstance(row.get("replay_target_seams"), Mapping)
        and all(row["replay_target_seams"].values())
        for row in rows
    )
    return {
        "case_count": len(rows),
        "status_histogram": dict(sorted(statuses.items())),
        "reason_histogram": dict(sorted(reasons.items())),
        "semantic_frontend_route_histogram": dict(sorted(frontends.items())),
        "structural_stratum_histogram": dict(sorted(strata.items())),
        "statically_admissible_if_descriptor_compatible_count": sum(
            row.get("statically_admissible_if_descriptor_compatible") is True
            for row in rows
        ),
        "statically_admissible_stratum_histogram": dict(sorted(eligible_strata.items())),
        "statically_admissible_stratum_count": len(eligible_strata),
        "source_replay_and_target_link_seam_complete_count": seam_complete,
        "source_replay_authority_bridge_wired_count": sum(
            row.get("source_replay_authority_bridge_wired") is True for row in rows
        ),
        "quotient_dimension": {
            "observed_count": len(quotient),
            "median": _quantile(quotient, 0.5),
            "p95": _quantile(quotient, 0.95),
            "maximum": max(quotient, default=None),
        },
        "sparse_cost_proxy": {
            "observed_count": len(costs),
            "median": _quantile(costs, 0.5),
            "p95": _quantile(costs, 0.95),
            "maximum": max(costs, default=None),
        },
    }


__all__ = [
    "aggregate",
    "assess_artifact",
    "assess_document",
    "assess_source_document",
    "dry_or_authority",
]
