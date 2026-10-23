"""Read-only numerical/document checks; writes only its report inside G/."""
from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def read(name):
    return json.loads((HERE/name).read_text())


def main():
    checks = {}
    a, s, c, audit = read("summary.json"), read("mechanism-summary.json"), read("constant-audit.json"), read("inheritance-audit.json")
    text = (HERE/"answer.md").read_text()
    checks["answer_a_through_f"] = all(f"## ({letter})" in text for letter in "abcdef")
    checks["292_problems_55097_starts"] = a["census_problems"] == 292 and a["totals"]["n_F"]+a["totals"]["n_I"] == 55097
    checks["boundary_counts"] = all(a["totals"][k] == value for k, value in {
        "F_failed_finite":10696, "F_failed_endF":10489, "fail_b6":5466,
        "wall_count":4120, "hit_b6":10, "hit_tested":2235}.items())
    checks["pilot_P1_P4_all_pass"] = all(a["pilot"][p]["pass"] for p in ("P1", "P2", "P3", "P4"))
    checks["resume_R1_R5_verdicts"] = [s[f"R{i}"]["pass"] for i in range(1,6)] == [True, True, False, False, False]
    checks["resume_source_and_trace_consistency"] = not any(s[k] for k in ("source_mismatches", "trace_issues", "native_call_count_issues"))
    checks["resume_run_count"] = s["runs"] == 6720 and s["pairs"] == 1120
    checks["unknown_counts"] = len(s["same_coordinate_trials_unknown"]) == 364 and sum(r["count"] for r in s["same_coordinate_trials_unknown"]) == 1483
    checks["constant_posthoc_counts"] = (c["denominator_N_hit_C_fail"], c["C_fail_with_rejected_hit_in_last8"], c["C_fail_with_rejected_hit_equal_float_norm"]) == (537,429,422)
    checks["stop_only_outcomes"] = (s["B_S_same_class"], s["B_S_same_x"], s["B_S_status_changed"]) == (1120,1092,145)
    checks["inheritance_recheck"] = (not audit["input_hash_mismatches"] and not audit["source_count_differences"]
        and not any(audit["reanalysis_differences"].values()) and not audit["instrumentation_fix_outcome_changes"]
        and all(not v for r in audit["endpoint_example_recheck"].values() for v in r.values()))

    aime = read("mechanism-data/AIME-2010-II-14.json")["records"]
    rescue = [r for r in aime if r["F"] and r["B"]["cls"] != "hit" and r["N"]["cls"] == "hit"]
    checks["AIME_31_rescues_used_I"] = len(rescue) == 31 and all(r["N"]["native"]["accepted_I"] > 0 for r in rescue)
    checks["AIME_B_S_all80_exact_x"] = all(r["B"].get("x") == r["S"].get("x") for r in aime)
    f = [r for r in aime if r["F"]]
    checks["AIME_arm_hits"] = [sum(r[arm]["cls"] == "hit" for r in f) for arm in ("B","S","J","N","C","CS")] == [5,5,5,36,0,0]
    checks["AIME_35_F_failures_crossing_rejected"] = sum(r["B"]["cls"] != "hit" and r["B"]["native"]["F_to_I_eq_descent_rejected_other_ss_decrease"] > 0 for r in f) == 35

    expected_names = ["AIME 2010 II-14", "HMMT 2007 幾何6", "HMMT 2007 幾何4", "HMMT 2024 幾何1", "JMO 2017 予選1", "AIME 2007 I-15", "HMMT 2022 幾何3", "JMO 2006 予選2", "HMMT 2024 幾何4", "HMMT 2008 幾何2", "HMMT 2006 幾何6", "AIME 2022 I-8", "AIME 2003 II-11", "JMO 2024 予選3"]
    table_ok = True
    for name, row in zip(expected_names, read("intervention-summary.json")):
        match = re.search(r"^\| " + re.escape(name) + r" \| [\d.]+ \| [^|]+ \| (\d+)→(\d+) \| (\d+)→(\d+) \|$", text, re.M)
        expected = tuple(row[k] for k in ("F_baseline_hit", "F_no_hard_hit", "I_baseline_hit", "I_no_hard_hit"))
        table_ok &= match is not None and tuple(map(int, match.groups())) == expected
    checks["answer_14_problem_table_matches_data"] = table_ok

    bad_links = []
    for link in re.findall(r"\]\(([^)]+)\)", text+(HERE/"README.md").read_text()):
        if not link.startswith(("http:", "https:", "#")) and not (HERE/link.split("#")[0]).exists():
            bad_links.append(link)
    checks["all_local_report_links_exist"] = not bad_links
    for path in HERE.glob("*.py"):
        ast.parse(path.read_text(), filename=str(path))
    checks["all_python_sources_parse"] = True
    frozen = subprocess.run(["git", "diff", "--quiet", "60db4b6", "--", "src"], cwd=ROOT)
    checks["src_matches_frozen_commit"] = frozen.returncode == 0
    for name in ("provenance.json", "mechanism-provenance.json"):
        manifest = read(name)["sha256"]
        checks[name+"_hashes_match"] = all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest() == digest for p, digest in manifest.items())

    files = [p for p in HERE.rglob("*") if p.is_file() and p.name != "delivery-check.json"]
    checks["each_file_under_10_MiB"] = max(p.stat().st_size for p in files) < 10*1024*1024
    report = {"checks": checks, "all_pass": all(checks.values()), "bad_links": bad_links,
              "file_count": len(files)+1, "bytes_excluding_this_report": sum(p.stat().st_size for p in files),
              "largest_file_bytes": max(p.stat().st_size for p in files),
              "sha256": {str(p.relative_to(HERE)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}}
    (HERE/"delivery-check.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({"checks":checks, "all_pass":report["all_pass"], "bytes":report["bytes_excluding_this_report"]}, ensure_ascii=False, indent=2))
    if not report["all_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
