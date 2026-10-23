"""Synthetic measurement and grader-adapter checks, no solve or reference lookup."""
import diagnostic as d
import measure_stage2 as m


def main():
    problem = d.GeometryProblem.model_validate({"id": "Q39-observation-synthetic", "variables": ["x"],
        "constructions": [{"name": "P", "expression": "Point(x, 0)"},
                          {"name": "Q", "expression": "Point(0, 0)"}],
        "conditions": [{"left": "Distance(P, Q)", "operator": "=", "right": 0}],
        "target": "x + 3"})
    bundle = d.load_problem_bundle(problem.engine_document())
    evaluator = d.build_ir_evaluator(bundle)
    plan = {"a_rows": 1, "b_rows": 2, "compiled_rewrites": [{"kind": "distance_point_zero"}],
            "blocks": [{"a": 0, "b": [0, 1], "kind": "distance_point_zero", "rewrite": {}}]}
    reps = d.Representations(bundle, plan, {"a": [1.], "b": [1.]})
    with d.mp.workdps(180):
        good = m.observe_point(evaluator, reps, [d.mp.mpf(0)], [d.mp.mpf(3)])
        bad = m.observe_point(evaluator, reps, [d.mp.mpf(1)], [d.mp.mpf(3)])
    assert good["R50"] and good["R80"] and good["target_digits"] == 100, good
    assert not bad["R50"] and 0 < bad["target_digits"] < 1, bad
    assert good["Q"] == "0.0" and bad["Q"] == "1.0"
    from benchmarks import research_runner as rr
    assert rr.read_run_outcome({"solver_result": {"status": "solved", "termination_reason": "time_limit_reached"}})["normal_completion"]
    assert not rr.read_run_outcome({"solver_result": {"status": "solved"}, "process": {"timed_out": True}})["normal_completion"]
    assert not rr.read_run_outcome({"solver_result": {"status": "solved"}, "execution_contract_issues": ["test"]})["normal_completion"]
    d.save(d.BASE / "observation-check.json", {"utc": d.utc(), "status": "passed",
           "synthetic_point_evaluations": 2, "benchmark_reference_reads": 0,
           "solver_runs": 0, "refinement_runs": 0, "good": good, "bad": bad,
           "official_status_semantics": "unchanged",
           "sha256": {n: d.sha(d.BASE / n) for n in
                      ("diagnostic.py", "measure_stage2.py", "check_observation.py")}})
    print("synthetic observation and original status semantics passed; no solver run")


if __name__ == "__main__":
    main()
