#!/usr/bin/env python3
"""CPU14-only generated activation and negative tests for Repair C."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import tempfile

import typed_cover_membership as C


HERE = Path(__file__).resolve().parent


def _proposal(value: int) -> dict[str, object]:
    return {
        "status": "TARGET_AUTHORITY_READY",
        "authority_pass": True,
        "descriptor": {
            "minimal_polynomial_high_to_low": [1, -value],
            "selected_real_root_index": 0,
            "isolating_interval": {
                "left": str(value), "right": str(value), "multiplicity": 1, "real_root_index": 0,
            },
        },
        "synthetic_only": True,
    }


def _root_certificate(job: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": "geotarget.local-krawczyk-certificate/v1",
        "status": "VERIFIED",
        "source_sha256": job["source_sha256"],
        "system_sha256": job["system_sha256"],
        "job_sha256": job["job_sha256"],
        "unique_regular_root_in_rational_box": True,
        "strict_krawczyk_inclusion": True,
        "all_source_predicates_interval_valid": True,
        "target_equality_requires_exact_link": True,
        "coverage": "UNKNOWN",
        "generated_fixture_only": True,
    }


def _write(root: Path, label: str, document: object) -> Path:
    path = root / f"{label}.json"
    path.write_text(json.dumps(document, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    return path


def _distance() -> tuple[dict[str, object], int, list[float], dict[str, int]]:
    return ({
        "task": "solve", "variables": {"names": ["x"]},
        "construction": [
            {"name": "P", "expr": "Point(x,0)"}, {"name": "O", "expr": "Point(0,0)"},
        ],
        "constraints": [{"def": "x", "value": "3"}], "guards": ["Assume(x > 0)"],
        "bounds": [[0, 10]], "answer": "Distance(P,O)**2", "post_process": None,
    }, 9, [3.0], {"x": 3, "__sqrt_1": 3})


def _point_on_circle() -> tuple[dict[str, object], int, list[float], dict[str, int]]:
    return ({
        "task": "solve", "variables": {"names": ["x"]},
        "construction": [
            {"name": "O", "expr": "Point(x,0)"},
            {"name": "C", "expr": "Circle(O,3)"},
            {"name": "P", "expr": "PointOnCircle(C,0)"},
        ],
        "constraints": [{"def": "x", "value": "2"}], "guards": [],
        "bounds": [[-10, 10]], "answer": "P.x", "post_process": None,
    }, 5, [2.0], {"x": 2})


def _absolute_area() -> tuple[dict[str, object], int, list[float], dict[str, int]]:
    return ({
        "task": "solve", "variables": {"names": ["x"]},
        "construction": [
            {"name": "A", "expr": "Point(0,0)"}, {"name": "B", "expr": "Point(2,0)"},
            {"name": "D", "expr": "Point(0,x)"},
        ],
        "constraints": [{"def": "x", "value": "3"}], "guards": ["Assume(x > 0)"],
        "bounds": [[0, 10]], "answer": "Area(A,B,D)**2", "post_process": None,
    }, 9, [3.0], {"x": 3, "__abs_1": 6})


def _bundle(path: Path, q: int, endpoint: list[float], assignment: dict[str, int]) -> dict[str, object]:
    proposal = _proposal(q)
    job = C.prepare_source_root_job(path, endpoint)
    certificate = _root_certificate(job)
    cover = C.exact_cover_certificate_for_generated_test(
        path, assignment=assignment, source_job=job, source_certificate=certificate
    )
    artifact = C.prove_typed_cover_identity(
        path, ordinary_proposal=proposal, source_job=job, source_certificate=certificate,
        cover_certificate=cover,
    )
    return {"proposal": proposal, "job": job, "certificate": certificate, "cover": cover, "artifact": artifact}


def main() -> int:
    if os.sched_getaffinity(0) != {14}:
        raise RuntimeError("Repair C generated gate must be pinned to CPU14")
    with tempfile.TemporaryDirectory(prefix="guided-target-typed-cover-") as directory:
        root = Path(directory)
        fixtures = {"distance-sqrt": _distance(), "circle-point-on-circle": _point_on_circle(), "absolute-area": _absolute_area()}
        paths = {name: _write(root, name, data[0]) for name, data in fixtures.items()}
        bundles = {
            name: _bundle(paths[name], data[1], data[2], data[3]) for name, data in fixtures.items()
        }
        direct_failed = {
            name: C.BASE.prove_subset_identity(paths[name], ordinary_proposal=bundle["proposal"]).get("status")
            == "SUBSET_IDENTITY_NOT_PROVED" for name, bundle in bundles.items()
        }
        repaired = {
            name: bundle["artifact"].get("status") == "TYPED_COVER_IDENTITY_PROVED_HOLD"
            for name, bundle in bundles.items()
        }

        distance = bundles["distance-sqrt"]
        wrong_q = C.prove_typed_cover_identity(
            paths["distance-sqrt"], ordinary_proposal=_proposal(8), source_job=distance["job"],
            source_certificate=distance["certificate"], cover_certificate=distance["cover"],
        )
        wrong_branch_cover = copy.deepcopy(distance["cover"])
        wrong_branch_cover["assignment"]["__sqrt_1"] = "-3"
        wrong_branch = C.prove_typed_cover_identity(
            paths["distance-sqrt"], ordinary_proposal=distance["proposal"], source_job=distance["job"],
            source_certificate=distance["certificate"], cover_certificate=wrong_branch_cover,
        )
        inconsistent_cover = copy.deepcopy(distance["cover"])
        inconsistent_cover["assignment"]["x"] = "4"
        inconsistent_cover["assignment"]["__sqrt_1"] = "4"
        inconsistent_unit = C.prove_typed_cover_identity(
            paths["distance-sqrt"], ordinary_proposal=distance["proposal"], source_job=distance["job"],
            source_certificate=distance["certificate"], cover_certificate=inconsistent_cover,
        )
        wrong_root = copy.deepcopy(distance["certificate"])
        wrong_root["strict_krawczyk_inclusion"] = False
        rejected_root = C.prove_typed_cover_identity(
            paths["distance-sqrt"], ordinary_proposal=distance["proposal"], source_job=distance["job"],
            source_certificate=wrong_root, cover_certificate=distance["cover"],
        )
        forged = copy.deepcopy(distance["artifact"])
        forged["statement"]["complete_equation_ledger"] = forged["statement"]["complete_equation_ledger"][:-1]
        omitted_rejected = False
        try:
            C.verify_typed_cover_proof(
                paths["distance-sqrt"], artifact=forged, ordinary_proposal=distance["proposal"],
                source_job=distance["job"], source_certificate=distance["certificate"],
                cover_certificate=distance["cover"],
            )
        except Exception:
            omitted_rejected = True

        mutation_path = paths["absolute-area"]
        mutation_artifact = bundles["absolute-area"]["artifact"]
        mutated = copy.deepcopy(fixtures["absolute-area"][0])
        mutated["constraints"][0]["value"] = "4"
        mutation_path.write_text(json.dumps(mutated, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        mutation_rejected = False
        try:
            C.verify_typed_cover_proof(
                mutation_path, artifact=mutation_artifact,
                ordinary_proposal=bundles["absolute-area"]["proposal"],
                source_job=bundles["absolute-area"]["job"],
                source_certificate=bundles["absolute-area"]["certificate"],
                cover_certificate=bundles["absolute-area"]["cover"],
            )
        except Exception:
            mutation_rejected = True

        selector = copy.deepcopy(fixtures["circle-point-on-circle"][0])
        selector["variables"] = {"names": ["x", "t"]}
        selector["construction"][2]["expr"] = "PointOnCircle(C,t)"
        selector_rejected = False
        try:
            C._compile_complete_cover(selector)
        except Exception:
            selector_rejected = True

    aggregate = {
        "schema_version": "geotarget.guided-target-typed-cover-generated/v1",
        "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "old_closed_affine_compiler_failed": direct_failed,
        "complete_typed_cover_repaired": repaired,
        "activation_count": sum(repaired.values()),
        "generated_family_count": len(repaired),
        "wrong_q_rejected": wrong_q.get("status") == "TYPED_COVER_IDENTITY_NOT_PROVED",
        "wrong_branch_rejected": wrong_branch.get("status") == "TYPED_COVER_IDENTITY_NOT_PROVED",
        "inconsistent_unit_cover_witness_rejected": inconsistent_unit.get("status")
        == "TYPED_COVER_IDENTITY_NOT_PROVED",
        "invalid_source_root_certificate_rejected": rejected_root.get("status") == "TYPED_COVER_IDENTITY_NOT_PROVED",
        "omitted_equation_artifact_rejected": omitted_rejected,
        "source_mutation_rejected": mutation_rejected,
        "selector_replay_rejected": selector_rejected,
        "authority_event_count": 0,
        "target_release_event_count": 0,
        "truth_used": False,
        "formal_corpus_or_scorer_used": False,
    }
    aggregate["passed"] = bool(
        all(direct_failed.values()) and all(repaired.values()) and aggregate["activation_count"] >= 3
        and aggregate["wrong_q_rejected"] and aggregate["wrong_branch_rejected"]
        and aggregate["inconsistent_unit_cover_witness_rejected"]
        and aggregate["invalid_source_root_certificate_rejected"]
        and aggregate["omitted_equation_artifact_rejected"] and aggregate["source_mutation_rejected"]
        and aggregate["selector_replay_rejected"] and aggregate["authority_event_count"] == 0
        and aggregate["target_release_event_count"] == 0
    )
    (HERE / "GENERATED_RESULT.json").write_text(json.dumps(aggregate, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(aggregate, separators=(",", ":")))
    return 0 if aggregate["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
