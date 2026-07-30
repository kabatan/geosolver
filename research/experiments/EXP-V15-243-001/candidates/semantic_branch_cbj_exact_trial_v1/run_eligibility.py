#!/usr/bin/env python3
"""Truth-free aggregate source eligibility for exact full-tuple branch reorder."""

from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
from fractions import Fraction
import hashlib
import json
from math import ceil, gcd, isqrt, prod
from pathlib import Path
import re
from typing import Any, Mapping


ARCHIVE_ROOT = Path("/home/kabatan/work/solver-experiment-runtime/solver")
DATASET = (
    ARCHIVE_ROOT
    / "research/experiments/EXP-OMC-V15-MERGED5-EVAL-001/inputs/omc_v15_merged_5files.audit-canonical.jsonl"
)
SPLIT = ARCHIVE_ROOT / "research/experiments/EXP-V15-243-001/benchmark/SPLIT_MANIFEST.json"
EXPECTED_SPLIT_SHA256 = "065b2602e515b16086768c5a60abf91248faee7ed0cb76b9d88d4c421bcbdf3f"
ROW_ID = re.compile(rb'"problem_id":"([^"\\]+)"')

LINE_OPERATORS = frozenset(
    {"Line", "AngleBisector", "PerpendicularBisector", "PerpendicularLine", "ParallelLine", "Tangent"}
)
CIRCLE_OPERATORS = frozenset(
    {"Circle", "CircleThroughPoint", "CircleThroughThreePoints", "Circumcircle", "Incircle", "Excircle"}
)
POINT_OPERATORS = frozenset(
    {
        "Point", "PointOnCircle", "PointOnLine", "PointOnSegment", "Intersect", "Midpoint", "Centroid",
        "Circumcenter", "Incenter", "Center", "FootOfPerpendicular", "Reflect", "ContactPoint",
        "IncircleContactPoint",
    }
)


def _tree(text: Any) -> ast.AST:
    return ast.parse(str(text), mode="eval").body


def _call_name(node: ast.AST) -> str | None:
    return node.func.id if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) else None


def _names(node: ast.AST) -> set[str]:
    return {item.id for item in ast.walk(node) if isinstance(item, ast.Name)}


def _fraction(node: ast.AST) -> Fraction | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
        return Fraction(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _fraction(node.operand)
        if value is None:
            return None
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
        left, right = _fraction(node.left), _fraction(node.right)
        if left is None or right is None:
            return None
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if right == 0:
            return None
        return left / right
    return None


def _bounds(formulation: Mapping[str, Any], declared: set[str]) -> dict[str, tuple[Fraction, Fraction, bool]]:
    result: dict[str, tuple[Fraction, Fraction, bool]] = {}
    for text in formulation.get("guards", ()):
        try:
            node = _tree(text)
        except SyntaxError:
            continue
        if _call_name(node) != "Bound" or len(node.args) < 2 or not isinstance(node.args[0], ast.Name):
            continue
        variable = node.args[0].id
        interval = node.args[1]
        if variable not in declared or not isinstance(interval, (ast.Tuple, ast.List)) or len(interval.elts) != 2:
            continue
        lower, upper = (_fraction(item) for item in interval.elts)
        if lower is None or upper is None or not lower < upper:
            continue
        inclusive = True
        for keyword in node.keywords:
            if keyword.arg == "inclusive" and isinstance(keyword.value, ast.Constant):
                inclusive = bool(keyword.value.value)
        previous = result.get(variable)
        if previous is not None:
            lower = max(lower, previous[0])
            upper = min(upper, previous[1])
            inclusive = inclusive and previous[2]
        if lower < upper:
            result[variable] = (lower, upper, inclusive)
    return result


def _operator_type(node: ast.AST, types: Mapping[str, str]) -> str | None:
    if isinstance(node, ast.Name):
        return types.get(node.id)
    operator = _call_name(node)
    if operator in LINE_OPERATORS:
        return "line"
    if operator in CIRCLE_OPERATORS:
        return "circle"
    if operator in POINT_OPERATORS:
        return "point"
    return None


def _incidence_points(
    node: ast.AST,
    definitions: Mapping[str, ast.AST],
    memo: dict[str, frozenset[str]],
) -> frozenset[str]:
    if isinstance(node, ast.Name):
        if node.id in memo:
            return memo[node.id]
        definition = definitions.get(node.id)
        if definition is None:
            return frozenset()
        memo[node.id] = frozenset()
        value = _incidence_points(definition, definitions, memo)
        memo[node.id] = value
        return value
    operator = _call_name(node)
    if operator == "Line" and len(node.args) == 2:
        return frozenset(argument.id for argument in node.args if isinstance(argument, ast.Name))
    if operator in {"Circumcircle", "CircleThroughPoint", "CircleThroughThreePoints"}:
        return frozenset(argument.id for argument in node.args if isinstance(argument, ast.Name))
    return frozenset()


def _intersect_branch(
    label: str,
    node: ast.Call,
    types: Mapping[str, str],
    definitions: Mapping[str, ast.AST],
) -> tuple[dict[str, Any] | None, str | None]:
    if len(node.args) < 2:
        return None, "malformed-intersect"
    first_type = _operator_type(node.args[0], types)
    second_type = _operator_type(node.args[1], types)
    if first_type is None or second_type is None:
        return None, None
    pair = tuple(sorted((first_type, second_type)))
    if pair not in {("circle", "circle"), ("circle", "line")}:
        return None, None
    keywords = {keyword.arg: keyword.value for keyword in node.keywords}
    if set(keywords) - {"exclude", "n"}:
        return None, "unstable-near-far-or-dynamic-selector"
    if set(keywords) == {"n"}:
        value = _fraction(keywords["n"])
        if value not in {Fraction(1), Fraction(2)}:
            return None, "dynamic-intersect-index"
        selector = "n"
    elif set(keywords) == {"exclude"} and isinstance(keywords["exclude"], ast.Name):
        excluded = keywords["exclude"].id
        memo: dict[str, frozenset[str]] = {}
        if any(excluded not in _incidence_points(argument, definitions, memo) for argument in node.args[:2]):
            return None, "unproved-exclude-incidence"
        selector = "exclude"
    else:
        return None, "implicit-or-multiple-intersect-selector"
    return {
        "key": f"intersect:{label}",
        "kind": f"typed-intersect-{pair[0]}-{pair[1]}-{selector}",
        "domain": 2,
        "label": label,
        "source_variable": None,
    }, None


def _safe_scalar_ast(node: ast.AST, declared: set[str]) -> bool:
    for item in ast.walk(node):
        if isinstance(item, ast.Name) and item.id not in declared:
            return False
        if isinstance(item, ast.Call):
            return False
        if isinstance(item, ast.Constant) and not isinstance(item.value, (int, float)):
            return False
        if isinstance(item, ast.BinOp) and not isinstance(item.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)):
            return False
    return True


def _affine(node: ast.AST, declared: set[str]) -> tuple[str, Fraction, Fraction] | None:
    names = _names(node) & declared
    if len(names) != 1 or not _safe_scalar_ast(node, declared):
        return None
    variable = next(iter(names))

    def visit(item: ast.AST) -> tuple[Fraction, Fraction] | None:
        if isinstance(item, ast.Name) and item.id == variable:
            return Fraction(1), Fraction(0)
        constant = _fraction(item)
        if constant is not None:
            return Fraction(0), constant
        if isinstance(item, ast.UnaryOp) and isinstance(item.op, (ast.UAdd, ast.USub)):
            value = visit(item.operand)
            if value is None:
                return None
            return value if isinstance(item.op, ast.UAdd) else (-value[0], -value[1])
        if isinstance(item, ast.BinOp) and isinstance(item.op, (ast.Add, ast.Sub)):
            left, right = visit(item.left), visit(item.right)
            if left is None or right is None:
                return None
            sign = 1 if isinstance(item.op, ast.Add) else -1
            return left[0] + sign * right[0], left[1] + sign * right[1]
        if isinstance(item, ast.BinOp) and isinstance(item.op, (ast.Mult, ast.Div)):
            left, right = visit(item.left), visit(item.right)
            if left is None or right is None:
                return None
            if isinstance(item.op, ast.Mult):
                if left[0] == 0:
                    return right[0] * left[1], right[1] * left[1]
                if right[0] == 0:
                    return left[0] * right[1], left[1] * right[1]
                return None
            if right[0] != 0 or right[1] == 0:
                return None
            return left[0] / right[1], left[1] / right[1]
        return None

    coefficients = visit(node)
    if coefficients is None or coefficients[0] == 0:
        return None
    return variable, coefficients[0], coefficients[1]


def _lcm(left: int, right: int) -> int:
    return abs(left * right) // gcd(left, right) if left and right else 0


def _periodic_sheet_branches(
    point_on_circle: Mapping[str, list[tuple[str, Fraction, Fraction]]],
    bounds: Mapping[str, tuple[Fraction, Fraction, bool]],
) -> list[dict[str, Any]]:
    result = []
    for variable, occurrences in sorted(point_on_circle.items()):
        if variable not in bounds:
            continue
        denominator_lcm = 1
        for _label, coefficient, _constant in occurrences:
            denominator_lcm = _lcm(denominator_lcm, coefficient.denominator)
        integer_coefficients = [
            abs(coefficient.numerator * (denominator_lcm // coefficient.denominator))
            for _label, coefficient, _constant in occurrences
        ]
        coefficient_gcd = 0
        for value in integer_coefficients:
            coefficient_gcd = gcd(coefficient_gcd, value)
        if coefficient_gcd == 0:
            continue
        period = Fraction(denominator_lcm, coefficient_gcd)
        lower, upper, _inclusive = bounds[variable]
        width_over_period = (upper - lower) / period
        domain = ceil(width_over_period)
        if domain < 2:
            continue
        result.append({
            "key": f"periodic:{variable}",
            "kind": "bounded-point-on-circle-sheet",
            "domain": domain,
            "labels": tuple(label for label, _coefficient, _constant in occurrences),
            "source_variable": variable,
            "period": str(period),
        })
    return result


def _quadratic_roots(
    left: ast.AST,
    right: ast.AST,
    variable: str,
) -> tuple[Fraction, Fraction] | None:
    # Restricted forms only: x**2 = q or (x-a)*(x-b) = 0, with QQ literals.
    if isinstance(left, ast.BinOp) and isinstance(left.op, ast.Pow):
        if isinstance(left.left, ast.Name) and left.left.id == variable and _fraction(left.right) == 2:
            value = _fraction(right)
            if value is None or value <= 0:
                return None
            numerator_root = isqrt(value.numerator)
            denominator_root = isqrt(value.denominator)
            if numerator_root**2 == value.numerator and denominator_root**2 == value.denominator:
                root = Fraction(numerator_root, denominator_root)
                return -root, root
    if _fraction(right) == 0 and isinstance(left, ast.BinOp) and isinstance(left.op, ast.Mult):
        roots = []
        for factor in (left.left, left.right):
            if not isinstance(factor, ast.BinOp) or not isinstance(factor.op, (ast.Add, ast.Sub)):
                return None
            if not isinstance(factor.left, ast.Name) or factor.left.id != variable:
                return None
            constant = _fraction(factor.right)
            if constant is None:
                return None
            roots.append(constant if isinstance(factor.op, ast.Sub) else -constant)
        if roots[0] != roots[1]:
            return tuple(sorted(roots))
    return None


def _scalar_disjunct_branches(
    formulation: Mapping[str, Any],
    declared: set[str],
    bounds: Mapping[str, tuple[Fraction, Fraction, bool]],
) -> list[dict[str, Any]]:
    candidates: dict[str, tuple[Fraction, Fraction]] = {}
    for item in formulation.get("constraints", ()):
        try:
            left, right = _tree(item["def"]), _tree(item.get("value", 0))
        except SyntaxError:
            continue
        names = (_names(left) | _names(right)) & declared
        if len(names) != 1:
            continue
        variable = next(iter(names))
        roots = _quadratic_roots(left, right, variable) or _quadratic_roots(right, left, variable)
        if roots is None or variable not in bounds:
            continue
        lower, upper, _inclusive = bounds[variable]
        if not all(lower < root < upper for root in roots):
            continue
        candidates[variable] = roots
    return [
        {
            "key": f"scalar:{variable}",
            "kind": "bounded-scalar-two-root-disjunct",
            "domain": 2,
            "label": None,
            "source_variable": variable,
        }
        for variable in sorted(candidates)
    ]


def _conflict_kind(node: ast.AST) -> str | None:
    operator = _call_name(node)
    if operator in {"AssumeGt", "AssumeLt", "AssumeNe"}:
        return operator
    if operator == "AssumeEq" and node.args and _call_name(node.args[0]) == "OnSegment":
        return "AssumeEq-OnSegment"
    if operator == "Bound":
        for keyword in node.keywords:
            if keyword.arg == "inclusive" and isinstance(keyword.value, ast.Constant) and keyword.value.value is False:
                return "Bound-open"
        return None
    if operator == "Assume" and node.args:
        allowed = (ast.Compare, ast.BoolOp, ast.And, ast.Or, ast.Lt, ast.Gt, ast.NotEq)
        if all(isinstance(item, allowed + (ast.Load, ast.Name, ast.Constant)) for item in ast.walk(node.args[0])):
            return "Assume-strict-boolean"
    return None


def analyze(formulation: Mapping[str, Any]) -> dict[str, Any]:
    declared = set(formulation.get("variables", {}).get("names", ()))
    constructions = list(formulation.get("construction", ()))
    definitions: dict[str, ast.AST] = {}
    types: dict[str, str] = {}
    intersect_branches = []
    unsupported = Counter()
    point_on_circle: dict[str, list[tuple[str, Fraction, Fraction]]] = defaultdict(list)
    for item in constructions:
        label = str(item["name"])
        try:
            node = _tree(item["expr"])
        except SyntaxError:
            unsupported["construction-syntax"] += 1
            continue
        definitions[label] = node
        inferred = _operator_type(node, types)
        if inferred is not None:
            types[label] = inferred
        operator = _call_name(node)
        if operator == "Intersect":
            branch, reason = _intersect_branch(label, node, types, definitions)
            if branch is not None:
                intersect_branches.append(branch)
            elif reason is not None:
                unsupported[reason] += 1
        elif operator == "Tangent":
            unsupported["dynamic-tangent-branch"] += 1
        elif operator == "PointOnCircle" and len(node.args) >= 2:
            affine = _affine(node.args[1], declared)
            if affine is not None:
                variable, coefficient, constant = affine
                point_on_circle[variable].append((label, coefficient, constant))
    source_bounds = _bounds(formulation, declared)
    sheet_branches = _periodic_sheet_branches(point_on_circle, source_bounds)
    scalar_branches = _scalar_disjunct_branches(formulation, declared, source_bounds)
    scalar_owners = Counter(
        branch["source_variable"]
        for branch in sheet_branches + scalar_branches
        if branch["source_variable"] is not None
    )
    if any(count > 1 for count in scalar_owners.values()):
        unsupported["overlapping-scalar-branch-model"] += 1
    branches = intersect_branches + sheet_branches + scalar_branches
    branch_by_key = {branch["key"]: branch for branch in branches}
    scalar_branch = {
        branch["source_variable"]: branch["key"]
        for branch in branches
        if branch["source_variable"] is not None
    }
    label_branch = {
        branch["label"]: branch["key"]
        for branch in intersect_branches
        if branch.get("label") is not None
    }
    for branch in sheet_branches:
        for label in branch["labels"]:
            label_branch[label] = branch["key"]
    label_dependencies: dict[str, set[str]] = {}
    for item in constructions:
        label = str(item["name"])
        node = definitions.get(label)
        if node is None:
            continue
        dependencies = {scalar_branch[name] for name in _names(node) if name in scalar_branch}
        for name in _names(node):
            dependencies.update(label_dependencies.get(name, set()))
        if label in label_branch:
            dependencies.add(label_branch[label])
        label_dependencies[label] = dependencies
    conflict_dependency_counts: Counter[tuple[str, ...]] = Counter()
    conflict_dependency_kinds: dict[tuple[str, ...], tuple[str, ...]] = {}
    conflict_kind_counts = Counter()
    for text in formulation.get("guards", ()):
        try:
            node = _tree(text)
        except SyntaxError:
            continue
        kind = _conflict_kind(node)
        if kind is None:
            continue
        dependencies = {scalar_branch[name] for name in _names(node) if name in scalar_branch}
        for name in _names(node):
            dependencies.update(label_dependencies.get(name, set()))
        if not dependencies:
            continue
        dependency_keys = tuple(sorted(dependencies))
        conflict_dependency_counts[dependency_keys] += 1
        conflict_dependency_kinds[dependency_keys] = tuple(
            sorted(branch_by_key[key]["kind"] for key in dependencies)
        )
        conflict_kind_counts[kind] += 1
    branch_count = len(branches)
    assignment_product = prod(branch["domain"] for branch in branches) if branches else 0
    source_ready = (
        not unsupported
        and 2 <= branch_count <= 6
        and assignment_product <= 16
        and bool(conflict_dependency_counts)
    )
    recurrent_subsets = {
        subset: count for subset, count in conflict_dependency_counts.items() if count >= 2
    }
    recurrent_conflict = source_ready and bool(recurrent_subsets)
    signature = None
    if source_ready:
        payload = {
            "branch_kinds": sorted(Counter(branch["kind"] for branch in branches).items()),
            "branch_domains": sorted(branch["domain"] for branch in branches),
            "assignment_product": assignment_product,
            "source_dimension": len(declared),
            "conflict_dependency_profiles": sorted(
                (conflict_dependency_kinds[subset], count)
                for subset, count in conflict_dependency_counts.items()
            ),
            "conflict_kinds": sorted(conflict_kind_counts.items()),
            "recurrent_dependency_multiplicities": sorted(recurrent_subsets.values()),
        }
        signature = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii")
        ).hexdigest()[:16]
    return {
        "ready": source_ready,
        "recurrent_conflict": recurrent_conflict,
        "signature": signature,
        "branch_count": branch_count,
        "assignment_product": assignment_product,
        "branch_kinds": Counter(branch["kind"] for branch in branches),
        "conflict_kind_counts": conflict_kind_counts,
        "recurrent_subset_multiplicities": Counter(recurrent_subsets.values()),
        "unsupported": unsupported,
    }


def census(dataset: Path) -> dict[str, Any]:
    split_bytes = SPLIT.read_bytes()
    if hashlib.sha256(split_bytes).hexdigest() != EXPECTED_SPLIT_SHA256:
        raise RuntimeError("split digest mismatch")
    development_ids = frozenset(json.loads(split_bytes)["partitions"]["development"]["case_ids"])
    payload = dataset.read_bytes()
    selected = skipped = ready = recurrent = 0
    signatures = Counter()
    recurrent_signatures = Counter()
    branch_counts = Counter()
    products = Counter()
    branch_kinds = Counter()
    conflict_kinds = Counter()
    recurrent_multiplicity = Counter()
    rejection = Counter()
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
        result = analyze(formulation)
        if result["ready"]:
            ready += 1
            signatures[result["signature"]] += 1
            branch_counts[str(result["branch_count"])] += 1
            products[str(result["assignment_product"])] += 1
            branch_kinds.update(result["branch_kinds"])
            conflict_kinds.update(result["conflict_kind_counts"])
            recurrent_multiplicity.update(result["recurrent_subset_multiplicities"])
            if result["recurrent_conflict"]:
                recurrent += 1
                recurrent_signatures[result["signature"]] += 1
        else:
            if result["unsupported"]:
                rejection.update(result["unsupported"])
            elif result["branch_count"] < 2:
                rejection["fewer-than-two-explicit-branch-variables"] += 1
            elif result["branch_count"] > 6:
                rejection["more-than-six-explicit-branch-variables"] += 1
            elif result["assignment_product"] > 16:
                rejection["assignment-product-cap"] += 1
            else:
                rejection["no-exact-strict-conflict-atom"] += 1
    if selected != 145 or skipped != 102:
        raise RuntimeError("partition custody mismatch")
    gate = (
        ready >= 4
        and len(signatures) >= 2
        and recurrent >= 2
        and len(recurrent_signatures) >= 2
    )
    return {
        "schema": "geotarget.semantic-branch-cbj-exact-trial-eligibility/v1",
        "authority": "TRUTH_FREE_SOURCE_ONLY_AGGREGATE_NO_SOLVER_EXECUTION",
        "development_case_count": selected,
        "ready_attempt_count": ready,
        "anonymous_structural_signature_count": len(signatures),
        "recurrent_exact_strict_conflict_attempt_count": recurrent,
        "recurrent_exact_strict_conflict_signature_count": len(recurrent_signatures),
        "branch_variable_count_histogram": dict(sorted(branch_counts.items(), key=lambda item: int(item[0]))),
        "assignment_product_histogram": dict(sorted(products.items(), key=lambda item: int(item[0]))),
        "eligible_branch_kind_histogram": dict(sorted(branch_kinds.items())),
        "eligible_conflict_kind_histogram": dict(sorted(conflict_kinds.items())),
        "recurrent_conflict_subset_multiplicity_histogram": dict(
            sorted(recurrent_multiplicity.items(), key=lambda item: int(item[0]))
        ),
        "rejection_reason_histogram": dict(sorted(rejection.items())),
        "gate": {
            "minimum_ready_attempts": 4,
            "minimum_anonymous_structural_signatures": 2,
            "explicit_branch_variable_range": [2, 6],
            "maximum_assignment_product": 16,
            "minimum_recurrent_strict_conflict_attempts": 2,
            "minimum_recurrent_strict_conflict_signatures": 2,
            "pass": gate,
        },
        "learning_contract": {
            "episode_scope": "ONE_EPISODE_ONLY",
            "learned_object": "EXACT_FULL_ASSIGNMENT_TUPLE_REORDER_ONLY",
            "subset_pruning": False,
            "permanent_suppression": False,
            "continuous_failure_learns": False,
            "strict_guard_or_segment_is_alternative": False,
            "conflict_provenance_may_overapproximate": True,
        },
        "future_connector_contract": {
            "baseline_minimum_fraction": 0.75,
            "side_maximum_fraction": 0.25,
            "callback_accounting_required": True,
            "canonical_source_guard_branch_raw_target_replay_required": True,
        },
        "conflict_recurrence_is_observed_runtime_evidence": False,
        "gate_scope": (
            "STATIC_SOURCE_GATE_PASS_HOLD_BEFORE_D0"
            if gate
            else "STATIC_SOURCE_GATE_FAILED_STOP_BEFORE_D0"
        ),
        "nondevelopment_rows_skipped_without_json_deserialization": skipped,
        "validation_or_sealed_formulation_parsed": False,
        "individual_id_value_target_truth_or_outcome_emitted": False,
        "formal_execute_scorer_full98_or_truth_used": False,
        "interpretation_limit": (
            "Source eligibility only. It is not selector stability, exact conflict observation, recall, authority, "
            "or evidence that conflict-directed reordering improves search."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    result = census(arguments.dataset)
    arguments.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
