"""Compare immutable, assessed solver campaigns without dropping failures."""

import argparse
import csv
import json
from pathlib import Path
import statistics


def read(path):
    return [json.loads(line) for line in (path / "assessment.jsonl").read_text().splitlines()]


def metrics(rows):
    values = sorted(row["process_wall_seconds"] for row in rows)
    return {
        "runs": len(rows),
        "exact_set_matches": sum(row["matched"] for row in rows),
        "mean_process_wall_seconds": statistics.mean(values),
        "median_process_wall_seconds": statistics.median(values),
        "total_process_wall_seconds": sum(values),
        "total_cpu_seconds": sum(row.get("cpu_seconds", 0) or 0 for row in rows),
        "non_normal_completion_count": sum(not row["normal_completion"] for row in rows),
        "failures_included": True,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    before = {row["case_id"]: row for row in read(args.baseline) if row["seed"] == args.seed}
    after = {row["case_id"]: row for row in read(args.candidate) if row["seed"] == args.seed}
    assert before.keys() == after.keys(), (before.keys() - after.keys(), after.keys() - before.keys())
    pairs = []
    for name in sorted(before):
        a, b = before[name], after[name]
        pairs.append({
            "case_id": name,
            "baseline_wall": a["process_wall_seconds"],
            "candidate_wall": b["process_wall_seconds"],
            "wall_delta": b["process_wall_seconds"] - a["process_wall_seconds"],
            "baseline_cpu": a.get("cpu_seconds"),
            "candidate_cpu": b.get("cpu_seconds"),
            "baseline_matched": a["matched"],
            "candidate_matched": b["matched"],
            "same_answer_set": a["actual"] == b["actual"],
            "baseline_answers": a["actual"],
            "candidate_answers": b["actual"],
        })
    report = {
        "baseline_campaign": str(args.baseline.resolve()),
        "candidate_campaign": str(args.candidate.resolve()),
        "seed": args.seed,
        "baseline": metrics(list(before.values())),
        "candidate": metrics(list(after.values())),
        "answer_set_agreements": sum(row["same_answer_set"] for row in pairs),
        "answer_set_changes": [row for row in pairs if not row["same_answer_set"]],
        "previous_matches_lost": [row for row in pairs if row["baseline_matched"] and not row["candidate_matched"]],
        "new_matches": [row for row in pairs if not row["baseline_matched"] and row["candidate_matched"]],
        "largest_wall_reductions": sorted(pairs, key=lambda row: row["wall_delta"])[:12],
        "largest_wall_increases": sorted(pairs, key=lambda row: -row["wall_delta"])[:12],
        "caution": "Campaigns are not interleaved paired timings; consult same-core ABBA experiments before attributing small timing differences to code.",
    }
    (args.candidate / "baseline-comparison.json").write_text(json.dumps(report, indent=2) + "\n")
    with (args.candidate / "baseline-comparison.csv").open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(pairs[0]))
        writer.writeheader()
        writer.writerows(pairs)
    print(json.dumps({key: value for key, value in report.items() if not isinstance(value, list)}, indent=2))


if __name__ == "__main__":
    main()
