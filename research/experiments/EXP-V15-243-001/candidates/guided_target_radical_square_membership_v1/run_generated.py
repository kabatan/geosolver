#!/usr/bin/env python3
"""CPU14 synthetic D0 for radical-square ideal membership."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from radical_square_membership import (
    BASE,
    prove_radical_square_identity,
    verify_radical_square_proof,
)


HERE = Path(__file__).resolve().parent


def _proposal(value: int) -> dict[str, object]:
    return {
        "status": "TARGET_AUTHORITY_READY",
        "authority_pass": True,
        "descriptor": {
            "minimal_polynomial_high_to_low": [1, -value],
            "selected_real_root_index": 0,
            "isolating_interval": {
                "left": str(value),
                "right": str(value),
                "multiplicity": 1,
                "real_root_index": 0,
            },
        },
        "synthetic_only": True,
    }


def _nonradical_scalar() -> dict[str, object]:
    return {
        "task": "solve",
        "variables": {"names": ["x"]},
        "construction": [],
        "constraints": [{"def": "(x-3)*(x-3)", "value": "0"}],
        "guards": [],
        "bounds": [[-10, 10]],
        "answer": "x",
        "post_process": None,
    }


def _nonradical_geometry() -> dict[str, object]:
    return {
        "task": "solve",
        "variables": {"names": ["x"]},
        "construction": [
            {"name": "P", "expr": "Point(x,0)"},
            {"name": "C", "expr": "Point(3,0)"},
            {"name": "V", "expr": "Vector(P,C)"},
        ],
        "constraints": [{"def": "Dot(V,V)", "value": "0"}],
        "guards": [],
        "bounds": [[-10, 10]],
        "answer": "x",
        "post_process": None,
    }


def _nonradical_metamorphic() -> dict[str, object]:
    return {
        "task": "solve",
        "variables": {"names": ["v", "u"]},
        "construction": [],
        "constraints": [
            {"def": "4*(u-3)*(u-3)", "value": "0"},
            {"def": "v", "value": "2"},
        ],
        "guards": [],
        "bounds": [[-10, 10], [-10, 10]],
        "answer": "u",
        "post_process": None,
    }


def _write(root: Path, label: str, document: object) -> Path:
    path = root / f"{label}.json"
    path.write_text(
        json.dumps(document, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return path


def _proved(artifact: object) -> bool:
    return bool(
        isinstance(artifact, dict)
        and artifact.get("status") == "RADICAL_SQUARE_IDENTITY_PROVED_HOLD"
        and artifact.get("radical_power") == 2
        and artifact.get("real_zero_implication") is True
        and artifact.get("exact_powered_remainder") == "0"
        and artifact.get("cofactor_witness_complete") is True
        and artifact.get("authority_pass") is False
        and artifact.get("target_release") is False
    )


def main() -> int:
    if os.sched_getaffinity(0) != {14}:
        raise RuntimeError("radical-square generated D0 must be pinned to CPU14")
    with tempfile.TemporaryDirectory(prefix="guided-target-radical-square-") as name:
        root = Path(name)
        positives = {
            "nonradical-scalar": _nonradical_scalar(),
            "nonradical-geometry": _nonradical_geometry(),
            "nonradical-metamorphic": _nonradical_metamorphic(),
        }
        paths = {label: _write(root, label, value) for label, value in positives.items()}
        proposal = _proposal(3)
        direct = {
            label: BASE.prove_subset_identity(
                path, ordinary_proposal=proposal, timeout_seconds=3.0
            )
            for label, path in paths.items()
        }
        repaired = {
            label: prove_radical_square_identity(
                path, ordinary_proposal=proposal, timeout_seconds=3.0
            )
            for label, path in paths.items()
        }

        multi_target = {
            "task": "solve",
            "variables": {"names": ["x"]},
            "construction": [],
            "constraints": [{"def": "x*x", "value": "1"}],
            "guards": [],
            "bounds": [[-2, 2]],
            "answer": "x",
            "post_process": None,
        }
        multi_target_result = prove_radical_square_identity(
            _write(root, "multi-target", multi_target),
            ordinary_proposal=_proposal(1),
            timeout_seconds=3.0,
        )
        wrong_q_result = prove_radical_square_identity(
            paths["nonradical-scalar"],
            ordinary_proposal=_proposal(4),
            timeout_seconds=3.0,
        )
        inconsistent = _nonradical_scalar()
        inconsistent["constraints"] = [
            {"def": "x", "value": "0"},
            {"def": "x", "value": "1"},
        ]
        inconsistent_result = prove_radical_square_identity(
            _write(root, "inconsistent", inconsistent),
            ordinary_proposal=_proposal(7),
            timeout_seconds=3.0,
        )
        postprocessed = _nonradical_scalar()
        postprocessed["post_process"] = "sqrt"
        postprocessed_result = prove_radical_square_identity(
            _write(root, "postprocessed", postprocessed),
            ordinary_proposal=proposal,
            timeout_seconds=3.0,
        )
        nonprimitive = _proposal(3)
        nonprimitive["descriptor"] = dict(nonprimitive["descriptor"])
        nonprimitive["descriptor"]["minimal_polynomial_high_to_low"] = [2, -6]
        nonprimitive_result = prove_radical_square_identity(
            paths["nonradical-scalar"],
            ordinary_proposal=nonprimitive,
            timeout_seconds=3.0,
        )

        artifact = repaired["nonradical-scalar"]
        forged = dict(artifact)
        forged_statement = dict(forged["statement"])
        forged_statement["theorem"] = "FORGED"
        forged["statement"] = forged_statement
        forged_rejected = False
        try:
            verify_radical_square_proof(
                paths["nonradical-scalar"],
                ordinary_proposal=proposal,
                artifact=forged,
            )
        except Exception:
            forged_rejected = True

        wrong_proposal_rejected = False
        try:
            verify_radical_square_proof(
                paths["nonradical-scalar"],
                ordinary_proposal=_proposal(4),
                artifact=artifact,
            )
        except Exception:
            wrong_proposal_rejected = True

        mutation_path = _write(root, "mutation", _nonradical_scalar())
        mutation_artifact = prove_radical_square_identity(
            mutation_path, ordinary_proposal=proposal
        )
        mutated = _nonradical_scalar()
        mutated["answer"] = "x+1"
        mutation_path.write_text(
            json.dumps(mutated, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        source_mutation_rejected = False
        try:
            verify_radical_square_proof(
                mutation_path,
                ordinary_proposal=proposal,
                artifact=mutation_artifact,
            )
        except Exception:
            source_mutation_rejected = True

    direct_rejected = {
        label: value.get("status") == "SUBSET_IDENTITY_NOT_PROVED"
        for label, value in direct.items()
    }
    repaired_passes = {label: _proved(value) for label, value in repaired.items()}
    aggregate = {
        "schema_version": "geotarget.guided-target-radical-square-generated/v1",
        "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "direct_membership_rejected": direct_rejected,
        "direct_rejected_count": sum(direct_rejected.values()),
        "radical_square_passes": repaired_passes,
        "radical_square_pass_count": sum(repaired_passes.values()),
        "positive_total": len(repaired_passes),
        "multi_target_component_not_extrapolated": multi_target_result.get("status")
        == "RADICAL_SQUARE_IDENTITY_NOT_PROVED",
        "wrong_q_rejected": wrong_q_result.get("status")
        == "RADICAL_SQUARE_IDENTITY_NOT_PROVED",
        "inconsistent_unit_ideal_rejected": inconsistent_result.get("status")
        == "RADICAL_SQUARE_IDENTITY_NOT_PROVED",
        "post_process_rejected": postprocessed_result.get("status")
        == "RADICAL_SQUARE_IDENTITY_NOT_PROVED",
        "nonprimitive_descriptor_rejected": nonprimitive_result.get("status")
        == "RADICAL_SQUARE_IDENTITY_NOT_PROVED",
        "forged_artifact_rejected": forged_rejected,
        "wrong_proposal_binding_rejected": wrong_proposal_rejected,
        "source_mutation_rejected": source_mutation_rejected,
        "authority_event_count": 0,
        "target_release_event_count": 0,
        "truth_used": False,
        "formal_scorer_used": False,
    }
    aggregate["passed"] = bool(
        aggregate["direct_rejected_count"] == aggregate["positive_total"]
        and aggregate["radical_square_pass_count"] == aggregate["positive_total"]
        and aggregate["multi_target_component_not_extrapolated"]
        and aggregate["wrong_q_rejected"]
        and aggregate["inconsistent_unit_ideal_rejected"]
        and aggregate["post_process_rejected"]
        and aggregate["nonprimitive_descriptor_rejected"]
        and aggregate["forged_artifact_rejected"]
        and aggregate["wrong_proposal_binding_rejected"]
        and aggregate["source_mutation_rejected"]
        and aggregate["authority_event_count"] == 0
        and aggregate["target_release_event_count"] == 0
    )
    (HERE / "GENERATED_RESULT.json").write_text(
        json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(aggregate, ensure_ascii=False, separators=(",", ":")))
    return 0 if aggregate["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
