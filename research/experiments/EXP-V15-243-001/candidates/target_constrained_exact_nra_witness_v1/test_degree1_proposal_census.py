from __future__ import annotations

import json
from copy import deepcopy

import pytest

import applicability
import candidate as backend
from run_degree1_proposal_census import (
    _assess_request,
    _proposal,
    _replay_existing_witness,
)


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


def _auxiliary_document():
    return {
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
    }


def _periodic_document():
    return {
        "task": "solve",
        "variables": {"names": ["t"]},
        "construction": [],
        "constraints": [{"def": "cos(t)", "value": "1"}],
        "guards": [],
        "bounds": [[0, 0]],
        "answer": "cos(t)",
        "post_process": None,
    }


def _selector_document():
    return {
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
    }


@pytest.mark.parametrize(
    ("document", "coefficients", "signal"),
    [
        (_auxiliary_document(), [1, -3], "qqbar_embedding_ready"),
        (_periodic_document(), [1, -1], "periodic_reconstruction_used"),
        (_selector_document(), [1, -1], "selector_or_branch_ledger_bound"),
    ],
)
def test_existing_reconstruction_and_exact_dsl_routes_join(
    tmp_path, document, coefficients, signal
):
    result = _assess(tmp_path, document, coefficients)
    assert result["thin_join_ready"] is True
    assert result[signal] is True


def _witness_and_bridge(document, coefficients):
    source, metadata = applicability._legacy_target_link_source(
        document, include_private_bridge_ledger=True
    )
    witness = backend.prove(source, _proposal(coefficients), timeout_seconds=3.0)
    assert witness["authority_pass"] is True
    return source, witness, metadata["private_bridge_ledger"]


def test_reconstruction_ledger_tamper_is_recompiled_and_rejected():
    document = _periodic_document()
    source, witness, bridge = _witness_and_bridge(document, [1, -1])
    tampered = deepcopy(bridge)
    tampered["reconstruction"][0]["formula"] = "atan2(forged,forged) mod 2*pi"
    unsigned = dict(tampered)
    del unsigned["bridge_ledger_sha256"]
    tampered["bridge_ledger_sha256"] = backend._canonical_sha256(unsigned)
    with pytest.raises(backend.NotProved):
        _replay_existing_witness(document, source, witness, tampered)


def test_backend_target_descriptor_tamper_is_rejected():
    document = _auxiliary_document()
    source, witness, bridge = _witness_and_bridge(document, [1, -3])
    tampered = deepcopy(witness)
    tampered["model_descriptors"]["__nra_raw_target"] = {
        "kind": "Rational",
        "numerator": 4,
        "denominator": 1,
    }
    with pytest.raises(backend.NotProved):
        _replay_existing_witness(document, source, tampered, bridge)
