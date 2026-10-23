"""Cross-check saved grading views, complete-case tables and missing-data bounds."""
from __future__ import annotations

from collections import Counter
import csv
import itertools
import json
import re

import isolated_stage2 as execution


def main():
    base = execution.BASE
    summary = execution.read(base / "summary.json")
    audit = execution.read(base / "integrity-audit.json")
    assert audit["complete"] and not audit["issues"]
    rows = list(csv.DictReader((base / "per-run.csv").open()))
    assert len(rows) == 360
    bykey = {(r["id"], int(r["seed"]), int(r["budget_seconds"])): r for r in rows}
    assert len(bykey) == 360
    unchanged = substituted = 0
    for receipt_path in sorted((base / "grading-views").glob("*/*/view-receipt.json")):
        receipt = execution.read(receipt_path)
        budget, seed = receipt["budget"], receipt["seed"]
        original = base / f"campaign/t{budget}/s{seed}"
        view = receipt_path.parent
        assert (original / "campaign-manifest.json").read_bytes() == (view / "campaign-manifest.json").read_bytes()
        exceptions = {r["id"] for r in receipt["substitutions_for_unknown_only"]}
        graded = [json.loads(line) for line in (view / "assessment.jsonl").read_text().splitlines()]
        assert len(graded) == 40
        assert execution.sha(view / "assessment.jsonl") == receipt["assessment_sha256"]
        for grade in graded:
            cid = grade["case_id"]
            rawpath = original / f"runs/{cid}/{seed}.json"
            viewpath = view / f"runs/{cid}/{seed}.json"
            row = bykey[cid, seed, budget]
            assert execution.sha(rawpath) == row["raw_sha256"]
            if cid in exceptions:
                raw = execution.read(rawpath)["solver_result"]
                assert raw["status"] == "engine_error" and raw["diagnostics"] is None
                assert execution.read(viewpath)["solver_result"] is None
                assert not grade["normal_completion"] and not grade["matched"]
                assert row["mechanism_y"] == ""
                substituted += 1
            else:
                assert rawpath.read_bytes() == viewpath.read_bytes()
                unchanged += 1
            expected = str(int(grade["matched"])) if grade["normal_completion"] and grade["matched"] is not None else ""
            assert row["mechanism_y"] == expected
    assert (unchanged, substituted) == (343, 17)
    assert Counter(r["category"] for r in rows) == {"correct": 285, "normal_incorrect": 24, "unknown": 51}
    for budget in (180, 360, 900):
        actual = Counter(r["category"] for r in rows if int(r["budget_seconds"]) == budget)
        assert dict(actual) == summary["budget_categories_out_of_120"][str(budget)]

    # Independently enumerate allowed three-bit patterns and use set
    # intersections (not the analysis code's loss-count implementation).
    edges = {"000": set(), "001": set(), "010": {"360-900"}, "011": set(),
             "100": {"180-360", "180-900"}, "101": {"180-360"},
             "110": {"180-900", "360-900"}, "111": set()}
    totals = {m: [0, 0] for m in ("N", "R", "R3", "V")}
    completion_count = 0
    for problem in csv.DictReader((base / "per-problem.csv").open()):
        patterns = [problem[f"pattern_{seed}"] for seed in (370101, 370201, 370301)]
        options = [[p for p in edges if all(x == "?" or x == y for x, y in zip(pattern, p, strict=True))]
                   for pattern in patterns]
        flags = []
        for a, b, c in itertools.product(*options):
            x, y, z = edges[a], edges[b], edges[c]
            flags.append({"N": int(bool(x | y | z)), "R": int(bool((x & y) | (x & z) | (y & z))),
                          "R3": int(bool(x & y & z)), "V": int(any(p in {"101", "010"} for p in (a, b, c)))})
        completion_count += len(flags)
        for metric in totals:
            limits = [min(r[metric] for r in flags), max(r[metric] for r in flags)]
            assert limits == [int(problem[metric + "_lower"]), int(problem[metric + "_upper"])]
            totals[metric] = [a + b for a, b in zip(totals[metric], limits, strict=True)]
    assert totals == summary["mechanism_metric_bounds_out_of_40"]
    assert all(p["verdict"] == "判定不能" for p in summary["predictions"].values())
    for name in ("answer.md", "execution-notes.md"):
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", (base / name).read_text()):
            assert (base / target).exists(), (name, target)
    report = {"utc": execution.now(), "solver_runs": 0, "issues": [], "checked_runs": 360,
              "byte_identical_grading_inputs": unchanged, "isolated_unknown_inputs": substituted,
              "independently_enumerated_problem_completions": completion_count,
              "independent_metric_bounds": totals, "report_links_exist": True,
              "script_sha256": execution.sha(__file__),
              "verified_file_sha256": {name: execution.sha(base / name) for name in (
                  "answer.md", "execution-notes.md", "summary.json", "per-run.csv", "per-problem.csv",
                  "budget-pairs.csv", "per-triplet.csv", "mechanism-summary.json", "integrity-audit.json")}}
    execution.save(execution.EXEC / "final-validation.json", report)
    print(json.dumps({k: v for k, v in report.items() if k != "verified_file_sha256"}, indent=2))


if __name__ == "__main__":
    main()
