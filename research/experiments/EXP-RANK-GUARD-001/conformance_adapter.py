#!/usr/bin/env python3
"""Aggregate-only conformance successor for frozen EXP-LOCAL-015 shards.

This script deliberately emits no case identifiers, coordinates, target data,
or per-case outcomes.  It changes no candidate mechanics.  It fixes the old
result-contract defects while keeping real proposal and route disagreements
visible as separate aggregate counters.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


ADAPTED = "GEOTARGET-ADAPTED-128-256-512-CPQR"
WEAK = "WEAK-BRACKET"
COMBINED = "WEAK-THEN-ADAPTIVE"
CANDIDATES = (ADAPTED, WEAK, COMBINED)
REPRESENTATIONS = ("base", "signed_permutation", "orthogonal")


def normalized_ledger(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        raise ValueError("precision ledger must be an object")
    output: dict[str, int] = {}
    for raw_tier, raw_count in value.items():
        tier = str(raw_tier)
        if isinstance(raw_count, bool) or not isinstance(raw_count, int):
            raise ValueError("precision counts must be integers")
        if raw_count < 0:
            raise ValueError("precision counts cannot be negative")
        if raw_count:
            output[tier] = raw_count
    return dict(sorted(output.items()))


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _proposal_signature(row: dict[str, Any]) -> dict[str, Any]:
    assessor = row.get("assessor")
    if not isinstance(assessor, dict):
        raise ValueError("row assessor is missing")
    emission = row.get("emission_kind")
    brackets = row.get("emitted_brackets")
    coordinates = row.get("emitted_seed_coordinates")
    activation = row.get("activation_observables")
    if not isinstance(brackets, list) or not isinstance(coordinates, list):
        raise ValueError("emitted proposal fields must be lists")
    if not isinstance(activation, dict):
        raise ValueError("activation observables must be an object")
    return {
        "activated": any(value is True for value in activation.values()),
        "emission_kind": emission,
        "emitted_bracket_count": len(brackets),
        "emitted_seed_count": len(coordinates),
        "matched_class_count": len(assessor.get("matched_isolated_root_classes", [])),
        "safety_emission": bool(assessor.get("safety_control")) and emission != "none",
        "valid_refinement_seed": bool(assessor.get("valid_refinement_seed")),
    }


def _route_signature(row: dict[str, Any]) -> dict[str, Any]:
    signature = _proposal_signature(row)
    signature.update(
        {
            "activation_observables": row.get("activation_observables"),
            "precision_counts": normalized_ledger(
                row.get("requested_precision_counts")
            ),
            "reason": row.get("reason"),
            "status": row.get("status"),
            "weighted_work": row.get("reported_weighted_work"),
        }
    )
    return signature


def _read_documents(raw_dir: Path) -> list[dict[str, Any]]:
    paths = sorted(raw_dir.glob("case-*.json"))
    if not paths:
        raise ValueError(f"no case shards found under {raw_dir}")
    documents = []
    for path in paths:
        document = json.loads(path.read_text())
        if document.get("experiment_id") != "EXP-LOCAL-015":
            raise ValueError("unexpected experiment id")
        if document.get("nonpromotional_t0") is not True:
            raise ValueError("only nonpromotional T0 shards are accepted")
        if not isinstance(document.get("rows"), list):
            raise ValueError("raw shard rows are missing")
        documents.append(document)
    expected = documents[0].get("case_count")
    if not isinstance(expected, int) or len(documents) != expected:
        raise ValueError(f"expected {expected} shards, found {len(documents)}")
    indices = sorted(document.get("case_index") for document in documents)
    if indices != list(range(1, expected + 1)):
        raise ValueError("case shard indices are incomplete or duplicated")
    return documents


def audit_documents(documents: Iterable[dict[str, Any]]) -> dict[str, Any]:
    documents = list(documents)
    rows_by_key: dict[tuple[str, str, int, str], dict[str, Any]] = {}
    accounting_by_arm: dict[str, Counter[str]] = defaultdict(Counter)
    metrics_by_arm: dict[str, Counter[str]] = defaultdict(Counter)
    revisions: set[str] = set()
    preregistrations: set[str] = set()
    source_sha = hashlib.sha256()

    for document in documents:
        case = document.get("case")
        if not isinstance(case, dict):
            raise ValueError("case metadata is missing")
        class_id = str(case.get("representation_class_id"))
        representation = str(case.get("representation"))
        if representation not in REPRESENTATIONS:
            raise ValueError("representation closure is malformed")
        revision = document.get("revision")
        if not isinstance(revision, dict) or revision.get("git_dirty") is not False:
            raise ValueError("shards must come from a frozen clean revision")
        revisions.add(str(revision.get("git_head")))
        preregistrations.add(canonical(document.get("preregistration")))
        source_sha.update(canonical(document).encode())

        for row in document["rows"]:
            arm = str(row.get("arm"))
            start = row.get("start_index")
            if isinstance(start, bool) or not isinstance(start, int):
                raise ValueError("start index is malformed")
            key = (class_id, representation, start, arm)
            if key in rows_by_key:
                raise ValueError("duplicate class/representation/start/arm row")
            rows_by_key[key] = row

            requested = normalized_ledger(row.get("requested_precision_counts"))
            observed = normalized_ledger(row.get("observed_precision_counts"))
            accounting_by_arm[arm]["precision_mismatch"] += requested != observed
            accounting_by_arm[arm]["exception"] += row.get("exception") is not None
            accounting_by_arm[arm]["callback_mismatch"] += not (
                row.get("charged_callback_count")
                == row.get("observed_callback_count")
                == row.get("reported_callback_count")
                == sum(requested.values())
            )
            assessor = row.get("assessor", {})
            emitted = row.get("emission_kind") != "none"
            metrics_by_arm[arm]["trials"] += 1
            metrics_by_arm[arm]["valid"] += bool(
                assessor.get("valid_refinement_seed")
            )
            metrics_by_arm[arm]["unsupported"] += emitted and not bool(
                assessor.get("valid_refinement_seed")
            )
            metrics_by_arm[arm]["safety_emission"] += emitted and bool(
                assessor.get("safety_control")
            )

    if len(revisions) != 1 or len(preregistrations) != 1:
        raise ValueError("all shards must share one revision and preregistration")

    classes = sorted({key[0] for key in rows_by_key})
    starts_by_class: dict[str, set[int]] = defaultdict(set)
    for class_id, _representation, start, _arm in rows_by_key:
        starts_by_class[class_id].add(start)

    proposal_mismatches: Counter[str] = Counter()
    route_mismatches: Counter[str] = Counter()
    for class_id in classes:
        for start in sorted(starts_by_class[class_id]):
            for arm in CANDIDATES:
                rows = [
                    rows_by_key.get((class_id, representation, start, arm))
                    for representation in REPRESENTATIONS
                ]
                if any(row is None for row in rows):
                    raise ValueError("representation triplet is incomplete")
                proposal_signatures = {canonical(_proposal_signature(row)) for row in rows}
                route_signatures = {canonical(_route_signature(row)) for row in rows}
                proposal_mismatches[arm] += len(proposal_signatures) != 1
                route_mismatches[arm] += len(route_signatures) != 1

    candidates: dict[str, Any] = {}
    for arm in CANDIDATES:
        accounting = accounting_by_arm[arm]
        metrics = metrics_by_arm[arm]
        proposal_disagreement = proposal_mismatches[arm]
        blockers = (
            accounting["precision_mismatch"]
            + accounting["exception"]
            + accounting["callback_mismatch"]
            + metrics["safety_emission"]
            + proposal_disagreement
        )
        candidates[arm] = {
            "classification": (
                "CONFORMANT_SIGNAL" if blockers == 0 else "REPRESENTATION_OR_ACCOUNTING_LIMITED"
            ),
            "precision_mismatch_count": accounting["precision_mismatch"],
            "callback_mismatch_count": accounting["callback_mismatch"],
            "exception_count": accounting["exception"],
            "proposal_representation_mismatch_count": proposal_disagreement,
            "route_representation_mismatch_count": route_mismatches[arm],
            "safety_emission_count": metrics["safety_emission"],
            "trial_count": metrics["trials"],
            "unsupported_seed_count": metrics["unsupported"],
            "valid_refinement_seed_count": metrics["valid"],
        }

    return {
        "schema_version": "geotarget.exp-rank-guard-001-conformance/v1",
        "experiment_id": "EXP-RANK-GUARD-001",
        "source_experiment_id": "EXP-LOCAL-015",
        "source_revision": next(iter(revisions)),
        "source_document_sha256": source_sha.hexdigest(),
        "case_count": len(documents),
        "candidate_local_gating": True,
        "zero_precision_buckets_canonicalized": True,
        "per_case_outcomes_disclosed": False,
        "candidates": candidates,
    }


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    options = _arguments()
    output = audit_documents(_read_documents(options.raw_dir))
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

