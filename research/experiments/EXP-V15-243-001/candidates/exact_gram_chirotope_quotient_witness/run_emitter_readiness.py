#!/usr/bin/env python3
"""Aggregate-only exact labelled EDM / ruler-compass emitter readiness."""

from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from run_source_eligibility import DEFAULT_DATASET, EXPECTED_SPLIT_SHA256, ROW_ID, SPLIT, analyze


DETERMINISTIC_CONSTRUCTIONS = frozenset(
    {
        "Line", "Circle", "CircleThroughPoint", "CircleThroughThreePoints", "Circumcenter",
        "Circumcircle", "Center", "Midpoint", "Centroid", "FootOfPerpendicular",
        "PerpendicularBisector", "PerpendicularLine", "ParallelLine", "Reflect", "Incenter",
        "Incircle", "ContactPoint", "IncircleContactPoint", "Excircle",
    }
)


def _tree(text: object) -> ast.AST:
    return ast.parse(str(text), mode="eval").body


def _call(text: object) -> ast.Call | None:
    node = _tree(text)
    return node if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) else None


def _names(node: ast.AST) -> set[str]:
    return {item.id for item in ast.walk(node) if isinstance(item, ast.Name)}


def _top_operator(node: ast.AST) -> str | None:
    return node.func.id if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) else None


def _exact_expression(node: ast.AST, exact_labels: set[str], declared: set[str]) -> bool:
    operator_names = DETERMINISTIC_CONSTRUCTIONS | {"Point", "sqrt", "abs", "Distance", "Radius"}
    for item in ast.walk(node):
        if isinstance(item, ast.Name):
            if item.id in declared:
                return False
            if item.id in operator_names:
                continue
            if item.id not in exact_labels:
                return False
        if isinstance(item, ast.Call):
            if not isinstance(item.func, ast.Name) or item.func.id not in {"sqrt", "abs", "Distance", "Radius"}:
                return False
    return True


def _exact_labels(
    definitions: Mapping[str, ast.AST],
    exact_points: set[str],
    declared: set[str],
) -> set[str]:
    exact = set(exact_points)
    changed = True
    while changed:
        changed = False
        for label, node in definitions.items():
            if label in exact:
                continue
            operator = _top_operator(node)
            if operator not in DETERMINISTIC_CONSTRUCTIONS:
                continue
            dependencies = _names(node) - (
                DETERMINISTIC_CONSTRUCTIONS | {"Point", "sqrt", "abs", "Distance", "Radius"}
            )
            if dependencies <= exact and _exact_expression(node, exact, declared):
                exact.add(label)
                changed = True
    return exact


def _pair_names(call: ast.Call) -> tuple[str, str] | None:
    if len(call.args) < 2 or not all(isinstance(arg, ast.Name) for arg in call.args[:2]):
        return None
    return call.args[0].id, call.args[1].id


def _loci_for_point(
    point: str,
    constraints: list[Mapping[str, Any]],
    exact: set[str],
    declared: set[str],
) -> set[tuple[str, str]]:
    loci: set[tuple[str, str]] = set()
    for constraint in constraints:
        left = _tree(constraint["def"])
        right = _tree(constraint.get("value", 0))
        for relation, other in ((left, right), (right, left)):
            operator = _top_operator(relation)
            if operator == "Distance":
                pair = _pair_names(relation)
                if pair and point in pair:
                    neighbor = pair[1] if pair[0] == point else pair[0]
                    if neighbor in exact and _exact_expression(other, exact, declared):
                        loci.add(("circle", f"distance:{neighbor}:{ast.dump(other, include_attributes=False)}"))
            elif operator in {"OnCircle", "OnLine"}:
                pair = _pair_names(relation)
                if pair and pair[0] == point and pair[1] in exact:
                    loci.add(("circle" if operator == "OnCircle" else "line", f"label:{pair[1]}"))
            elif operator == "Area" and isinstance(other, ast.Constant) and other.value == 0:
                names = [arg.id for arg in relation.args if isinstance(arg, ast.Name)]
                if len(names) == 3 and point in names and set(names) - {point} <= exact:
                    anchors = sorted(set(names) - {point})
                    loci.add(("line", "area-zero:" + ":".join(anchors)))
    return loci


def _readiness(formulation: Mapping[str, Any]) -> dict[str, Any]:
    declared = set(formulation.get("variables", {}).get("names", ()))
    definitions = {item["name"]: _tree(item["expr"]) for item in formulation.get("construction", ())}
    anchors: set[str] = set()
    free: set[str] = set()
    construction_ops: Counter[str] = Counter()
    for label, node in definitions.items():
        operator = _top_operator(node)
        if operator:
            construction_ops[operator] += 1
        if operator == "Point":
            if _names(node) & declared:
                free.add(label)
            else:
                anchors.add(label)
    all_points = anchors | free
    constraints = list(formulation.get("constraints", ()))

    # Direct labelled EDM readiness: every pair either has exact anchor
    # coordinates or an exact source Distance equality.
    direct_edges = {tuple(sorted((a, b))) for a in anchors for b in anchors if a != b}
    for constraint in constraints:
        left, right = _tree(constraint["def"]), _tree(constraint.get("value", 0))
        for relation, other in ((left, right), (right, left)):
            if _top_operator(relation) == "Distance" and _exact_expression(other, anchors, declared):
                pair = _pair_names(relation)
                if pair and set(pair) <= all_points:
                    direct_edges.add(tuple(sorted(pair)))
    required_edges = {
        tuple(sorted((a, b))) for index, a in enumerate(sorted(all_points)) for b in sorted(all_points)[index + 1 :]
    }
    direct_complete = bool(all_points) and required_edges <= direct_edges

    constructed = set(anchors)
    remaining = set(free)
    branch_cap = 1
    steps: list[tuple[str, str]] = []
    while remaining:
        exact = _exact_labels(definitions, constructed, declared)
        candidates = []
        for candidate in remaining:
            loci = _loci_for_point(candidate, constraints, exact, declared)
            kinds = sorted(kind for kind, _identity in loci)
            if len(loci) >= 2:
                pair = tuple(kinds[:2])
                candidates.append((candidate, pair, loci))
        if not candidates:
            break
        candidate, pair, _loci = sorted(candidates, key=lambda item: (item[1], item[0]))[0]
        branch_cap *= 1 if pair == ("line", "line") else 2
        if branch_cap > 32:
            break
        steps.append(pair)
        constructed.add(candidate)
        remaining.remove(candidate)
    henneberg_complete = bool(free) and not remaining and branch_cap <= 32
    constraint_ops = Counter(
        operator
        for item in constraints
        for node in (_tree(item["def"]), _tree(item.get("value", 0)))
        if (operator := _top_operator(node)) is not None
    )
    signature_payload = {
        "anchors": len(anchors),
        "free": len(free),
        "steps": steps,
        "construction_ops": sorted(construction_ops.items()),
        "constraint_ops": sorted(constraint_ops.items()),
        "direct_complete": direct_complete,
    }
    return {
        "direct_complete": direct_complete,
        "henneberg_complete": henneberg_complete,
        "branch_cap": branch_cap,
        "unresolved_free_count": len(remaining),
        "signature": hashlib.sha256(
            json.dumps(signature_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:16],
        "steps": steps,
    }


def census(dataset: Path) -> dict[str, Any]:
    split_bytes = SPLIT.read_bytes()
    if hashlib.sha256(split_bytes).hexdigest() != EXPECTED_SPLIT_SHA256:
        raise RuntimeError("split digest mismatch")
    development_ids = frozenset(json.loads(split_bytes)["partitions"]["development"]["case_ids"])
    payload = dataset.read_bytes()
    eligible_sources = 0
    ready_attempts = 0
    direct = 0
    henneberg = 0
    signatures: Counter[str] = Counter()
    step_histogram: Counter[str] = Counter()
    rejection: Counter[str] = Counter()
    skipped = 0
    selected = 0
    for line in payload.splitlines():
        if not line.strip():
            continue
        match = ROW_ID.search(line)
        if match is None:
            raise RuntimeError("row identity missing")
        if match.group(1).decode("utf-8") not in development_ids:
            skipped += 1
            continue
        selected += 1
        formulation = json.loads(line)["formulation"]
        accepted, _reasons, _signature, _occurrences = analyze(formulation)
        if not accepted:
            continue
        eligible_sources += 1
        result = _readiness(formulation)
        is_ready = result["direct_complete"] or result["henneberg_complete"]
        if is_ready:
            ready_attempts += 1
            direct += int(result["direct_complete"])
            henneberg += int(result["henneberg_complete"])
            signatures[result["signature"]] += 1
            step_histogram.update("+".join(step) for step in result["steps"])
        else:
            rejection[f"unresolved-free-count:{result['unresolved_free_count']}"] += 1
    if selected != 145 or skipped != 102:
        raise RuntimeError("partition custody mismatch")
    gate = ready_attempts >= 4 and len(signatures) >= 2
    return {
        "schema": "geotarget.exact-gram-source-labelled-emitter-readiness/v1",
        "authority": "TRUTH_FREE_AGGREGATE_ONLY_STATIC_EMITTER_READINESS",
        "dataset_sha256": hashlib.sha256(payload).hexdigest(),
        "split_manifest_sha256": EXPECTED_SPLIT_SHA256,
        "development_case_count": selected,
        "original_invariant_eligible_source_count": eligible_sources,
        "ready_attempt_count": ready_attempts,
        "direct_complete_edm_count": direct,
        "henneberg_line_circle_complete_count": henneberg,
        "anonymous_structural_signature_count": len(signatures),
        "anonymous_signature_multiplicity_histogram": dict(sorted(Counter(signatures.values()).items())),
        "construction_step_type_histogram": dict(sorted(step_histogram.items())),
        "rejection_reason_histogram": dict(sorted(rejection.items())),
        "branch_cap": 32,
        "endpoint_role": "TRIAL_ORDER_ONLY_NEVER_EDM_OR_PSLQ_AUTHORITY",
        "gate": {
            "minimum_attempts": 4,
            "minimum_anonymous_structural_signatures": 2,
            "pass": gate,
        },
        "nondevelopment_rows_skipped_without_json_deserialization": skipped,
        "validation_or_sealed_formulation_parsed": False,
        "individual_id_value_target_truth_or_outcome_emitted": False,
        "formal_execute_scorer_or_full98_used": False,
        "interpretation_limit": (
            "Static readiness only. Each admitted free point has two source-labelled exact line/circle loci, "
            "all branch leaves remain subject to exact canonical replay, and no endpoint numeric value is authority."
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
