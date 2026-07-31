#!/usr/bin/env python3
"""Disposable multi-target ideal-membership proposal.

This candidate changes the proposition tested by the old exact-link worker:
instead of asking whether one discovered target factor vanishes on every
source component, it asks whether the square-free product of every discovered
factor does.  The result is proposal evidence only; witness existence and the
untouched source/guard/target replay remain mandatory downstream.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any, Sequence

import sympy as sp


EXACT_LINK = Path(
    "/home/kabatan/work/solver-experiment-runtime/solver/research/experiments/"
    "EXP-REAL61-004/local_validated_witness/exact_link.py"
)
EXACT_LINK_SHA256 = "cf408f3cc56eecbbb6ed246443d138e1f208c2e0a7c8068f70933b1ac3e17301"
SCHEMA = "geotarget.multi-target-sparse-cofactor-identity/v1"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_exact_link() -> Any:
    if _sha256(EXACT_LINK) != EXACT_LINK_SHA256:
        raise RuntimeError("frozen exact-link implementation changed")
    spec = importlib.util.spec_from_file_location(
        "geotarget_multi_target_frozen_exact_link", EXACT_LINK
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load frozen exact-link implementation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def squarefree_product(
    factors_high_to_low: Sequence[Sequence[int]],
) -> tuple[int, ...]:
    """Return a primitive, positive-leading, square-free integer product."""

    if len(factors_high_to_low) < 2:
        raise ValueError("multi-target gate requires at least two factors")
    target = sp.Symbol("__target")
    product = sp.Poly(1, target, domain=sp.ZZ)
    for coefficients in factors_high_to_low:
        if len(coefficients) < 2:
            raise ValueError("constant target factor")
        if any(not isinstance(item, int) or isinstance(item, bool) for item in coefficients):
            raise ValueError("target coefficients must be integers")
        factor = sp.Poly.from_list(list(coefficients), gens=target, domain=sp.ZZ)
        if factor.is_zero:
            raise ValueError("zero target factor")
        product *= factor
    squarefree = product.sqf_part()
    _content, primitive = squarefree.primitive()
    if primitive.LC() < 0:
        primitive = -primitive
    return tuple(int(item) for item in primitive.all_coeffs())


def prove_multi_target_identity(
    *,
    variables: Sequence[str],
    active_equations: Sequence[str],
    all_equations: Sequence[str],
    target_expression: str,
    factors_high_to_low: Sequence[Sequence[int]],
) -> dict[str, Any]:
    exact_link = _load_exact_link()
    product = squarefree_product(factors_high_to_low)
    proof = exact_link.prove_exact_target_link(
        variables=variables,
        active_equations=active_equations,
        all_equations=all_equations,
        target_expression=target_expression,
        coefficients_high_to_low=product,
    )
    proof_valid = bool(
        proof.get("status") == "VERIFIED" and exact_link.verify_artifact(proof)
    )
    factor_digests = [
        hashlib.sha256(
            json.dumps(list(item), separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        for item in factors_high_to_low
    ]
    return {
        "schema_version": SCHEMA,
        "status": "IDENTITY_VERIFIED" if proof_valid else "NOT_PROVED",
        "proposal_authority": False,
        "target_release": False,
        "target_set_completeness_claim": False,
        "truth_used": False,
        "case_family_target_count_routing": False,
        "factor_count": len(factors_high_to_low),
        "factor_digests": factor_digests,
        "product_degree": len(product) - 1,
        "product_coefficients_high_to_low": list(product),
        "exact_link_sha256": EXACT_LINK_SHA256,
        "exact_link_status": proof.get("status"),
        "exact_link_reason": proof.get("reason"),
        "exact_link_artifact_sha256": proof.get("artifact_sha256"),
        "exact_identity_verified": proof_valid,
        "per_root_existence_required": True,
        "untouched_source_guard_target_replay_required": True,
    }


__all__ = ["prove_multi_target_identity", "squarefree_product"]
