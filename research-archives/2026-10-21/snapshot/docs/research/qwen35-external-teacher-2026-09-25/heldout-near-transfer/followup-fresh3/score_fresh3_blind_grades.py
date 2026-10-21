"""Count frozen fresh3 blind grades by condition and source-ID group.

This helper reads only frozen job metadata, the blind-ID mapping, and grader
JSON. It never opens model-output or packet files.
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path


HERE = Path(__file__).resolve().parent
FIELDS = ("exact", "relation", "proof", "use")
EXPECTED_IDS = {
    "H03", "H04", "H08", "H14", "H15", "H01", "H02", "H07", "H13"
}
EXPECTED_CONDITIONS = 3


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_grade_rows(path: Path):
    value = read_json(path)
    if isinstance(value, dict):
        if "grades" not in value:
            raise ValueError(f"{path}: expected a grade list or an object with 'grades'")
        value = value["grades"]
    if not isinstance(value, list):
        raise ValueError(f"{path}: grades must be a JSON list")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mapping", type=Path, required=True,
                        help="mapping.json emitted by make_blind_packet.py")
    parser.add_argument("--grade", type=Path, action="append", required=True,
                        help="blind-grade JSON; repeat to combine grade partitions")
    parser.add_argument("--jobs", type=Path, default=HERE / "eval_jobs.json",
                        help="frozen fresh3 eval_jobs.json (defaults to this directory)")
    args = parser.parse_args()

    jobs = read_json(args.jobs)
    require(isinstance(jobs, list), f"{args.jobs}: jobs must be a JSON list")
    jobs_by_id = {}
    jobs_by_source = {}
    for row in jobs:
        job_id = row["id"]
        source_id = row["source_id"]
        require(job_id not in jobs_by_id, f"duplicate frozen job id: {job_id}")
        require(source_id not in jobs_by_source,
                f"duplicate frozen source id: {source_id}")
        jobs_by_id[job_id] = row
        jobs_by_source[source_id] = row
    require(set(jobs_by_source) == EXPECTED_IDS,
            f"frozen job source IDs differ: {sorted(jobs_by_source)}")
    require(len(jobs) == 9, f"expected 9 frozen jobs, found {len(jobs)}")

    projection_ids = {
        source_id for source_id, row in jobs_by_source.items()
        if row.get("transfer_cluster") == "orthocenter_median_projection"
    }
    h08_ids = {
        source_id for source_id, row in jobs_by_source.items()
        if row.get("transfer_cluster") == "tangent_circle_reflection_near_transfer"
    }
    h15_ids = {
        source_id for source_id, row in jobs_by_source.items()
        if row.get("transfer_cluster") == "three_reflection_midpoint_independent_case"
    }
    retention_ids = {
        source_id for source_id, row in jobs_by_source.items()
        if row.get("evaluation_role") == "source_retention_control"
    }
    require(projection_ids == {"H03", "H04", "H14"},
            f"unexpected projection cluster IDs: {sorted(projection_ids)}")
    require(h08_ids == {"H08"}, f"unexpected H08 cluster IDs: {sorted(h08_ids)}")
    require(h15_ids == {"H15"}, f"unexpected H15 cluster IDs: {sorted(h15_ids)}")
    require(retention_ids == {"H01", "H02", "H07", "H13"},
            f"unexpected retention IDs: {sorted(retention_ids)}")
    groups = {
        "projection_cluster": projection_ids,
        "H08": h08_ids,
        "H15": h15_ids,
        "retention": retention_ids,
        "all9": EXPECTED_IDS,
    }

    mapping_rows = read_json(args.mapping)
    require(isinstance(mapping_rows, list),
            f"{args.mapping}: mapping must be a JSON list")
    mapping = {}
    sources_by_condition = defaultdict(set)
    for row in mapping_rows:
        blind_id = row["blind_id"]
        condition = row["condition"]
        job_id = row["job_id"]
        require(blind_id not in mapping, f"duplicate blind ID in mapping: {blind_id}")
        require(isinstance(condition, str) and condition.strip(),
                f"mapping row {blind_id}: empty condition")
        require(job_id in jobs_by_id, f"mapping row {blind_id}: unknown job id {job_id}")
        source_id = jobs_by_id[job_id]["source_id"]
        if "source_id" in row:
            require(row["source_id"] == source_id,
                    f"mapping row {blind_id}: source_id disagrees with frozen jobs")
        require(source_id not in sources_by_condition[condition],
                f"duplicate source {source_id} in condition {condition}")
        sources_by_condition[condition].add(source_id)
        mapping[blind_id] = {
            "condition": condition,
            "job_id": job_id,
            "source_id": source_id,
        }

    conditions = set(sources_by_condition)
    require(len(conditions) == EXPECTED_CONDITIONS,
            f"expected exactly 3 conditions, found {sorted(conditions)}")
    require(len(mapping) == EXPECTED_CONDITIONS * len(EXPECTED_IDS),
            f"expected 27 mapping rows, found {len(mapping)}")
    for condition, source_ids in sources_by_condition.items():
        require(source_ids == EXPECTED_IDS,
                f"condition {condition} has source IDs {sorted(source_ids)}, expected all 9")

    grades = {}
    for path in args.grade:
        for row in read_grade_rows(path):
            blind_id = row["blind_id"]
            require(blind_id in mapping, f"grade {blind_id} is absent from mapping")
            require(blind_id not in grades, f"duplicate grade for blind ID {blind_id}")
            for field in FIELDS:
                require(type(row.get(field)) is bool,
                        f"grade {blind_id}: {field} must be a boolean")
            require(type(row.get("uncertain")) is bool and not row["uncertain"],
                    f"grade {blind_id}: uncertain grades are not allowed")
            if "source_id" in row:
                require(row["source_id"] == mapping[blind_id]["source_id"],
                        f"grade {blind_id}: source_id disagrees with mapping")
            grades[blind_id] = row
    require(grades.keys() == mapping.keys(),
            f"grade/mapping blind IDs differ; missing={sorted(mapping.keys() - grades.keys())}, "
            f"extra={sorted(grades.keys() - mapping.keys())}")

    grouped = defaultdict(lambda: defaultdict(dict))
    for blind_id, row in grades.items():
        map_row = mapping[blind_id]
        grouped[map_row["condition"]][map_row["source_id"]] = row

    result = {"conditions": {}}
    for condition in sorted(conditions):
        condition_rows = grouped[condition]
        require(set(condition_rows) == EXPECTED_IDS,
                f"condition {condition} grades do not cover the 9 source IDs")
        condition_counts = {}
        for group_name, source_ids in groups.items():
            rows = [condition_rows[source_id] for source_id in sorted(source_ids)]
            scores = {field: sum(row[field] for row in rows) for field in FIELDS}
            scores["complete"] = sum(all(row[field] for field in FIELDS) for row in rows)
            condition_counts[group_name] = {"n": len(rows), **scores}
        result["conditions"][condition] = condition_counts

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
