"""Static comparison preflight. There is intentionally no natural-case run command."""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
from collections import Counter
from pathlib import Path

from benchmarks.gmb_comparison.alignment import PROFILE, select_comparison_input
from benchmarks.gmb_comparison.checker import CHECKER_POLICY, inspect_gmbl
from benchmarks.gmb_comparison.sources import DEFAULT_UPSTREAM, HERE, UPSTREAM_COMMIT, sha256
from benchmarks.gmb_comparison.witness import WitnessExporter


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def check_review(review, *, case_hash, audit_hash, entry, statement):
    expected = {
        "case_id": entry["case_id"],
        "case_sha256": case_hash,
        "audit_sha256": audit_hash,
        "gmbl_sha256": entry["gmbl_sha256"],
        "reviewed_original_pdf_sha256": statement["pdf_sha256"],
    }
    problems = [
        f"review_identity_mismatch:{key}" for key, val in expected.items() if review.get(key) != val
    ]
    if review.get("reviewer") != "independent_review":
        problems.append("independent_reviewer_missing")
    if review.get("verdict") != "pass":
        problems.append("independent_review_not_passed")
    for key in ("normalization_checked", "conclusion_not_assumed"):
        if review.get(key) is not True:
            problems.append(f"review_missing:{key}")
    return problems


def inspect_case(root, entry, statement, upstream, supplementary_statements=None):
    from geosolver.problem.models import GeometryProblem
    from geosolver.problem.validation import validate

    case_id = entry["case_id"]
    case_path, audit_path, review_path = (
        root / folder / f"{case_id}.json" for folder in ("cases", "audit", "reviews")
    )
    row = {
        "case_id": case_id,
        "issues": [],
        "static_valid": False,
        "independently_reviewed": False,
        "original_assumptions_covered": False,
    }
    issues = row["issues"]
    gmbl_path = upstream / entry["gmbl_relative_path"]
    if not gmbl_path.is_file() or sha256(gmbl_path) != entry["gmbl_sha256"]:
        issues.append("gmb_input_missing_or_changed")
        return row
    gmbl = gmbl_path.read_text(encoding="utf-8")
    coverage = inspect_gmbl(gmbl)
    row["checker_coverage"] = coverage
    if not coverage["supported"]:
        issues.append("unsupported_gmbl")
    for path, label in ((case_path, "case"), (audit_path, "audit"), (review_path, "review")):
        if not path.is_file():
            issues.append(f"missing_{label}")
    if not case_path.is_file():
        return row
    row["case_sha256"] = sha256(case_path)
    try:
        document = read_json(case_path)
        problem = GeometryProblem.model_validate(document)
        report = validate(problem)
        row["static_valid"] = report.valid
        row["validation_issues"] = [item.model_dump() for item in report.issues]
        row["variable_count"] = len(problem.variables)
        row["condition_count"] = len(problem.conditions)
        row["construction_count"] = len(problem.constructions)
        if problem.id != case_id:
            issues.append("case_id_mismatch")
        if problem.target != "0":
            issues.append("target_must_be_zero")
        if not report.valid:
            issues.append("invalid_dsl")
        # Detect accidentally fixed, unused variables without pretending that
        # counting equations establishes the geometric degrees of freedom.
        expressions = [item.expression for item in problem.constructions]
        expressions.extend(
            item.predicate if hasattr(item, "predicate") else f"({item.left}) + ({item.right})"
            for item in problem.conditions
        )
        used = {
            node.id
            for expr in expressions
            for node in ast.walk(ast.parse(expr, mode="eval"))
            if isinstance(node, ast.Name)
        }
        if set(problem.variables) - used:
            issues.append("unused_variable")
    except Exception as error:
        issues.append(f"invalid_case:{type(error).__name__}:{error}")
        return row
    if not audit_path.is_file():
        return row
    audit = read_json(audit_path)
    row["audit_sha256"] = sha256(audit_path)
    if audit.get("case_id") != case_id:
        issues.append("audit_case_id_mismatch")
    source = audit.get("source", {})
    for key, expected in (
        ("gmbl_sha256", entry["gmbl_sha256"]),
        ("official_pdf_sha256", statement["pdf_sha256"]),
        ("official_url", statement["url"]),
    ):
        if source.get(key) != expected:
            issues.append(f"audit_source_mismatch:{key}")
    supplement = source.get("supplementary_primary_source")
    if supplement and not any(
        item["url"] == supplement.get("url") and item["pdf_sha256"] == supplement.get("pdf_sha256")
        for item in (supplementary_statements or {}).values()
    ):
        issues.append("supplementary_source_identity_mismatch")
    normalization = audit.get("normalization", {})
    row["normalization"] = normalization
    if normalization.get("scale_invariant") is not True:
        issues.append("scale_normalization_unjustified")
    if normalization.get("removed_continuous_dof") != 4:
        issues.append("normalization_dof_not_four")
    if normalization.get("reflection_fixed") is not False:
        issues.append("mirror_branch_not_retained")
    if not normalization.get("justification") or not audit.get("clauses"):
        issues.append("semantic_justification_missing")
    row["source_differences"] = audit.get("source_differences", [])
    row["open_issues"] = audit.get("open_issues", [])
    if audit.get("comparison_status") == "blocked":
        issues.append("author_blocked")
    if any(
        item.get("blocking") is True for item in row["source_differences"] if isinstance(item, dict)
    ):
        issues.append("unresolved_source_difference")
    if audit.get("open_issues"):
        issues.append("author_open_issues")
    try:
        exporter = WitnessExporter(
            document, coverage.get("declarations", {}), audit.get("witness_bindings", {})
        )
        row["compiled_coordinate_names"] = list(exporter.coordinate_names)
    except Exception as error:
        issues.append(f"witness_binding_error:{error}")
    if review_path.is_file():
        review = read_json(review_path)
        row["review_sha256"] = sha256(review_path)
        review_issues = check_review(
            review,
            case_hash=row["case_sha256"],
            audit_hash=row["audit_sha256"],
            entry=entry,
            statement=statement,
        )
        if supplement and review.get("reviewed_supplementary_pdf_sha256") != supplement.get(
            "pdf_sha256"
        ):
            review_issues.append("supplementary_source_review_missing_or_stale")
        issues.extend(review_issues)
        row["independently_reviewed"] = not review_issues
        row["original_assumptions_covered"] = (
            review.get("original_conditions_covered_by_gmbl") is True and not review_issues
        )
        row["review_findings"] = review.get("findings", [])
        if not row["original_assumptions_covered"]:
            issues.append("original_assumptions_not_covered_by_common_checker")
    return row


def preflight(root=HERE, upstream=DEFAULT_UPSTREAM):
    from geosolver.runtime.integrity import engine_identity_hashes, verify_engine_lock

    root, upstream = Path(root), Path(upstream)
    sources = read_json(root / "source-manifest.json")
    protocol = read_json(root / "protocol.json")
    entries = sources["inputs"]
    expected = {entry["case_id"] for entry in entries}
    global_issues = []
    try:
        adjustments = read_json(root / "input-adjustments.json")
    except (OSError, ValueError):
        adjustments = {}
        global_issues.append("input_adjustments_manifest_missing_or_invalid")
    if (
        adjustments.get("schema_version") != 1
        or adjustments.get("profile") != PROFILE
        or adjustments.get("approved_by_user") is not True
        or adjustments.get("gmb_commit") != UPSTREAM_COMMIT
        or protocol.get("input_profile") != PROFILE
    ):
        global_issues.append("input_alignment_contract_mismatch")
    variants = adjustments.get("variants", {})
    if not isinstance(variants, dict):
        variants = {}
        global_issues.append("invalid_input_variants")
    if set(variants) - expected:
        global_issues.append("unexpected_aligned_input_id")
    aligned_files = {path.stem for path in (root / "gmbl-original-aligned").glob("*.smt2")}
    if aligned_files != set(variants):
        global_issues.append("aligned_input_inventory_mismatch")
    if (
        sources.get("gmb_commit") != UPSTREAM_COMMIT
        or protocol.get("gmb_commit") != UPSTREAM_COMMIT
    ):
        global_issues.append("gmb_commit_contract_mismatch")
    try:
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=upstream, text=True, stderr=subprocess.PIPE
        ).strip()
        if revision != UPSTREAM_COMMIT:
            global_issues.append("gmb_checkout_revision_mismatch")
    except (OSError, subprocess.CalledProcessError):
        revision = None
        global_issues.append("gmb_checkout_unavailable")
    assets = Path(sources["asset_directory"])
    statements = {**sources["statements"], **sources.get("supplementary_statements", {})}
    for key, statement in statements.items():
        for kind in ("pdf", "text"):
            path = assets / statement[f"{kind}_filename"]
            if not path.is_file() or sha256(path) != statement[f"{kind}_sha256"]:
                global_issues.append(f"source_asset_missing_or_changed:{key}:{kind}")
    if len(entries) != 36 or len(expected) != 36:
        global_issues.append("expected_36_unique_inputs")
    actual = {path.stem for path in (root / "cases").glob("*.json")}
    if actual != expected:
        global_issues.append("case_inventory_mismatch")
    for folder in ("audit", "reviews"):
        unexpected = {path.stem for path in (root / folder).glob("IMO_*.json")} - expected
        if unexpected:
            global_issues.append(f"unexpected_{folder}_ids:{sorted(unexpected)}")
    lock_ok, lock_message = verify_engine_lock()
    if not lock_ok:
        global_issues.append("solver_lock_mismatch")
    rows = [
        inspect_case(
            root,
            entry,
            sources["statements"][str(entry["year"])],
            upstream,
            sources.get("supplementary_statements", {}),
        )
        for entry in entries
    ]
    for entry, row in zip(entries, rows, strict=True):
        select_comparison_input(root, entry, upstream, row, variants.get(entry["case_id"]))
        row["input_ready"] = not row["issues"]
    files = sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and (path.suffix in {".py", ".json", ".md", ".smt2"} or path.name == "LICENSE")
        and "__pycache__" not in path.parts
        and path.name not in {"preflight-report.json", "PREPARATION_REPORT.md"}
    )
    return {
        "schema_version": 2,
        "natural_cases_executed": 0,
        "comparison_profile": PROFILE,
        "input_count": len(rows),
        "official_input_count": sum(
            row["comparison_input"]["origin"] == "official_gmb" for row in rows
        ),
        "original_aligned_input_count": sum(
            row["comparison_input"]["origin"] == PROFILE for row in rows
        ),
        "source_asset_count": 2 * len(statements),
        "gmb_checkout_revision": revision,
        "static_valid_count": sum(row["static_valid"] for row in rows),
        "independently_reviewed_count": sum(row["independently_reviewed"] for row in rows),
        "input_ready_count": sum(row["input_ready"] for row in rows),
        "global_issues": global_issues,
        "issue_counts": dict(sorted(Counter(i for row in rows for i in row["issues"]).items())),
        "all_inputs_ready": not global_issues and all(row["input_ready"] for row in rows),
        "execution_unlocked": False,
        "execution_note": (
            "Static validation never executes natural cases; main execution separately requires "
            "explicit user authorization, a passing canary and a sealed campaign manifest"
        ),
        "solver_lock": {
            "valid": lock_ok,
            "message": lock_message,
            "identity": engine_identity_hashes(),
        },
        "protocol": protocol,
        "checker_policy": CHECKER_POLICY,
        "file_sha256": {str(path.relative_to(root)): sha256(path) for path in files},
        "cases": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=HERE)
    parser.add_argument("--upstream", type=Path, default=DEFAULT_UPSTREAM)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()
    report = preflight(args.root, args.upstream)
    content = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(content, encoding="utf-8")
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "input_count",
                    "static_valid_count",
                    "independently_reviewed_count",
                    "input_ready_count",
                    "global_issues",
                    "issue_counts",
                    "all_inputs_ready",
                    "execution_unlocked",
                )
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if args.require_ready and not report["all_inputs_ready"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
