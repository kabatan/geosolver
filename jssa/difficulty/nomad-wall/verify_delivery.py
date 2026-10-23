"""Verify frozen inputs, preserved evidence, explicit missingness, and file sizes."""
from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    selection = json.loads((HERE / "selection-manifest.json").read_text())
    campaign = json.loads((HERE / "campaign-manifest.json").read_text())["identity"]
    inventory = json.loads((HERE / "initial-attempt-inventory.json").read_text())
    sequential = json.loads((HERE / "completion-sequential-receipt.json").read_text())
    src_files = {str(p.relative_to(ROOT)): sha(p) for p in (ROOT / "src").rglob("*")
                 if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}
    checks = {
        "src_identical_to_initial_snapshot": src_files == selection["src_file_sha256"],
        "src_git_diff_60db4b6_empty": subprocess.check_output(
            ["git", "diff", "60db4b6", "--", "src"], cwd=ROOT, text=True) == "",
        "preregistration_unchanged": sha(HERE / "preregistration.md") == selection["preregistration_sha256"],
        "selection_unchanged": sha(HERE / "selected-cases.csv") == selection["selected_cases_sha256"],
        "selection_source_unchanged": sha(ROOT / "jssa/difficulty/minima/basins-323.csv") == selection["source_csv_sha256"],
        "registered_code_unchanged": all(sha(HERE / p) == h for p, h in campaign["code_sha256"].items()),
        "input_dsls_unchanged": all(sha(ROOT / v["path"]) == v["sha256"] for v in campaign["inputs"].values()),
        "research_runner_unchanged": sha(ROOT / "benchmarks/research_runner.py") == campaign["research_runner_sha256"],
        "original_121_raw_unchanged": all(sha(HERE / p) == h for p, h in inventory["retained_raw_sha256"].items()),
        "supplemental_first_4_raw_unchanged": all(sha(HERE / p) == h for p, h in sequential["preexisting_raw_sha256"].items()),
    }
    with (ROOT / "jssa/difficulty/minima/basins-323.csv").open() as stream:
        population = [{"id": r["id"], "n_vars": int(r["n_vars"])} for r in csv.DictReader(stream) if int(r["n_vars"]) >= 1]
    for r in population:
        r["hash"] = hashlib.sha256(("Q14-nomad-wall-20261023|" + r["id"]).encode()).hexdigest()
    fixed = list(csv.DictReader((HERE / "selected-cases.csv").open()))
    checks["selection_rule_reproduced"] = len(population) == 292 and [r["id"] for r in sorted(population, key=lambda r:(r["hash"], r["id"]))[:24]] == [r["id"] for r in fixed]
    primary = list(csv.DictReader((HERE / "per-run.csv").open()))
    supplement = list(csv.DictReader((HERE / "completion-per-run.csv").open()))
    checks["primary_slots_unique_complete"] = len(primary) == len({(r["id"], r["seed"], r["mode"]) for r in primary}) == 144
    pending = {(r["id"], str(r["seed"]), r["mode"]) for r in inventory["missing_slots"] if not r["solver_started"]}
    checks["supplement_only_initially_unstarted_slots"] = len(supplement) == 22 and {(r["id"], r["seed"], r["mode"]) for r in supplement} == pending
    accounting = Counter()
    evidence_exceptions = []
    observed_raw = Counter()
    for group, pattern in (("primary", "runs/*/runs/*/[012].json"), ("supplement", "completion/*/runs/*/[012].json")):
        for path in HERE.glob(pattern):
            raw = json.loads(path.read_text())
            if raw.get("failure_accounting_record"):
                accounting[group] += 1
                assert raw["solver_result"] is None and raw["observed_solver_result"] is False
            else:
                observed_raw[group] += 1
            if not path.with_suffix(".audit.jsonl").exists():
                evidence_exceptions.append({"path": str(path.relative_to(HERE)), "missing": "hook audit",
                    "accounting_record": bool(raw.get("failure_accounting_record")),
                    "status": (raw.get("solver_result") or {}).get("status")})
    checks["missing_results_explicitly_accounted"] = accounting == {"primary": 23, "supplement": 1}
    patch_hash = sha(HERE / "patch/nomad_wall_patch.py")
    counters = Counter()
    for path in list(HERE.glob("runs/*/runs/*/*.audit.jsonl")) + list(HERE.glob("completion/*/runs/*/*.audit.jsonl")):
        for line in path.read_text().splitlines():
            row = json.loads(line)
            if row["event"] == "installed":
                assert row["patch_sha256"] == patch_hash
                counters["installed_receipts"] += 1
            if row["event"] != "evaluation":
                continue
            assert row["preserved_record_score"] == row["original_score"]
            target = row["original_score"] if row["mode"] == "B" else row["equality_sq"]
            assert row["sent_score"] == target
            counters[f"{row['mode']}_finite_evaluations"] += 1
            counters[f"{row['mode']}_changed_payloads"] += row["changed"]
    checks["observed_payloads_and_record_scores_consistent"] = True
    pairs = list(csv.DictReader((HERE / "completion-merged-trace-pairs.csv").open()))
    checks["paired_nomad_initial_inputs_match"] = len(pairs) == 48 and all(r["same_initial_inputs"] == "True" for r in pairs)
    checks["no_coordinate_divergence_before_changed_payload"] = all(r["diverged_before_changed_payload"] == "False" for r in pairs)
    files = [p for p in HERE.rglob("*") if p.is_file() and p.name != "delivery-verification.json"]
    largest = max(files, key=lambda p:p.stat().st_size)
    checks["all_files_at_most_20_MiB"] = all(p.stat().st_size <= 20 * 1024**2 for p in files)
    checks["no_bytecode_artifacts"] = not any(p.suffix == ".pyc" for p in files)
    missing_links = []
    for name in ("answer.md", "README.md", "code-audit.md"):
        for link in re.findall(r"\]\(([^)]+)\)", (HERE / name).read_text()):
            if "://" in link or link == "delivery-verification.json":
                continue
            if not (HERE / link.split("#", 1)[0]).exists():
                missing_links.append({"file": name, "link": link})
    checks["report_links_resolve"] = not missing_links
    assert all(checks.values()), checks
    result = {"integrity_checks_passed": True, "checks": checks,
        "scientific_runtime_evidence_complete": False,
        "primary_slots": 144, "primary_observed_raw": observed_raw["primary"],
        "primary_failure_accounting_records": accounting["primary"],
        "supplement_slots": 22, "supplement_observed_raw": observed_raw["supplement"],
        "supplement_failure_accounting_records": accounting["supplement"],
        "known_missing_audits": evidence_exceptions, "observed_audit_counts": dict(counters),
        "paired_nomad_traces": len(pairs),
        "file_count_excluding_this_report": len(files), "total_bytes_excluding_this_report": sum(p.stat().st_size for p in files),
        "largest_file": str(largest.relative_to(HERE)), "largest_file_bytes": largest.stat().st_size,
        "artifact_sha256": {str(p.relative_to(HERE)): sha(p) for p in sorted(files)},
    }
    (HERE / "delivery-verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({k:v for k,v in result.items() if k not in ("artifact_sha256", "known_missing_audits")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
