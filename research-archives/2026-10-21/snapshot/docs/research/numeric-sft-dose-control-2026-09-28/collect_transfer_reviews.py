"""Join blind grades to final transfer answers by exact response-content hash."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import prepare_transfer_review as prep

P, O = prep.P, prep.O
REVIEW = P / "review"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--label", required=True, help="Label used by prepare_transfer_review.py")
    ap.add_argument("--manifest", type=Path, default=REVIEW / "transfer-review-manifest.json")
    args = ap.parse_args()

    plan_path = O / f"transfer-review-plan-{args.label}.json"
    plan = prep.read(plan_path)
    if plan["label"] != args.label:
        raise ValueError("Plan label mismatch")
    scores_path = Path(plan["scores_file"])
    if prep.sha(scores_path) != plan["scores_sha256"]:
        raise ValueError("Final transfer scores changed since packet preparation")
    if prep.sha(prep.PRIOR_BANK) != plan["prior_bank_sha256"]:
        raise ValueError("Prior review bank changed since packet preparation")
    old_bank = prep.read(prep.PRIOR_BANK)["bank"]
    new_grades = prep.manifest_grades(args.manifest)
    private = prep.read(O / f"private-transfer-{args.label}.json")
    result = []
    missing = []
    for row in plan["rows"]:
        source = Path(row["file"])
        if prep.sha(source) != row["file_sha256"]:
            raise ValueError(f"Response file changed: {source}")
        digest = prep.content_hash(prep.read(source))
        if digest != row["content_sha256"]:
            raise ValueError(f"Content changed: {source}")
        prior = old_bank.get(digest)
        if prior is not None:
            prep.validate_prior(prior, digest, row["kind"])
        current_review = new_grades.get(digest)
        supersedes_prior = prior is not None and current_review is not None and current_review.get("supersedes_prior", False)
        if prior is not None and not supersedes_prior:
            grade = prep.normalize_grade(row["kind"], prior["grade"])
            review = {"origin": "prior_exact_content", "grade": grade,
                      "grade_file": prior["grade_file"],
                      "grade_file_sha256": prior["grade_file_sha256"]}
        else:
            case_id = row["case_id"]
            found = new_grades.get(digest)
            if case_id is not None and private[case_id]["content_sha256"] != digest:
                raise ValueError(f"Private mapping mismatch: {source}")
            if case_id is None and found is None:
                raise ValueError(f"Previously registered grade disappeared: {source}")
            if found is None:
                review = None
                missing.append({"arm": row["arm"], "job_id": row["job_id"],
                                "kind": row["kind"], "case_id": case_id})
            else:
                if found["kind"] != row["kind"]:
                    raise ValueError(f"New grade kind mismatch: {digest}")
                review = {"origin": "registered_exact_content" if case_id is None else "new_blind_review",
                          "grade": found["grade"],
                          "grade_file": found["grade_file"],
                          "grade_file_sha256": found["grade_file_sha256"],
                          "case_id": found["case_id"]}
                if supersedes_prior:
                    review["superseded_prior"] = {"grade": prior["grade"],
                        "grade_file": prior["grade_file"],
                        "grade_file_sha256": prior["grade_file_sha256"]}
        result.append({"kind": row["kind"], "arm": row["arm"], "job_id": row["job_id"],
                       "source_id": row["source_id"], "split": row["split"],
                       "file": row["file"], "file_sha256": row["file_sha256"],
                       "content_sha256": digest, "review": review})
    output = {"status": "complete" if not missing else "partial", "label": args.label,
              "required": len(result), "reviewed": len(result) - len(missing),
              "reused_prior": sum(x["review"] is not None and x["review"]["origin"] == "prior_exact_content" for x in result),
              "reused_registered": sum(x["review"] is not None and x["review"]["origin"] == "registered_exact_content" for x in result),
              "missing": missing, "rows": result,
              "inputs_sha256": {str(path): prep.sha(path) for path in
                                [scores_path, plan_path, prep.PRIOR_BANK, args.manifest]}}
    target = O / f"transfer-review-results-{args.label}.json"
    prep.write(target, output)
    print(json.dumps({"output": str(target), "status": output["status"],
                      "required": output["required"], "reviewed": output["reviewed"],
                      "reused_prior": output["reused_prior"], "reused_registered": output["reused_registered"],
                      "missing": len(missing)},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
