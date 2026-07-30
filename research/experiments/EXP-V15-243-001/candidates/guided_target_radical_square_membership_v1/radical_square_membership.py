#!/usr/bin/env python3
"""Proof-only repair: certify ``(raw_target - q)^2`` in a source ideal.

At every real source solution, an exact identity ``h^2 = 0`` implies ``h = 0``.
This module proves that narrow implication only.  It never proves root
existence, guards, target-set completeness, or target authority.
"""

from __future__ import annotations

import ast
from fractions import Fraction
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
from typing import Any, Mapping

import sympy as sp


HERE = Path(__file__).resolve().parent
BASE_PATH = HERE.parent / "guided_target_ideal_membership_v1/ideal_membership.py"
BASE_SHA256 = "74915d163e471df9e745735a8f5e3f7a128950d72c94d581c6435ffd081b60b4"
SCHEMA = "geotarget.guided-target-radical-square-proof/v1"
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


if _sha256_bytes(BASE_PATH.read_bytes()) != BASE_SHA256:
    raise RuntimeError("frozen direct ideal-membership dependency changed")
_spec = importlib.util.spec_from_file_location(
    "guided_target_frozen_direct_ideal_membership", BASE_PATH
)
if _spec is None or _spec.loader is None:
    raise ImportError(BASE_PATH)
BASE = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = BASE
_spec.loader.exec_module(BASE)


def _failure_class(reason: str) -> str:
    if "post-process" in reason:
        return "POST_PROCESS_OUTSIDE_RAW_TARGET_THEOREM"
    if "remainder is nonzero" in reason:
        return "POWERED_REMAINDER_NONZERO"
    if "unit" in reason or "inconsistent" in reason:
        return "INCONSISTENT_UNIT_IDEAL"
    if "cofactor" in reason:
        return "COFACTOR_WITNESS_UNAVAILABLE"
    if "deadline" in reason:
        return "PROOF_DEADLINE"
    if "target" in reason:
        return "TARGET_OUTSIDE_SAFE_POLYNOMIAL_SUBSET"
    if "equality count" in reason or "constraint" in reason:
        return "SOURCE_EQUALITIES_OUTSIDE_SAFE_SUBSET"
    if "descriptor" in reason or "proposal" in reason or "isolator" in reason:
        return "DEGREE_ONE_PROPOSAL_REJECTED"
    if "cap" in reason:
        return "POWERED_POLYNOMIAL_CAP"
    return "OTHER_FAIL_CLOSED"


def _unproved(
    reason: str, *, source_sha256: str, elapsed: float
) -> dict[str, object]:
    return {
        "schema_version": SCHEMA,
        "status": "RADICAL_SQUARE_IDENTITY_NOT_PROVED",
        "failure_class": _failure_class(reason),
        "source_sha256": source_sha256,
        "authority_pass": False,
        "target_release": False,
        "radical_power": 2,
        "regular_root_evidence_required": True,
        "guards_branches_definedness_proved": False,
        "truth_used": False,
        "elapsed_wall_seconds": elapsed,
    }


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
        lowerer = BASE._SubsetLowerer(document)
        construction_counts = lowerer.construction(document.get("construction", []))
        constraints = document.get("constraints")
        if not isinstance(constraints, list):
            raise BASE.ProofOnlyRejected("source constraints are not a list")
        adopted = []
        for ordinal, relation in enumerate(constraints):
            if time.monotonic() - started >= timeout_seconds:
                raise BASE.ProofOnlyRejected("proof deadline exceeded")
            if not isinstance(relation, Mapping) or not isinstance(
                relation.get("def"), str
            ):
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
                        node_sha256=BASE._ast_sha(ordinal, left_text, right_text),
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
        if not 1 <= len(adopted) <= BASE.MAX_ADOPTED_EQUATIONS:
            raise BASE.ProofOnlyRejected(
                "adopted exact equality count is outside radical-square v1"
            )

        target = lowerer.scalar(document.get("answer"), "raw-target")
        if target.zero_equivalent_only and rational_target != 0:
            raise BASE.ProofOnlyRejected("zero-equivalent target can prove only q=0")
        h = sp.expand(
            target.expression
            - sp.Rational(rational_target.numerator, rational_target.denominator)
        )
        powered_relation = sp.expand(h**2)
        powered_polynomial = sp.Poly(
            powered_relation, *lowerer.symbols, domain=sp.QQ
        )
        if (
            powered_polynomial.total_degree() > MAX_POWERED_DEGREE
            or len(powered_polynomial.terms()) > MAX_POWERED_TERMS
        ):
            raise BASE.ProofOnlyRejected("radical-square powered polynomial cap exceeded")

        equations = [item.expression for item in adopted]
        basis = sp.groebner(
            equations, *lowerer.symbols, order="grevlex", domain=sp.QQ
        )
        if any(
            polynomial.total_degree() == 0 and not polynomial.is_zero
            for polynomial in basis.polys
        ):
            raise BASE.ProofOnlyRejected("adopted subset ideal is inconsistent/unit")
        basis_quotients, remainder = basis.reduce(powered_relation)
        remainder = sp.expand(remainder)
        if remainder != 0:
            return _unproved(
                "exact powered remainder is nonzero",
                source_sha256=source_sha256,
                elapsed=time.monotonic() - started,
            )
        basis_expressions = [item.as_expr() for item in basis.polys]
        if sp.expand(
            sum(q * b for q, b in zip(basis_quotients, basis_expressions))
            + remainder
            - powered_relation
        ) != 0:
            raise BASE.ProofOnlyRejected(
                "powered basis reduction witness failed exact replay"
            )
        cofactors = BASE._cofactor_witness(
            equations, powered_relation, lowerer.symbols
        )
        if cofactors is None:
            raise BASE.ProofOnlyRejected(
                "bounded powered source-equation cofactor witness unavailable"
            )
        elapsed = time.monotonic() - started
        if elapsed > timeout_seconds:
            raise BASE.ProofOnlyRejected("proof deadline exceeded")

        statement = {
            "theorem": "REAL_RADICAL_SQUARE_ZERO_IMPLIES_ZERO",
            "source_sha256": source_sha256,
            "ordinary_proposal_sha256": ordinary_proposal_sha256,
            "candidate_relation": dict(candidate_relation),
            "radical_power": 2,
            "source_variables_are_real": True,
            "source_variables": list(lowerer.names),
            "adopted_source_node_hashes": [item.node_sha256 for item in adopted],
            "adopted_equations": [str(item.expression) for item in adopted],
            "raw_target_minus_q": str(h),
            "powered_target_relation": str(powered_relation),
            "groebner_basis": [str(item) for item in basis_expressions],
            "basis_reduction_quotients": [str(item) for item in basis_quotients],
            "source_equation_cofactors": [str(item) for item in cofactors],
            "exact_powered_remainder": "0",
        }
        return {
            "schema_version": SCHEMA,
            "status": "RADICAL_SQUARE_IDENTITY_PROVED_HOLD",
            "reason": "h^2 is a source-ideal consequence; real h^2=0 implies h=0",
            "source_sha256": source_sha256,
            "ordinary_proposal_sha256": ordinary_proposal_sha256,
            "candidate_relation": dict(candidate_relation),
            "authority_pass": False,
            "target_release": False,
            "proof_only": True,
            "radical_power": 2,
            "real_zero_implication": True,
            "regular_root_evidence_required": True,
            "guards_branches_definedness_proved": False,
            "adopted_source_node_hashes": [item.node_sha256 for item in adopted],
            "adopted_equation_count": len(adopted),
            "ignored_constraint_count": len(constraints) - len(adopted),
            "construction_counts": construction_counts,
            "groebner_basis_size": len(basis_expressions),
            "exact_powered_remainder": "0",
            "cofactor_witness_complete": True,
            "statement": statement,
            "statement_sha256": _canonical_sha256(statement),
            "anonymous_structure_signature": {
                "variable_count": len(lowerer.symbols),
                "adopted_equation_count": len(adopted),
                "maximum_equation_degree": max(
                    sp.Poly(item.expression, *lowerer.symbols).total_degree()
                    for item in adopted
                ),
                "target_degree": sp.Poly(h, *lowerer.symbols).total_degree(),
                "radical_power": 2,
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


def prove_radical_square_identity(
    source_path: Path,
    *,
    ordinary_proposal: Mapping[str, object],
    timeout_seconds: float = 3.0,
) -> dict[str, object]:
    """Read and bind source plus degree-one proposal, then prove h^2 in I."""

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


def verify_radical_square_proof(
    source_path: Path,
    *,
    ordinary_proposal: Mapping[str, object],
    artifact: Mapping[str, object],
    timeout_seconds: float = 3.0,
) -> None:
    """Recompile and exactly replay the radical-square proof artifact."""

    replayed = prove_radical_square_identity(
        source_path,
        ordinary_proposal=ordinary_proposal,
        timeout_seconds=timeout_seconds,
    )
    if replayed.get("status") != "RADICAL_SQUARE_IDENTITY_PROVED_HOLD":
        raise BASE.ProofOnlyRejected("radical-square identity does not replay")
    mandatory = (
        "schema_version",
        "status",
        "source_sha256",
        "ordinary_proposal_sha256",
        "candidate_relation",
        "radical_power",
        "real_zero_implication",
        "adopted_source_node_hashes",
        "adopted_equation_count",
        "exact_powered_remainder",
        "cofactor_witness_complete",
        "statement",
        "statement_sha256",
    )
    if any(artifact.get(key) != replayed.get(key) for key in mandatory):
        raise BASE.ProofOnlyRejected(
            "radical-square proof artifact differs from exact replay"
        )
    statement = artifact.get("statement")
    if not isinstance(statement, Mapping) or _canonical_sha256(
        statement
    ) != artifact.get("statement_sha256"):
        raise BASE.ProofOnlyRejected("radical-square statement digest is invalid")
    if (
        artifact.get("authority_pass") is not False
        or artifact.get("target_release") is not False
    ):
        raise BASE.ProofOnlyRejected("proof-only artifact claims target authority")


__all__ = [
    "BASE_SHA256",
    "prove_radical_square_identity",
    "verify_radical_square_proof",
]
