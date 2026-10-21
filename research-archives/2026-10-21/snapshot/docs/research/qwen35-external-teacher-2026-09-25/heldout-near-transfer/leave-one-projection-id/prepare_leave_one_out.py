#!/usr/bin/env python3
"""Create three isolated 36-row leave-one-projection-ID datasets and manifests."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in HERE.parents if (p / "benchmarks").is_dir())
PARENT = HERE.parent
TEACHER = ROOT / "docs/research/qwen35-external-teacher-2026-09-24/train.json"
PARENT_HASHES = PARENT / "hashes.json"
TARGET_JOBS = PARENT / "target_eval_jobs.json"
RETENTION_JOBS = PARENT / "retention_control_jobs.json"
ANSWER_KEY = PARENT / "answer_key.json"
REPEAT_JOBS = PARENT / "eval_jobs_repeat1.json"
MAIN_SPLIT = PARENT / "split_manifest.json"

LOO_IDS = ["H03", "H04", "H14"]
RETENTION_IDS = ["H01", "H02", "H07", "H13"]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(name: str, value):
    path = HERE / name
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    return digest(path)


def main():
    teachers = json.loads(TEACHER.read_text())
    assert len(teachers) == 37
    source_ids = [row["source"] for row in teachers]
    assert len(set(source_ids)) == 37
    assert {"H03", "H04", "H14", *RETENTION_IDS}.issubset(source_ids)

    targets = json.loads(TARGET_JOBS.read_text())
    retention = json.loads(RETENTION_JOBS.read_text())
    target_job_by_id = {job["source_id"]: job for job in targets}
    retention_job_by_id = {job["source_id"]: job for job in retention}
    assert set(target_job_by_id) == {"H03", "H04", "H08", "H14", "H15"}
    assert set(retention_job_by_id) == set(RETENTION_IDS)

    arms = {}
    output_hashes = {}
    for omitted in LOO_IDS:
        rows = [row for row in teachers if row["source"] != omitted]
        included = {row["source"] for row in rows}
        assert len(rows) == 36 and len(included) == 36
        assert omitted not in included
        assert included == set(source_ids) - {omitted}
        # The two other projection IDs remain trained in this arm; they must not
        # be used as its heldout evaluation tasks.
        other_projection_ids = set(LOO_IDS) - {omitted}
        other_heldout_ids = set(target_job_by_id) - {omitted}
        assert other_projection_ids.issubset(included)
        assert other_heldout_ids.issubset(included)

        name = f"train-minus-{omitted}.json"
        output_hashes[name] = save_json(name, rows)
        retention_ids = [retention_job_by_id[cid]["id"] for cid in RETENTION_IDS]
        arms[f"minus-{omitted}"] = {
            "training_file": name,
            "training_sha256": output_hashes[name],
            "n_rows": len(rows),
            "excluded_configuration_id": omitted,
            "excluded_id_absent": True,
            "included_configuration_ids": sorted(included),
            "other_projection_ids_in_training": sorted(other_projection_ids),
            "other_heldout_target_ids_in_training": sorted(other_heldout_ids),
            "heldout_target_job_id": target_job_by_id[omitted]["id"],
            "heldout_target_source_id": omitted,
            "retention_control_job_ids": retention_ids,
            "evaluation_job_ids": [target_job_by_id[omitted]["id"], *retention_ids],
            "forbidden_target_job_ids": [target_job_by_id[cid]["id"] for cid in sorted(other_heldout_ids)],
        }

    frozen_refs = json.loads(PARENT_HASHES.read_text())["created_files"]
    arm_manifest = {
        "status": "frozen_exploratory_leave_one_id_lower_bound",
        "source_teacher_file": str(TEACHER.relative_to(ROOT)),
        "source_teacher_sha256": digest(TEACHER),
        "main_split_manifest_sha256": digest(MAIN_SPLIT),
        "evaluation_source_hashes": {
            "target_eval_jobs.json": frozen_refs["target_eval_jobs.json"],
            "retention_control_jobs.json": frozen_refs["retention_control_jobs.json"],
            "eval_jobs_repeat1.json": frozen_refs["eval_jobs_repeat1.json"],
            "answer_key.json": frozen_refs["answer_key.json"],
        },
        "shared_retention_control_source_ids": RETENTION_IDS,
        "arms": arms,
        "base_evaluation_union_job_ids": [
            target_job_by_id[cid]["id"] for cid in LOO_IDS
        ] + [retention_job_by_id[cid]["id"] for cid in RETENTION_IDS],
        "integrity_checks": {
            "source_rows": 37,
            "each_arm_rows": 36,
            "each_arm_excludes_only_its_named_id": True,
            "other_projection_ids_are_in_training_and_not_evaluated": True,
            "same_four_retention_jobs_for_all_arms": True,
            "existing_target_and_retention_jobs_copied_or_modified": False,
        },
    }
    output_hashes["arm_manifest.json"] = save_json("arm_manifest.json", arm_manifest)

    hash_record = {
        "inputs": {
            str(path.relative_to(ROOT)): digest(path)
            for path in [TEACHER, PARENT_HASHES, TARGET_JOBS, RETENTION_JOBS,
                         ANSWER_KEY, REPEAT_JOBS, MAIN_SPLIT]
        },
        "outputs": dict(output_hashes),
    }
    protocol = HERE / "PROTOCOL.md"
    if protocol.exists():
        output_hashes["PROTOCOL.md"] = digest(protocol)
        hash_record["outputs"]["PROTOCOL.md"] = output_hashes["PROTOCOL.md"]
    save_json("hashes.json", hash_record)
    print(json.dumps({"arms": {k: v["training_sha256"] for k, v in arms.items()},
                      "n_rows_each": 36, "target_job_count_per_arm": 5,
                      "retention_controls_each": 4}, indent=2))


if __name__ == "__main__":
    main()
