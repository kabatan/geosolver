"""Select explicitly reviewed original-statement repairs without changing upstream inputs."""

from __future__ import annotations

import json
from pathlib import Path

from benchmarks.gmb_comparison.checker import inspect_gmbl, parse_gmbl
from benchmarks.gmb_comparison.checker_geometry import CheckError
from benchmarks.gmb_comparison.sources import sha256

PROFILE = "original_statement_aligned"
SOURCE_OMISSION_ISSUES = {
    "author_blocked",
    "author_open_issues",
    "unresolved_source_difference",
    "original_assumptions_not_covered_by_common_checker",
}


def local_path(root, relative):
    root = Path(root).resolve()
    path = Path(relative)
    if path.is_absolute() or not (root / path).resolve().is_relative_to(root):
        raise ValueError("comparison input/review must be inside the preparation directory")
    return root / path


def additions_only(official_text, comparison_text, additions):
    """Retain every original command, inserting only declared assertions before the goal."""
    original, selected = parse_gmbl(official_text), parse_gmbl(comparison_text)
    if not isinstance(additions, list) or not additions:
        return False
    extra = []
    for text in additions:
        commands = parse_gmbl(text)
        if len(commands) != 1 or commands[0][0] != "assert":
            return False
        extra.append(commands[0])
    if original[-1][0] != "eval":
        return False
    return selected == original[:-1] + tuple(extra) + original[-1:]


def select_comparison_input(root, entry, upstream, row, adjustment=None):
    """Apply a hash-bound supplemental review, never waive unrelated input failures."""
    official_path = Path(upstream) / entry["gmbl_relative_path"]
    row["comparison_input"] = {
        "origin": "official_gmb",
        "path": str(official_path.resolve()),
        "sha256": entry["gmbl_sha256"],
    }
    if adjustment is None:
        return
    row["official_pairing"] = {
        "issues": list(row["issues"]),
        "original_assumptions_covered": row["original_assumptions_covered"],
        "independently_reviewed": row["independently_reviewed"],
        "source_differences": row.get("source_differences", []),
        "open_issues": row.get("open_issues", []),
    }
    # A passed review of the unmodified input does not approve the selected repair.
    row["independently_reviewed"] = False
    row["original_assumptions_covered"] = False
    issues = []
    try:
        path = local_path(root, adjustment["comparison_relative_path"])
        review_path = local_path(root, adjustment["review_relative_path"])
        actual_hash = sha256(path)
        row["comparison_input"] = {
            "origin": PROFILE,
            "path": str(path.resolve()),
            "sha256": actual_hash,
            "official_gmbl_sha256": entry["gmbl_sha256"],
            "added_assertions": adjustment["added_assertions"],
            "reason_ja": adjustment["reason_ja"],
        }
        if adjustment["official_gmbl_sha256"] != entry["gmbl_sha256"]:
            issues.append("alignment_official_hash_mismatch")
        if actual_hash != adjustment["comparison_gmbl_sha256"]:
            issues.append("alignment_input_hash_mismatch")
        selected = path.read_text(encoding="utf-8")
        if not additions_only(
            official_path.read_text(encoding="utf-8"), selected, adjustment["added_assertions"]
        ):
            issues.append("alignment_changed_unlisted_commands")
        coverage = inspect_gmbl(selected)
        if not coverage["supported"]:
            issues.append("unsupported_alignment_gmbl")
        if coverage.get("declarations") != row.get("checker_coverage", {}).get("declarations"):
            issues.append("alignment_changed_declarations")
        row["checker_coverage"] = coverage
        blocking_ids = sorted(
            item.get("id", "")
            for item in row.get("source_differences", [])
            if item.get("blocking") is True
        )
        resolved_ids = sorted(adjustment["resolved_source_difference_ids"])
        if not resolved_ids or blocking_ids != resolved_ids:
            issues.append("alignment_blocker_scope_mismatch")
        review = json.loads(review_path.read_text(encoding="utf-8"))
        expected = {
            "case_id": entry["case_id"],
            "reviewer": "independent_review",
            "verdict": "pass",
            "official_gmbl_sha256": entry["gmbl_sha256"],
            "comparison_gmbl_sha256": actual_hash,
            "geosolver_case_sha256": row.get("case_sha256"),
            "audit_sha256": row.get("audit_sha256"),
            "prior_review_sha256": row.get("review_sha256"),
            "resolved_source_difference_ids": adjustment["resolved_source_difference_ids"],
            "assumptions_equivalent": True,
            "conclusion_not_added": True,
            "reflection_retained": True,
            "only_missing_conditions_added": True,
        }
        for key, value in expected.items():
            if review.get(key) != value:
                issues.append(f"alignment_review_mismatch:{key}")
        if review.get("open_issues"):
            issues.append("alignment_review_open_issues")
        row["alignment_review"] = {
            "path": str(review_path.resolve()),
            "sha256": sha256(review_path),
            "resolved_source_difference_ids": resolved_ids,
            "findings": review.get("findings", []),
        }
    except (OSError, KeyError, TypeError, ValueError, CheckError) as error:
        issues.append(f"invalid_alignment:{type(error).__name__}:{error}")
    if issues:
        row["issues"].extend(issues)
        return
    if not row["official_pairing"]["independently_reviewed"]:
        row["issues"].append("alignment_requires_valid_prior_dsl_review")
        return
    row["independently_reviewed"] = True
    row["original_assumptions_covered"] = True
    row["issues"] = [issue for issue in row["issues"] if issue not in SOURCE_OMISSION_ISSUES]
    row["source_differences"] = [
        {
            **item,
            "blocking": False,
            "comparison_resolution": adjustment["review_relative_path"],
        }
        if item.get("id") in resolved_ids
        else item
        for item in row.get("source_differences", [])
    ]
    row["open_issues"] = []
