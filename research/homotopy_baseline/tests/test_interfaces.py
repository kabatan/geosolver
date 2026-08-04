from __future__ import annotations

import json

from research.homotopy_baseline.cli import _arm_metrics, _arm_score, main
from research.homotopy_baseline.compiler import compile_problem
from research.homotopy_baseline.runner import DATASET_SHA256


def test_analyze_cli_emits_machine_readable_manifest(tmp_path):
    problem = {
        "task": "solve",
        "id": "constant",
        "variables": {"names": []},
        "construction": [],
        "constraints": [],
        "guards": [],
        "answer": "3/2",
        "post_process": "",
    }
    source = tmp_path / "problem.json"
    output = tmp_path / "admission.json"
    source.write_text(json.dumps(problem), encoding="utf-8")
    assert main(["analyze", str(source), "--output", str(output)]) == 0
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["schema_version"] == "geotarget.homotopy-admission/v1"
    assert result["supported"] is True
    assert result["dataset_sha256"] == DATASET_SHA256


def test_target_policy_never_claims_global_completeness(monkeypatch):
    from research.homotopy_baseline import runner

    problem = {
        "task": "solve",
        "id": "target-policy",
        "variables": {"names": ["x"]},
        "construction": [],
        "constraints": [{"def": "x", "value": 1}],
        "guards": [],
        "answer": "x",
        "post_process": "",
    }
    compilation = compile_problem(problem)
    monkeypatch.setattr(runner, "_run_julia", lambda *_args, **_kwargs: {
        "status": "certified",
        "paths": 1,
        "failed_paths": 0,
        "singular_paths": 0,
        "certified_count": 1,
        "real_certified_count": 1,
        "candidates": [
            {
                "certified": True,
                "real": True,
                "coordinates": [{"re": "1", "im": "0"}, {"re": "1", "im": "0"}],
            }
        ],
        "timings": {},
    })
    monkeypatch.setattr(runner, "compile_problem", lambda *_args, **_kwargs: compilation)
    monkeypatch.setattr(
        runner,
        "descriptors_from_candidates",
        lambda *_args, **_kwargs: (
            [{
                "minimal_polynomial_high_to_low": [1, -1],
                "selected_real_root_index": 0,
                "isolating_interval": ["0", "2"],
                "decimal": "1",
            }],
            type("Polynomial", (), {"degree": lambda self: 1})(),
        ),
    )

    def fail_if_degree_is_requested(_compilation):
        raise AssertionError("target mode must not compute ideal degree")

    monkeypatch.setattr(runner, "exact_degree", fail_if_degree_is_requested)
    result = runner.solve_problem(problem, seconds=180, completeness="target")
    assert result["status"] == "answers_found_completeness_unknown"
    assert result["completeness_policy"] == "target"
    assert result["completeness_claim"] is False
    assert result["answers"]


def test_offline_score_accepts_exact_rational_descriptors():
    result = _arm_score(
        {"answer": "81/29"},
        {"answers": [{"decimal": "81/29"}]},
    )
    assert result["exact_set_match"] is True
    assert result["exact_set_recall"] == 1.0


def test_admission_timeout_is_not_a_conditional_success_case():
    cases = [
        {
            "homotopy": {"status": "timeout", "answers": []},
            "offline_score": {"homotopy": {"truth_available": True}},
        },
        {
            "homotopy": {
                "status": "answers_found_completeness_unknown",
                "answers": [{"decimal": "1"}],
                "admission": {"supported": True},
            },
            "offline_score": {
                "homotopy": {
                    "truth_available": True,
                    "exact_set_match": True,
                    "exact_set_recall": 1.0,
                }
            },
        },
    ]
    metrics = _arm_metrics(cases, "homotopy", 180.0)
    assert metrics["admission_coverage"] == 0.5
    assert metrics["admission_timeout_count"] == 1
    assert metrics["conditional_answer_rate"] == 1.0
