#!/usr/bin/env python3
"""Aggregate-only readiness for one-DOF exact rational parameter witnesses."""

from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import sympy as sp

from run_source_eligibility import DEFAULT_DATASET, EXPECTED_SPLIT_SHA256, ROW_ID, SPLIT, analyze
from run_emitter_readiness import (
    _exact_labels,
    _loci_for_point,
    _names,
    _pair_names,
    _readiness,
    _top_operator,
    _tree,
)


QQ_PARAMETER_SET = (
    "0", "1", "-1", "2", "-2", "3", "-3",
    "1/2", "-1/2", "1/3", "-1/3", "2/3", "-2/3",
)


def _rational_anchors(formulation: Mapping[str, Any]) -> dict[str, tuple[sp.Rational, sp.Rational]]:
    declared = set(formulation.get("variables", {}).get("names", ()))
    result = {}
    for item in formulation.get("construction", ()):
        node = _tree(item["expr"])
        if _top_operator(node) != "Point" or _names(node) & declared or len(node.args) != 2:
            continue
        try:
            pair = tuple(sp.Rational(ast.unparse(argument)) for argument in node.args)
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        result[item["name"]] = pair
    return result


def _constant_rational(node: ast.AST) -> sp.Rational | None:
    if {
        item.id for item in ast.walk(node) if isinstance(item, ast.Name)
    } - {"sqrt", "abs"}:
        return None
    try:
        value = sp.sympify(ast.unparse(node))
    except Exception:
        return None
    return value if value.is_Rational is True else None


def _circle_label_has_rational_base(
    label: str,
    definitions: Mapping[str, ast.AST],
    exact_points: set[str],
) -> bool:
    node = definitions.get(label)
    operator = _top_operator(node) if node is not None else None
    names = _names(node) if node is not None else set()
    if operator in {"CircleThroughPoint", "CircleThroughThreePoints", "Circumcircle"}:
        return bool(names & exact_points) and (names - {str(operator)}) <= exact_points
    if operator == "Circle" and len(node.args) >= 2:
        center = node.args[0].id if isinstance(node.args[0], ast.Name) else None
        radius = _constant_rational(node.args[1])
        return center in exact_points and radius is not None and radius != 0
    return False


def _distance_radius_has_rational_base(
    other: ast.AST,
    exact_points: set[str],
    definitions: Mapping[str, ast.AST],
) -> bool:
    constant = _constant_rational(other)
    if constant is not None and constant != 0:
        return True
    if isinstance(other, ast.Call) and isinstance(other.func, ast.Name):
        if other.func.id == "Distance":
            pair = _pair_names(other)
            return pair is not None and all(name in exact_points for name in pair)
        if other.func.id == "Radius" and len(other.args) == 1 and isinstance(other.args[0], ast.Name):
            return _circle_label_has_rational_base(other.args[0].id, definitions, exact_points)
    return False


def _line_from_perpendicular(
    point: str,
    relation: ast.AST,
    rational_points: set[str],
) -> bool:
    if _top_operator(relation) != "Perpendicular" or len(relation.args) != 2:
        return False
    lines = relation.args
    if any(_top_operator(line) != "Line" or len(line.args) != 2 for line in lines):
        return False
    for variable_line, fixed_line in (lines, tuple(reversed(lines))):
        variable_names = [arg.id for arg in variable_line.args if isinstance(arg, ast.Name)]
        fixed_names = [arg.id for arg in fixed_line.args if isinstance(arg, ast.Name)]
        if (
            len(variable_names) == 2
            and point in variable_names
            and set(variable_names) - {point} <= rational_points
            and len(fixed_names) == 2
            and set(fixed_names) <= rational_points
        ):
            return True
    return False


def _line_label_is_qq(
    label: str,
    definitions: Mapping[str, ast.AST],
    rational_points: set[str],
) -> bool:
    node = definitions.get(label)
    if node is None or _top_operator(node) != "Line" or len(node.args) != 2:
        return False
    points = [argument.id for argument in node.args if isinstance(argument, ast.Name)]
    return len(points) == 2 and set(points) <= rational_points


def _parameter_loci(
    point: str,
    formulation: Mapping[str, Any],
    definitions: Mapping[str, ast.AST],
    exact: set[str],
    rational_points: Mapping[str, tuple[sp.Rational, sp.Rational]],
) -> set[str]:
    loci = set()
    for constraint in formulation.get("constraints", ()):
        left, right = _tree(constraint["def"]), _tree(constraint.get("value", 0))
        for relation, other in ((left, right), (right, left)):
            operator = _top_operator(relation)
            if operator == "Distance":
                pair = _pair_names(relation)
                if pair and point in pair:
                    neighbor = pair[1] if pair[0] == point else pair[0]
                    if neighbor in exact and _distance_radius_has_rational_base(other, exact, definitions):
                        loci.add("circle")
            elif operator == "OnCircle":
                pair = _pair_names(relation)
                if pair and pair[0] == point and pair[1] in exact and _circle_label_has_rational_base(
                    pair[1], definitions, exact
                ):
                    loci.add("circle")
            elif operator == "OnLine":
                pair = _pair_names(relation)
                if (
                    pair
                    and pair[0] == point
                    and pair[1] in exact
                    and _line_label_is_qq(pair[1], definitions, set(rational_points))
                ):
                    loci.add("line")
            elif _line_from_perpendicular(point, relation, set(rational_points)):
                loci.add("line")
            elif operator == "Area" and _constant_rational(other) == 0:
                names = [argument.id for argument in relation.args if isinstance(argument, ast.Name)]
                if (
                    len(names) == 3
                    and point in names
                    and set(names) - {point} <= set(rational_points)
                ):
                    loci.add("line")
    return loci


def _parameter_ready(formulation: Mapping[str, Any]) -> dict[str, Any]:
    declared = set(formulation.get("variables", {}).get("names", ()))
    definitions = {item["name"]: _tree(item["expr"]) for item in formulation.get("construction", ())}
    rational = _rational_anchors(formulation)
    anchors = set(rational)
    free = {
        label for label, node in definitions.items()
        if _top_operator(node) == "Point" and _names(node) & declared
    }
    constructed = set(anchors)
    remaining = set(free)
    exact_branch_factor = 1
    # Close every ordinary two-locus exact placement first.
    while remaining:
        exact = _exact_labels(definitions, constructed, declared)
        candidates = []
        for point in remaining:
            loci = _loci_for_point(point, list(formulation.get("constraints", ())), exact, declared)
            if len(loci) >= 2:
                candidates.append((point, tuple(sorted(kind for kind, _ in loci)[:2])))
        if not candidates:
            break
        point, pair = sorted(candidates)[0]
        exact_branch_factor *= 1 if pair == ("line", "line") else 2
        constructed.add(point)
        # A Henneberg intersection of rational lines/circles can be QQBar but
        # is not necessarily rational, so it cannot seed a QQ parameter locus.
        remaining.remove(point)
    exact = _exact_labels(definitions, constructed, declared)
    parameter_options = []
    if len(remaining) == 1:
        point = next(iter(remaining))
        kinds = _parameter_loci(point, formulation, definitions, exact, rational)
        if len(kinds) == 1:
            parameter_options.append((point, next(iter(kinds)), (), 1))
    elif len(remaining) == 2:
        # Admit two free points only when one is the single rational parameter
        # and treating that exact trial point as constructed closes the other
        # by two already source-labelled exact loci.
        for point in sorted(remaining):
            kinds = _parameter_loci(point, formulation, definitions, exact, rational)
            if len(kinds) != 1:
                continue
            second = next(iter(remaining - {point}))
            after_parameter = _exact_labels(definitions, constructed | {point}, declared)
            closing_loci = sorted(_loci_for_point(
                second,
                list(formulation.get("constraints", ())),
                after_parameter,
                declared,
            ))
            if len(closing_loci) < 2:
                continue
            dependency_pair = tuple(kind for kind, _identity in closing_loci[:2])
            dependency_factor = 1 if dependency_pair == ("line", "line") else 2
            parameter_options.append((point, next(iter(kinds)), dependency_pair, dependency_factor))
    ready = bool(parameter_options)
    selected = sorted(parameter_options, key=lambda item: (item[1], item[2], item[0]))[0] if ready else None
    dependency_factor = selected[3] if selected is not None else 1
    total_trials = exact_branch_factor * len(QQ_PARAMETER_SET) * dependency_factor
    if total_trials > 32:
        ready = False
    signature = None
    if ready:
        payload = {
            "locus": selected[1],
            "dependency_step": selected[2],
            "exact_branch_factor": exact_branch_factor,
            "construction_ops": sorted(
                Counter(_top_operator(node) for node in definitions.values()).items()
            ),
            "constraint_ops": sorted(
                Counter(
                    _top_operator(_tree(item["def"]))
                    for item in formulation.get("constraints", ())
                ).items()
            ),
        }
        signature = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()[:16]
    return {
        "ready": ready,
        "locus": selected[1] if ready else None,
        "dependency_step": list(selected[2]) if ready else [],
        "remaining_dimension_upper_bound": len(remaining),
        "total_trials": total_trials,
        "signature": signature,
    }


def census(dataset: Path) -> dict[str, Any]:
    split_bytes = SPLIT.read_bytes()
    if hashlib.sha256(split_bytes).hexdigest() != EXPECTED_SPLIT_SHA256:
        raise RuntimeError("split digest mismatch")
    development_ids = frozenset(json.loads(split_bytes)["partitions"]["development"]["case_ids"])
    payload = dataset.read_bytes()
    selected = skipped = source_eligible = ready = 0
    signatures = Counter()
    loci = Counter()
    rejection = Counter()
    trials = Counter()
    for line in payload.splitlines():
        if not line.strip():
            continue
        match = ROW_ID.search(line)
        if match is None:
            raise RuntimeError("row identity missing")
        if match.group(1).decode() not in development_ids:
            skipped += 1
            continue
        selected += 1
        formulation = json.loads(line)["formulation"]
        accepted, _reasons, _signature, _occurrences = analyze(formulation)
        if not accepted:
            continue
        source_eligible += 1
        result = _parameter_ready(formulation)
        if result["ready"]:
            ready += 1
            signatures[result["signature"]] += 1
            loci[result["locus"]] += 1
            trials[str(result["total_trials"])] += 1
        else:
            rejection[f"remaining-dimension-or-unresolved:{result['remaining_dimension_upper_bound']}"] += 1
    if selected != 145 or skipped != 102:
        raise RuntimeError("partition custody mismatch")
    gate = ready >= 4 and len(signatures) >= 2
    return {
        "schema": "geotarget.source-labelled-rational-parameter-readiness/v1",
        "authority": "TRUTH_FREE_AGGREGATE_ONLY_STATIC_ONE_DOF_READINESS",
        "development_case_count": selected,
        "parent_source_eligible_count": source_eligible,
        "ready_attempt_count": ready,
        "anonymous_structural_signature_count": len(signatures),
        "locus_type_histogram": dict(sorted(loci.items())),
        "total_trial_count_histogram": dict(sorted(trials.items())),
        "rejection_reason_histogram": dict(sorted(rejection.items())),
        "fixed_qq_parameter_set": list(QQ_PARAMETER_SET),
        "parameter_count": len(QQ_PARAMETER_SET),
        "branch_cap": 32,
        "endpoint_role": "TRIAL_ORDER_ONLY_NEVER_PARAMETER_OR_PSLQ_AUTHORITY",
        "gate": {"minimum_attempts": 4, "minimum_signatures": 2, "pass": gate},
        "nondevelopment_rows_skipped_without_json_deserialization": skipped,
        "validation_or_sealed_formulation_parsed": False,
        "individual_id_value_target_truth_or_outcome_emitted": False,
        "formal_execute_scorer_full98_or_truth_used": False,
        "interpretation_limit": (
            "Static route readiness only. A real candidate still must enumerate every fixed QQ parameter, "
            "reject zero denominators, and exactly replay every remaining source obligation."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    result = census(arguments.dataset)
    arguments.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__": main()
