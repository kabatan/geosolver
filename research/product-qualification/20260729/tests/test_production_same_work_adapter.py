from __future__ import annotations

from geotarget.production_same_work_adapter import (
    create_executor,
    structural_profile,
    workload_from_v15,
)


def test_v15_workload_discards_identity_and_profiles_structure() -> None:
    construction = [
        {"name": "A", "expr": "Point(x,y)"},
        {"name": "B", "expr": "Point(u,v)"},
    ]
    previous = "A"
    for index in range(9):
        name = f"P{index}"
        construction.append({"name": name, "expr": f"Midpoint({previous},B)"})
        previous = name
    problem = {
        "task": "solve",
        "id": "private-corpus-identity",
        "variables": {"names": ["x", "y", "u", "v"]},
        "construction": construction,
        "constraints": [{"def": f"Distance({previous},A)", "value": 1}],
        "guards": [],
        "answer": f"Distance({previous},B)",
        "post_process": "",
    }
    workload = workload_from_v15(problem, starts=3, callbacks_per_start=7)
    assert "deep_dag" in workload.structural_class
    assert workload.expression["problem"]["id"] == "same-work-generic-v15"
    assert "private-corpus-identity" not in str(workload.expression)
    assert workload.callback_cap == 21
    assert len(workload.proposals) == 21
    assert len(set(workload.proposals)) == 21


def test_profile_detects_fanout_and_wide_expression_without_id() -> None:
    problem = {
        "id": "ignored",
        "construction": [
            {"name": "A", "expr": "Point(x,y)"},
            *(
                {"name": f"P{i}", "expr": "Midpoint(A,A)"}
                for i in range(9)
            ),
        ],
        "constraints": [
            {"def": "Area(" + ",".join(f"P{i}" for i in range(9)) + ")", "value": 0}
        ],
        "guards": [],
        "answer": "Distance(A,A)",
    }
    profile = structural_profile(problem)
    assert profile["maximum_fanout"] == 11
    assert profile["maximum_call_arity"] == 9
    assert profile["structural_class"] == "high_fanout+wide_expression"


def test_factory_drives_production_reference_and_optimized_semantics() -> None:
    problem = {
        "task": "solve",
        "id": "generic",
        "variables": {"names": ["ax", "ay", "bx", "by"]},
        "construction": [
            {"name": "A", "expr": "Point(ax,ay)"},
            {"name": "B", "expr": "Point(bx,by)"},
        ],
        "constraints": [{"def": "Distance(A,B)", "value": 1}],
        "guards": [],
        "answer": "Distance(A,B)",
        "post_process": "",
    }
    workload = workload_from_v15(problem, starts=1, callbacks_per_start=1)
    executor = create_executor()
    executor.prepare((workload,))
    point = workload.proposals[0]
    reference = executor.callback("reference", workload, point)
    optimized = executor.callback("optimized", workload, point)
    manifest = executor.manifest()

    assert reference == optimized
    assert manifest["case_specific_routing"] is False
    assert manifest["problem_id_read"] is False
    assert len(manifest["prepared_support"]) == 1
    assert manifest["prepared_support"][0]["compiled_supported"] is True
    assert manifest["runner_owned_callback_wrapper"] is True
    assert manifest["untimed_correctness"][0]["guard_hard_selector_fault_checked"] is False
    assert manifest["untimed_correctness"][0]["status"].startswith("deferred")
