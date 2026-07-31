#!/usr/bin/env python3
"""CPU14 synthetic D0 for explicitly bound source-equality subsets."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from bound_subset_membership import (
    BASE,
    prove_bound_subset_identity,
    verify_bound_subset_proof,
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


def _irrelevant_constraints() -> list[dict[str, str]]:
    names = ["a", "b", "c", "d", "f", "g"]
    return [
        {"def": names[index % len(names)], "value": str(index % len(names) + 1)}
        for index in range(16)
    ]


def _document(last_constraints: list[dict[str, str]]) -> dict[str, object]:
    return {
        "task": "solve",
        "variables": {"names": ["x", "y", "a", "b", "c", "d", "f", "g"]},
        "construction": [],
        "constraints": _irrelevant_constraints() + last_constraints,
        "guards": [],
        "bounds": [[-10, 10] for _ in range(8)],
        "answer": "x",
        "post_process": None,
    }


def _direct_after_many() -> dict[str, object]:
    return _document([{"def": "x", "value": "3"}])


def _square_after_many() -> dict[str, object]:
    return _document([{"def": "(x-3)*(x-3)", "value": "0"}])


def _chain_after_many() -> dict[str, object]:
    return _document(
        [
            {"def": "x-y", "value": "0"},
            {"def": "y", "value": "3"},
        ]
    )


def _omitted_only_determines_target() -> dict[str, object]:
    return {
        "task": "solve",
        "variables": {"names": ["x", "y"]},
        "construction": [],
        "constraints": [
            {"def": "y", "value": "0"},
            {"def": "Distance(Point(x,0),Point(3,0))", "value": "0"},
        ],
        "guards": [],
        "bounds": [[-10, 10], [-10, 10]],
        "answer": "x",
        "post_process": None,
    }


def _write(root: Path, label: str, document: object) -> Path:
    path = root / f"{label}.json"
    path.write_text(
        json.dumps(document, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return path


def _proved(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    selected = value.get("selected_constraint_ordinals")
    excluded = value.get("excluded_constraint_ordinals")
    statement = value.get("statement")
    return bool(
        value.get("status") == "BOUND_SUBSET_IDENTITY_PROVED_HOLD"
        and value.get("radical_power") in (1, 2)
        and value.get("exact_powered_remainder") == "0"
        and value.get("cofactor_witness_complete") is True
        and value.get("excluded_constraints_used_in_identity") is False
        and value.get("full_source_typed_root_required") is True
        and isinstance(selected, list)
        and 1 <= len(selected) <= 12
        and isinstance(excluded, list)
        and not set(selected) & set(excluded)
        and isinstance(statement, dict)
        and statement.get("selected_constraint_ordinals") == selected
        and statement.get("excluded_constraint_ordinals") == excluded
        and value.get("authority_pass") is False
        and value.get("target_release") is False
    )


def main() -> int:
    if os.sched_getaffinity(0) != {14}:
        raise RuntimeError("bound-subset generated D0 must be pinned to CPU14")
    with tempfile.TemporaryDirectory(prefix="guided-target-bound-subset-") as name:
        root = Path(name)
        fixtures = {
            "direct-after-many": _direct_after_many(),
            "square-after-many": _square_after_many(),
            "two-generator-chain": _chain_after_many(),
        }
        paths = {label: _write(root, label, doc) for label, doc in fixtures.items()}
        proposal = _proposal(3)
        frozen_direct = {
            label: BASE.prove_subset_identity(
                path, ordinary_proposal=proposal, timeout_seconds=3.0
            )
            for label, path in paths.items()
        }
        repaired = {
            label: prove_bound_subset_identity(
                path, ordinary_proposal=proposal, timeout_seconds=3.0
            )
            for label, path in paths.items()
        }

        omitted_result = prove_bound_subset_identity(
            _write(root, "omitted-only", _omitted_only_determines_target()),
            ordinary_proposal=proposal,
            timeout_seconds=3.0,
        )
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
        multi_target_result = prove_bound_subset_identity(
            _write(root, "multi-target", multi_target),
            ordinary_proposal=_proposal(1),
            timeout_seconds=3.0,
        )
        wrong_q_result = prove_bound_subset_identity(
            paths["direct-after-many"],
            ordinary_proposal=_proposal(4),
            timeout_seconds=3.0,
        )
        unit = {
            "task": "solve",
            "variables": {"names": ["x"]},
            "construction": [],
            "constraints": [
                {"def": "x", "value": "0"},
                {"def": "x", "value": "1"},
            ],
            "guards": [],
            "bounds": [[-2, 2]],
            "answer": "x",
            "post_process": None,
        }
        unit_result = prove_bound_subset_identity(
            _write(root, "unit", unit),
            ordinary_proposal=_proposal(7),
            timeout_seconds=3.0,
        )

        artifact = repaired["direct-after-many"]
        forged = dict(artifact)
        forged["excluded_constraint_ordinals"] = []
        forged_rejected = False
        try:
            verify_bound_subset_proof(
                paths["direct-after-many"],
                ordinary_proposal=proposal,
                artifact=forged,
            )
        except Exception:
            forged_rejected = True

        wrong_proposal_rejected = False
        try:
            verify_bound_subset_proof(
                paths["direct-after-many"],
                ordinary_proposal=_proposal(4),
                artifact=artifact,
            )
        except Exception:
            wrong_proposal_rejected = True

        mutation_path = _write(root, "mutation", _direct_after_many())
        mutation_artifact = prove_bound_subset_identity(
            mutation_path, ordinary_proposal=proposal
        )
        mutation = _direct_after_many()
        mutation["constraints"] = list(mutation["constraints"])
        mutation["constraints"][-1] = {"def": "x", "value": "4"}
        mutation_path.write_text(
            json.dumps(mutation, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        source_mutation_rejected = False
        try:
            verify_bound_subset_proof(
                mutation_path,
                ordinary_proposal=proposal,
                artifact=mutation_artifact,
            )
        except Exception:
            source_mutation_rejected = True

    frozen_direct_rejected = {
        label: value.get("status") == "SUBSET_IDENTITY_NOT_PROVED"
        for label, value in frozen_direct.items()
    }
    repaired_passes = {label: _proved(value) for label, value in repaired.items()}
    aggregate = {
        "schema_version": "geotarget.guided-target-bound-subset-generated/v1",
        "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "frozen_direct_rejected": frozen_direct_rejected,
        "frozen_direct_rejected_count": sum(frozen_direct_rejected.values()),
        "bound_subset_passes": repaired_passes,
        "bound_subset_pass_count": sum(repaired_passes.values()),
        "positive_total": len(repaired_passes),
        "omitted_equality_not_used_implicitly": omitted_result.get("status")
        == "BOUND_SUBSET_IDENTITY_NOT_PROVED",
        "multi_target_component_not_extrapolated": multi_target_result.get("status")
        == "BOUND_SUBSET_IDENTITY_NOT_PROVED",
        "wrong_q_rejected": wrong_q_result.get("status")
        == "BOUND_SUBSET_IDENTITY_NOT_PROVED",
        "unit_ideal_not_used": unit_result.get("status")
        == "BOUND_SUBSET_IDENTITY_NOT_PROVED",
        "forged_selected_excluded_ledger_rejected": forged_rejected,
        "wrong_proposal_binding_rejected": wrong_proposal_rejected,
        "source_mutation_rejected": source_mutation_rejected,
        "authority_event_count": 0,
        "target_release_event_count": 0,
        "truth_used": False,
        "formal_scorer_used": False,
    }
    aggregate["passed"] = bool(
        aggregate["frozen_direct_rejected_count"] == aggregate["positive_total"]
        and aggregate["bound_subset_pass_count"] == aggregate["positive_total"]
        and aggregate["omitted_equality_not_used_implicitly"]
        and aggregate["multi_target_component_not_extrapolated"]
        and aggregate["wrong_q_rejected"]
        and aggregate["unit_ideal_not_used"]
        and aggregate["forged_selected_excluded_ledger_rejected"]
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
