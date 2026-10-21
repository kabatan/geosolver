"""Synthetic and static checks, never natural-case optimization or outcome tuning."""

import copy
import hashlib
import importlib
import json
import sys
from types import SimpleNamespace

import pytest
from mpmath import mp

from tests.paths import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT))
try:
    canary_module = importlib.import_module("benchmarks.gmb_comparison.canary")
    checker_module = importlib.import_module("benchmarks.gmb_comparison.checker")
    observation_module = importlib.import_module("benchmarks.gmb_comparison.observation")
    prepare_module = importlib.import_module("benchmarks.gmb_comparison.prepare")
    sources_module = importlib.import_module("benchmarks.gmb_comparison.sources")
    witness_module = importlib.import_module("benchmarks.gmb_comparison.witness")
finally:
    sys.path.pop(0)
SYNTHETIC_GMBL = canary_module.SYNTHETIC_GMBL
synthetic_problem = canary_module.synthetic_problem
check_configuration = checker_module.check_configuration
inspect_gmbl = checker_module.inspect_gmbl
observe_candidates = observation_module.observe_candidates
check_review = prepare_module.check_review
DEFAULT_UPSTREAM = sources_module.DEFAULT_UPSTREAM
HERE = sources_module.HERE
WitnessExporter = witness_module.WitnessExporter


@pytest.mark.parametrize("coordinates", [("0", "1"), ("0.3", "1.2"), ("0.3", "-1.2")])
def test_export_preserves_shape_freedom_and_mirror(coordinates):
    declarations = inspect_gmbl(SYNTHETIC_GMBL)["declarations"]
    exporter = WitnessExporter(synthetic_problem(), declarations)
    initial_dps = mp.dps
    witness = exporter.export(coordinates)
    assert mp.dps == initial_dps
    assert witness["points"]["A"] == ["0.0", "0.0"]
    assert witness["points"]["B"] == ["1.0", "0.0"]
    result = check_configuration(SYNTHETIC_GMBL, witness)
    assert result["valid"] is True
    assert result["original_problem_valid"] is None


def test_false_goal_does_not_repair_or_invalidate_assumptions():
    exporter = WitnessExporter(synthetic_problem(), inspect_gmbl(SYNTHETIC_GMBL)["declarations"])
    witness = exporter.export(["0", "1"])
    result = check_configuration(SYNTHETIC_GMBL, witness)
    assert result["valid"] is True
    assert any(item["status"] == "failed" for item in result["goals"])
    witness["points"]["M"][1] = "0.1"
    assert check_configuration(SYNTHETIC_GMBL, witness)["valid"] is False


def test_export_rejects_rounded_or_incomplete_coordinate_vector():
    exporter = WitnessExporter(synthetic_problem(), inspect_gmbl(SYNTHETIC_GMBL)["declarations"])
    with pytest.raises(TypeError):
        exporter.export([0.0, 1.0])
    with pytest.raises(ValueError):
        exporter.export(["1"])
    with pytest.raises(ValueError):
        exporter.export(["nan", "1"])


def test_witness_bindings_fail_closed():
    declarations = inspect_gmbl(SYNTHETIC_GMBL)["declarations"]
    with pytest.raises(ValueError):
        WitnessExporter(synthetic_problem(), declarations, {"not_declared": "A"})
    with pytest.raises(ValueError):
        WitnessExporter(synthetic_problem(), declarations, {"A": "missing"})
    problem = synthetic_problem()
    problem["constructions"][3]["name"] = "midpoint_AB"
    exporter = WitnessExporter(problem, declarations, {"M": "midpoint_AB"})
    assert exporter.export(["0", "1"])["points"]["M"] == ["0.5", "0.0"]


def test_observation_calls_original_once_and_restores_hooks(monkeypatch):
    from geosolver.engine.standard.refinement.mpmath_refiner import MpmathRefiner

    assembly = importlib.import_module(
        "geosolver.engine.standard.orchestration.assemble_exact_results"
    )
    pipeline = importlib.import_module(
        "geosolver.engine.standard.orchestration.run_external_pipeline"
    )
    result = (object(), object())
    calls, seen = [], []

    def original(self, *, marker):
        calls.append(marker)
        return result

    def revise(candidate, verification):
        calls.append((candidate, verification))
        return verification

    monkeypatch.setattr(MpmathRefiner, "_refine_single_candidate", original)
    monkeypatch.setattr(assembly, "_revise", revise)
    native_result = SimpleNamespace(accepted_candidates=(result[1],))

    def assemble(*args, **kwargs):
        calls.append("assemble_once")
        return native_result

    monkeypatch.setattr(assembly, "assemble_exact_results", assemble)
    monkeypatch.setattr(pipeline, "assemble_exact_results", assemble)
    with observe_candidates(
        lambda value, stage: seen.append((value, stage)), include_intermediate=True
    ):
        assert MpmathRefiner()._refine_single_candidate(marker="once") is result
        assert assembly._revise(result[0], result[1]) is result[1]
        assert pipeline.assemble_exact_results() is native_result
    assert calls == ["once", result, "assemble_once"]
    assert seen == [
        (result[0], "refinement_return"),
        (result[1], "refinement_return"),
        (result[1], "verified_candidate_revision"),
        (result[1], "native_accepted_return"),
    ]
    assert MpmathRefiner._refine_single_candidate is original
    assert assembly._revise is revise
    assert assembly.assemble_exact_results is assemble
    assert pipeline.assemble_exact_results is assemble


def test_default_observation_does_not_wrap_or_export_intermediate_candidates(monkeypatch):
    from geosolver.engine.standard.refinement.mpmath_refiner import MpmathRefiner

    assembly = importlib.import_module(
        "geosolver.engine.standard.orchestration.assemble_exact_results"
    )
    pipeline = importlib.import_module(
        "geosolver.engine.standard.orchestration.run_external_pipeline"
    )
    original_refine, original_revise = MpmathRefiner._refine_single_candidate, assembly._revise
    accepted = object()
    result = SimpleNamespace(accepted_candidates=(accepted,))
    seen = []

    def assemble():
        return result

    monkeypatch.setattr(assembly, "assemble_exact_results", assemble)
    monkeypatch.setattr(pipeline, "assemble_exact_results", assemble)
    with observe_candidates(lambda candidate, stage: seen.append((candidate, stage))):
        assert MpmathRefiner._refine_single_candidate is original_refine
        assert assembly._revise is original_revise
        assert pipeline.assemble_exact_results() is result
    assert seen == [(accepted, "native_accepted_return")]


def test_static_witness_output_type_mismatch_cannot_reach_measurement():
    problem = {
        "id": "SYNTHETIC_BAD_TYPE",
        "variables": [],
        "conditions": [],
        "target": "0",
        "constructions": [{"name": "A", "expression": "Line(Point(0,0),Point(1,0))"}],
    }
    with pytest.raises(TypeError, match="Static witness type mismatch"):
        WitnessExporter(problem, {"A": "point"})


def test_redundant_canary_checker_includes_the_actual_equality():
    exporter = WitnessExporter(
        synthetic_problem(redundant=True), inspect_gmbl(SYNTHETIC_GMBL)["declarations"]
    )
    witness = exporter.export(["0", "1"])
    assert check_configuration(SYNTHETIC_GMBL, witness)["valid"] is True
    source = canary_module.synthetic_gmbl(redundant=True)
    assert check_configuration(source, witness)["valid"] is False


def test_native_accepted_export_failure_is_never_a_benign_domain_rejection():
    classify = canary_module.unexpected_observation_failure
    assert classify({"kind": "candidate_domain_rejection", "stage": "native_accepted_return"})
    assert classify({"kind": "observation_error", "stage": "refinement_return"})
    assert classify({"kind": "candidate_domain_rejection", "stage": "unknown"})
    assert not classify({"kind": "candidate_domain_rejection", "stage": "refinement_return"})


def test_identical_error_artifacts_cannot_pass_the_instrumentation_canary():
    completed = canary_module.healthy_canary_completion
    artifact = {"status": "completed", "solver_status": "success", "public_solved": True}
    child = {"outcome": "completed", "solver_status": "success"}
    assert completed(artifact, child)
    assert not completed({**artifact, "status": "error"}, child)
    assert not completed({**artifact, "solver_status": "error"}, child)
    assert not completed({**artifact, "public_solved": False}, child)
    assert not completed(artifact, {**child, "outcome": "error"})
    assert not completed(None, child)


def test_emission_evidence_rejects_old_coordinates_or_backdated_clock():
    coordinate_hash = hashlib.sha256(b'["1","2"]').hexdigest()
    payload = {
        "candidate": {"candidate_id": 1, "revision": 2, "x_hp": ["1", "2"]},
        "candidate_uid": "test/1",
        "candidate_id": 1,
        "revision": 2,
        "coordinate_sha256": coordinate_hash,
        "stage": "native_accepted_return",
        "coordinate_observed_seconds": 2,
        "materialized_seconds": 3,
    }
    event = {**payload, "emitted_seconds": 4}
    inspect = canary_module.observation_record_issues
    assert inspect(payload, event, timeout=5) == []
    assert "invalid_emission_time" in inspect(payload, {**event, "emitted_seconds": 1}, timeout=5)
    changed = copy.deepcopy(payload)
    changed["candidate"]["x_hp"][0] = "0"
    assert "coordinate_hash_mismatch" in inspect(changed, event, timeout=5)
    assert "event_identity_mismatch:revision" in inspect(
        payload, {**event, "revision": 1}, timeout=5
    )


def test_stale_independent_review_cannot_authorize_changed_input():
    entry = {"case_id": "synthetic", "gmbl_sha256": "gmb"}
    statement = {"pdf_sha256": "pdf"}
    review = {
        "case_id": "synthetic",
        "case_sha256": "case",
        "audit_sha256": "audit",
        "gmbl_sha256": "gmb",
        "reviewed_original_pdf_sha256": "pdf",
        "reviewer": "independent_review",
        "verdict": "pass",
        "normalization_checked": True,
        "conclusion_not_assumed": True,
    }
    kwargs = dict(case_hash="case", audit_hash="audit", entry=entry, statement=statement)
    assert check_review(review, **kwargs) == []
    changed = copy.deepcopy(review)
    changed["case_sha256"] = "old"
    assert "review_identity_mismatch:case_sha256" in check_review(changed, **kwargs)


@pytest.mark.parametrize("block_kind", ["author", "source_difference"])
def test_positive_independent_review_cannot_override_source_or_author_block(tmp_path, block_kind):
    if not DEFAULT_UPSTREAM.is_dir():
        pytest.skip("Independent GMB source environment has not been bootstrapped")
    sources = json.loads((HERE / "source-manifest.json").read_text())
    case_id = "IMO_2001_P1"
    entry = next(item for item in sources["inputs"] if item["case_id"] == case_id)
    for folder in ("cases", "audit", "reviews"):
        (tmp_path / folder).mkdir()
        filename = f"{case_id}.json"
        (tmp_path / folder / filename).write_bytes((HERE / folder / filename).read_bytes())
    audit_path = tmp_path / "audit" / f"{case_id}.json"
    audit = json.loads(audit_path.read_text())
    if block_kind == "author":
        audit["comparison_status"] = "blocked"
        expected_issue = "author_blocked"
    else:
        audit["source_differences"].append({"blocking": True})
        expected_issue = "unresolved_source_difference"
    audit_path.write_text(json.dumps(audit), encoding="utf-8")
    review_path = tmp_path / "reviews" / f"{case_id}.json"
    review = json.loads(review_path.read_text())
    review["audit_sha256"] = sources_module.sha256(audit_path)
    review_path.write_text(json.dumps(review), encoding="utf-8")
    result = prepare_module.inspect_case(
        tmp_path, entry, sources["statements"][str(entry["year"])], DEFAULT_UPSTREAM
    )
    assert result["independently_reviewed"] is True
    assert result["issues"] == [expected_issue]


def test_all_36_input_shapes_and_witness_bindings_compile_without_solving():
    sources = json.loads((HERE / "source-manifest.json").read_text())
    if not DEFAULT_UPSTREAM.is_dir():
        pytest.skip("Independent GMB source environment has not been bootstrapped")
    assert len(sources["inputs"]) == 36
    for item in sources["inputs"]:
        case_id = item["case_id"]
        document = json.loads((HERE / "cases" / f"{case_id}.json").read_text())
        assert document["id"] == case_id
        assert document["target"] == "0"
        coverage = inspect_gmbl((DEFAULT_UPSTREAM / item["gmbl_relative_path"]).read_text())
        assert coverage["supported"], (case_id, coverage)
        audit = json.loads((HERE / "audit" / f"{case_id}.json").read_text())
        WitnessExporter(document, coverage["declarations"], audit.get("witness_bindings", {}))
