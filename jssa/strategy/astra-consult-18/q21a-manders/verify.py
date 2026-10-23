"""Check Q21a saved evidence and unchanged inputs; no optimization or imports from src."""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def csvrows(name):
    with (HERE / name).open(newline="") as f:
        return list(csv.DictReader(f))


def main():
    manifest = json.loads((HERE / "input-manifest.json").read_text())
    changed = [name for name, digest in manifest["files"].items()
               if sha(ROOT / name) != digest]
    src_paths = sorted((ROOT / "src").rglob("*.py"))
    src_digest = hashlib.sha256("".join(str(p.relative_to(ROOT)) + sha(p)
                                      for p in src_paths).encode()).hexdigest()
    assert not changed, changed
    assert src_digest == manifest["src_py_sha256"]
    assert sha(HERE / "analysis-plan.md") == manifest["analysis_plan_sha256"]
    assert sha(HERE / "analyze.py") == manifest["script_sha256"]

    summary = json.loads((HERE / "summary.json").read_text())
    problems = csvrows("per-problem.csv")
    eqs, guards = csvrows("constraint-taxonomy.csv"), csvrows("guard-taxonomy.csv")
    assert len(problems) == summary["problems"] == 292
    for key in ("records", "hit", "failed"):
        assert sum(int(r[key] or 0) for r in problems) == summary["totals"][key]
    assert summary["totals"]["records"] == summary["totals"]["hit"] + summary["totals"]["failed"]
    assert dict(Counter(r["semantic"] for r in eqs)) == summary["equation_types"]
    assert dict(Counter(r["semantic"] for r in guards)) == summary["guard_types"]
    eq_cross = Counter()
    semantic_cross = Counter()
    overlap = Counter()
    selected = {cid: [] for cid in (
        "HMMT-2007-FEB-GEO-02", "HMMT-2007-FEB-GEO-04",
        "HMMT-2024-FEB-GEO-02", "HMMT-2024-FEB-GEO-04")}
    with gzip.open(HERE / "endpoints.jsonl.gz", "rt") as f:
        count = 0
        for r in map(json.loads, f):
            count += 1
            eq_cross[(r["saved_class"], r["equalities"], r["hard"])] += 1
            semantic_cross[(r["metric_rows"], r["diagram_rows"], r["unclassified_rows"],
                            str(r["diagram_unmet_observed"]), str(r["metric_unmet_observed"]))] += 1
            overlap[(r["metric_unmet_observed"], r["diagram_unmet_observed"])] += 1
            if r["id"] in selected:
                selected[r["id"]].append(r)
    assert count == summary["totals"]["failed"]
    assert dict(eq_cross) == {(r["saved_class"], r["equalities"], r["hard"]): int(r["n"])
                              for r in csvrows("endpoint-cross-tab.csv")}
    assert dict(semantic_cross) == {(r["metric_rows"], r["diagram_rows"], r["unclassified_rows"],
                                    r["diagram_unmet"], r["metric_unmet"]): int(r["n"])
                                    for r in csvrows("semantic-cross-tab.csv")}
    for tol in ("1e-10", "1e-08", "1e-06"):
        assert sum(int(r["n"]) for r in csvrows("sensitivity.csv") if r["tolerance"] == tol) == count
    audited = summary["audits"]
    for key in ("q15_hard_mismatch", "q15_residual_mismatch", "hit_control_mismatch"):
        assert audited.get(key, 0) == 0

    v2 = json.loads((HERE / "two-axis-summary.json").read_text())
    assert sha(HERE / "semantic-v2-plan.md") == v2["plan_sha256"]
    assert sha(HERE / "semantic_v2.py") == v2["script_sha256"]
    assert sha(HERE / "hamami-2020-preprint.pdf") == v2["source_paper_sha256"]
    for filename, key in (("two-axis-constraints.csv", "constraints"), ("two-axis-guards.csv", "guards")):
        assert dict(Counter(r["two_axis_type"] for r in csvrows(filename))) == v2[key]
    v2_endpoints = csvrows("two-axis-endpoints.csv")
    assert len(v2_endpoints) == count
    assert len({(r["id"], r["k"]) for r in v2_endpoints}) == count
    v2_totals = Counter()
    for r in v2_endpoints:
        co = r["coexact_guard_unmet_observed"] == "True"
        for key, value in {"failed": True, "exact_unmet": r["exact_rows"] == "unmet",
                           "exact_metric_unmet": r["exact_metric_rows"] == "unmet",
                           "exact_topological_unmet": r["exact_topological_rows"] == "unmet",
                           "coexact_guard_unmet": co,
                           "both_exact_and_coexact_unmet": r["exact_rows"] == "unmet" and co,
                           "known_exact_met_coexact_unmet": r["exact_rows"] == "met" and co,
                           "unclassified_or_evaluation_issue": r["unclassified_or_evaluation_issue"] == "True"}.items():
            v2_totals[key] += int(value)
    for key, value in v2_totals.items():
        assert value == v2["totals"][key]
        assert value == sum(int(r[key]) for r in csvrows("two-axis-per-problem.csv"))
    assert v2["totals"]["finite_norm_crosschecks"] == audited["q15_finite_residual_pairs"]
    broken_links = []
    for filename in ("answer.md", "README.md"):
        for target in re.findall(r"\]\(([^)]+)\)", (HERE / filename).read_text()):
            if not target.startswith(("https://", "http://", "#")) and not (HERE / target).exists():
                broken_links.append((filename, target))
    assert not broken_links, broken_links

    r24 = selected["HMMT-2024-FEB-GEO-04"]
    assert len(r24) == 90
    assert all(r["guard_violations"] == ["guard[2] returned False"] and
               r["metric_rows"] == "unmet" for r in r24)
    r07 = selected["HMMT-2007-FEB-GEO-02"]
    assert len(r07) == 17
    assert all(r["metric_rows"] == "met" and r["diagram_rows"] == "unmet" and
               r["hard"] == "pass" for r in r07)
    cases = {r["id"]: r for r in map(json.loads, (ROOT / "benchmarks/cases.jsonl").read_text().splitlines())}
    c24 = cases["HMMT-2024-FEB-GEO-04"]["dsl"]
    assert next(x["expression"] for x in c24["constructions"] if x["name"] == "P") == "Point(s, p)"
    assert next(r["source"] for r in guards if r["id"] == "HMMT-2024-FEB-GEO-04" and r["row"] == "2") == "AssumeLt(p, s)"

    manual = {
        "status": "posthoc source-level annotation; does not modify fixed automatic taxonomy",
        "HMMT-2024-FEB-GEO-04": {
            "failed": 90,
            "metric_rows_unmet_and_guard_2_false": 90,
            "guard_2": "p < s",
            "meaning": "B=(s,0), C=(s,s), P=(s,p), s>0; P must lie before C on BC. The violated guard is diagrammatic order here.",
            "causal_interpretation": "unknown; both metric and diagrammatic conditions are unmet",
            "warning": "DSL point P is not the auxiliary foot P used in the official solution"
        },
        "HMMT-2007-FEB-GEO-02": {
            "selection": "additional semantic counterexample, selected after main aggregate; not one of the three fixed human-solution examples",
            "failed": 17,
            "metric_rows_met_diagram_row_unmet_hard_pass": 17,
            "meaning": "The three metric residual rows AP=8, PC=1, BD=6 are already imposed by construction on 0<b<3. The remaining OnCircle(D,Gamma) row is diagrammatic incidence but numerically an equation.",
            "branch_inequality": "b<3 represents BP<DP, a metric co-exact comparison, not a topological order predicate",
            "causal_interpretation": "no general workload reversal follows from construction-imposed metric rows"
        }
    }
    (HERE / "manual-audit.json").write_text(json.dumps(manual, ensure_ascii=False, indent=2) + "\n")
    result = {
        "passed": True,
        "input_files_unchanged": len(manifest["files"]),
        "src_py_files_unchanged": len(src_paths),
        "analysis_plan_unchanged": True,
        "analysis_script_unchanged": True,
        "problems": len(problems),
        "failed_endpoints_checked": count,
        "constraint_rows": len(eqs),
        "guard_rows": len(guards),
        "diagram_residual_problems": len({r["id"] for r in eqs if r["semantic"].startswith("diagram")}),
        "metric_guard_problems": len({r["id"] for r in guards if r["semantic"] == "metric_comparison"}),
        "metric_only_observed_unmet": overlap[(True, False)],
        "diagram_only_observed_unmet": overlap[(False, True)],
        "both_observed_unmet": overlap[(True, True)],
        "neither_observed_unmet": overlap[(False, False)],
        "unclassified_or_evaluation_issue": sum(int(r["unclassified_or_evaluation_issue"] or 0) for r in problems),
        "source_pdf_sha256": {p.name: sha(p) for p in sorted(HERE.glob("*.pdf"))},
        "q15_residual_mismatch": audited.get("q15_residual_mismatch", 0),
        "q15_hard_mismatch": audited["q15_hard_mismatch"],
        "hit_control_mismatch": audited["hit_control_mismatch"],
        "two_axis_summary_matches_endpoint_and_problem_counts": True,
        "two_axis_plan_and_script_unchanged": True,
        "broken_local_report_links": broken_links,
        "largest_current_artifact_bytes": max(p.stat().st_size for p in HERE.iterdir() if p.is_file())
    }
    (HERE / "verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
