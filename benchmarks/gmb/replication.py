"""Repeat a sealed GMB campaign without changing its per-run measurement code."""

from __future__ import annotations

import argparse
import copy
import csv
import io
import json
import statistics
import subprocess
from collections import Counter
from contextlib import ExitStack, redirect_stdout
from pathlib import Path

from benchmarks.gmb import campaign as c

SCRIPT = Path(__file__).resolve()
PROTOCOL = c.ROOT / "REPLICATION_PROTOCOL.md"
SAME_CONDITIONS = (
    "upstream_commit",
    "source_files",
    "cpu",
    "jobs",
    "timeout_seconds",
    "termination_grace_seconds",
    "upstream_defaults",
    "options",
    "entries",
)


def check_seeds(seeds, previous):
    if not seeds or any(type(seed) is not int or seed < 0 or seed >= 2**32 for seed in seeds):
        raise ValueError("seeds must be unsigned 32-bit integers")
    if len(set(seeds)) != len(seeds) or set(seeds) & set(previous):
        raise ValueError("duplicate or already-measured seed")


def check_same_conditions(baseline, repeated):
    for key in SAME_CONDITIONS:
        if baseline[key] != repeated[key]:
            raise ValueError(f"condition changed: {key}")
    for name, digest in baseline["identity_files"].items():
        if repeated["identity_files"].get(name) != digest:
            raise ValueError(f"measurement implementation changed: {name}")
    if baseline["runtime_identity"] != repeated["runtime_identity"]:
        raise ValueError("runtime identity changed")
    check_seeds(repeated["seeds"], baseline["seeds"])


def prepare(baseline_dir, directory, seeds):
    baseline = c.read_json(baseline_dir / "campaign-manifest.json")
    check_seeds(seeds, baseline["seeds"])
    c.assert_identity(baseline_dir, baseline)
    with redirect_stdout(io.StringIO()):
        c.verify(baseline_dir)
    scoped_dirty = c.git(
        "status",
        "--porcelain",
        "--untracked-files=all",
        "--",
        "benchmarks/gmb",
        "tests/gmb/test_campaign.py",
        "tests/gmb/test_environment.py",
        "tests/gmb/test_replication.py",
    )
    if scoped_dirty:
        raise RuntimeError("commit the GMB protocol/implementation before running")
    c.env.choose_cpu(baseline["cpu"])
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "inputs").mkdir()
    for entry in baseline["entries"]:
        if entry["input"]:
            (directory / entry["input"]).write_bytes((baseline_dir / entry["input"]).read_bytes())
    for name in ("PROTOCOL.md", "requirements.lock", "UPSTREAM-LICENSE"):
        (directory / name).write_bytes((baseline_dir / name).read_bytes())
    (directory / PROTOCOL.name).write_bytes(PROTOCOL.read_bytes())
    with ExitStack() as stack:
        stdout = stack.enter_context((directory / "doctor.stdout.log").open("w"))
        stderr = stack.enter_context((directory / "doctor.stderr.log").open("w"))
        subprocess.run(
            [
                "taskset",
                "--cpu-list",
                str(baseline["cpu"]),
                str(c.env.PYTHON),
                "-B",
                str(c.ROOT / "environment.py"),
                "_child",
                "doctor",
                str(baseline["cpu"]),
            ],
            cwd=directory,
            env=c.env.child_environment(directory),
            stdout=stdout,
            stderr=stderr,
            check=True,
            timeout=120,
        )
    manifest = copy.deepcopy(baseline)
    manifest.update(
        purpose="gmb_imo39_seed_replication",
        prepared_utc=c.utc_now(),
        repo_commit=c.git("rev-parse", "HEAD"),
        repo_dirty=c.git("status", "--porcelain", "--untracked-files=all"),
        runtime_identity=c.read_json(directory / "doctor.stdout.log"),
        doctor_sha256=c.sha256(directory / "doctor.stdout.log"),
        host=c.host_snapshot(baseline["cpu"]),
        seeds=seeds,
        execution_order="seed_major_then_case_id",
        baseline={
            "directory": str(baseline_dir),
            "manifest_sha256": c.sha256(baseline_dir / "campaign-manifest.json"),
            "sha256sums_sha256": c.sha256(baseline_dir / "SHA256SUMS"),
        },
    )
    for path in (SCRIPT, PROTOCOL):
        manifest["identity_files"][str(path.relative_to(c.REPO))] = c.sha256(path)
    check_same_conditions(baseline, manifest)
    c.write_json(directory / "campaign-manifest.json", manifest)
    print(f"Prepared seeds {seeds}, same inputs/settings/measurement code: {directory}")


def run(directory):
    manifest = c.read_json(directory / "campaign-manifest.json")
    c.assert_identity(directory, manifest)
    if (directory / "SHA256SUMS").exists():
        raise RuntimeError("sealed campaign cannot be rerun")
    for seed in manifest["seeds"]:
        print(f"Starting seed {seed}", flush=True)
        for entry in manifest["entries"]:
            if not entry["input"]:
                continue
            run_dir = directory / "runs" / entry["case_id"] / str(seed)
            if (run_dir / "run.json").exists():
                continue
            if run_dir.exists():
                raise RuntimeError(f"incomplete run requires review: {run_dir}")
            c.run_one(directory, manifest, entry, seed)
    c.assert_identity(directory, manifest)


def statistics_from_rows(rows):
    pairs = [(row["case_id"], row["seed"]) for row in rows]
    if len(set(pairs)) != len(pairs):
        raise ValueError("duplicate case/seed result")
    seeds = sorted({row["seed"] for row in rows})
    case_ids = {row["case_id"] for row in rows}
    if len(rows) != len(seeds) * len(case_ids):
        raise ValueError("incomplete case/seed matrix")
    per_seed = []
    for seed in seeds:
        all_rows = [row for row in rows if row["seed"] == seed]
        executed = [row for row in all_rows if row["outcome"] != "unsupported"]
        models = [row for row in executed if row["outcome"] == "model_returned"]
        goals = [row for row in models if row.get("all_goals_passed") is not None]
        goal_success = sum(row["all_goals_passed"] for row in goals)
        per_seed.append(
            {
                "seed": seed,
                "executed": len(executed),
                "outcomes": dict(sorted(Counter(row["outcome"] for row in all_rows).items())),
                "model_returned": len(models),
                "model_rate": len(models) / len(executed),
                "goal_evaluable_models": len(goals),
                "goal_all_passed": goal_success,
                "goal_rate": goal_success / len(goals) if goals else None,
                "wall_seconds_all": c.distribution([row["wall_seconds"] for row in executed]),
                "wall_seconds_model_returned": c.distribution(
                    [row["wall_seconds"] for row in models]
                ),
                "cpu_seconds_all": c.distribution([row["cpu_seconds"] for row in executed]),
                "max_peak_rss_bytes": max(row["peak_rss_bytes"] for row in executed),
            }
        )
    per_case = []
    for case_id in sorted(case_ids):
        group = sorted((row for row in rows if row["case_id"] == case_id), key=lambda r: r["seed"])
        if len({row["availability"] for row in group}) != 1:
            raise ValueError("inconsistent case availability")
        entry = {"case_id": case_id, "availability": group[0]["availability"]}
        for row in group:
            for key in ("outcome", "all_goals_passed", "wall_seconds"):
                entry[f"seed{row['seed']}_{key}"] = row.get(key)
        entry["model_returned_count"] = sum(row["outcome"] == "model_returned" for row in group)
        entry["model_and_goals_passed_count"] = sum(
            row["outcome"] == "model_returned" and row.get("all_goals_passed") is True
            for row in group
        )
        per_case.append(entry)
    ran = [row for row in rows if row["outcome"] != "unsupported"]
    cases = [row for row in per_case if row["availability"] != "unsupported"]
    eligible = sum(item["goal_evaluable_models"] for item in per_seed)
    summary = {
        "seeds": seeds,
        "unique_cases_including_unsupported": len(case_ids),
        "unique_executable_cases": len(cases),
        "executed_runs": len(ran),
        "per_seed": per_seed,
        "macro_model_rate": statistics.mean(item["model_rate"] for item in per_seed),
        "macro_goal_rate": statistics.mean(item["goal_rate"] for item in per_seed)
        if all(item["goal_rate"] is not None for item in per_seed)
        else None,
        "pooled_model_rate": sum(item["model_returned"] for item in per_seed) / len(ran),
        "pooled_goal_rate": sum(item["goal_all_passed"] for item in per_seed) / eligible
        if eligible
        else None,
        "model_returned_count_histogram": dict(
            sorted(Counter(str(row["model_returned_count"]) for row in cases).items())
        ),
        "cases_succeeding_in_every_seed": sum(
            row["model_returned_count"] == len(seeds) for row in cases
        ),
        "cases_succeeding_in_any_seed": sum(row["model_returned_count"] > 0 for row in cases),
        "outcomes_all_runs_including_unsupported": dict(
            sorted(Counter(row["outcome"] for row in rows).items())
        ),
        "wall_seconds_all": c.distribution([row["wall_seconds"] for row in ran]),
        "cpu_seconds_all": c.distribution([row["cpu_seconds"] for row in ran]),
        "max_peak_rss_bytes": max(row["peak_rss_bytes"] for row in ran),
        "independent_geometry_validation": "not_performed",
    }
    return summary, per_case


def write_unchanged(path, text):
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            raise RuntimeError(f"refusing to overwrite different aggregation: {path}")
    else:
        path.write_text(text, encoding="utf-8")


def combine(baseline_dir, directory):
    baseline = c.read_json(baseline_dir / "campaign-manifest.json")
    repeated = c.read_json(directory / "campaign-manifest.json")
    check_same_conditions(baseline, repeated)
    if c.sha256(baseline_dir / "campaign-manifest.json") != repeated["baseline"]["manifest_sha256"]:
        raise ValueError("baseline manifest changed")
    if c.sha256(baseline_dir / "SHA256SUMS") != repeated["baseline"]["sha256sums_sha256"]:
        raise ValueError("baseline checksum manifest changed")
    with redirect_stdout(io.StringIO()):
        c.verify(baseline_dir)
        c.summarize(directory)
    rows = []
    for source, manifest in ((baseline_dir, baseline), (directory, repeated)):
        for row in c.rows_from_raw(source, manifest):
            rows.append(dict(row, campaign_directory=str(source)))
    summary, per_case = statistics_from_rows(rows)
    summary["source_manifest_hashes"] = [
        c.sha256(path / "campaign-manifest.json") for path in (baseline_dir, directory)
    ]
    write_unchanged(
        directory / "combined-summary.json",
        json.dumps(summary, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
    )
    write_unchanged(
        directory / "combined-runs.jsonl",
        "".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows),
    )
    write_unchanged(
        directory / "combined-cases.json",
        json.dumps(per_case, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
    )
    output = io.StringIO(newline="")
    fields = ["case_id", "availability", *sorted(set(per_case[0]) - {"case_id", "availability"})]
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(per_case)
    write_unchanged(directory / "combined-cases.csv", output.getvalue())
    print(json.dumps(summary, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "run", "combine"])
    parser.add_argument("directory", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--seeds", type=int, nargs="+", default=[1, 2])
    args = parser.parse_args()
    directory = args.directory.resolve()
    if args.command != "run" and args.baseline is None:
        parser.error("--baseline is required")
    if args.command == "prepare":
        prepare(args.baseline.resolve(), directory, args.seeds)
    elif args.command == "run":
        run(directory)
    else:
        combine(args.baseline.resolve(), directory)


if __name__ == "__main__":
    main()
