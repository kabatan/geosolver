#!/usr/bin/env python3
"""CPU14 generated D0 for QQbar reconstruction and untouched DSL replay."""

from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile

import applicability
import candidate as backend
from run_degree1_proposal_census import (
    _assess_request,
    _proposal,
    _replay_existing_witness,
)


HERE = Path(__file__).resolve().parent


def _documents():
    return {
        "algebraic-auxiliary": (
            {
                "task": "solve",
                "variables": {"names": ["x"]},
                "construction": [
                    {"name": "A", "expr": "Point(0,0)"},
                    {"name": "B", "expr": "Point(x,0)"},
                ],
                "constraints": [{"def": "Distance(A,B)", "value": "3"}],
                "guards": ["AssumeGt(x,0)"],
                "bounds": [[-10, 10]],
                "answer": "x",
                "post_process": None,
            },
            [1, -3],
            "qqbar_embedding_ready",
        ),
        "periodic-reconstruction": (
            {
                "task": "solve",
                "variables": {"names": ["t"]},
                "construction": [],
                "constraints": [{"def": "cos(t)", "value": "1"}],
                "guards": [],
                "bounds": [[0, 0]],
                "answer": "cos(t)",
                "post_process": None,
            },
            [1, -1],
            "periodic_reconstruction_used",
        ),
        "selector-replay": (
            {
                "task": "solve",
                "variables": {"names": ["x"]},
                "construction": [
                    {"name": "C", "expr": "Circle(Point(0,0),1)"},
                    {"name": "L", "expr": "Line(Point(-2,0),Point(2,0))"},
                    {
                        "name": "P",
                        "expr": "Intersect(C,L,exclude=Point(-1,0))",
                    },
                ],
                "constraints": [],
                "guards": [],
                "answer": "P.x",
                "post_process": None,
            },
            [1, -1],
            "selector_or_branch_ledger_bound",
        ),
    }


def _write(root: Path, label: str, document: object) -> Path:
    path = root / f"{label}.json"
    path.write_text(
        json.dumps(document, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return path


def _witness(document, coefficients):
    source, metadata = applicability._legacy_target_link_source(
        document, include_private_bridge_ledger=True
    )
    witness = backend.prove(source, _proposal(coefficients), timeout_seconds=3.0)
    if witness.get("authority_pass") is not True:
        raise RuntimeError("generated backend witness unavailable")
    return source, witness, metadata["private_bridge_ledger"]


def main() -> int:
    if os.sched_getaffinity(0) != {14}:
        raise RuntimeError("reconstruction generated D0 must be pinned to CPU14")
    documents = _documents()
    with tempfile.TemporaryDirectory(prefix="nra-degree1-reconstruction-") as name:
        root = Path(name)
        positives = {}
        private_boundary = {}
        for label, (document, coefficients, signal) in documents.items():
            path = _write(root, label, document)
            row = _assess_request(
                {
                    "source_path": str(path),
                    "endpoint": [0.0],
                    "candidate_relation_high_to_low": coefficients,
                },
                timeout_seconds=3.0,
            )
            positives[label] = bool(row.get("thin_join_ready") and row.get(signal))
            private_boundary[label] = set(row).isdisjoint(
                {"witness", "target", "descriptor", "source_path"}
            )

        periodic, periodic_coefficients, _signal = documents[
            "periodic-reconstruction"
        ]
        source, witness, bridge = _witness(periodic, periodic_coefficients)
        tampered_bridge = deepcopy(bridge)
        tampered_bridge["reconstruction"][0]["formula"] = (
            "atan2(forged,forged) mod 2*pi"
        )
        unsigned = dict(tampered_bridge)
        del unsigned["bridge_ledger_sha256"]
        tampered_bridge["bridge_ledger_sha256"] = backend._canonical_sha256(
            unsigned
        )
        bridge_tamper_rejected = False
        try:
            _replay_existing_witness(periodic, source, witness, tampered_bridge)
        except Exception:
            bridge_tamper_rejected = True

        auxiliary, auxiliary_coefficients, _signal = documents[
            "algebraic-auxiliary"
        ]
        source, witness, bridge = _witness(auxiliary, auxiliary_coefficients)
        tampered_witness = deepcopy(witness)
        tampered_witness["model_descriptors"]["__nra_raw_target"] = {
            "kind": "Rational",
            "numerator": 4,
            "denominator": 1,
        }
        target_tamper_rejected = False
        try:
            _replay_existing_witness(
                auxiliary, source, tampered_witness, bridge
            )
        except Exception:
            target_tamper_rejected = True

        wrong_path = _write(root, "wrong-proposal", auxiliary)
        wrong = _assess_request(
            {
                "source_path": str(wrong_path),
                "endpoint": [0.0],
                "candidate_relation_high_to_low": [1, -4],
            },
            timeout_seconds=3.0,
        )

    aggregate = {
        "schema_version": "geotarget.target-constrained-nra-reconstruction-generated/v1",
        "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "positive_routes": positives,
        "positive_pass_count": sum(positives.values()),
        "positive_total": len(positives),
        "private_rows_emit_no_witness_target_descriptor_or_path": all(
            private_boundary.values()
        ),
        "reconstruction_ledger_tamper_rejected": bridge_tamper_rejected,
        "backend_target_descriptor_tamper_rejected": target_tamper_rejected,
        "wrong_degree_one_proposal_rejected": wrong.get("thin_join_ready") is False,
        "external_authority_event_count": 0,
        "external_target_release_event_count": 0,
        "truth_used": False,
        "formal_scorer_used": False,
    }
    aggregate["passed"] = bool(
        aggregate["positive_pass_count"] == aggregate["positive_total"]
        and aggregate["private_rows_emit_no_witness_target_descriptor_or_path"]
        and aggregate["reconstruction_ledger_tamper_rejected"]
        and aggregate["backend_target_descriptor_tamper_rejected"]
        and aggregate["wrong_degree_one_proposal_rejected"]
        and aggregate["external_authority_event_count"] == 0
        and aggregate["external_target_release_event_count"] == 0
    )
    (HERE / "DEGREE1_RECONSTRUCTION_RESULT.json").write_text(
        json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(aggregate, ensure_ascii=False, separators=(",", ":")))
    return 0 if aggregate["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
