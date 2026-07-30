"""Fresh source-digest and semantic-artifact replay after D0 verification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from repair_adapter import (
    AdapterFailure,
    build_problem,
    load_pinned_algebraic_compiler,
    load_pinned_semantic_lift,
)
from verifier import VerificationFailure, verify


def _canonical_sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def verify_untouched_replay(
    *,
    source: Path,
    source_sha256: str,
    descriptor: Mapping[str, Any],
    expected_binding: Mapping[str, Any],
    certificate: Mapping[str, Any],
) -> dict[str, Any]:
    """Re-read and recompile the exact source; no endpoint is an authority."""

    try:
        raw = source.read_bytes()
        observed_source_sha = hashlib.sha256(raw).hexdigest()
        if observed_source_sha != source_sha256:
            raise AdapterFailure("fresh-source-digest-mismatch")
        document = json.loads(raw)
        if not isinstance(document, Mapping):
            raise AdapterFailure("fresh-source-not-object")
        semantic = load_pinned_semantic_lift(fresh_name="geotarget_repair_a_semantic_lift_replay")
        algebraic = load_pinned_algebraic_compiler(
            fresh_name="geotarget_repair_a_algebraic_compiler_replay"
        )
        semantic_artifact = semantic.compile_document(document)
        algebraic_artifact = algebraic.compile_document(document)
        fresh_problem, fresh_binding = build_problem(
            algebraic_artifact, semantic_artifact, descriptor
        )
        fields = {
            "semantic_lift_sha256",
            "algebraic_compiler_sha256",
            "semantic_source_sha256",
            "semantic_artifact_sha256",
            "algebraic_artifact_sha256",
            "target_descriptor_identity",
            "predicate_count",
            "predicate_mapping",
            "definedness_count",
            "definedness_ledger_sha256",
            "raw_target_link_sha256",
            "d0_problem_sha256",
            "phase_sheet_obligations_dropped",
            "selector_obligations_dropped",
            "typed_predicates_dropped",
            "definedness_entries_dropped",
        }
        if {field: fresh_binding.get(field) for field in fields} != {
            field: expected_binding.get(field) for field in fields
        }:
            raise AdapterFailure("fresh-semantic-binding-mismatch")
        if fresh_binding["semantic_artifact_sha256"] != _canonical_sha(semantic_artifact.to_data()):
            raise AdapterFailure("fresh-semantic-artifact-digest-mismatch")
        if fresh_binding["algebraic_artifact_sha256"] != _canonical_sha(algebraic_artifact.to_data()):
            raise AdapterFailure("fresh-algebraic-artifact-digest-mismatch")
        independent = verify(fresh_problem, certificate)
        return {
            "verified": independent.get("verified") is True,
            "source_sha256": observed_source_sha,
            "semantic_source_sha256": semantic_artifact.semantic_source_sha256,
            "semantic_artifact_sha256": fresh_binding["semantic_artifact_sha256"],
            "algebraic_artifact_sha256": fresh_binding["algebraic_artifact_sha256"],
            "d0_problem_sha256": fresh_binding["d0_problem_sha256"],
            "raw_target_replayed": True,
            "all_typed_predicates_replayed": fresh_binding["typed_predicates_dropped"] == 0,
            "all_definedness_replayed": fresh_binding["definedness_entries_dropped"] == 0,
            "source_or_problem_modified": False,
            "endpoint_used_as_authority": False,
        }
    except Exception as error:  # noqa: BLE001 - independent replay is fail closed
        reason = getattr(error, "reason", None)
        if not isinstance(reason, str) or not reason:
            reason = str(error) or f"unsupported-exception:{type(error).__name__}"
        return {"verified": False, "reason": reason}


__all__ = ["verify_untouched_replay"]
