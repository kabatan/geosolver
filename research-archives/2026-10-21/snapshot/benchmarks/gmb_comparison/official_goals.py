"""Post-hoc upstream goal diagnostics; never run either solver or rescale outputs.

The first timely native-accepted output is selected before goal evaluation, even
if the common checker rejected it. The upstream default threshold is preserved.
GMB's stored goals must first replay with matching labels and close values.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import subprocess
from collections import Counter
from pathlib import Path

from benchmarks.gmb import environment
from benchmarks.gmb_comparison.assessment import Assessment, sha256
from benchmarks.gmb_comparison.campaign import assert_identity
from benchmarks.gmb_comparison.checker import parse_gmbl

WORKER = Path(__file__).with_name("official_goals_worker.py")


def write_json(path, value):
    with path.open("x", encoding="utf-8") as handle:
        handle.write(
            json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
        )


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def seal_for(assessment, path):
    for seal in (assessment.raw, *(item[0] for item in assessment.legacy.values())):
        if path.is_relative_to(seal.root):
            return seal
    raise ValueError(f"No source seal: {path}")


def replay_validation(request, evaluated):
    """Tolerance is for float64 replay only, not a change to the official cutoff."""
    results = {row["job"]: row["result"] for row in evaluated}
    if len(results) != len(evaluated) or set(results) != {j["id"] for j in request["jobs"]}:
        raise ValueError("incomplete_or_duplicate_worker_output")
    comparisons = []
    for job in request["jobs"]:
        model = json.loads(Path(job["model"]).read_text())
        if sha256(job["model"]) != job["model_sha256"]:
            raise ValueError("GMB model changed during replay")
        expected = model["goals"]
        result = results[job["id"]]
        actual = result.get("values", {})
        expected_label = (
            all(math.isfinite(v) and v <= 0.01 for v in expected.values()) if expected else None
        )
        keys_match = set(actual) == set(expected)
        finite = keys_match and all(
            isinstance(actual[k], int | float) and math.isfinite(actual[k]) for k in expected
        )
        close = finite and all(
            math.isclose(actual[k], expected[k], rel_tol=1e-9, abs_tol=1e-12) for k in expected
        )
        comparisons.append(
            {
                "job": job["id"],
                "keys_match": keys_match,
                "values_close": close,
                "label_match": result["all_passed"] == expected_label,
                "status_ok": result["status"] in {"evaluated", "no_eval"},
                "max_abs_error": max((abs(actual[k] - expected[k]) for k in expected), default=0)
                if finite
                else None,
            }
        )
    return {
        "passed": all(
            all(row[k] for k in ("keys_match", "values_close", "label_match", "status_ok"))
            for row in comparisons
        ),
        "model_count": len(comparisons),
        "value_rtol": 1e-9,
        "value_atol": 1e-12,
        "comparisons": comparisons,
    }


def prepare(campaign, output):
    evidence = Assessment(campaign)
    assert_identity(evidence.root, evidence.manifest)
    if evidence.previous is None or evidence.legacy_errors:
        raise ValueError("Requires complete sealed common assessment and legacy records")
    summary = evidence.previous.mapping(evidence.output / "summary.json")
    if summary["complete_evidence"] is not True:
        raise ValueError("Common assessment has evidence issues")
    rows = [
        json.loads(line)
        for line in evidence.previous.read(evidence.output / "run-results.jsonl").splitlines()
    ]
    entries = {entry["case_id"]: entry for entry in evidence.manifest["entries"]}
    # Count input Eval clauses, not goals reached by the common checker. That
    # checker may stop at a failed assumption before reaching any goals.
    goal_counts = {
        case: sum(
            command[0] == "eval"
            for command in parse_gmbl(evidence.raw.read(evidence.root / entry["gmbl_input"]))
        )
        for case, entry in entries.items()
    }
    selection, jobs = [], {"gmb": [], "geosolver": []}
    for row in rows:
        models = [
            evidence.previous.mapping(evidence.output / name) for name in row["model_check_files"]
        ]
        timely = [
            model
            for model in models
            if model["native_accepted"]
            and model["within_deadline"]
            and not model["evidence_issues"]
        ]
        item = {
            "id": f"{row['method']}/{row['case_id']}/{row['seed']}",
            "method": row["method"],
            "case_id": row["case_id"],
            "seed": row["seed"],
            "common_any_output_success": row["success"],
            "model": None,
            "goal_clause_count": goal_counts[row["case_id"]],
        }
        if timely:
            first = min(timely, key=lambda model: (model["emitted_seconds"], model["model"]))
            model_path = Path(first["model"]).resolve()
            model_sha = seal_for(evidence, model_path).verify(model_path)
            if model_sha != first["identity"]["model_sha256"]:
                raise ValueError("model_identity_mismatch")
            source = evidence.root / entries[row["case_id"]]["gmbl_input"]
            source_sha = evidence.raw.verify(source)
            item.update(
                model=str(model_path),
                model_sha256=model_sha,
                emitted_seconds=first["emitted_seconds"],
                common_first_output_valid=first["checks"]["1e-6"]["result"]["valid"],
            )
            jobs[row["method"]].append(
                {
                    "id": item["id"],
                    "method": row["method"],
                    "model": str(model_path),
                    "model_sha256": model_sha,
                    "input": str(source),
                    "input_sha256": source_sha,
                    "goal_clause_count": goal_counts[row["case_id"]],
                }
            )
        selection.append(item)
    output.mkdir(parents=True, exist_ok=False)
    upstream = {
        str(path.relative_to(environment.SOURCE)): sha256(path)
        for path in sorted((environment.SOURCE / "src").glob("*.py"))
    }
    policy = {
        "schema_version": 1,
        "campaign": str(evidence.root),
        "campaign_manifest_sha256": evidence.manifest_hash,
        "raw_seal_sha256": evidence.raw.digest,
        "assessment_seal_sha256": evidence.previous.digest,
        "solver_identity": evidence.manifest["engine_identity"],
        "upstream_commit": environment.source_identity(),
        "upstream_source": str(environment.SOURCE),
        "upstream_sha256": upstream,
        "upstream_environment": evidence.manifest["gmb_environment"],
        "adapter_sha256": {
            str(Path(__file__).resolve()): sha256(__file__),
            str(WORKER): sha256(WORKER),
        },
        "model_selection": "first emitted timely native-accepted output, before any goal check",
        "coordinate_policy": (
            "saved coordinates, float64 conversion only; no rescaling or polishing"
        ),
        "evaluation": "original GMB Eval/eval_cons/register_goal; default eps*10=0.01",
        "nonfinite_policy": "never pass; report evaluation error/nonfinite separately",
        "goal_missing_policy": (
            "no_eval, never success; exclude only from conditional goal denominator"
        ),
        "scope": "post-hoc conclusion diagnostic, not assumption/configuration validation or proof",
        "scale_warning": "upstream goal values are not invariant under geometric rescaling",
        "replay_gate": {"all_labels_match": True, "rtol": 1e-9, "atol": 1e-12},
        "seeds": evidence.manifest["seeds"],
        "case_count": len(entries),
    }
    write_json(output / "manifest.json", policy)
    write_json(output / "selection.json", selection)
    for method in jobs:
        write_json(
            output / f"{method}-request.json",
            {
                "upstream_source": str(environment.SOURCE),
                "upstream_sha256": upstream,
                "jobs": jobs[method],
            },
        )
    return evidence, selection, policy


def invoke(output, method):
    env = environment.child_environment(output)
    with (output / f"{method}-worker.log").open("x") as log:
        subprocess.run(
            [
                "taskset",
                "--cpu-list",
                "4",
                str(environment.PYTHON),
                "-B",
                str(WORKER),
                str(output / f"{method}-request.json"),
                str(output / f"{method}-results.jsonl"),
            ],
            env=env,
            cwd=output,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=True,
            timeout=300,
        )


def aggregate(rows):
    eligible = [row for row in rows if row["model"] and row["goal_clause_count"] > 0]
    passed = sum(row["official"]["all_passed"] is True for row in eligible)
    return {
        "planned_runs": len(rows),
        "emitted_runs": sum(bool(r["model"]) for r in rows),
        "goal_eligible_emitted_runs": len(eligible),
        "goal_passed_runs": passed,
        "conditional_goal_rate": passed / len(eligible) if eligible else None,
        "status_counts": dict(Counter(row["official"]["status"] for row in rows)),
    }


def finish(output, evidence, selection, policy, validation):
    results = {}
    for method in ("gmb", "geosolver"):
        evaluated = read_rows(output / f"{method}-results.jsonl")
        expected = {
            job["id"] for job in json.loads((output / f"{method}-request.json").read_text())["jobs"]
        }
        if len(evaluated) != len(expected) or {r["job"] for r in evaluated} != expected:
            raise ValueError("Incomplete worker output")
        results.update({row["job"]: row["result"] for row in evaluated})
    rows = [
        dict(row, official=results.get(row["id"], {"status": "no_output", "all_passed": None}))
        for row in selection
    ]
    summary = {
        "schema_version": 1,
        "policy": policy,
        "replay_passed": validation["passed"],
        "by_method": {},
    }
    for method in ("gmb", "geosolver"):
        selected = [row for row in rows if row["method"] == method]
        value = aggregate(selected)
        value["by_seed"] = {
            str(seed): aggregate([r for r in selected if r["seed"] == seed])
            for seed in policy["seeds"]
        }
        rates = [v["conditional_goal_rate"] for v in value["by_seed"].values()]
        value["paper_style_mean_seed_goal_rate"] = (
            statistics.mean(rates) if all(r is not None for r in rates) else None
        )
        value["common_first_output_valid_and_goal_passed"] = sum(
            r.get("common_first_output_valid") is True and r["official"]["all_passed"] is True
            for r in selected
        )
        summary["by_method"][method] = value
    # Recheck all source evidence before publishing diagnostics.
    for seal in (evidence.raw, evidence.previous, *(item[0] for item in evidence.legacy.values())):
        seal.recheck()
    assert_identity(evidence.root, evidence.manifest)
    for name, digest in policy["adapter_sha256"].items():
        if sha256(name) != digest:
            raise ValueError("Adapter changed during evaluation")
    write_json(output / "rows.json", rows)
    write_json(output / "summary.json", summary)
    paths = sorted(path for path in output.rglob("*") if path.is_file())
    with (output / "SHA256SUMS").open("x") as handle:
        for path in paths:
            handle.write(f"{sha256(path)}  {path.relative_to(output).as_posix()}\n")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    evidence, selection, policy = prepare(args.campaign, output)
    print("Selection fixed; replaying GMB's stored goals", flush=True)
    invoke(output, "gmb")
    validation = replay_validation(
        json.loads((output / "gmb-request.json").read_text()),
        read_rows(output / "gmb-results.jsonl"),
    )
    write_json(output / "replay-validation.json", validation)
    if not validation["passed"]:
        raise RuntimeError("GMB replay gate failed; GeoSolver has not been scored")
    print("GMB replay passed; evaluating GeoSolver without search", flush=True)
    invoke(output, "geosolver")
    summary = finish(output, evidence, selection, policy, validation)
    print(json.dumps(summary["by_method"], ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
