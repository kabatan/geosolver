#!/usr/bin/env python3
"""Occurrence-complete, truth-free source eligibility for invariant Gram D0."""

from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping


ARCHIVE_ROOT = Path("/home/kabatan/work/solver-experiment-runtime/solver")
DEFAULT_DATASET = (
    ARCHIVE_ROOT
    / "research/experiments/EXP-OMC-V15-MERGED5-EVAL-001/inputs/omc_v15_merged_5files.audit-canonical.jsonl"
)
SPLIT = ARCHIVE_ROOT / "research/experiments/EXP-V15-243-001/benchmark/SPLIT_MANIFEST.json"
EXPECTED_SPLIT_SHA256 = "065b2602e515b16086768c5a60abf91248faee7ed0cb76b9d88d4c421bcbdf3f"
ROW_ID = re.compile(rb'"problem_id":"([^"\\]+)"')

CONSTRUCTION_OPERATORS = frozenset(
    {
        "Point", "Line", "Circle", "CircleThroughPoint", "CircleThroughThreePoints",
        "Circumcenter", "Circumcircle", "Center", "Midpoint", "Centroid",
        "FootOfPerpendicular", "PerpendicularBisector", "PerpendicularLine",
        "ParallelLine", "Reflect", "Intersect", "Incenter", "Incircle",
        "ContactPoint", "IncircleContactPoint", "Excircle", "Distance", "sqrt", "abs",
    }
)
INVARIANT_RELATIONS = frozenset(
    {
        "Distance", "Dot", "Vector", "Area", "Radius", "Line", "Circle", "Center",
        "OnLine", "OnCircle", "OnSegment", "Parallel", "Perpendicular", "IsTangent",
        "Assume", "AssumeAcute", "AssumeConvex", "AssumeEq", "AssumeGe", "AssumeGt",
        "AssumeLt", "AssumeNe", "AssumeNoSelfIntersecting", "sqrt", "abs",
    }
)
TARGET_OPERATORS = frozenset({"Distance", "Area", "Radius", "Dot", "Vector", "sqrt", "abs"})
ALLOWED_BY_SITE = {
    "construction": CONSTRUCTION_OPERATORS,
    "constraint": INVARIANT_RELATIONS,
    "guard": INVARIANT_RELATIONS,
    "target": TARGET_OPERATORS,
}


def _sites(formulation: Mapping[str, Any]) -> list[tuple[str, str]]:
    sites: list[tuple[str, str]] = []
    for item in formulation.get("construction", ()):
        sites.append(("construction", str(item["expr"])))
    for item in formulation.get("constraints", ()):
        sites.append(("constraint", str(item["def"])))
        sites.append(("constraint", str(item.get("value", 0))))
    sites.extend(("guard", str(text)) for text in formulation.get("guards", ()))
    sites.append(("target", str(formulation["answer"])))
    return sites


def analyze(formulation: Mapping[str, Any]) -> tuple[bool, list[str], str | None, Counter[str]]:
    reasons: set[str] = set()
    occurrences: Counter[str] = Counter()
    declared = frozenset(formulation.get("variables", {}).get("names", ()))
    if formulation.get("bounds") is not None:
        reasons.add("absolute-or-chart-bound")
    for site, text in _sites(formulation):
        try:
            root = ast.parse(text, mode="eval")
        except SyntaxError:
            reasons.add("syntax-outside-closed-subset")
            continue
        point_coordinate_names: set[int] = set()
        for node in ast.walk(root):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "Point"
            ):
                point_coordinate_names.update(
                    id(child)
                    for argument in node.args
                    for child in ast.walk(argument)
                    if isinstance(child, ast.Name)
                )
        site_calls = []
        for node in ast.walk(root):
            if isinstance(node, ast.Call):
                if not isinstance(node.func, ast.Name):
                    reasons.add("dynamic-or-attribute-call")
                    continue
                operator = node.func.id
                occurrences[f"{site}:{operator}"] += 1
                site_calls.append(operator)
                if operator not in ALLOWED_BY_SITE[site]:
                    reasons.add(f"operator-escape:{site}:{operator}")
                if operator == "Intersect" and any(
                    keyword.arg not in {"exclude"} for keyword in node.keywords
                ):
                    reasons.add("selector-keyword-escape")
            elif isinstance(node, ast.Attribute):
                reasons.add("absolute-coordinate-or-attribute-use")
            elif isinstance(node, (ast.Subscript, ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp)):
                reasons.add("non-invariant-operation-escape")
            elif (
                isinstance(node, ast.Name)
                and node.id in declared
                and id(node) not in point_coordinate_names
            ):
                reasons.add("raw-scalar-variable-use")
        if site == "target" and not site_calls:
            reasons.add("raw-scalar-target")
    signature = None
    if not reasons:
        signature_payload = json.dumps(
            sorted(occurrences.items()), separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
        signature = hashlib.sha256(signature_payload).hexdigest()[:16]
    return not reasons, sorted(reasons), signature, occurrences


def census(dataset: Path) -> dict[str, Any]:
    split_bytes = SPLIT.read_bytes()
    if hashlib.sha256(split_bytes).hexdigest() != EXPECTED_SPLIT_SHA256:
        raise RuntimeError("split digest mismatch")
    development_ids = frozenset(json.loads(split_bytes)["partitions"]["development"]["case_ids"])
    payload = dataset.read_bytes()
    eligible = 0
    signatures: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    eligible_occurrences: Counter[str] = Counter()
    skipped = 0
    selected = 0
    for line in payload.splitlines():
        if not line.strip():
            continue
        match = ROW_ID.search(line)
        if match is None:
            raise RuntimeError("dataset row missing identity")
        if match.group(1).decode("utf-8") not in development_ids:
            skipped += 1
            continue
        selected += 1
        formulation = json.loads(line)["formulation"]
        accepted, case_reasons, signature, occurrences = analyze(formulation)
        if accepted:
            eligible += 1
            signatures[str(signature)] += 1
            eligible_occurrences.update(occurrences)
        else:
            reasons.update(case_reasons)
    if selected != 145 or skipped != 102:
        raise RuntimeError("development custody mismatch")
    return {
        "schema": "geotarget.exact-gram-chirotope-source-eligibility/v1",
        "authority": "TRUTH_FREE_SOURCE_ONLY_OPERATOR_OCCURRENCE_COMPLETE",
        "dataset_sha256": hashlib.sha256(payload).hexdigest(),
        "split_manifest_sha256": EXPECTED_SPLIT_SHA256,
        "partition": "development",
        "case_count": selected,
        "nondevelopment_rows_skipped_without_json_deserialization": skipped,
        "validation_or_sealed_formulation_parsed": False,
        "outer_truth_indexed_or_copied": False,
        "individual_case_id_target_truth_or_outcome_emitted": False,
        "eligible_attempt_count": eligible,
        "anonymous_structural_signature_count": len(signatures),
        "anonymous_signature_multiplicity_histogram": dict(
            sorted(Counter(signatures.values()).items())
        ),
        "eligible_operator_occurrences": dict(sorted(eligible_occurrences.items())),
        "rejection_reason_histogram": dict(sorted(reasons.items())),
        "gate": {
            "minimum_attempts": 4,
            "minimum_anonymous_structural_signatures": 2,
            "pass": eligible >= 4 and len(signatures) >= 2,
        },
        "coordinate_policy": (
            "Point constructor arguments are proposal chart inputs only. Any component/attribute read, "
            "bound, raw scalar use outside Point arguments, or raw scalar target fails closed."
        ),
        "interpretation_limit": (
            "Eligibility is not activation, solvability, authority, target correctness, or recall. It only "
            "shows a closed Euclidean-invariant operator surface on which a private Gram/EDM witness may try."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    result = census(arguments.dataset)
    arguments.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
