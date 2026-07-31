#!/usr/bin/env python3
"""Proof-only Repair B: bind and search a safe source-equality subset."""

from __future__ import annotations

import ast
from fractions import Fraction
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
from typing import Mapping, Sequence

import sympy as sp


HERE = Path(__file__).resolve().parent
RADICAL_PATH = (
    HERE.parent / "guided_target_radical_square_membership_v1/radical_square_membership.py"
)
RADICAL_SHA256 = "a41b8b4452fe11fc126c164518b335e43ac997a77fe9ce9e7fe72fba0a975f20"
SCHEMA = "geotarget.guided-target-bound-subset-proof/v1"
MAX_SAFE_GENERATOR_CANDIDATES = 64
MAX_SELECTED_GENERATORS = 12
MAX_POWERED_DEGREE = 8
MAX_POWERED_TERMS = 400


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_sha256(value: object) -> str:
    return _sha256_bytes(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    )


if _sha256_bytes(RADICAL_PATH.read_bytes()) != RADICAL_SHA256:
    raise RuntimeError("frozen radical-square dependency changed")
_spec = importlib.util.spec_from_file_location(
    "guided_target_frozen_radical_square_membership", RADICAL_PATH
)
if _spec is None or _spec.loader is None:
    raise ImportError(RADICAL_PATH)
RADICAL = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = RADICAL
_spec.loader.exec_module(RADICAL)
BASE = RADICAL.BASE


def _failure_class(reason: str) -> str:
    if "post-process" in reason:
        return "POST_PROCESS_OUTSIDE_RAW_TARGET_THEOREM"
    if "no safe source equality" in reason:
        return "NO_SAFE_SOURCE_EQUALITY_GENERATOR"
    if "candidate cap" in reason:
        return "SAFE_GENERATOR_CANDIDATE_CAP"
    if "bounded subset search" in reason:
        return "BOUND_SUBSET_REMAINDER_NONZERO"
    if "unit" in reason or "inconsistent" in reason:
        return "INCONSISTENT_UNIT_IDEAL"
    if "cofactor" in reason:
        return "COFACTOR_WITNESS_UNAVAILABLE"
    if "deadline" in reason:
        return "PROOF_DEADLINE"
    if "target" in reason:
        return "TARGET_OUTSIDE_SAFE_POLYNOMIAL_SUBSET"
    if "descriptor" in reason or "proposal" in reason or "isolator" in reason:
        return "DEGREE_ONE_PROPOSAL_REJECTED"
    return "OTHER_FAIL_CLOSED"


def _unproved(
    reason: str, *, source_sha256: str, elapsed: float
) -> dict[str, object]:
    return {
        "schema_version": SCHEMA,
        "status": "BOUND_SUBSET_IDENTITY_NOT_PROVED",
        "reason": reason,
        "failure_class": _failure_class(reason),
        "source_sha256": source_sha256,
        "authority_pass": False,
        "target_release": False,
        "regular_root_evidence_required": True,
        "full_source_typed_root_required": True,
        "truth_used": False,
        "elapsed_wall_seconds": elapsed,
    }


def _constraint_digest(ordinal: int, relation: object) -> str:
    if isinstance(relation, Mapping) and isinstance(relation.get("def"), str):
        left = relation["def"]
        right = relation.get("value", "0")
        if not isinstance(right, str):
            right = str(right)
        try:
            return BASE._ast_sha(ordinal, left, right)
        except (SyntaxError, TypeError, ValueError):
            pass
    return _canonical_sha256(
        {"source_constraint_ordinal": ordinal, "raw_record": relation}
    )


def _collect_safe_generators(
    document: Mapping[str, object],
    *,
    started: float,
    timeout_seconds: float,
) -> tuple[object, list[object], list[str], dict[str, int]]:
    lowerer = BASE._SubsetLowerer(document)
    construction_counts = lowerer.construction(document.get("construction", []))
    constraints = document.get("constraints")
    if not isinstance(constraints, list):
        raise BASE.ProofOnlyRejected("source constraints are not a list")
    digests = [_constraint_digest(i, relation) for i, relation in enumerate(constraints)]
    adopted = []
    for ordinal, relation in enumerate(constraints):
        if time.monotonic() - started >= timeout_seconds:
            raise BASE.ProofOnlyRejected("proof deadline exceeded")
        if not isinstance(relation, Mapping) or not isinstance(relation.get("def"), str):
            continue
        left_text = relation["def"]
        right_text = relation.get("value", "0")
        if not isinstance(right_text, str):
            right_text = str(right_text)
        try:
            left = lowerer.scalar(left_text, f"constraint:{ordinal}:left")
            right = lowerer.scalar(right_text, f"constraint:{ordinal}:right")
            if left.zero_equivalent_only or right.zero_equivalent_only:
                if (
                    left.zero_equivalent_only
                    and not right.zero_equivalent_only
                    and right.expression == 0
                ):
                    expression = left.expression
                elif (
                    right.zero_equivalent_only
                    and not left.zero_equivalent_only
                    and left.expression == 0
                ):
                    expression = right.expression
                else:
                    continue
            else:
                expression = sp.expand(left.expression - right.expression)
            polynomial = sp.Poly(expression, *lowerer.symbols, domain=sp.QQ)
            if polynomial.is_zero:
                continue
            if (
                polynomial.total_degree() > BASE.MAX_DEGREE
                or len(polynomial.terms()) > BASE.MAX_TERMS
            ):
                continue
            adopted.append(
                BASE._AdoptedEquation(
                    ordinal=ordinal,
                    expression=polynomial.as_expr(),
                    node_sha256=digests[ordinal],
                    operation_signature=BASE._call_signature(
                        ast.parse(left_text, mode="eval").body
                    ),
                )
            )
        except (
            BASE.EXACT.Unsupported,
            BASE.ProofOnlyRejected,
            SyntaxError,
            TypeError,
            ValueError,
            sp.PolynomialError,
        ):
            continue
    if not adopted:
        raise BASE.ProofOnlyRejected("no safe source equality generator exists")
    if len(adopted) > MAX_SAFE_GENERATOR_CANDIDATES:
        raise BASE.ProofOnlyRejected("safe source equality candidate cap exceeded")
    return lowerer, adopted, digests, construction_counts


def _relevance_order(adopted: Sequence[object], h: sp.Expr) -> list[object]:
    reached = set(h.free_symbols)
    remaining = list(adopted)
    ordered = []
    while remaining:
        connected = [
            item for item in remaining if set(item.expression.free_symbols) & reached
        ]
        if not connected:
            break
        connected.sort(
            key=lambda item: (
                sp.Poly(item.expression).total_degree(),
                len(sp.Poly(item.expression).terms()),
                item.ordinal,
            )
        )
        for item in connected:
            reached.update(item.expression.free_symbols)
            remaining.remove(item)
            ordered.append(item)
    return ordered


def _candidate_subsets(adopted: Sequence[object], h: sp.Expr):
    ranked = _relevance_order(adopted, h)
    seen: set[tuple[int, ...]] = set()
    for item in ranked:
        key = (item.ordinal,)
        seen.add(key)
        yield [item]
    for size in range(2, min(MAX_SELECTED_GENERATORS, len(ranked)) + 1):
        subset = ranked[:size]
        key = tuple(item.ordinal for item in subset)
        if key not in seen:
            seen.add(key)
            yield subset
    if len(ranked) > MAX_SELECTED_GENERATORS:
        for start in range(1, len(ranked) - MAX_SELECTED_GENERATORS + 1):
            subset = ranked[start : start + MAX_SELECTED_GENERATORS]
            key = tuple(item.ordinal for item in subset)
            if key not in seen:
                seen.add(key)
                yield subset


def _attempt_identity(
    subset: Sequence[object],
    h: sp.Expr,
    symbols: Sequence[sp.Symbol],
) -> dict[str, object] | None:
    equations = [item.expression for item in subset]
    basis = sp.groebner(equations, *symbols, order="grevlex", domain=sp.QQ)
    if any(
        polynomial.total_degree() == 0 and not polynomial.is_zero
        for polynomial in basis.polys
    ):
        return None
    basis_expressions = [item.as_expr() for item in basis.polys]
    for power in (1, 2):
        relation = sp.expand(h**power)
        polynomial = sp.Poly(relation, *symbols, domain=sp.QQ)
        if (
            polynomial.total_degree() > MAX_POWERED_DEGREE
            or len(polynomial.terms()) > MAX_POWERED_TERMS
        ):
            continue
        quotients, remainder = basis.reduce(relation)
        remainder = sp.expand(remainder)
        if remainder != 0:
            continue
        if sp.expand(
            sum(q * b for q, b in zip(quotients, basis_expressions)) - relation
        ) != 0:
            continue
        cofactors = BASE._cofactor_witness(equations, relation, symbols)
        if cofactors is None:
            continue
        return {
            "radical_power": power,
            "relation": relation,
            "basis": basis_expressions,
            "basis_quotients": quotients,
            "cofactors": cofactors,
        }
    return None


def _prove_document(
    document: object,
    *,
    source_sha256: str,
    rational_target: Fraction,
    candidate_relation: Mapping[str, object],
    ordinary_proposal_sha256: str,
    timeout_seconds: float,
) -> dict[str, object]:
    started = time.monotonic()
    try:
        if not isinstance(document, Mapping) or document.get("task") != "solve":
            raise BASE.ProofOnlyRejected("raw solve source is required")
        if document.get("post_process") not in (None, ""):
            raise BASE.ProofOnlyRejected("raw target with no post-process is required")
        lowerer, adopted, constraint_digests, construction_counts = (
            _collect_safe_generators(
                document, started=started, timeout_seconds=timeout_seconds
            )
        )
        target = lowerer.scalar(document.get("answer"), "raw-target")
        if target.zero_equivalent_only and rational_target != 0:
            raise BASE.ProofOnlyRejected("zero-equivalent target can prove only q=0")
        h = sp.expand(
            target.expression
            - sp.Rational(rational_target.numerator, rational_target.denominator)
        )
        selected = None
        witness = None
        for subset in _candidate_subsets(adopted, h):
            if time.monotonic() - started >= timeout_seconds:
                raise BASE.ProofOnlyRejected("proof deadline exceeded")
            trial = _attempt_identity(subset, h, lowerer.symbols)
            if trial is not None:
                selected, witness = list(subset), trial
                break
        if selected is None or witness is None:
            raise BASE.ProofOnlyRejected(
                "bounded subset search has nonzero exact remainder"
            )
        elapsed = time.monotonic() - started
        if elapsed > timeout_seconds:
            raise BASE.ProofOnlyRejected("proof deadline exceeded")

        selected_ordinals = [item.ordinal for item in selected]
        selected_set = set(selected_ordinals)
        excluded_ordinals = [
            ordinal
            for ordinal in range(len(constraint_digests))
            if ordinal not in selected_set
        ]
        power = int(witness["radical_power"])
        statement = {
            "theorem": (
                "SOURCE_EQUALITY_SUBSET_DIRECT_ZERO"
                if power == 1
                else "REAL_RADICAL_SQUARE_ZERO_IMPLIES_ZERO"
            ),
            "source_sha256": source_sha256,
            "ordinary_proposal_sha256": ordinary_proposal_sha256,
            "candidate_relation": dict(candidate_relation),
            "all_constraint_ast_digests": constraint_digests,
            "all_constraint_ast_ledger_sha256": _canonical_sha256(
                constraint_digests
            ),
            "selected_constraint_ordinals": selected_ordinals,
            "selected_source_node_hashes": [item.node_sha256 for item in selected],
            "excluded_constraint_ordinals": excluded_ordinals,
            "excluded_source_node_hashes": [
                constraint_digests[index] for index in excluded_ordinals
            ],
            "source_variables": list(lowerer.names),
            "selected_source_generators": [str(item.expression) for item in selected],
            "raw_target_minus_q": str(h),
            "radical_power": power,
            "powered_target_relation": str(witness["relation"]),
            "groebner_basis": [str(item) for item in witness["basis"]],
            "basis_reduction_quotients": [
                str(item) for item in witness["basis_quotients"]
            ],
            "source_equation_cofactors": [str(item) for item in witness["cofactors"]],
            "exact_powered_remainder": "0",
            "excluded_constraints_used_in_identity": False,
            "full_source_typed_root_required": True,
        }
        return {
            "schema_version": SCHEMA,
            "status": "BOUND_SUBSET_IDENTITY_PROVED_HOLD",
            "reason": "h or h^2 proved from an explicitly bound source equality subset",
            "source_sha256": source_sha256,
            "ordinary_proposal_sha256": ordinary_proposal_sha256,
            "candidate_relation": dict(candidate_relation),
            "authority_pass": False,
            "target_release": False,
            "proof_only": True,
            "radical_power": power,
            "real_zero_implication": True,
            "regular_root_evidence_required": True,
            "full_source_typed_root_required": True,
            "excluded_constraints_used_in_identity": False,
            "all_constraint_ast_ledger_sha256": statement[
                "all_constraint_ast_ledger_sha256"
            ],
            "selected_constraint_ordinals": selected_ordinals,
            "selected_source_node_hashes": [item.node_sha256 for item in selected],
            "excluded_constraint_ordinals": excluded_ordinals,
            "excluded_source_node_hashes": [
                constraint_digests[index] for index in excluded_ordinals
            ],
            "safe_generator_candidate_count": len(adopted),
            "selected_generator_count": len(selected),
            "construction_counts": construction_counts,
            "exact_powered_remainder": "0",
            "cofactor_witness_complete": True,
            "statement": statement,
            "statement_sha256": _canonical_sha256(statement),
            "anonymous_structure_signature": {
                "variable_count": len(lowerer.symbols),
                "safe_generator_candidate_count": len(adopted),
                "selected_generator_count": len(selected),
                "excluded_constraint_count": len(excluded_ordinals),
                "radical_power": power,
            },
            "truth_used": False,
            "elapsed_wall_seconds": elapsed,
        }
    except Exception as error:
        reason = (
            str(error)
            if isinstance(error, (BASE.ProofOnlyRejected, BASE.EXACT.Unsupported))
            else f"{type(error).__name__}: {error}"
        )
        return _unproved(
            reason,
            source_sha256=source_sha256,
            elapsed=time.monotonic() - started,
        )


def prove_bound_subset_identity(
    source_path: Path,
    *,
    ordinary_proposal: Mapping[str, object],
    timeout_seconds: float = 3.0,
) -> dict[str, object]:
    started = time.monotonic()
    try:
        payload = source_path.read_bytes()
        source_sha256 = _sha256_bytes(payload)
        document = json.loads(payload)
        if not (
            isinstance(ordinary_proposal, Mapping)
            and ordinary_proposal.get("status") == "TARGET_AUTHORITY_READY"
            and ordinary_proposal.get("authority_pass") is True
        ):
            raise BASE.ProofOnlyRejected("existing ordinary HP proposal is not ready")
        rational_target, candidate_relation = BASE.rational_candidate_from_descriptor(
            ordinary_proposal.get("descriptor")
        )
        remaining = timeout_seconds - (time.monotonic() - started)
        if remaining <= 0:
            raise BASE.ProofOnlyRejected("proof deadline exceeded")
        return _prove_document(
            document,
            source_sha256=source_sha256,
            rational_target=rational_target,
            candidate_relation=candidate_relation,
            ordinary_proposal_sha256=_canonical_sha256(ordinary_proposal),
            timeout_seconds=remaining,
        )
    except Exception as error:
        reason = (
            str(error)
            if isinstance(error, BASE.ProofOnlyRejected)
            else f"{type(error).__name__}: {error}"
        )
        source_sha256 = (
            _sha256_bytes(source_path.read_bytes())
            if source_path.is_file()
            else "UNAVAILABLE"
        )
        return _unproved(
            reason,
            source_sha256=source_sha256,
            elapsed=time.monotonic() - started,
        )


def verify_bound_subset_proof(
    source_path: Path,
    *,
    ordinary_proposal: Mapping[str, object],
    artifact: Mapping[str, object],
    timeout_seconds: float = 3.0,
) -> None:
    replayed = prove_bound_subset_identity(
        source_path,
        ordinary_proposal=ordinary_proposal,
        timeout_seconds=timeout_seconds,
    )
    if replayed.get("status") != "BOUND_SUBSET_IDENTITY_PROVED_HOLD":
        raise BASE.ProofOnlyRejected("bound subset identity does not replay")
    mandatory = (
        "schema_version",
        "status",
        "source_sha256",
        "ordinary_proposal_sha256",
        "candidate_relation",
        "radical_power",
        "real_zero_implication",
        "all_constraint_ast_ledger_sha256",
        "selected_constraint_ordinals",
        "selected_source_node_hashes",
        "excluded_constraint_ordinals",
        "excluded_source_node_hashes",
        "excluded_constraints_used_in_identity",
        "exact_powered_remainder",
        "cofactor_witness_complete",
        "statement",
        "statement_sha256",
    )
    if any(artifact.get(key) != replayed.get(key) for key in mandatory):
        raise BASE.ProofOnlyRejected("bound subset proof differs from exact replay")
    statement = artifact.get("statement")
    if not isinstance(statement, Mapping) or _canonical_sha256(
        statement
    ) != artifact.get("statement_sha256"):
        raise BASE.ProofOnlyRejected("bound subset statement digest is invalid")
    if (
        artifact.get("authority_pass") is not False
        or artifact.get("target_release") is not False
        or artifact.get("excluded_constraints_used_in_identity") is not False
    ):
        raise BASE.ProofOnlyRejected("bound subset proof violates HOLD boundary")


__all__ = [
    "RADICAL_SHA256",
    "prove_bound_subset_identity",
    "verify_bound_subset_proof",
]
