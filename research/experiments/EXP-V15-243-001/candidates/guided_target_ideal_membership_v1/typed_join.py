#!/usr/bin/env python3
"""Three-way experimental join; deliberately emits no target authority."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

from ideal_membership import rational_candidate_from_descriptor, verify_subset_proof


RUNTIME_ROOT = Path(
    os.environ.get(
        "GEOTARGET_CURRENT_RUNTIME_ROOT",
        "/home/kabatan/work/solver-experiment-runtime/solver",
    )
).resolve()
TYPED_ROOT = (
    RUNTIME_ROOT
    / "research/experiments/EXP-V15-243-001/candidates/"
    "typed_guard_algebraic_extension"
)
TYPED_ADAPTER = TYPED_ROOT / "typed_guard_adapter.py"
LOCAL_ADAPTER = TYPED_ROOT / "local_worker_adapter.py"
TYPED_ADAPTER_SHA256 = "1d93005c49cf4e3360b8b64449022be46e97ae59cc437ef889f5289e239709b4"
LOCAL_ADAPTER_SHA256 = "711a14c9bcce7bd99c770768199f4b778b819434b1bcf0b9454024d0cea68150"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


if _sha256(TYPED_ADAPTER) != TYPED_ADAPTER_SHA256 or _sha256(LOCAL_ADAPTER) != LOCAL_ADAPTER_SHA256:
    raise RuntimeError("audited typed regular-root compiler closure changed")
_prior = sys.modules.get("typed_guard_adapter")
TYPED = _load("typed_guard_adapter", TYPED_ADAPTER)
LOCAL = _load("guided_target_typed_local_adapter", LOCAL_ADAPTER)
if _prior is None:
    del sys.modules["typed_guard_adapter"]
else:
    sys.modules["typed_guard_adapter"] = _prior


def prepare_typed_regular_job(source_path: Path, endpoint: Sequence[float]) -> dict[str, Any]:
    """Use the independently audited non-recursive source-root compiler."""

    job = LOCAL.prepare_source_certificate_job(source_path, endpoint)
    system = job.get("system")
    if not (
        job.get("schema_version") == "geotarget.typed-guard-source-certificate-job/v2"
        and job.get("authority") == "SOURCE_ROOT_AND_TYPED_GUARDS_ONLY_NO_TARGET_AUTHORITY"
        and job.get("target_read") is False
        and job.get("truth_used") is False
        and isinstance(system, Mapping)
        and system.get("source_target_not_read") is True
        and system.get("replay_obligations") == []
        and system.get("reconstruction") == []
        and system.get("target_expression_text") == "0"
        and system.get("typed_guard_adapter_sha256") == TYPED_ADAPTER_SHA256
    ):
        raise ValueError("typed regular-root job violates the audited non-target boundary")
    return job


def source_only_readiness(source_path: Path, endpoint: Sequence[float]) -> dict[str, object]:
    """Return an anonymous structural signature; never target or identity."""

    job = prepare_typed_regular_job(source_path, endpoint)
    system = job["system"]
    predicates = system["predicates"]
    return {
        "ready": True,
        "anonymous_signature": {
            "variable_count": len(system["variables"]),
            "equation_count": len(system["equations"]),
            "predicate_count": len(predicates),
            "strict_predicate_present": bool(predicates),
        },
        "target_read": False,
        "truth_used": False,
    }


def verify_three_way_join(
    *,
    source_path: Path,
    job: Mapping[str, Any],
    certificate: Mapping[str, Any],
    subset_proof: Mapping[str, Any],
    ordinary_proposal: Mapping[str, Any],
) -> dict[str, object]:
    """Verify the three conjuncts and return experimental readiness only."""

    base = {
        "authority_pass": False,
        "target_release": False,
        "common_worker_integration": "HOLD",
        "truth_used": False,
    }
    try:
        verify_subset_proof(
            source_path,
            ordinary_proposal=ordinary_proposal,
            artifact=subset_proof,
            timeout_seconds=3.0,
        )
        if not (
            ordinary_proposal.get("status") == "TARGET_AUTHORITY_READY"
            and ordinary_proposal.get("authority_pass") is True
            and isinstance(ordinary_proposal.get("descriptor"), Mapping)
        ):
            raise ValueError("existing ordinary HP proposal is not ready")
        if subset_proof.get("ordinary_proposal_sha256") != _canonical_sha256(
            ordinary_proposal
        ):
            raise ValueError("ordinary HP proposal is not proof-bound")
        rational_target, candidate_relation = rational_candidate_from_descriptor(
            ordinary_proposal["descriptor"]
        )
        if subset_proof.get("candidate_relation") != candidate_relation:
            raise ValueError("degree-one candidate relation is not proof-bound")
        source_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()
        if subset_proof.get("source_sha256") != source_sha256:
            raise ValueError("subset proof/source binding mismatch")
        LOCAL.verify_source_certificate_binding(
            source_path, dict(job), dict(certificate)
        )
        system = job.get("system")
        if not (
            job.get("authority") == "SOURCE_ROOT_AND_TYPED_GUARDS_ONLY_NO_TARGET_AUTHORITY"
            and job.get("source_sha256") == source_sha256
            and job.get("target_read") is False
            and isinstance(system, Mapping)
            and system.get("source_target_not_read") is True
            and system.get("replay_obligations") == []
            and system.get("reconstruction") == []
            and certificate.get("schema_version") == "geotarget.local-krawczyk-certificate/v1"
            and certificate.get("status") == "VERIFIED"
            and certificate.get("source_sha256") == source_sha256
            and certificate.get("unique_regular_root_in_rational_box") is True
            and certificate.get("strict_krawczyk_inclusion") is True
            and certificate.get("all_source_predicates_interval_valid") is True
            and certificate.get("target_equality_requires_exact_link") is True
            and certificate.get("coverage") == "UNKNOWN"
        ):
            raise ValueError("typed regular-root/guard certificate is incomplete")
        statement = {
            "source_sha256": source_sha256,
            "typed_job_sha256": job.get("job_sha256"),
            "typed_system_sha256": job.get("system_sha256"),
            "subset_statement_sha256": subset_proof.get("statement_sha256"),
            "ordinary_degree_one_relation": candidate_relation,
            "unique_real_root_ordinal": 0,
            "rational_target": str(rational_target),
        }
        return {
            **base,
            "status": "THREE_WAY_JOIN_READY_EXPERIMENTAL",
            "typed_regular_root_and_guards": True,
            "subset_universal_target_identity": True,
            "degree_one_unique_real_root_ordinal": True,
            "experimental_three_way_join_verified": True,
            "all_target_authority_conjuncts_present": False,
            "authority_policy_review_required": True,
            "join_statement": statement,
            "join_statement_sha256": hashlib.sha256(
                json.dumps(statement, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        }
    except Exception as error:
        return {
            **base,
            "status": "THREE_WAY_JOIN_HOLD",
            "reason": str(error),
            "experimental_three_way_join_verified": False,
            "all_target_authority_conjuncts_present": False,
        }


__all__ = [
    "LOCAL_ADAPTER_SHA256",
    "TYPED_ADAPTER_SHA256",
    "prepare_typed_regular_job",
    "source_only_readiness",
    "verify_three_way_join",
]
