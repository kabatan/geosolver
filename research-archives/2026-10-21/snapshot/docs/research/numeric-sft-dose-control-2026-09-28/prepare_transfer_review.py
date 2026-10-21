"""Prepare blind transfer-review packets; reuse only exact-content prior grades.

This reads the completed numerical transfer scores, but writes no correctness,
arm, source ID, or answer key into reviewer-visible packet files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path

import run_study as study

P, O, OLD = study.P, study.O, study.OLD
PRIOR_BANK = OLD / "review-bank.json"
REVIEW = P / "review"
MANIFEST = REVIEW / "transfer-review-manifest.json"
SEED = 2026092818


def read(path: Path):
    return json.loads(path.read_text())


def write(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def content_hash(response: dict) -> str:
    """Byte-for-byte compatible with the previous collect_reviews.py key."""
    content = {k: response[k] for k in ["messages", "raw_text", "finish_reason"]}
    return hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def validate_prior(prior: dict, digest: str, kind: str) -> None:
    """Check the old bank's source and grade receipts before reusing its verdict."""
    if prior["kind"] != kind or prior["content_sha256"] != digest:
        raise ValueError(f"Prior review identity mismatch: {digest}")
    source = prior["original_source"]
    source_path = Path(source["file"])
    if sha(source_path) != source["file_sha256"] or content_hash(read(source_path)) != digest:
        raise ValueError(f"Prior reviewed response changed: {source_path}")
    grade_path = Path(prior["grade_file"])
    if sha(grade_path) != prior["grade_file_sha256"]:
        raise ValueError(f"Prior grade file changed: {grade_path}")


def normalize_grade(kind: str, grade: dict) -> dict:
    result = dict(grade)
    if kind == "proof":
        score = result.get("score")
        complete = result.get("complete_proof")
        if type(score) is not int or not 0 <= score <= 4 or type(complete) is not bool:
            raise ValueError("proof grade requires integer score 0..4 and boolean complete_proof")
        if complete != (score == 4):
            raise ValueError("complete_proof must equal score == 4")
    else:
        if "calibrated_status" in result:
            result["derivation_status"] = result["calibrated_status"]
        if result.get("derivation_status") not in {"valid", "invalid", "unclear", "no_derivation"}:
            raise ValueError("numeric grade requires a recognized derivation_status")
    return result


def manifest_grades(manifest_path: Path | None = None) -> dict[str, dict]:
    """Load already registered new reviews, checking both blind packet and source."""
    manifest_path = manifest_path or MANIFEST
    manifest = read(manifest_path)
    if not isinstance(manifest, list):
        raise TypeError("review manifest must be a list")
    reviewed = {}
    for item in manifest:
        kind, label = item["kind"], item["label"]
        if kind not in {"proof", "numeric"}:
            raise ValueError(f"Unexpected review kind: {kind}")
        grade_path = (REVIEW / item["file"]).resolve()
        if not grade_path.is_relative_to(REVIEW.resolve()):
            raise ValueError(f"Grade path escapes review directory: {grade_path}")
        grades = read(grade_path)
        if isinstance(grades, dict):
            grades = grades["cases"]
        private = read(O / f"private-transfer-{label}.json")
        if not isinstance(grades, list):
            raise TypeError(f"Grade file must contain a case list: {grade_path}")
        for raw_grade in grades:
            case_id = raw_grade["case_id"]
            mapping = private[case_id]
            if mapping["kind"] != kind:
                raise ValueError(f"Kind mismatch for {label}/{case_id}")
            source = Path(mapping["file"])
            packet = Path(mapping["packet_file"])
            if sha(source) != mapping["file_sha256"] or sha(packet) != mapping["packet_sha256"]:
                raise ValueError(f"Response or blind packet changed: {label}/{case_id}")
            digest = content_hash(read(source))
            if digest != mapping["content_sha256"]:
                raise ValueError(f"Content hash mismatch: {label}/{case_id}")
            grade = normalize_grade(kind, raw_grade)
            entry = {"kind": kind, "grade": grade, "grade_file": str(grade_path),
                     "grade_file_sha256": sha(grade_path), "case_id": case_id,
                     "packet_sha256": mapping["packet_sha256"], "content_sha256": digest,
                     "supersedes_prior": item.get("supersedes_prior", False)}
            prior = reviewed.get(digest)
            if prior is not None and (prior["kind"] != kind or prior["grade"] != grade):
                raise ValueError(f"Conflicting grades for exact content {digest}")
            reviewed[digest] = entry
    return reviewed


def required_rows(scores: dict, arms: set[str], excluded: set[str], require_full: bool = True) -> list[tuple[str, dict]]:
    if require_full:
        assert scores["status"] == "complete", "transfer-scores.json must be complete"
        assert len(scores["proof"]) == 16 and len(scores["numeric"]) == 80
    selected = [("proof", row) for row in scores["proof"]]
    # Keep None (unparsed) distinct from False (parsed but numerically wrong).
    selected += [("numeric", row) for row in scores["numeric"]
                 if row["split"] == "untrained_configuration"
                 and (row["numeric_correct"] is True or row["numeric_correct"] is None)]
    return [(kind, row) for kind, row in selected
            if row["arm"] in arms and row["job_id"] not in excluded]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--label", required=True, help="Unique packet label, e.g. final")
    ap.add_argument("--arms", nargs="+", choices=study.ARMS, default=study.ARMS)
    ap.add_argument("--exclude-jobs", nargs="*", default=[])
    ap.add_argument("--scores-file", type=Path,
                    help="Same-schema partial score snapshot; skips final 16+80 count check")
    args = ap.parse_args()
    if not args.label or not all(c.isalnum() or c in "-_" for c in args.label):
        ap.error("--label must use only letters, digits, hyphens, or underscores")
    assert len(set(args.arms)) == len(args.arms)

    destination = O / f"review-transfer-{args.label}"
    private_path = O / f"private-transfer-{args.label}.json"
    plan_path = O / f"transfer-review-plan-{args.label}.json"
    for path in (destination, private_path, plan_path):
        if path.exists():
            raise FileExistsError(path)

    scores_path = args.scores_file or O / "transfer-scores.json"
    scores = read(scores_path)
    jobs = {job["id"]: job for job in read(O / "transfer-jobs.json")}
    bank = read(PRIOR_BANK)["bank"]
    registered = manifest_grades()
    selected = required_rows(scores, set(args.arms), set(args.exclude_jobs),
                             require_full=args.scores_file is None)
    assert selected and len({(row["arm"], row["job_id"]) for _, row in selected}) == len(selected)

    entries = []
    for kind, row in selected:
        job = jobs[row["job_id"]]
        assert job["split"] == row["split"]
        path = Path(row["file"])
        assert sha(path) == row["file_sha256"], path
        response = read(path)
        assert response["messages"] == job["messages"]
        assert response["seed"] == job["seed"]
        assert response["finish_reason"] == row["finish_reason"]
        key = content_hash(response)
        prior = bank.get(key)
        if prior is not None:
            validate_prior(prior, key, kind)
        current_review = registered.get(key)
        if prior is None or (current_review is not None and current_review["supersedes_prior"]):
            prior = current_review
        if prior is not None:
            assert prior["kind"] == kind
            normalize_grade(kind, prior["grade"])
        entries.append({"kind": kind, "row": row, "job": job, "path": path,
                        "response": response, "content_sha256": key, "prior": prior})

    new_by_content = {}
    for entry in entries:
        if entry["prior"] is None:
            prior_entry = new_by_content.setdefault(entry["content_sha256"], entry)
            assert prior_entry["kind"] == entry["kind"]
    new_entries = list(new_by_content.values())
    random.Random(SEED).shuffle(new_entries)
    destination.mkdir(exist_ok=False)
    index = []
    private = {}
    case_id_by_content = {}
    counts = {"proof": 0, "numeric": 0}
    for entry in new_entries:
        kind = entry["kind"]
        case_id = f"{kind}-{counts[kind]:02d}"
        counts[kind] += 1
        packet_path = destination / (case_id + ".md")
        prompt = "\n\n".join(message["content"] for message in entry["job"]["messages"])
        packet_path.write_text(f"# {case_id}\n\n## Problem\n\n{prompt}\n\n"
                               f"## Model answer (full)\n\n{entry['response']['raw_text']}\n")
        packet_hash = sha(packet_path)
        index.append({"case_id": case_id, "kind": kind, "file": packet_path.name,
                      "packet_sha256": packet_hash})
        row = entry["row"]
        private[case_id] = {"kind": kind, "arm": row["arm"], "job_id": row["job_id"],
                            "source_id": row["source_id"], "file": str(entry["path"]),
                            "file_sha256": row["file_sha256"], "content_sha256": entry["content_sha256"],
                            "packet_file": str(packet_path), "packet_sha256": packet_hash,
                            "cap": row["cap"]}
        case_id_by_content[entry["content_sha256"]] = case_id

    plan = []
    for entry in entries:
        row = entry["row"]
        plan.append({"kind": entry["kind"], "arm": row["arm"], "job_id": row["job_id"],
                     "source_id": row["source_id"], "split": row["split"],
                     "file": str(entry["path"]), "file_sha256": row["file_sha256"],
                     "content_sha256": entry["content_sha256"],
                     "prior_review": entry["prior"] is not None,
                     "case_id": case_id_by_content.get(entry["content_sha256"])})
    write(destination / "index.json", index)
    write(private_path, private)
    write(plan_path, {"label": args.label, "scores_file": str(scores_path.resolve()),
                      "scores_sha256": sha(scores_path),
                      "prior_bank_sha256": sha(PRIOR_BANK), "selected": len(plan),
                      "reused": sum(x["prior_review"] for x in plan),
                      "new": len(index), "rows": plan})
    print(json.dumps({"packet": str(destination), "selected": len(plan),
                      "reused": sum(x["prior_review"] for x in plan),
                      "new": len(index), "new_by_kind": counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
