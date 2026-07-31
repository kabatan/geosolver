#!/usr/bin/env python3
"""Join an exact target-image upper bound with one exact witness per real root."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import sympy as sp


HERE = Path(__file__).resolve().parent
UPPER_PATH = HERE.parent / "multi_target_sparse_cofactor_identity_v1" / "candidate.py"
UPPER_SHA256 = "0df1332185f3e0f1195cabb0cbe657b8f040bf0d04a2b2ebb37b702a407156b5"
SCHEMA = "geotarget.squarefree-image-all-real-root-witness-join/v1"


def canonical_sha256(document: object) -> str:
    return hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _load_upper() -> Any:
    if hashlib.sha256(UPPER_PATH.read_bytes()).hexdigest() != UPPER_SHA256:
        raise RuntimeError("frozen sparse-cofactor upper-bound candidate changed")
    spec = importlib.util.spec_from_file_location("geotarget_sparse_upper_frozen", UPPER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load sparse-cofactor upper-bound candidate")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _root_specifications(
    factors_high_to_low: Sequence[Sequence[int]],
    product_high_to_low: Sequence[int],
) -> list[dict[str, object]]:
    target = sp.Symbol("target")
    factors = [sp.Poly.from_list(list(item), gens=target, domain=sp.ZZ) for item in factors_high_to_low]
    product = sp.Poly.from_list(list(product_high_to_low), gens=target, domain=sp.ZZ)
    product_roots = product.real_roots()
    specifications: list[dict[str, object]] = []
    for product_index, root in enumerate(product_roots):
        owners = [index for index, factor in enumerate(factors) if sp.simplify(factor.as_expr().subs(target, root)) == 0]
        if len(owners) != 1:
            raise ValueError("real root must belong to exactly one distinct irreducible factor")
        factor_index = owners[0]
        factor_roots = factors[factor_index].real_roots()
        matching = [index for index, item in enumerate(factor_roots) if sp.simplify(item - root) == 0]
        if len(matching) != 1:
            raise ValueError("factor real-root ordinal is ambiguous")
        specifications.append(
            {
                "product_real_root_index": product_index,
                "factor_index": factor_index,
                "factor_coefficients_high_to_low": [int(item) for item in factors[factor_index].all_coeffs()],
                "factor_real_root_index": matching[0],
                "exact_root": root,
            }
        )
    return specifications


def certify_complete_target_image(
    *,
    variables: Sequence[str],
    active_equations: Sequence[str],
    all_equations: Sequence[str],
    target_expression: str,
    factors_high_to_low: Sequence[Sequence[int]],
    descriptor_artifact_sha256s: Sequence[str],
    source_sha256: str,
    witness_provider: Callable[[Mapping[str, object]], Mapping[str, object] | None],
) -> dict[str, object]:
    upper_module = _load_upper()
    upper = upper_module.prove_multi_target_identity(
        variables=variables,
        active_equations=active_equations,
        all_equations=all_equations,
        target_expression=target_expression,
        factors_high_to_low=factors_high_to_low,
        descriptor_artifact_sha256s=descriptor_artifact_sha256s,
        source_sha256=source_sha256,
    )
    if upper.get("status") != "IDENTITY_VERIFIED" or upper.get("exact_identity_verified") is not True:
        return {
            "schema_version": SCHEMA,
            "status": "NOT_CERTIFIED",
            "reason": "target-image-upper-bound-not-proved",
            "upper_bound_verified": False,
            "all_real_roots_witnessed": False,
            "completeness_certificate_ready": False,
            "target_release": False,
        }

    canonical_factors = [upper_module._canonical_factor(item) for item in factors_high_to_low]
    bound_pairs = sorted(zip(canonical_factors, descriptor_artifact_sha256s, strict=True))
    ordered_factors = [item[0] for item in bound_pairs]
    specifications = _root_specifications(
        ordered_factors, upper["product_coefficients_high_to_low"]
    )
    witness_artifacts: list[str] = []
    for specification in specifications:
        public_specification = {key: value for key, value in specification.items() if key != "exact_root"}
        witness = witness_provider(specification)
        if not isinstance(witness, Mapping):
            return {
                "schema_version": SCHEMA,
                "status": "NOT_CERTIFIED",
                "reason": "real-root-witness-missing",
                "missing_product_real_root_index": specification["product_real_root_index"],
                "upper_bound_verified": True,
                "all_real_roots_witnessed": False,
                "completeness_certificate_ready": False,
                "target_release": False,
            }
        body = dict(witness)
        artifact_sha256 = body.pop("artifact_sha256", None)
        required = {
            "source_sha256": source_sha256,
            "system_sha256": upper["system_sha256"],
            "descriptor_set_sha256": upper["descriptor_set_sha256"],
            **public_specification,
            "exact_source_guard_branch_raw_target_replay": True,
            "target_equals_selected_root": True,
            "truth_used": False,
            "target_set_completeness_claim": False,
        }
        if any(body.get(key) != value for key, value in required.items()):
            return {
                "schema_version": SCHEMA,
                "status": "NOT_CERTIFIED",
                "reason": "real-root-witness-contract-failed",
                "upper_bound_verified": True,
                "all_real_roots_witnessed": False,
                "completeness_certificate_ready": False,
                "target_release": False,
            }
        if artifact_sha256 != canonical_sha256(body) or artifact_sha256 in witness_artifacts:
            return {
                "schema_version": SCHEMA,
                "status": "NOT_CERTIFIED",
                "reason": "real-root-witness-artifact-invalid",
                "upper_bound_verified": True,
                "all_real_roots_witnessed": False,
                "completeness_certificate_ready": False,
                "target_release": False,
            }
        witness_artifacts.append(artifact_sha256)

    certificate_body = {
        "source_sha256": source_sha256,
        "system_sha256": upper["system_sha256"],
        "descriptor_set_sha256": upper["descriptor_set_sha256"],
        "upper_bound_artifact_sha256": upper["exact_link_artifact_sha256"],
        "real_root_count": len(specifications),
        "witness_artifact_sha256s": witness_artifacts,
    }
    return {
        "schema_version": SCHEMA,
        "status": "COMPLETE_TARGET_IMAGE_CERTIFICATE_READY",
        "upper_bound_verified": True,
        "all_real_roots_witnessed": True,
        "real_root_count": len(specifications),
        "witness_count": len(witness_artifacts),
        "certificate_sha256": canonical_sha256(certificate_body),
        "completeness_certificate_ready": True,
        "target_set_completeness_claim": True,
        "truth_used": False,
        "target_release": False,
        "canonical_outer_release_required": True,
    }


__all__ = ["canonical_sha256", "certify_complete_target_image"]
