"""Build the final dose/control results only after all scores and reviews exist.

No model is invoked. This script counts only naturally stopped correct answers,
reports unfinished answers separately, and counts only new guard-wrapped GPU time.
"""
from __future__ import annotations

import collections
import hashlib
import json
import math
import statistics
from pathlib import Path

import prepare_transfer_review as review_io
import run_study as study

P, O, SH = study.P, study.O, study.SH
ARMS = study.ARMS
CAPS = (32768, 81920, 131072)


def read(path: Path):
    return json.loads(path.read_text())


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def complete(path: Path, expected: str = "complete") -> dict:
    record = read(path)
    require(record.get("status") == expected, f"Incomplete {path}: {record.get('status')}")
    return record


def natural_correct(row: dict) -> bool:
    return row.get("finish_reason") == "stop" and row.get("numeric_correct") is True


def numeric_summary(rows: list[dict]) -> dict:
    positive = [r for r in rows if isinstance(r.get("value"), (int, float)) and r["value"] > 0]
    return {
        "n": len(rows),
        "natural_stop": sum(r.get("finish_reason") == "stop" for r in rows),
        "natural_stop_correct": sum(natural_correct(r) for r in rows),
        "unparsed": sum(r.get("value") is None for r in rows),
        "length": sum(r.get("finish_reason") == "length" for r in rows),
        "nonpositive": sum(r.get("value") is not None and r["value"] <= 0 for r in rows),
        "other_finish": sum(r.get("finish_reason") not in {"stop", "length"} for r in rows),
        "mean_relative_error_if_all_positive": (
            statistics.mean(relative_error(r) for r in rows)
            if rows and len(positive) == len(rows) and all(relative_error(r) is not None for r in rows)
            else None),
        "mean_absolute_log_ratio_if_all_positive": (
            statistics.mean(abs(math.log(r["value"] / r["target"])) for r in rows)
            if rows and len(positive) == len(rows) else None),
    }


def relative_error(row: dict) -> float | None:
    value, target = row.get("value"), row.get("target")
    if value is None or target is None or target == 0:
        return None
    return abs(value - target) / abs(target)


def numeric_direction(base: dict, other: dict) -> dict:
    baseline, candidate = natural_correct(base), natural_correct(other)
    correctness = "improved" if candidate and not baseline else "worsened" if baseline and not candidate else "unchanged"
    b_err, c_err = relative_error(base), relative_error(other)
    if b_err is None or c_err is None:
        error_direction = None
        delta = None
    else:
        delta = c_err - b_err
        error_direction = "improved" if delta < 0 else "worsened" if delta > 0 else "unchanged"
    return {"base_natural_correct": baseline, "arm_natural_correct": candidate,
            "correctness_direction": correctness, "base_relative_error": b_err,
            "arm_relative_error": c_err, "relative_error_delta_arm_minus_base": delta,
            "relative_error_direction": error_direction}


def paired_numeric(rows: list[dict]) -> dict:
    indexed = {(r["job_id"], r["arm"]): r for r in rows}
    jobs = sorted({r["job_id"] for r in rows})
    by_job = []
    for job_id in jobs:
        base = indexed[(job_id, "base")]
        arms = {}
        for arm in ARMS[1:]:
            other = indexed[(job_id, arm)]
            require(other["source_id"] == base["source_id"] and other["split"] == base["split"]
                    and other["target"] == base["target"],
                    f"Mispaired numeric job {job_id}/{arm}")
            arms[arm] = numeric_direction(base, other)
        by_job.append({"job_id": job_id, "source_id": base["source_id"],
                       "split": base["split"], "arms": arms})
    def summarize_comparisons(subset: list[dict], arm: str) -> dict:
        directions = [x["arms"][arm] for x in subset]
        deltas = [x["relative_error_delta_arm_minus_base"] for x in directions
                  if x["relative_error_delta_arm_minus_base"] is not None]
        return {
            "jobs": len(subset),
            "natural_correct_improved": sum(x["correctness_direction"] == "improved" for x in directions),
            "natural_correct_worsened": sum(x["correctness_direction"] == "worsened" for x in directions),
            "natural_correct_unchanged": sum(x["correctness_direction"] == "unchanged" for x in directions),
            "relative_error_improved": sum(x["relative_error_direction"] == "improved" for x in directions),
            "relative_error_worsened": sum(x["relative_error_direction"] == "worsened" for x in directions),
            "mean_relative_error_delta_arm_minus_base": statistics.mean(deltas) if deltas else None,
        }

    by_source = {}
    by_source_split = {}
    for source in sorted({x["source_id"] for x in by_job}):
        by_source[source] = {}
        by_source_split[source] = {}
        subset = [x for x in by_job if x["source_id"] == source]
        for arm in ARMS[1:]:
            by_source[source][arm] = summarize_comparisons(subset, arm)
        for split in sorted({x["split"] for x in subset}):
            group = [x for x in subset if x["split"] == split]
            by_source_split[source][split] = {arm: summarize_comparisons(group, arm) for arm in ARMS[1:]}
    return {"by_job": by_job, "by_source": by_source, "by_source_and_split": by_source_split}


def paired_correct512_shuffled512_unknown(rows: list[dict]) -> dict:
    selected = [r for r in rows if r["split"] == "untrained_configuration"
                and r["arm"] in {"correct512", "shuffled512"}]
    indexed = {(r["job_id"], r["arm"]): r for r in selected}
    jobs = sorted({r["job_id"] for r in selected})
    require(len(jobs) == 16 and len(indexed) == 2 * len(jobs),
            "Wrong correct512/shuffled512 unknown pairing")
    categories = ("correct512_only", "shuffled512_only", "both_success", "both_fail")
    by_category = {category: [] for category in categories}
    by_source = {}
    for job_id in jobs:
        correct = indexed[(job_id, "correct512")]
        shuffled = indexed[(job_id, "shuffled512")]
        require(correct["source_id"] == shuffled["source_id"]
                and correct["target"] == shuffled["target"],
                f"Mispaired correct512/shuffled512 unknown job {job_id}")
        c, s = natural_correct(correct), natural_correct(shuffled)
        category = ("both_success" if c and s else "correct512_only" if c else
                    "shuffled512_only" if s else "both_fail")
        item = {"job_id": job_id, "source_id": correct["source_id"]}
        by_category[category].append(item)
        source_categories = by_source.setdefault(correct["source_id"],
                                                 {name: [] for name in categories})
        source_categories[category].append(job_id)
    return {
        "jobs": len(jobs),
        "counts": {name: len(by_category[name]) for name in categories},
        "job_lists": by_category,
        "by_source": {source: {"jobs": sum(len(ids) for ids in groups.values()),
                               "counts": {name: len(groups[name]) for name in categories},
                               "job_lists": groups}
                      for source, groups in sorted(by_source.items())},
    }


def permissive_sensitivity_valid(row: dict, reviews: dict) -> bool:
    """Use the explicit DB08 boundary grade only; retain primary grades elsewhere."""
    grade = reviews[(row["arm"], row["job_id"])]["review"]["grade"]
    status = (grade.get("permissive_status", grade["derivation_status"])
              if row["source_id"] == "DB08" else grade["derivation_status"])
    require(status in {"valid", "invalid", "unclear", "no_derivation"},
            f"Invalid permissive grade: {row['arm']}/{row['job_id']}")
    return status == "valid"


def score_rows(scores: dict, key: str, expected_per_arm: int) -> list[dict]:
    rows = scores[key]
    require(len(rows) == len(ARMS) * expected_per_arm, f"Wrong {key} count")
    for arm in ARMS:
        arm_rows = [r for r in rows if r["arm"] == arm]
        require(len(arm_rows) == expected_per_arm and len({r["job_id"] for r in arm_rows}) == expected_per_arm,
                f"Wrong {key} coverage for {arm}")
    for row in rows:
        require(digest(Path(row["file"])) == row["file_sha256"],
                f"Scored response file changed: {row['file']}")
    return rows


def check_caps(rows: list[dict], mapping: dict, jobs: list[dict], name: str) -> list[dict]:
    valid_jobs = {j["id"]: j for j in jobs}
    require(set(mapping) <= set(valid_jobs), f"Unknown {name} cap-map job")
    require(set(mapping.values()) <= set(CAPS[1:]), f"Invalid {name} extension cap")
    output = []
    for job_id, job in valid_jobs.items():
        cap = mapping.get(job_id, CAPS[0])
        matches = [r for r in rows if r["job_id"] == job_id]
        require(len(matches) == len(ARMS) and {r["arm"] for r in matches} == set(ARMS),
                f"Missing {name} arm for {job_id}")
        require(all(r["cap"] == cap for r in matches), f"Inconsistent {name} cap for {job_id}")
        output.append({"job_id": job_id, "source_id": job["source_id"],
                       "split": job["split"], "final_cap": cap})
    return output


def stage_caps(mapping: dict) -> list[int]:
    highest = max(mapping.values(), default=32768)
    return [32768] + ([81920] if highest >= 81920 else []) + ([131072] if highest >= 131072 else [])


def guard_time(label: str, group: str, receipts: list[dict], seen: set[str]) -> None:
    require(label not in seen, f"Duplicate GPU stage: {label}")
    seen.add(label)
    path = SH / f"dose-control-{label}-20260928" / "receipt.json"
    record = complete(path)
    require(record.get("returncode") == 0, f"Failed guard process: {label}")
    seconds = record.get("elapsed_seconds")
    require(isinstance(seconds, (int, float)) and math.isfinite(seconds) and seconds >= 0,
            f"Invalid guard elapsed_seconds: {label}")
    receipts.append({"stage": label, "group": group, "seconds": seconds,
                     "guard_receipt": str(path), "guard_receipt_sha256": digest(path)})


def generation_receipts(fit_caps: dict, transfer_caps: dict) -> dict:
    gpu, seen = [], set()
    for label in ("correct-train512", "shuffled-train32", "shuffled-train128", "shuffled-train512"):
        complete(O / label / "receipt.json")
        guard_time(label, "training", gpu, seen)
    fit_jobs = read(O / "fit-jobs.json")
    for cap in stage_caps(fit_caps):
        path = O / ("fit-jobs.json" if cap == 32768 else f"fit-extension-{cap}-jobs.json")
        jobs = fit_jobs if cap == 32768 else read(path)
        require(len(jobs) > 0, f"Empty fit cap stage {cap}")
        for arm in ARMS:
            label = f"{arm}-fit" + ("" if cap == 32768 else f"-{cap}")
            receipt = complete(O / label / "receipt.json")
            require(receipt["jobs_sha256"] == digest(path) and receipt["completed_jobs"] == len(jobs)
                    and receipt["cap"] == cap, f"Wrong fit receipt: {label}")
            guard_time(label, "fit_generation", gpu, seen)

    transfer_jobs = read(O / "transfer-jobs.json")
    reused = []
    for cap in stage_caps(transfer_caps):
        path = O / ("transfer-jobs.json" if cap == 32768 else f"transfer-extension-{cap}-jobs.json")
        jobs = transfer_jobs if cap == 32768 else read(path)
        require(len(jobs) > 0, f"Empty transfer cap stage {cap}")
        for arm in ARMS:
            ref_path = O / f"transfer-reference-{arm}-{cap}.json"
            ref = read(ref_path)
            directory = Path(ref["directory"])
            receipt_path = directory / "receipt.json"
            receipt = complete(receipt_path)
            require(ref["arm"] == arm and ref["cap"] == cap and ref["jobs_sha256"] == digest(path)
                    and ref["receipt_sha256"] == digest(receipt_path), f"Wrong transfer reference: {ref_path}")
            require(receipt["jobs_sha256"] == digest(path) and receipt["completed_jobs"] == len(jobs)
                    and receipt["cap"] == cap, f"Wrong transfer receipt: {ref_path}")
            require(set(ref["response_sha256"]) == {j["id"] for j in jobs},
                    f"Wrong response set: {ref_path}")
            for job in jobs:
                answer_path = directory / (job["id"] + "-0.json")
                require(digest(answer_path) == ref["response_sha256"][job["id"]],
                        f"Response hash mismatch: {answer_path}")
            label = f"{arm}-transfer" + ("" if cap == 32768 else f"-{cap}")
            if ref["origin"] == "generated in this study":
                guard_time(label, "transfer_generation", gpu, seen)
            elif ref["origin"] == "reused prior exact-identity run":
                reused.append({"stage": label, "reference": str(ref_path),
                               "prior_receipt": str(receipt_path), "new_gpu_seconds": 0})
            else:
                raise ValueError(f"Unknown transfer origin: {ref_path}")

    groups = {name: sum(x["seconds"] for x in gpu if x["group"] == name)
              for name in ("training", "fit_generation", "transfer_generation")}
    return {"new_guard_gpu_seconds_by_group": groups,
            "new_guard_gpu_seconds_total": sum(groups.values()),
            "new_guard_gpu_hours_total": sum(groups.values()) / 3600,
            "new_guard_receipts": gpu, "reused_prior_transfer_stages": reused}


def review_lookup(review: dict, numeric: list[dict], proof: list[dict]) -> dict:
    require(review.get("status") == "complete" and not review.get("missing"),
            "Transfer review is incomplete")
    require(review.get("inputs_sha256"), "Transfer review has no input hashes")
    for path, expected in review["inputs_sha256"].items():
        require(digest(Path(path)) == expected, f"Review input changed: {path}")
    needed = {(r["arm"], r["job_id"]) for r in proof}
    needed.update((r["arm"], r["job_id"]) for r in numeric
                  if r["split"] == "untrained_configuration"
                  and (r["numeric_correct"] is True or r["numeric_correct"] is None))
    rows = review["rows"]
    require(review.get("required") == len(rows) and review.get("reviewed") == len(rows),
            "Transfer review count metadata is inconsistent")
    indexed = {(r["arm"], r["job_id"]): r for r in rows}
    require(len(indexed) == len(rows) and set(indexed) == needed,
            "Transfer review coverage differs from required proof/numeric answers")
    scores = {(r["arm"], r["job_id"]): r for r in proof + numeric}
    for identity, item in indexed.items():
        source = scores[identity]
        require(item["file"] == source["file"] and item["file_sha256"] == source["file_sha256"]
                and digest(Path(item["file"])) == item["file_sha256"],
                f"Review does not match final response: {identity}")
        require(review_io.content_hash(read(Path(item["file"]))) == item["content_sha256"],
                f"Review content hash changed: {identity}")
        entry = item.get("review")
        require(entry is not None and isinstance(entry.get("grade"), dict),
                f"Missing mathematical review: {identity}")
        grade_file = Path(entry["grade_file"])
        require(digest(grade_file) == entry["grade_file_sha256"],
                f"Review grade file changed: {identity}")
        grade = entry["grade"]
        if item["kind"] == "proof":
            require(type(grade.get("score")) is int and 0 <= grade["score"] <= 4
                    and type(grade.get("complete_proof")) is bool
                    and grade["complete_proof"] == (grade["score"] == 4),
                    f"Invalid proof grade: {identity}")
        else:
            require(grade.get("derivation_status") in {"valid", "invalid", "unclear", "no_derivation"},
                    f"Invalid numeric grade: {identity}")
        require(item["kind"] == ("proof" if source["split"] == "proof" else "numeric"),
                f"Review kind mismatch: {identity}")
    return indexed


def proof_comparisons(rows: list[dict], reviews: dict) -> dict:
    indexed = {(r["job_id"], r["arm"]): r for r in rows}
    output = []
    for job_id in sorted({r["job_id"] for r in rows}):
        base = indexed[(job_id, "base")]
        bg = reviews[("base", job_id)]["review"]["grade"]
        baseline = bg["complete_proof"] and base["finish_reason"] == "stop"
        comparisons = {}
        for arm in ARMS[1:]:
            other = indexed[(job_id, arm)]
            grade = reviews[(arm, job_id)]["review"]["grade"]
            candidate = grade["complete_proof"] and other["finish_reason"] == "stop"
            comparisons[arm] = {"base_complete_natural": baseline,
                                "arm_complete_natural": candidate,
                                "direction": "improved" if candidate and not baseline else
                                             "worsened" if baseline and not candidate else "unchanged",
                                "score_delta_arm_minus_base": grade["score"] - bg["score"]}
        output.append({"job_id": job_id, "source_id": base["source_id"], "arms": comparisons})
    by_source = {}
    for source in sorted({x["source_id"] for x in output}):
        subset = [x for x in output if x["source_id"] == source]
        by_source[source] = {}
        for arm in ARMS[1:]:
            directions = [x["arms"][arm] for x in subset]
            by_source[source][arm] = {
                "jobs": len(subset),
                "complete_natural_improved": sum(x["direction"] == "improved" for x in directions),
                "complete_natural_worsened": sum(x["direction"] == "worsened" for x in directions),
                "mean_score_delta_arm_minus_base": statistics.mean(x["score_delta_arm_minus_base"]
                                                                    for x in directions),
            }
    return {"by_job": output, "by_source": by_source}


def main() -> None:
    fit_path, transfer_path = O / "fit-scores.json", O / "transfer-scores.json"
    review_path = O / "transfer-review-results-final.json"
    fit, transfer, review = complete(fit_path), complete(transfer_path), complete(review_path)
    fit_generation = complete(O / "fit-generation-complete.json")
    transfer_generation = complete(O / "transfer-generation-complete.json")
    freeze = complete(O / "freeze.json", "frozen")
    transfer_freeze = read(O / "transfer-freeze.json")
    audit = complete(P / "data-audit.json", "pass")
    require(set(freeze["arms"]) == set(ARMS) and audit["counts"]["fit_jobs"] == 110,
            "Freeze or data audit mismatch")
    require("sha256" in transfer_freeze and transfer_freeze["sha256"],
            "Transfer freeze is missing")
    for registry in (freeze, transfer_freeze):
        for path, expected in registry["sha256"].items():
            require(digest(Path(path)) == expected, f"Frozen input changed: {path}")
    require(fit_generation["jobs_per_arm"] == 110 and transfer_generation["jobs_per_arm"] == 24,
            "Generation completion counts differ from protocol")

    fit_rows = score_rows(fit, "rows", 110)
    numeric = score_rows(transfer, "numeric", 20)
    proof = score_rows(transfer, "proof", 4)
    require(all(r["split"] in {"trained_all", "reserved_shape"} for r in fit_rows),
            "Unexpected fit split")
    require(all(r["split"] in {"untrained_configuration", "retention"} for r in numeric)
            and all(r["split"] == "proof" for r in proof), "Unexpected transfer split")
    for arm in ARMS:
        require(sum(r["arm"] == arm and r["split"] == "trained_all" for r in fit_rows) == 80
                and sum(r["arm"] == arm and r["split"] == "reserved_shape" for r in fit_rows) == 30,
                f"Wrong fit split counts for {arm}")
        require(sum(r["arm"] == arm and r["split"] == "untrained_configuration" for r in numeric) == 16
                and sum(r["arm"] == arm and r["split"] == "retention" for r in numeric) == 4,
                f"Wrong transfer split counts for {arm}")
    fit_caps = read(O / "final-cap-by-job.json")
    transfer_caps = read(O / "transfer-final-cap-by-job.json")
    require(fit_generation["chosen_caps"] == fit_caps
            and transfer_generation["chosen_caps"] == transfer_caps,
            "Generation cap maps changed after completion")
    cap_lists = {"fit": check_caps(fit_rows, fit_caps, read(O / "fit-jobs.json"), "fit"),
                 "transfer": check_caps(numeric + proof, transfer_caps,
                                        read(O / "transfer-jobs.json"), "transfer")}
    reviews = review_lookup(review, numeric, proof)
    gpu = generation_receipts(fit_caps, transfer_caps)

    fit_by_arm = {arm: {split: numeric_summary([r for r in fit_rows if r["arm"] == arm and r["split"] == split])
                        for split in ("trained_all", "reserved_shape")} for arm in ARMS}
    fit_by_source = {source: {arm: {split: numeric_summary([r for r in fit_rows
                                                               if r["source_id"] == source and r["arm"] == arm and r["split"] == split])
                                    for split in ("trained_all", "reserved_shape")} for arm in ARMS}
                     for source in sorted({r["source_id"] for r in fit_rows})}
    unknown_by_arm = {}
    retention_by_arm = {}
    proof_by_arm = {}
    for arm in ARMS:
        unknown = [r for r in numeric if r["arm"] == arm and r["split"] == "untrained_configuration"]
        retention = [r for r in numeric if r["arm"] == arm and r["split"] == "retention"]
        grade_counts = collections.Counter(reviews[(arm, r["job_id"])]["review"]["grade"]["derivation_status"]
                                            for r in unknown if (arm, r["job_id"]) in reviews)
        unknown_by_arm[arm] = dict(numeric_summary(unknown),
                                   correct_with_valid_derivation=sum(natural_correct(r) and
                                        reviews[(arm, r["job_id"])]["review"]["grade"]["derivation_status"] == "valid"
                                        for r in unknown if (arm, r["job_id"]) in reviews),
                                   db08_permissive_sensitivity_count=sum(
                                       natural_correct(r) and permissive_sensitivity_valid(r, reviews)
                                       for r in unknown if (arm, r["job_id"]) in reviews),
                                   derivation_status_counts=dict(grade_counts),
                                   answers=[{"job_id": r["job_id"], "source_id": r["source_id"],
                                             "finish_reason": r["finish_reason"], "cap": r["cap"],
                                             "numeric_correct": r["numeric_correct"],
                                             "natural_stop_correct": natural_correct(r),
                                             "derivation_status": reviews[(arm, r["job_id"])]["review"]["grade"]["derivation_status"]
                                             if (arm, r["job_id"]) in reviews else None}
                                            for r in unknown])
        retention_by_arm[arm] = dict(numeric_summary(retention),
                                     answers=[{"job_id": r["job_id"], "source_id": r["source_id"],
                                               "finish_reason": r["finish_reason"], "cap": r["cap"],
                                               "numeric_correct": r["numeric_correct"],
                                               "natural_stop_correct": natural_correct(r)}
                                              for r in retention])
        arm_proofs = [r for r in proof if r["arm"] == arm]
        graded = []
        for row in arm_proofs:
            grade = reviews[(arm, row["job_id"])]["review"]["grade"]
            graded.append({"job_id": row["job_id"], "source_id": row["source_id"],
                           "finish_reason": row["finish_reason"], "cap": row["cap"],
                           "score": grade["score"], "complete_proof": grade["complete_proof"],
                           "complete_and_natural_stop": grade["complete_proof"] and row["finish_reason"] == "stop"})
        proof_by_arm[arm] = {"n": 4, "natural_stop": sum(r["finish_reason"] == "stop" for r in arm_proofs),
                             "length": sum(r["finish_reason"] == "length" for r in arm_proofs),
                             "complete_and_natural_stop": sum(r["complete_and_natural_stop"] for r in graded),
                             "answers": graded}
    unknown_by_source = {}
    for source in sorted({r["source_id"] for r in numeric if r["split"] == "untrained_configuration"}):
        unknown_by_source[source] = {}
        for arm in ARMS:
            subset = [r for r in numeric if r["source_id"] == source and r["arm"] == arm
                      and r["split"] == "untrained_configuration"]
            unknown_by_source[source][arm] = dict(
                numeric_summary(subset),
                correct_with_valid_derivation=sum(natural_correct(r) and
                    reviews[(arm, r["job_id"])]["review"]["grade"]["derivation_status"] == "valid"
                    for r in subset if (arm, r["job_id"]) in reviews),
                db08_permissive_sensitivity_count=sum(
                    natural_correct(r) and permissive_sensitivity_valid(r, reviews)
                    for r in subset if (arm, r["job_id"]) in reviews))

    inputs = [fit_path, transfer_path, review_path, O / "fit-generation-complete.json",
              O / "transfer-generation-complete.json", O / "freeze.json",
              O / "transfer-freeze.json", P / "data-audit.json",
              O / "final-cap-by-job.json", O / "transfer-final-cap-by-job.json",
              O / "fit-jobs.json", O / "transfer-jobs.json"]
    scale_path = P / "scale-baseline.json"
    scale_baseline = None
    if scale_path.exists():
        scale_baseline = read(scale_path)
        require(isinstance(scale_baseline.get("evaluation"), dict)
                and isinstance(scale_baseline.get("inputs"), dict)
                and scale_baseline["inputs"], "Malformed posthoc scale baseline")
        for name, item in scale_baseline["inputs"].items():
            source = Path(item["path"])
            require(digest(source) == item["sha256"],
                    f"Posthoc scale baseline input changed: {name} ({source})")
        inputs.append(scale_path)
    output = {
        "status": "complete",
        "arms": ARMS,
        "fit": {"primary_summary": fit["summary"], "primary_by_source": fit["by_source"],
                "by_arm": fit_by_arm, "by_source": fit_by_source,
                "paired_base_comparisons": paired_numeric(fit_rows),
                "source_median_baseline": fit["summary"]["source_median"],
                "transfer_gate": fit["transfer_gate"]},
        "transfer": {"unknown_configuration_by_arm": unknown_by_arm,
                     "unknown_configuration_by_source": unknown_by_source,
                     "correct512_vs_shuffled512_unknown_natural_correct":
                         paired_correct512_shuffled512_unknown(numeric),
                     "retention_by_arm": retention_by_arm,
                     "proof_by_arm": proof_by_arm,
                     "numeric_paired_base_comparisons": paired_numeric(numeric),
                     "proof_paired_base_comparisons": proof_comparisons(proof, reviews)},
        "final_caps": cap_lists,
        "new_gpu_time": gpu,
        "posthoc_scale_baseline": scale_baseline,
        "review": {"required": review["required"], "reviewed": review["reviewed"],
                   "reused_prior": review["reused_prior"],
                   "reused_registered": review.get("reused_registered", 0),
                   "review_results_sha256": digest(review_path)},
        "inputs_sha256": {str(path): digest(path) for path in inputs},
    }
    destination = P / "results.json"
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    temporary.replace(destination)
    print(json.dumps({"output": str(destination), "status": "complete",
                      "new_gpu_hours": gpu["new_guard_gpu_hours_total"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
