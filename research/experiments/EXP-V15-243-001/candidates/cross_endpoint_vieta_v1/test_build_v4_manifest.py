from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct

import pytest

import build_v4_manifest as builder
import canonical_connector as connector


def _write(path: Path, value: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, indent=2, sort_keys=True).encode() + b"\n"
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def _source(inputs: Path) -> tuple[Path, str]:
    path = inputs / "source.json"
    digest = _write(
        path,
        {
            "id": "generated-formal-control",
            "task": "solve",
            "variables": {"names": ["x", "y"]},
            "construction": [],
            "constraints": [],
            "guards": [],
            "answer": "x",
        },
    )
    return path, digest


def _endpoint(
    artifact_root: Path,
    *,
    ordinal: int,
    source_sha: str,
    guard_ok: bool = True,
    plan_source_sha: str | None = None,
) -> Path:
    directory = artifact_root / f"endpoint-{ordinal}"
    directory.mkdir(parents=True)
    endpoint = [float(ordinal), float(ordinal + 10)]
    bits = [struct.pack(">d", item).hex() for item in endpoint]
    endpoint_sha = connector._endpoint_sha256(bits)
    plan_sha = _write(
        directory / "PLAN.json",
        {
            "schema_version": "geotarget.exp008-single-raw-endpoint-hp-plan/v1",
            "source_sha256": plan_source_sha or source_sha,
            "endpoint_float64_sha256": endpoint_sha,
            "endpoint": endpoint,
            "truth_read": False,
            "case_or_family_identity_read": False,
            "source_or_problem_modified": False,
            "bounds_or_gauge_added": False,
            "endpoint_unchanged_before_refinement": True,
        },
    )
    lanes = [
        {
            "bits": precision,
            "point": [str(ordinal), str(ordinal + 10)],
            "answer": str(ordinal),
            "finite": True,
            "hard_feasible": True,
            "guard_ok": guard_ok,
            "guard_violations": [] if guard_ok else ["generated-mutation"],
            "raw_hard_feasible_without_intrinsic_domains": True,
            "intrinsic_domain_ok": True,
            "intrinsic_domain_violations": [],
        }
        for precision in (768, 1024)
    ]
    lane_sha = _write(
        directory / "authority.json",
        {
            "schema_version": "geotarget.exp008-target-first-fallback-composition/v1",
            "status": "TARGET_AUTHORITY_READY",
            "authority_pass": True,
            "final_result": {
                "status": "TARGET_AUTHORITY_READY",
                "source_raw_sha256": source_sha,
                "endpoint_float64_sha256": endpoint_sha,
                "authority_pass": True,
                "input_contract": {
                    "source_bytes_and_digest": True,
                    "bare_float64_endpoint": True,
                    "truth": False,
                    "known_target_count": False,
                    "case_id": False,
                    "family": False,
                },
                "problem_transformations": {
                    "source_mutated": False,
                    "bounds_added": False,
                    "coordinate_fixing_or_gauge": False,
                    "symmetry_reduction": False,
                    "constraint_or_answer_changed": False,
                },
                "float64_replay": {
                    "semantic_valid": True,
                    "hard_feasible": True,
                    "guard_ok": guard_ok,
                    "intrinsic_domain_ok": True,
                },
                "original_numerical_replay": {
                    "numeric_v3_ready": True,
                    "lanes": lanes,
                },
                "authority_scope": {"original_dsl_hp_replay": True},
            },
        },
    )
    _write(
        directory / "RESULT.json",
        {
            "schema_version": "geotarget.exp008-single-raw-endpoint-hp-result/v1",
            "status": "COMPLETE",
            "process_classification": "SUCCESS",
            "artifact_accepted": True,
            "authority_pass": True,
            "source_sha256": source_sha,
            "endpoint_float64_sha256": endpoint_sha,
            "artifact_sha256": lane_sha,
            "truth_read": False,
            "case_or_family_identity_read": False,
            "source_or_problem_modified": False,
            "bounds_or_gauge_added": False,
            "endpoint_unchanged_before_refinement": True,
            "transitive_implementation_current_at_result_write": True,
        },
    )
    assert plan_sha
    return directory


def _layout(tmp_path: Path, monkeypatch, *, endpoint_count: int = 3):
    results = tmp_path / "results"
    artifact_root = results / "formal-control-hp"
    inputs = tmp_path / "inputs"
    results.mkdir()
    artifact_root.mkdir()
    inputs.mkdir()
    monkeypatch.setattr(builder, "RESULTS_ROOT", results)
    _source_path, source_sha = _source(inputs)
    for ordinal in range(1, endpoint_count + 1):
        _endpoint(artifact_root, ordinal=ordinal, source_sha=source_sha)
    return results, artifact_root, inputs, source_sha


def test_generated_builder_emits_v4_ranked_private_manifest(tmp_path, monkeypatch):
    results, artifact_root, inputs, _source_sha = _layout(tmp_path, monkeypatch)
    # An unrelated outcome/scorer-shaped tree is skipped by PLAN schema prefilter.
    unrelated = artifact_root / "unrelated"
    _write(unrelated / "PLAN.json", {"schema_version": "some-other-plan/v1"})
    _write(unrelated / "RESULT.json", {"truth": "must-not-be-consumed", "score": 1})
    _write(unrelated / "authority.json", {"status": "not-hp-authority"})
    private = results / "v4" / "PANEL.json"
    aggregate_path = results / "v4" / "AGGREGATE.json"
    aggregate = builder.build_manifest(
        artifact_root=artifact_root,
        input_directory=inputs,
        private_output=private,
        aggregate_output=aggregate_path,
    )
    panel = json.loads(private.read_text())
    assert aggregate["status"] == "PRIVATE_V4_MANIFEST_READY"
    assert aggregate["accepted_unique_endpoint_count"] == 3
    assert aggregate["private_subset_count"] == 4
    assert aggregate["ignored_nonordinary_plan_count"] == 1
    assert panel["schema_version"] == builder.PANEL_SCHEMA
    assert len(panel["subsets"]) == 4
    assert all(row["schema_version"] == builder.WORK_ITEM_SCHEMA for row in panel["subsets"])
    assert all("source_projection_sha256" in row for row in panel["subsets"])
    assert private.stat().st_mode & 0o777 == 0o600
    assert aggregate_path.stat().st_mode & 0o777 == 0o600
    assert aggregate["truth_read"] is False
    assert aggregate["scorer_read"] is False
    assert aggregate["individual_records_emitted_publicly"] is False


def test_guard_mutation_is_rejected_before_subset_build(tmp_path, monkeypatch):
    results, artifact_root, inputs, source_sha = _layout(
        tmp_path, monkeypatch, endpoint_count=2
    )
    _endpoint(
        artifact_root,
        ordinal=3,
        source_sha=source_sha,
        guard_ok=False,
    )
    aggregate = builder.build_manifest(
        artifact_root=artifact_root,
        input_directory=inputs,
        private_output=results / "out" / "PANEL.json",
        aggregate_output=results / "out" / "AGGREGATE.json",
    )
    assert aggregate["accepted_unique_endpoint_count"] == 2
    assert aggregate["rejected_ordinary_hp_artifact_count"] == 1
    assert aggregate["private_subset_count"] == 1


def test_crossed_plan_source_binding_is_rejected(tmp_path, monkeypatch):
    results, artifact_root, inputs, source_sha = _layout(
        tmp_path, monkeypatch, endpoint_count=2
    )
    _endpoint(
        artifact_root,
        ordinal=3,
        source_sha=source_sha,
        plan_source_sha="f" * 64,
    )
    aggregate = builder.build_manifest(
        artifact_root=artifact_root,
        input_directory=inputs,
        private_output=results / "out" / "PANEL.json",
        aggregate_output=results / "out" / "AGGREGATE.json",
    )
    assert aggregate["accepted_unique_endpoint_count"] == 2
    assert aggregate["rejected_ordinary_hp_artifact_count"] == 1


def test_private_output_must_remain_under_results_root(tmp_path, monkeypatch):
    results, artifact_root, inputs, _source_sha = _layout(tmp_path, monkeypatch)
    with pytest.raises(builder.BuildFailure, match="approved root"):
        builder.build_manifest(
            artifact_root=artifact_root,
            input_directory=inputs,
            private_output=tmp_path / "escaped-panel.json",
            aggregate_output=results / "aggregate.json",
        )
