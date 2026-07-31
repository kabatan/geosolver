#!/usr/bin/env python3
"""Generated S0 and metamorphic audit for relation-domain CSP V1."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import candidate


HERE = Path(__file__).resolve().parent


def _source(
    names,
    constraints,
    *,
    guards=(),
    bounds=None,
    construction=(),
    answer="0",
):
    return {
        "id": "generated-id-must-not-route",
        "task": "solve",
        "variables": {"names": list(names)},
        "bounds": bounds,
        "construction": list(construction),
        "constraints": list(constraints),
        "guards": list(guards),
        "answer": answer,
        "post_process": "",
    }


def _positive_cases():
    return {
        "unary_guard_prune": _source(
            ["x"],
            [{"def": "x*x", "value": "1"}],
            guards=["AssumeGt(x,0)"],
            bounds=[[-2, 2]],
            answer="x",
        ),
        "root_chain": _source(
            ["x", "y"],
            [
                {"def": "x*x", "value": "2"},
                {"def": "y-x", "value": "0"},
            ],
            guards=["AssumeGt(x,0)"],
            bounds=[[-2, 2], [-2, 2]],
            answer="x+y",
        ),
        "point_coordinate_relations": _source(
            ["x", "y"],
            [
                {"def": "P.x*P.x", "value": "4"},
                {"def": "P.y-P.x", "value": "0"},
            ],
            guards=["AssumeLt(x,0)"],
            bounds=[[-3, 3], [-3, 3]],
            construction=[{"name": "P", "expr": "Point(x,y)"}],
            answer="Distance(P,Point(0,0))",
        ),
        "intersection_selector_replay": _source(
            [],
            [{"def": "Q.y", "value": "0"}],
            construction=[
                {"name": "O", "expr": "Point(0,0)"},
                {"name": "C", "expr": "Circle(O,1)"},
                {"name": "L", "expr": "Line(Point(-2,0),Point(2,0))"},
                {"name": "Q", "expr": "Intersect(L,C)"},
            ],
            answer="Q.x",
        ),
    }


def _cap_case():
    names = [f"x{index}" for index in range(candidate.MAX_VARIABLES + 1)]
    return _source(
        names,
        [{"def": f"{name}*{name}", "value": "1"} for name in names],
        answer="+".join(names),
    )


def run():
    records = []
    for name, document in _positive_cases().items():
        result = candidate.build_proposals(document)
        replay = candidate.audit_untouched_full_replay(document, result)
        records.append(
            {
                "name": name,
                "ready": result["status"] == "PROPOSAL_READY_HOLD",
                "proposal_count": result["proposal_count"],
                "pre_arc_assignment_product": result.get("pre_arc_assignment_product", 0),
                "post_arc_assignment_product": result.get("post_arc_assignment_product", 0),
                "arc_values_removed": result.get("arc_values_removed", 0),
                "full_replay_pass_count": replay[
                    "full_source_raw_target_replay_pass_count"
                ],
                "authority_pass": result["authority_pass"],
                "target_release": result["target_release"],
            }
        )

    target_a = _positive_cases()["root_chain"]
    target_b = deepcopy(target_a)
    target_b["id"] = "different-ignored-id"
    target_b["answer"] = "1000-y"
    first = candidate.build_proposals(target_a)
    second = candidate.build_proposals(target_b)

    permuted = deepcopy(target_a)
    permuted["constraints"] = list(reversed(permuted["constraints"]))
    third = candidate.build_proposals(permuted)

    underconstrained = candidate.build_proposals(
        _source(
            ["x", "y"],
            [{"def": "x+y", "value": "0"}],
            bounds=[[-1, 1], [-1, 1]],
            answer="x-y",
        )
    )
    capped = candidate.build_proposals(_cap_case())
    truth_tamper = _positive_cases()["unary_guard_prune"]
    truth_tamper["truth"] = ["1"]
    truth_rejected = candidate.build_proposals(truth_tamper)
    postprocess = _positive_cases()["unary_guard_prune"]
    postprocess["post_process"] = "sqrt"
    postprocess_rejected = candidate.build_proposals(postprocess)
    optimize = _positive_cases()["unary_guard_prune"]
    optimize["task"] = "optimize"
    optimize_rejected = candidate.build_proposals(optimize)

    positive_ready = sum(item["ready"] for item in records)
    positive_full_replay = sum(
        item["full_replay_pass_count"] == item["proposal_count"] > 0
        for item in records
    )
    result = {
        "schema_version": "geotarget.replay-guided-relation-domain-csp-generated/v1",
        "positive_total": len(records),
        "positive_ready": positive_ready,
        "positive_full_replay_all": positive_full_replay,
        "target_change_preserved_assignment_signature": (
            first.get("assignment_signature_sha256")
            == second.get("assignment_signature_sha256")
            and first.get("proposal_count") == second.get("proposal_count")
        ),
        "constraint_permutation_preserved_assignment_signature": (
            first.get("assignment_signature_sha256")
            == third.get("assignment_signature_sha256")
        ),
        "all_root_then_guard_prune_observed": (
            records[0]["pre_arc_assignment_product"] == 2
            and records[0]["post_arc_assignment_product"] == 1
            and records[0]["arc_values_removed"] >= 1
        ),
        "underconstrained_fell_back": underconstrained["status"]
        == "NOT_APPLICABLE_BASELINE_FALLBACK",
        "combinatorial_cap_fell_back": capped["status"]
        == "NOT_APPLICABLE_BASELINE_FALLBACK",
        "truth_input_rejected": truth_rejected["status"]
        == "NOT_APPLICABLE_BASELINE_FALLBACK",
        "postprocess_rejected": postprocess_rejected["status"]
        == "NOT_APPLICABLE_BASELINE_FALLBACK",
        "nonsolve_task_rejected": optimize_rejected["status"]
        == "NOT_APPLICABLE_BASELINE_FALLBACK",
        "authority_pass_count": sum(item["authority_pass"] for item in records),
        "target_release_count": sum(item["target_release"] for item in records),
        "selection_read_raw_target": False,
        "selection_used_case_id_family_truth_or_outcome": False,
        "records": records,
        "hashes": {
            name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
            for name in ("candidate.py", "run_generated.py")
        },
    }
    result["decision"] = (
        "GO_STATIC_AUDIT"
        if (
            positive_ready == len(records)
            and positive_full_replay == len(records)
            and result["target_change_preserved_assignment_signature"]
            and result["constraint_permutation_preserved_assignment_signature"]
            and result["all_root_then_guard_prune_observed"]
            and result["underconstrained_fell_back"]
            and result["combinatorial_cap_fell_back"]
            and result["truth_input_rejected"]
            and result["postprocess_rejected"]
            and result["nonsolve_task_rejected"]
            and result["authority_pass_count"] == 0
            and result["target_release_count"] == 0
        )
        else "STOP_STATIC_AUDIT"
    )
    return result


def main():
    result = run()
    output = HERE / "GENERATED_RESULT.json"
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "records"}, indent=2))
    if result["decision"] != "GO_STATIC_AUDIT":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
