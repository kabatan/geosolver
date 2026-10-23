"""Audit preserved Q39 evidence without running a solver or changing its records."""
from collections import Counter
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import statistics


BASE = Path(__file__).resolve().parent
OUT = BASE / "execution"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binary_value(value):
    sign, mantissa, exponent, _ = value
    return Fraction((-1 if int(sign) else 1) * int(mantissa)) * Fraction(2) ** int(exponent)


def main():
    assert (OUT / "rear-complete.json").exists(), "Rear execution is still incomplete"
    errors = []

    def check(condition, message):
        if not condition:
            errors.append(message)

    root = Path(read(BASE / "runtime-location.json")["root"])
    lock = read(BASE / "prediction.lock.json")
    source = read(BASE / "source-manifest.json")
    start = read(BASE / "rear-start.json")
    check(sha(BASE / "prediction.lock.json") == read(BASE / "execution-start.json")["prediction_lock_sha256"], "prediction lock")
    frozen = {**{BASE / p: h for p, h in lock["artifacts_sha256"].items()},
              **{root / p: h for p, h in {**source["tracked_src_files_sha256"], **source["read_inputs_sha256"]}.items()}}
    for path, expected in frozen.items():
        check(sha(path) == expected, "frozen bytes: " + str(path))
    for path, expected in start["wrapper_sha256"].items():
        check(sha(BASE / path) == expected, "rear wrapper: " + path)
    selected = read(BASE / "selection.json")["selected"]
    for row in selected:
        check(sha(root / row["dsl_path"]) == row["dsl_sha256"], "DSL: " + row["id"])
    seal = read(OUT / "front-seal.json")
    check(sha(OUT / "front-seal.json") == start["front_seal_sha256"], "front seal")
    check(len(seal["sha256"]) == 1440, "front record count")
    check(set(seal["sha256"]) == {str(p.relative_to(OUT)) for p in (OUT / "front").rglob("[0-7].json")}, "front record identities")
    for path, expected in seal["sha256"].items():
        check(sha(OUT / path) == expected, "sealed front: " + path)

    jobs, status, load, intervals = {}, {}, [], []
    for stage, expected_count in (("prepare", 25), ("front", 180), ("rear", 516)):
        plan = read(OUT / (stage + "-jobs.json"))
        check(len(plan) == expected_count, "job count: " + stage)
        check(read(OUT / (stage + "-complete.json"))["jobs"] == expected_count, "completion marker: " + stage)
        expected_keys = {job["key"] for job in plan}
        actual_keys = {p.stem for p in (OUT / "jobs").glob(stage + "-*.json") if not p.name.endswith(".started.json")}
        check(actual_keys == expected_keys, "job receipt identities: " + stage)
        statuses = Counter()
        for job in plan:
            key = job["key"]
            receipt = read(OUT / "jobs" / (key + ".json"))
            began = read(OUT / "jobs" / (key + ".started.json"))
            process = read(OUT / "processes" / (key + ".json"))
            check(receipt["job"] == job and began["job"] == job and process["job"] == job, "job identity: " + key)
            check(process["cpu"] in (3, 7, 12), "CPU: " + key)
            check(not process["affinity_violations"], "affinity: " + key)
            check(process["peak_tree_rss_bytes"] <= 2 * 1024**3, "RSS: " + key)
            statuses[receipt["status"]] += 1
            if began.get("load_average"):
                load.append(began["load_average"])
            end = datetime.fromisoformat(process["utc_end"].replace("Z", "+00:00")).timestamp()
            intervals.extend([(end - process["elapsed_seconds"], 1), (end, -1)])
        jobs[stage] = plan
        status[stage] = dict(statuses)
    active = maximum = 0
    for _, change in sorted(intervals):
        active += change
        maximum = max(maximum, active)
    check(maximum <= 3, "more than three concurrent numerical jobs")

    rear_count = measurement_count = input_count = 0
    observation_statuses = Counter()
    for job in jobs["rear"]:
        f, r = job["front_mode"], job["rear_mode"]
        path = OUT / "rear" / job["id"] / str(job["seed"]) / (f + "--" + r).replace(":", "_")
        phase = path / "phase-c.json"
        check(phase.exists(), "missing Phase C: " + job["key"])
        observation_statuses[read(path / "observation-receipt.json")["status"]] += 1
        for index in range(8):
            src = OUT / "front" / job["id"] / str(job["seed"]) / f.replace(":", "_") / f"{index}.json"
            saved_path = path / f"{index}.json"
            saved, front = read(saved_path), read(src)
            rear_count += 1
            check(saved["input_sha256"] == sha(src), "rear input hash: " + str(saved_path))
            check(saved["missing"] == (front["candidate"] is None), "missing candidate: " + str(saved_path))
            if front["candidate"] is not None:
                point = next(s["point"] for s in saved["snapshots"] if s["label"] == "input")
                check([binary_value(x) for x in point] == [Fraction.from_float(float.fromhex(x)) for x in front["candidate"]["x_hex"]], "binary input coordinates: " + str(saved_path))
                input_count += 1
            measured_path = path / f"measurement-{index}.json"
            measured = read(measured_path)
            measurement_count += 1
            check(measured["source_sha256"] == sha(saved_path), "measurement source: " + str(measured_path))
            check(measured_path.stat().st_mtime_ns <= phase.stat().st_mtime_ns, "measurement saved after Phase C: " + str(measured_path))
    check(rear_count == 4128 and measurement_count == 4128, "rear/measurement counts")

    protocol = read(BASE / "protocol.json")
    orders = [read(p) for p in (OUT / "orders").glob("*.json")]
    check({r["id"] for r in orders} == set(protocol["controls"]["R0_ids"]), "order probe identities")
    for row in orders:
        check(row["new_solves"] == 0, "new root search in order diagnostic")
        if row.get("root_file"):
            check(sha(OUT / row["root_file"]) == row["root_file_sha256"], "order root hash: " + row["id"])
    grading = {}
    summary = read(BASE / "summary.json")
    for name in summary["official"]:
        folder = BASE / "campaign" / name
        manifest = read(folder / "campaign-manifest.json")
        rows = [json.loads(line) for line in (folder / "assessment.jsonl").read_text().splitlines()]
        expected = {(case["id"], seed) for case in manifest["cases"] for seed in protocol["seeds"]}
        check(len(rows) == len(expected) and {(r["case_id"], r["seed"]) for r in rows} == expected, "assessment identities: " + name)
        check(sum(r["matched"] is True for r in rows) == summary["official"][name]["all_matches"], "assessment total: " + name)
        receipt = read(OUT / "postprocessing" / ("grade-" + name + ".json"))
        check(receipt["status"] == "completed", "grade completion: " + name)
        grading[name] = {"runs": len(rows), "matched": sum(r["matched"] is True for r in rows)}
    check(len(grading) == 22, "campaign count")
    budget = read(OUT / "observation-budget.json")
    check(not budget["active"] and budget["remaining"] >= 0 and budget["spent"] <= 1200, "observation budget")
    files = [p for p in BASE.rglob("*") if p.is_file()]
    oversized = [str(p.relative_to(BASE)) for p in files if p.stat().st_size >= 5_000_000]
    check(not oversized, "oversized files")
    result = {"utc": datetime.now(timezone.utc).isoformat(), "passed": not errors, "errors": errors,
              "frozen_hash_checks": len(frozen), "selected_DSL_checks": len(selected),
              "rear_wrapper_hash_checks": len(start["wrapper_sha256"]), "sealed_front_records": 1440,
              "job_statuses": status, "maximum_concurrent_numerical_jobs": maximum,
              "rear_records": rear_count, "exact_binary_input_checks": input_count,
              "measurement_source_hash_checks": measurement_count, "measurements_saved_before_Phase_C": not any("after Phase C" in e for e in errors),
              "observation_statuses": dict(observation_statuses), "order_statuses": dict(Counter(r["status"] for r in orders)),
              "grading": grading, "observation_budget": budget,
              "job_start_load_average": {str(minutes) + "min": {"min": min(x[i] for x in load), "median": statistics.median(x[i] for x in load), "max": max(x[i] for x in load)} for i, minutes in enumerate((1, 5, 15))},
              "max_file_bytes": max(p.stat().st_size for p in files), "oversized_files": oversized,
              "solver_executions_in_this_audit": 0}
    (BASE / "completion-audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("passed", "errors", "job_statuses", "rear_records", "exact_binary_input_checks", "measurement_source_hash_checks", "order_statuses")}))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
