from copy import deepcopy

import candidate


def document(*, scale=1, tx=0, ty=0, answer="Area(A,B,Q)"):
    ax, ay = tx, ty
    bx, by = tx + scale, ty
    cx, cy = tx, ty + scale
    qx, qy = tx + scale / 4, ty + scale / 2
    return {
        "task": "solve",
        "variables": {"names": ["x", "y"]},
        "bounds": [[tx - scale, tx + 2 * scale], [ty - scale, ty + 2 * scale]],
        "construction": [
            {"name": "A", "expr": f"Point({ax},{ay})"},
            {"name": "B", "expr": f"Point({bx},{by})"},
            {"name": "C", "expr": f"Point({cx},{cy})"},
            {"name": "Q", "expr": "Point(x,y)"},
        ],
        "constraints": [
            {"def": "x", "value": str(qx)},
            {"def": "y", "value": str(qy)},
        ],
        "guards": ["AssumeGt(x, %s)" % (tx - scale / 2)],
        "answer": answer,
        "post_process": "",
    }, [qx, qy]


def test_exact_anchor_simplex_cf_reconstruction_and_full_replay_hold():
    source, endpoint = document()
    result = candidate.propose(source, endpoint)
    assert result["status"] == "PROPOSAL_READY_HOLD"
    assert result["proposal_count"] >= 1
    proposal = result["proposals"][0]
    assert proposal["raw_coordinate_assignment"]["x"] == {
        "kind": "Rational",
        "numerator": 1,
        "denominator": 4,
    }
    assert proposal["raw_coordinate_assignment"]["y"]["numerator"] == 1
    assert proposal["raw_coordinate_assignment"]["y"]["denominator"] == 2
    assert proposal["untouched_source_raw_target_replay_pass"] is True
    assert result["authority_pass"] is False
    assert result["target_release"] is False


def test_translation_and_uniform_scale_preserve_barycentric_signature():
    first_source, first_endpoint = document()
    second_source, second_endpoint = document(scale=8, tx=13, ty=-7)
    first = candidate.propose(first_source, first_endpoint)
    second = candidate.propose(second_source, second_endpoint)
    assert first["status"] == second["status"] == "PROPOSAL_READY_HOLD"
    assert first["barycentric_signature_sha256"] == second["barycentric_signature_sha256"]


def test_polygon_and_composite_area_targets_replay():
    polygon, endpoint = document(answer="Area(A,B,C,Q)")
    composite, _ = document(answer="2*Area(A,B,Q)+Area(A,Q,C)")
    assert candidate.propose(polygon, endpoint)["status"] == "PROPOSAL_READY_HOLD"
    assert candidate.propose(composite, endpoint)["status"] == "PROPOSAL_READY_HOLD"


def test_wrong_endpoint_and_unsupported_raw_target_do_not_emit():
    source, _endpoint = document()
    wrong = candidate.propose(source, [0.251, 0.5])
    assert wrong["status"] == "NOT_APPLICABLE_BASELINE_FALLBACK"
    unsupported = deepcopy(source)
    unsupported["answer"] = "Area(A,B,Q)+sin(x)"
    result = candidate.propose(unsupported, [0.25, 0.5])
    assert result["status"] == "NOT_APPLICABLE_BASELINE_FALLBACK"
    assert result["authority_pass"] is False


def test_degenerate_anchor_simplex_falls_back():
    source, endpoint = document()
    source["construction"][2]["expr"] = "Point(2,0)"
    result = candidate.propose(source, endpoint)
    assert result["status"] == "NOT_APPLICABLE_BASELINE_FALLBACK"
    assert result["reason"] == "NONDEGENERATE_EXACT_ANCHOR_SIMPLEX_NOT_FOUND"


def test_swapped_direct_point_coordinates_are_reconstructed():
    source, endpoint = document()
    source["construction"][3]["expr"] = "Point(y,x)"
    source["constraints"] = [
        {"def": "x", "value": "1/4"},
        {"def": "y", "value": "1/2"},
    ]
    result = candidate.propose(source, endpoint)
    assert result["status"] == "PROPOSAL_READY_HOLD"
    raw = result["proposals"][0]["raw_coordinate_assignment"]
    assert raw["x"]["numerator"] == 1 and raw["x"]["denominator"] == 4
    assert raw["y"]["numerator"] == 1 and raw["y"]["denominator"] == 2


def test_prejoin_fallback_preserves_baseline_object_identity(monkeypatch):
    source, endpoint = document()
    baseline = {"opaque": object()}
    source["task"] = "optimize"
    assert candidate.prejoin_or_baseline(source, endpoint, baseline) is baseline

    def explode(_document, _endpoint):
        raise RuntimeError("synthetic")

    monkeypatch.setattr(candidate, "propose", explode)
    good, endpoint = document()
    assert candidate.prejoin_or_baseline(good, endpoint, baseline) is baseline
