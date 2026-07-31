from copy import deepcopy

import candidate


def source(answer="x"):
    return {
        "id": "ignored",
        "task": "solve",
        "variables": {"names": ["x"]},
        "bounds": [[-2, 2]],
        "construction": [],
        "constraints": [{"def": "x*x", "value": "1"}],
        "guards": ["AssumeGt(x,0)"],
        "answer": answer,
        "post_process": "",
    }


def test_target_blind_root_domain_and_exact_replay_hold():
    result = candidate.build_proposals(source())
    assert result["status"] == "PROPOSAL_READY_HOLD"
    assert result["pre_arc_assignment_product"] == 2
    assert result["post_arc_assignment_product"] == 1
    assert result["proposal_count"] == 1
    assert result["proposals"][0]["raw_coordinate_assignment"]["x"]["text"] == "1"
    assert result["authority_pass"] is False
    assert result["target_release"] is False
    replay = candidate.audit_untouched_full_replay(source(), result)
    assert replay["proposal_count_unchanged"] == 1
    assert replay["full_source_raw_target_replay_pass_count"] == 1
    assert replay["authority_pass"] is False


def test_target_and_id_cannot_change_proposal_membership_or_order():
    first = candidate.build_proposals(source("x"))
    changed = source("100-x")
    changed["id"] = "different"
    second = candidate.build_proposals(changed)
    assert first["assignment_signature_sha256"] == second["assignment_signature_sha256"]
    assert first["proposals"] == second["proposals"]


def test_underconstrained_and_truth_inputs_fall_back():
    document = source()
    document["variables"]["names"] = ["x", "y"]
    document["bounds"] = [[-2, 2], [-2, 2]]
    document["constraints"] = [{"def": "x+y", "value": "0"}]
    document["guards"] = []
    assert candidate.build_proposals(document)["status"] == "NOT_APPLICABLE_BASELINE_FALLBACK"
    document = source()
    document["known_truth"] = [1]
    result = candidate.build_proposals(document)
    assert result["status"] == "NOT_APPLICABLE_BASELINE_FALLBACK"
    assert result["reason"] == "FORBIDDEN_TRUTH_OR_OUTCOME_INPUT"


def test_task_and_postprocess_semantics_are_not_silently_changed():
    document = source()
    document["task"] = "optimize"
    assert candidate.build_proposals(document)["reason"] == "TASK_IS_NOT_SOLVE"
    document = source()
    document["post_process"] = "sqrt"
    assert candidate.build_proposals(document)["reason"] == "POST_PROCESS_NOT_EMPTY"


def test_candidate_prejoin_returns_untouched_baseline_by_identity_on_fallback(monkeypatch):
    baseline = {"opaque": object()}
    document = source()
    document["task"] = "optimize"
    assert candidate.candidate_prejoin_or_baseline(document, baseline) is baseline

    def explode(_document):
        raise RuntimeError("synthetic")

    monkeypatch.setattr(candidate, "build_proposals", explode)
    assert candidate.candidate_prejoin_or_baseline(source(), baseline) is baseline


def test_constraint_permutation_is_metamorphic():
    document = {
        "task": "solve",
        "variables": {"names": ["x", "y"]},
        "bounds": [[-2, 2], [-2, 2]],
        "construction": [],
        "constraints": [
            {"def": "x*x", "value": "2"},
            {"def": "y-x", "value": "0"},
        ],
        "guards": ["AssumeGt(x,0)"],
        "answer": "x+y",
        "post_process": "",
    }
    permuted = deepcopy(document)
    permuted["constraints"].reverse()
    first = candidate.build_proposals(document)
    second = candidate.build_proposals(permuted)
    assert first["assignment_signature_sha256"] == second["assignment_signature_sha256"]


def test_combinatorial_cap_fails_closed():
    names = [f"x{index}" for index in range(candidate.MAX_VARIABLES + 1)]
    document = {
        "task": "solve",
        "variables": {"names": names},
        "construction": [],
        "constraints": [
            {"def": f"{name}*{name}", "value": "1"} for name in names
        ],
        "guards": [],
        "answer": "+".join(names),
        "post_process": "",
    }
    result = candidate.build_proposals(document)
    assert result["status"] == "NOT_APPLICABLE_BASELINE_FALLBACK"
    assert result["reason"] == "VARIABLE_CAP"
