from __future__ import annotations

import json

from run_degree1_proposal_census import _assess_request


def _document():
    return {
        "task": "solve",
        "variables": {"names": ["x"]},
        "construction": [],
        "constraints": [{"def": "x", "value": "3"}],
        "guards": [],
        "bounds": [[-10, 10]],
        "answer": "x",
        "post_process": None,
    }


def _assess(tmp_path, document, coefficients):
    source = tmp_path / "source.json"
    source.write_text(json.dumps(document, separators=(",", ":")), encoding="utf-8")
    return _assess_request(
        {
            "source_path": str(source),
            "endpoint": [3.0],
            "candidate_relation_high_to_low": coefficients,
        },
        timeout_seconds=3.0,
    )


def test_degree_one_projection_reaches_existing_backend_and_untouched_replay(tmp_path):
    result = _assess(tmp_path, _document(), [1, -3])
    assert result["thin_join_ready"] is True
    assert result["backend_witness_ready"] is True
    assert result["untouched_source_replay_pass"] is True
    assert result["untouched_target_link_pass"] is True
    assert set(result).isdisjoint({"witness", "target", "descriptor", "source_path"})


def test_wrong_degree_one_projection_does_not_join(tmp_path):
    result = _assess(tmp_path, _document(), [1, -4])
    assert result["thin_join_ready"] is False
    assert result["internal_candidate_authority_observed"] is False


def test_post_process_remains_outside_raw_target_theorem(tmp_path):
    document = _document()
    document["post_process"] = "sqrt"
    result = _assess(tmp_path, document, [1, -3])
    assert result["thin_join_ready"] is False
    assert result["failure_class"] == "POST_PROCESS_OUTSIDE_RAW_TARGET_THEOREM"


def test_nonprimitive_projection_fails_before_backend(tmp_path):
    result = _assess(tmp_path, _document(), [2, -6])
    assert result["descriptor_accepted"] is False
    assert result["backend_attempted"] is False
