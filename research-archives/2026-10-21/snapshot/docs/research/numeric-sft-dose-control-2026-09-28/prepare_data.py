"""Prepare the correct-vs-within-source-shuffled numeric dose-control data.

CPU/data-only. The source train and provenance files are read-only. Re-running
this script with the frozen inputs yields byte-identical output files.
"""

from __future__ import annotations

import collections
import copy
import hashlib
import json
import math
import random
import shutil
from pathlib import Path


DOC = Path(__file__).resolve().parent
ROOT = DOC.parents[2]
OLD = ROOT / "qwen/.runtime/related_numeric_sft_20260928"
OUT = ROOT / "qwen/.runtime/numeric_sft_dose_control_20260928"
OLD_AUDIT = ROOT / "docs/research/related-numeric-sft-2026-09-28/b-final-data-audit.json"

DERANGEMENT_SEED = 2026092817
FIT_SEED_START = 2026092811
TRAIN_PREFIX = (
    "Solve the following numerical geometry problem. Give only the requested "
    "numerical value, with at least 10 significant digits when appropriate. "
    "Do not give a proof or explanation.\n\n"
)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def variant(record: dict) -> int:
    number = int(record["id"].rsplit("-variant-", 1)[1])
    if "variant_index" in record:
        assert record["variant_index"] == number
    return number


def ordered_sources(records: list[dict]) -> list[str]:
    return list(dict.fromkeys(record["source_id"] for record in records))


def check_source_data(train: list[dict], provenance: list[dict], old_audit: dict) -> dict:
    assert len(train) == 80 and len(provenance) == 120
    assert old_audit["status"] == "pass"
    assert old_audit["provenance_count"] == 120
    assert old_audit["training_count"] == 80
    assert sha(OLD / "train.json") == old_audit["frozen_file_sha256"]["train.json"]
    assert sha(OLD / "data-provenance.json") == old_audit["frozen_file_sha256"]["data-provenance.json"]

    by_id = {record["id"]: record for record in provenance}
    assert len(by_id) == 120
    sources = ordered_sources(train)
    assert len(sources) == 10
    assert set(sources) == {record["source_id"] for record in provenance}
    assert len({record["id"] for record in train}) == 80
    shape_minima = {}
    max_audit_residual = 0.0
    per_pack = collections.Counter()

    for record in provenance:
        per_pack[record["pack_id"]] += 1
        number = variant(record)
        expected_split = "train" if number <= 8 else "heldout" if number <= 10 else "reserve"
        assert record["split"] == expected_split
        assert math.isfinite(float(record["target"]))
        assert record["target"] == format(float(record["target"]), ".17g")
        assert record["problem_en"] and record["query"]
        for point in record["points"].values():
            assert len(point) == 2 and all(math.isfinite(float(x)) for x in point)
        assert all(math.isfinite(float(x)) for x in record["givens"].values())
        assert all(math.isfinite(float(x)) for x in record["shape_signature"])
        checks = record.get("audit_checks", record.get("audit"))
        assert isinstance(checks, dict) and checks
        for residual in checks.values():
            assert math.isfinite(float(residual))
            max_audit_residual = max(max_audit_residual, abs(float(residual)))

    assert dict(per_pack) == old_audit["per_pack"]
    assert math.isclose(
        max_audit_residual,
        old_audit["max_recorded_audit_residual"],
        rel_tol=0,
        abs_tol=1e-15,
    )

    for source in sources:
        rows = [record for record in provenance if record["source_id"] == source]
        assert len(rows) == 12
        assert [variant(record) for record in rows] == list(range(1, 13))
        signatures = [tuple(float(x) for x in row["shape_signature"]) for row in rows]
        assert len({tuple(round(x, 8) for x in sig) for sig in signatures}) == 12
        distances = [
            math.dist(first, second)
            for i, first in enumerate(signatures)
            for second in signatures[i + 1 :]
        ]
        all_min = min(distances)
        ninth_min = min(math.dist(signatures[8], sig) for sig in signatures[:8])
        assert all_min > 0
        reference = old_audit["shape_distances"][source]
        assert math.isclose(all_min, reference["all_twelve_min"], rel_tol=0, abs_tol=1e-12)
        assert math.isclose(ninth_min, reference["ninth_to_train_min"], rel_tol=0, abs_tol=1e-12)
        shape_minima[source] = {
            "all_twelve_min": all_min,
            "ninth_to_train_min": ninth_min,
        }

    for row in train:
        source = by_id[row["id"]]
        assert row["source_id"] == source["source_id"]
        assert source["split"] == "train"
        assert row["kind"] == "numeric" and row["target"] == source["target"]
        assert row["messages"] == [{"role": "user", "content": TRAIN_PREFIX + source["problem_en"]}]

    return {
        "sources": sources,
        "per_pack": dict(per_pack),
        "shape_distances": shape_minima,
        "max_recorded_audit_residual": max_audit_residual,
        "old_120_point_audit_status": old_audit["status"],
    }


def audit_old_jobs(reserved: list[dict]) -> list[dict]:
    files = sorted(OLD.rglob("*jobs.json"))
    assert files
    summary = []
    for path in files:
        jobs = load(path)
        assert isinstance(jobs, list)
        matched_problems = []
        matched_ids = []
        for job in jobs:
            assert isinstance(job, dict)
            prompts = [m.get("content", "") for m in job.get("messages", []) if isinstance(m, dict)]
            for record in reserved:
                if any(record["problem_en"] in prompt for prompt in prompts):
                    matched_problems.append(record["id"])
                if record["id"] in str(job.get("id", "")) or job.get("provenance_id") == record["id"]:
                    matched_ids.append(record["id"])
        assert not matched_problems and not matched_ids, path
        summary.append({
            "file": str(path.relative_to(OLD)),
            "sha256": sha(path),
            "jobs": len(jobs),
            "reserved_prompt_matches": 0,
            "reserved_id_matches": 0,
        })
    return summary


def main() -> None:
    DOC.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    source_train = OLD / "train.json"
    source_provenance = OLD / "data-provenance.json"
    original_bytes = source_train.read_bytes()
    train = load(source_train)
    provenance = load(source_provenance)
    old_audit = load(OLD_AUDIT)
    source_audit = check_source_data(train, provenance, old_audit)
    sources = source_audit["sources"]
    provenance_by_id = {record["id"]: record for record in provenance}

    correct_path = OUT / "train-correct.json"
    shutil.copyfile(source_train, correct_path)
    assert correct_path.read_bytes() == original_bytes

    rng = random.Random(DERANGEMENT_SEED)
    shuffled = copy.deepcopy(train)
    mapping = {}
    for source in sources:
        positions = [i for i, row in enumerate(train) if row["source_id"] == source]
        assert len(positions) == 8
        original_targets = [train[i]["target"] for i in positions]
        assert len(set(original_targets)) == 8
        attempts = 0
        while True:
            permutation = rng.sample(range(8), 8)
            attempts += 1
            if all(permutation[i] != i for i in range(8)):
                break
        recipients_to_donors = {}
        for recipient, donor in enumerate(permutation):
            recipient_pos, donor_pos = positions[recipient], positions[donor]
            shuffled[recipient_pos]["target"] = train[donor_pos]["target"]
            recipients_to_donors[train[recipient_pos]["id"]] = train[donor_pos]["id"]
        assert sorted(shuffled[i]["target"] for i in positions) == sorted(original_targets)
        assert all(shuffled[i]["target"] != train[i]["target"] for i in positions)
        mapping[source] = {
            "recipient_ids_in_order": [train[i]["id"] for i in positions],
            "donor_index_zero_based": permutation,
            "recipient_to_donor": recipients_to_donors,
            "rejection_attempts": attempts,
        }
    assert len(shuffled) == len(train)
    for original, control in zip(train, shuffled, strict=True):
        assert {k: v for k, v in original.items() if k != "target"} == {
            k: v for k, v in control.items() if k != "target"
        }
    shuffled_path = OUT / "train-shuffled.json"
    write(shuffled_path, shuffled)
    mapping_path = OUT / "shuffle-map.json"
    write(mapping_path, {"seed": DERANGEMENT_SEED, "method": "source-ordered RNG sample with fixed-point rejection", "sources": mapping})

    reserved = [record for record in provenance if variant(record) in (10, 11, 12)]
    assert len(reserved) == 30
    assert collections.Counter(record["source_id"] for record in reserved) == {source: 3 for source in sources}
    assert {record["id"] for record in reserved}.isdisjoint({row["id"] for row in train})
    old_jobs = audit_old_jobs(reserved)

    jobs = []
    answer_key = {}
    for index, record in enumerate([provenance_by_id[row["id"]] for row in train] + reserved):
        split = "trained_all" if index < 80 else "reserved_shape"
        job_id = "fit-" + record["id"]
        messages = copy.deepcopy(train[index]["messages"]) if index < 80 else [
            {"role": "user", "content": TRAIN_PREFIX + record["problem_en"]}
        ]
        assert messages == [{"role": "user", "content": TRAIN_PREFIX + record["problem_en"]}]
        job = {
            "id": job_id,
            "source_id": record["source_id"],
            "pack_id": record["pack_id"],
            "provenance_id": record["id"],
            "seed": FIT_SEED_START + index,
            "split": split,
            "messages": messages,
        }
        assert "target" not in job and "answer_exact" not in job
        jobs.append(job)
        answer_key[job_id] = {
            "id": job_id,
            "source_id": record["source_id"],
            "provenance_id": record["id"],
            "split": split,
            "answer_exact": record["target"],
        }
    assert len(jobs) == 110 and len(answer_key) == 110
    assert len({job["id"] for job in jobs}) == 110
    assert [job["seed"] for job in jobs] == list(range(FIT_SEED_START, FIT_SEED_START + 110))
    assert collections.Counter(job["split"] for job in jobs) == {"trained_all": 80, "reserved_shape": 30}
    jobs_path = OUT / "fit-jobs.json"
    key_path = OUT / "fit-answer-key.json"
    write(jobs_path, jobs)
    write(key_path, answer_key)

    output_paths = [correct_path, shuffled_path, mapping_path, jobs_path, key_path]
    audit = {
        "status": "pass",
        "scope": "CPU-only dataset preparation; no training or model evaluation",
        "source_sha256": {
            "train.json": sha(source_train),
            "data-provenance.json": sha(source_provenance),
            "b-final-data-audit.json": sha(OLD_AUDIT),
        },
        "source_audit": source_audit,
        "counts": {
            "provenance": len(provenance),
            "sources": len(sources),
            "correct_train": len(train),
            "shuffled_train": len(shuffled),
            "deranged_targets": sum(a["target"] != b["target"] for a, b in zip(train, shuffled, strict=True)),
            "fit_jobs": len(jobs),
            "trained_all": 80,
            "reserved_shape": 30,
            "old_job_files_checked": len(old_jobs),
        },
        "prefix": TRAIN_PREFIX,
        "seeds": {"derangement": DERANGEMENT_SEED, "fit_first": FIT_SEED_START, "fit_last": FIT_SEED_START + 109},
        "byte_identical_correct_copy": correct_path.read_bytes() == original_bytes,
        "same_train_id_order_messages_other_fields": True,
        "per_source_target_multiset_preserved": True,
        "zero_fixed_points": True,
        "derangement_mapping": mapping,
        "reserved_provenance_ids": [record["id"] for record in reserved],
        "old_evaluation_job_audit": old_jobs,
        "old_evaluation_scope_note": "No variant-10/11/12 prompt or ID occurred in these old model-evaluation job manifests. This does not claim the researcher had never inspected the constructed provenance records.",
        "output_sha256": {path.name: sha(path) for path in output_paths},
        "script_sha256": sha(Path(__file__)),
    }
    write(DOC / "data-audit.json", audit)
    print(json.dumps({"counts": audit["counts"], "output_sha256": audit["output_sha256"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
